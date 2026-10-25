"""Anime Tier Night - tiny multiplayer tier list server (Python stdlib only).

Run:  python server.py  (then open http://localhost:8000)
"""
import json
import os
import queue
import random
import string
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "rooms.json")
TIERS = ["S", "A", "B", "C", "D", "F"]

lock = threading.Condition()
rooms = {}


# ---------- persistence ----------
# Online (Render) the disk is wiped on every restart, so rooms live in an Upstash
# Redis database when UPSTASH_REDIS_REST_URL / _TOKEN are set; locally, rooms.json.

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
REDIS_KEY = "anime-tier-night:rooms"


def redis(*cmd):
    req = urllib.request.Request(REDIS_URL, data=json.dumps(cmd).encode("utf-8"), headers={
        "Authorization": "Bearer " + REDIS_TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8")).get("result")


def load():
    global rooms
    try:
        if REDIS_URL:
            rooms = json.loads(redis("GET", REDIS_KEY) or "{}")
        else:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                rooms = json.load(f)
    except (OSError, ValueError):
        rooms = {}
    print(f"Loaded {len(rooms)} room(s) from {'Upstash' if REDIS_URL else DATA_FILE}")


_save_pending = threading.Event()


def write_snapshot(snapshot):
    if REDIS_URL:
        redis("SET", REDIS_KEY, snapshot)
        return
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(snapshot)
    os.replace(tmp, DATA_FILE)


def saver():
    while True:
        _save_pending.wait()
        time.sleep(1)
        _save_pending.clear()
        with lock:
            snapshot = json.dumps(rooms)
        try:
            write_snapshot(snapshot)
        except Exception as e:  # keep serving; the next change retries the save
            print("Save failed:", e)
            _save_pending.set()
            time.sleep(5)


def changed(room):
    """Call with lock held after mutating a room."""
    room["version"] += 1
    lock.notify_all()
    _save_pending.set()


# ---------- AniList poster lookup ----------

_api_lock = threading.Lock()
_last_call = [0.0]

QUERY = """query ($q: String, $n: Int) { Page(perPage: $n) { media(search: $q, type: ANIME, isAdult: false, sort: [POPULARITY_DESC]) {
  id siteUrl format seasonYear popularity
  title { romaji english native } synonyms coverImage { extraLarge large } } } }"""


def anilist(q, n):
    body = json.dumps({"query": QUERY, "variables": {"q": q, "n": n}}).encode("utf-8")
    for attempt in range(4):
        with _api_lock:  # AniList allows ~30-90 req/min; space calls out
            wait = 0.8 - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
        try:
            req = urllib.request.Request("https://graphql.anilist.co", data=body, headers={
                "Content-Type": "application/json", "Accept": "application/json",
                "User-Agent": "AnimeTierNight/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))["data"]["Page"]["media"]
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(int(e.headers.get("Retry-After") or 0) or 2 * (attempt + 1))
                continue
            return []
        except Exception:
            time.sleep(1)
    return []


def to_option(a):
    t = a.get("title") or {}
    cover = a.get("coverImage") or {}
    return {
        "mal_id": a.get("id"),
        "title": t.get("english") or t.get("romaji"),
        "subtitle": t.get("romaji"),
        "year": a.get("seasonYear"),
        "type": a.get("format"),
        "members": a.get("popularity") or 0,
        "img": cover.get("extraLarge") or cover.get("large"),
        "url": a.get("siteUrl"),
    }


def search(q, limit=12):
    return [to_option(a) for a in anilist(q, limit)]


def best_match(q):
    items = anilist(q, 8)
    if not items:
        return None
    ql = q.strip().lower()
    for a in items:
        t = a.get("title") or {}
        names = [t.get("romaji"), t.get("english"), t.get("native")] + (a.get("synonyms") or [])
        if any(n and n.strip().lower() == ql for n in names):
            return to_option(a)
    return to_option(items[0])  # results are sorted by popularity


lookup_q = queue.Queue()


def lookup_worker():
    while True:
        code, aid = lookup_q.get()
        with lock:
            room = rooms.get(code)
            item = find(room, aid)
            name = item["name"] if item else None
        if not name:
            continue
        m = best_match(name)
        with lock:
            room = rooms.get(code)
            item = find(room, aid)
            if not item:
                continue
            item["status"] = "ok" if m and m["img"] else "missing"
            if m:
                item.update(title=m["title"], img=m["img"], url=m["url"], year=m["year"])
                # two people typed the same show differently: keep one card, credit both
                twin = next((x for x in room["anime"] if x is not item and x.get("url") == m["url"]), None)
                if twin:
                    for pid in item.get("by", []):
                        if pid not in twin.setdefault("by", []):
                            twin["by"].append(pid)
                    room["anime"].remove(item)
            changed(room)


# ---------- AI roast (Gemini, Cerebras, Mistral) ----------

OPENAI_STYLE = {"cerebras": "https://api.cerebras.ai/v1", "mistral": "https://api.mistral.ai/v1"}
PROVIDER_NAMES = {"gemini": "Gemini", "cerebras": "Cerebras", "mistral": "Mistral"}
# built-in keys come from the host's environment (Render > Environment), never from the code
BUILTIN_KEYS = {p: os.environ.get(p.upper() + "_API_KEY", "").strip() for p in PROVIDER_NAMES}
BUILTIN_ORDER = [p for p in ("gemini", "mistral", "cerebras") if BUILTIN_KEYS[p]]
_builtin_calls = []
_default_models = {}


def builtin_allowed(per_hour=40):
    """Caps roasts on the built-in keys so one busy room can't burn the whole quota."""
    now = time.time()
    with _api_lock:
        _builtin_calls[:] = [t for t in _builtin_calls if now - t < 3600]
        if len(_builtin_calls) >= per_hour:
            return False
        _builtin_calls.append(now)
        return True


def builtin_models(provider, key):
    """Up to 3 models to try in order, so one overloaded model doesn't sink the roast."""
    if provider not in _default_models:
        models = list_models(provider, key)
        prefs = {"gemini": ["flash-latest", "flash", "flash-lite"], "mistral": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
                 "cerebras": ["gpt-oss", "llama-3.3", "qwen", "llama"]}[provider]
        picks = []
        # newest versions sort last, so search from the end
        for want in prefs:
            for m in reversed(models):
                if want in m and "preview" not in m and m not in picks and (want == "flash-lite" or "lite" not in m):
                    picks.append(m)
                    break
        picks = picks[:3] or models[:1]
        if not picks:
            raise AIError("no usable models were found for this key.")
        _default_models[provider] = picks
        time.sleep(1.2)  # free tiers allow about one call per second
    return _default_models[provider]


GEMINI = "https://generativelanguage.googleapis.com/v1beta"


class AIError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


BUSY = (429, 500, 502, 503, 504)


def http_json(url, key_headers, body=None, timeout=90):
    # busy or rate-limited AIs usually answer on a second or third try
    for wait in (2.5, 6, None):
        try:
            return http_json_once(url, key_headers, body, timeout)
        except AIError as e:
            if e.code not in BUSY or wait is None:
                raise
            time.sleep(wait)


def http_json_once(url, key_headers, body, timeout):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "AnimeTierNight/1.0", **key_headers}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(detail)
            detail = (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else (j.get("message") or j.get("detail") or j.get("error") or detail)
        except ValueError:
            pass
        reason = {401: "the API key was rejected", 403: "the API key isn't allowed to use this",
                  404: "that model wasn't found", 429: "it's out of quota or rate limited"}.get(e.code, f"it returned error {e.code}")
        raise AIError(f"{reason}. {str(detail)[:200]}".strip(), e.code)
    except TimeoutError:
        raise AIError(f"took longer than {timeout}s and timed out.", "timeout")
    except Exception as e:
        if "timed out" in str(e):
            raise AIError(f"took longer than {timeout}s and timed out.", "timeout")
        raise AIError(f"couldn't reach it ({e.__class__.__name__}).")


def auth(provider, key):
    return {"x-goog-api-key": key} if provider == "gemini" else {"Authorization": "Bearer " + key}


def list_models(provider, key):
    if provider == "gemini":
        res = http_json(GEMINI + "/models?pageSize=200", auth(provider, key), timeout=20)
        ids = [m["name"].split("/", 1)[-1] for m in res.get("models", [])
               if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        ids = [i for i in ids if not any(s in i for s in ("embedding", "aqa", "imagen", "tts", "image", "live", "veo"))]
    else:
        res = http_json(OPENAI_STYLE[provider] + "/models", auth(provider, key), timeout=20)
        ids = [m["id"] for m in res.get("data", [])
               if not any(s in m["id"] for s in ("embed", "moderation", "ocr", "transcribe", "voxtral"))]
    return sorted(set(ids))


def complete(provider, key, model, system, prompt):
    if provider == "gemini":
        res = http_json(f"{GEMINI}/models/{urllib.parse.quote(model)}:generateContent", auth(provider, key), {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"}}, timeout=60)
        parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    else:
        res = http_json(OPENAI_STYLE[provider] + "/chat/completions", auth(provider, key), {
            "model": model, "temperature": 0.95,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        text = ((res.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise AIError("it answered, but not in the expected format. Try again or switch model.")
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        raise AIError("it answered, but the reply was cut off or malformed. Try again or switch model.")


SPICE = {
    "wholesome": "Keep it friendly: gentle teasing, mostly hype and compliments.",
    "spicy": "Roast properly: sharp, specific jokes about their picks and rankings, balanced with real compliments where earned.",
    "unhinged": "Go hard: savage, over-the-top roasts like a chaotic friend in the group chat. Still punch at taste, never at identity.",
}


def roast_prompt(room, spice):
    by_id = {a["id"]: a for a in room["anime"]}
    lines = [f'Room: "{room["title"]}". Mode: {"each person secretly submitted picks, then everyone ranked the combined pool" if room.get("mode") == "picks" else "host chose the list, everyone ranked it"}.']
    for pid, p in room["players"].items():
        lines.append(f'\n## {p["name"]}')
        if room.get("mode") == "picks":
            picks = [a["title"] for a in room["anime"] if pid in a.get("by", [])]
            lines.append("Their secret picks: " + (", ".join(picks) or "none"))
        for t in TIERS:
            titles = [by_id[i]["title"] for i in p["tiers"].get(t, []) if i in by_id]
            if titles:
                lines.append(f"{t}: " + ", ".join(titles))
        ranked = {i for t in TIERS for i in p["tiers"].get(t, [])}
        skipped = [a["title"] for a in room["anime"] if a["id"] not in ranked]
        if skipped:
            lines.append("Didn't rank: " + ", ".join(skipped[:15]))
    if room.get("mode") == "picks":
        shared = [a["title"] for a in room["anime"] if len(a.get("by", [])) > 1]
        if shared:
            lines.append("\nPicked by more than one person: " + ", ".join(shared))
    names = [p["name"] for p in room["players"].values()]
    system = ("You are the hype-man and roaster in a friend group's anime tier list night, typing in their group chat "
              "while they record a video. You know anime deeply: reference real plot points, characters, fandom "
              "stereotypes and memes so the jokes land. " + SPICE.get(spice, SPICE["spicy"]) +
              " Never use slurs or attack real-world identity. Keep each message short like a chat text (1-3 sentences), "
              "casual, funny, no hashtags. Address people by name.")
    prompt = ("\n".join(lines) + "\n\nWrite the group chat. Return only JSON in this shape:\n"
              '{"messages":[{"to":"<player name or everyone>","text":"..."}],'
              '"awards":[{"name":"<player name>","award":"<funny 2-5 word title>"}]}\n'
              f"Open with one message to everyone, then 2 messages for each of these people: {', '.join(names)}. "
              "Call out contradictions (e.g. they picked a show then ranked it low, or put a masterpiece in F), "
              "compare people's taste with each other, then close with one message to everyone naming the best and worst taste. "
              "Give each person exactly one award.")
    return system, prompt


# ---------- room helpers ----------

def rid(n=6, alphabet=string.ascii_uppercase + string.digits):
    return "".join(random.choice(alphabet) for _ in range(n))


def find(room, aid):
    return next((x for x in room["anime"] if x["id"] == aid), None) if room else None


def clean_name(raw):
    return raw.strip().lstrip("-*0123456789.) ").strip()[:120]


def new_item(room, name, by=None):
    item = {"id": rid(8), "name": name, "title": name, "img": None, "url": None, "year": None, "status": "searching"}
    if by is not None:
        item["by"] = list(by)
    room["anime"].append(item)
    lookup_q.put((room["code"], item["id"]))
    return item


def add_anime(room, names):
    seen = {x["name"].lower() for x in room["anime"]}
    for raw in names:
        name = clean_name(raw)
        if not name or name.lower() in seen or len(room["anime"]) >= 150:
            continue
        seen.add(name.lower())
        new_item(room, name)


def hidden_phase(room):
    return room.get("mode") == "picks" and room.get("phase") != "results"


def public(room, viewer=None):
    r = {k: v for k, v in room.items() if k not in ("hostKey",)}
    r["now"] = time.time()
    r["builtinAI"] = BUILTIN_ORDER
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    if room.get("mode") == "picks":
        for pid, p in r["players"].items():
            p["picks"] = sum(1 for a in room["anime"] if pid in a.get("by", []))
        if hidden_phase(room):
            # anonymous until the results: nobody sees who picked what
            r["mine"] = [a["id"] for a in room["anime"] if viewer and viewer in a.get("by", [])]
            anime = [{k: v for k, v in a.items() if k != "by"} for a in room["anime"]]
            if room.get("phase") == "submit":
                r["poolSize"] = len(anime)
                anime = [a for a in anime if a["id"] in r["mine"]]
            r["anime"] = anime
    return r


def clean_tiers(room, tiers):
    valid = {x["id"] for x in room["anime"]}
    out, used = {}, set()
    for t in TIERS:
        out[t] = []
        for aid in (tiers or {}).get(t, []):
            if aid in valid and aid not in used:
                used.add(aid)
                out[t].append(aid)
    return out


def finish(room):
    room["phase"] = "results"
    room["revealed"] = True
    room["deadline"] = None
    start_show(room)


def start_show(room):
    """Puts every screen on the Reveal Show and starts the AI roast in the background. Call with lock held."""
    room["show"] = {"slide": 0, "done": False}
    anyone_ranked = any(any(p["tiers"].get(t) for t in TIERS) for p in room["players"].values())
    if anyone_ranked and not room.get("roasts") and (room.get("roastState") or {}).get("status") != "working":
        room["roastState"] = {"status": "working", "error": None}
        threading.Thread(target=auto_roast, args=(room["code"],), daemon=True).start()


def auto_roast(code):
    errors = []
    for provider in BUILTIN_ORDER:
        try:
            run_roast(code, provider, "", "", None)
            return
        except AIError as e:
            errors.append(f"{PROVIDER_NAMES[provider]}: {e}")
    with lock:
        room = rooms.get(code)
        if room:
            room["roastState"] = {"status": "failed", "error": " ".join(errors) or "No built-in AI is set up on this server."}
            changed(room)


def run_roast(code, provider, key, model, spice):
    """Asks one AI for the roast and saves it to the room. Raises AIError with a readable reason."""
    if provider not in PROVIDER_NAMES:
        raise AIError("pick an AI.")
    if not key:  # no key from the host: use the built-in one from the server's settings
        key = BUILTIN_KEYS.get(provider)
        if not key:
            raise AIError("there's no built-in key for it. Paste your own.")
        if not builtin_allowed():
            raise AIError("the built-in AI is busy (too many roasts this hour). Try again soon or use your own key.")
        if not model:
            tried = []
            for m in builtin_models(provider, key):
                started = time.time()
                try:
                    return run_roast_with(code, provider, key, m, spice)
                except AIError as e:
                    tried.append(f"{m} ({int(time.time() - started)}s): {e}")
                    if e.code not in BUSY + (404, "timeout"):
                        break
            raise AIError(" | ".join(tried))
    if not model:
        raise AIError("choose a model first (press Load).")
    return run_roast_with(code, provider, key, model, spice)


def run_roast_with(code, provider, key, model, spice):
    with lock:
        room = rooms.get(code)
        if not room:
            raise AIError("the room is gone.")
        if not any(any(p["tiers"].get(t) for t in TIERS) for p in room["players"].values()):
            raise AIError("nobody has ranked anything yet, so there's nothing to roast.")
        spice = spice or room.get("spice") or "spicy"
        system, prompt = roast_prompt(room, spice)
        names = {p["name"].lower(): p["name"] for p in room["players"].values()}
    out = complete(provider, key, model, system, prompt)  # the key is used here and never stored
    msgs = [{"to": names.get(str(m.get("to") or "").lower(), str(m.get("to") or "everyone")[:30]),
             "text": str(m.get("text") or "")[:600]}
            for m in (out.get("messages") or []) if isinstance(m, dict) and m.get("text")][:40]
    awards = [{"name": names.get(str(a.get("name", "")).lower(), str(a.get("name", ""))[:30]),
               "award": str(a.get("award") or "")[:60]}
              for a in (out.get("awards") or []) if isinstance(a, dict)][:30]
    if not msgs:
        raise AIError("it replied with nothing usable. Try again or switch model.")
    entry = {"id": rid(6), "at": time.time(), "provider": PROVIDER_NAMES[provider], "model": model,
             "spice": spice, "messages": msgs, "awards": awards}
    with lock:
        room = rooms.get(code)
        if room:
            room.setdefault("roasts", []).insert(0, entry)
            del room["roasts"][5:]
            room["roastState"] = {"status": "done", "error": None}
            changed(room)
    return entry


def ticker():
    """Ends timed ranking rounds (a 2s grace lets last moves save)."""
    while True:
        time.sleep(1)
        with lock:
            for room in rooms.values():
                if room.get("phase") == "ranking" and room.get("deadline") and time.time() > room["deadline"] + 2:
                    finish(room)
                    changed(room)


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def err(self, msg, status=400):
        self.send_json({"error": msg}, status)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 200_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        qs = urllib.parse.parse_qs(u.query)

        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parts[:2] == ["api", "search"]:
            q = (qs.get("q") or [""])[0].strip()
            return self.send_json({"results": search(q) if q else []})

        # long-poll: GET /api/rooms/CODE?v=N waits until version > N (max ~25s)
        if len(parts) == 3 and parts[:2] == ["api", "rooms"]:
            code = parts[2].upper()
            try:
                v = int((qs.get("v") or ["-1"])[0])
            except ValueError:
                v = -1
            pid, key = (qs.get("pid") or [""])[0], (qs.get("key") or [""])[0]
            deadline = time.time() + 25
            with lock:
                while code in rooms and rooms[code]["version"] <= v and time.time() < deadline:
                    lock.wait(timeout=deadline - time.time())
                room = rooms.get(code)
                if not room:
                    return self.err("Room not found. Check the code.", 404)
                p = room["players"].get(pid)
                return self.send_json(public(room, pid if p and p["key"] == key else None))

        self.err("Not found", 404)

    def do_POST(self):
        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        b = self.body()

        if parts == ["api", "ai", "models"]:
            provider, key = b.get("provider"), (b.get("key") or "").strip()
            if provider not in PROVIDER_NAMES or not key:
                return self.err("Pick a provider and paste its API key.")
            try:
                return self.send_json({"models": list_models(provider, key)})
            except AIError as e:
                return self.err(f"{PROVIDER_NAMES[provider]}: {e}", 502)

        if parts == ["api", "rooms"]:
            with lock:
                code = rid(4, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                while code in rooms:
                    code = rid(4, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                mode = "picks" if b.get("mode") == "picks" else "classic"
                room = {"code": code, "hostKey": rid(16), "title": (b.get("title") or "Anime Tier Night")[:80],
                        "mode": mode, "phase": "submit" if mode == "picks" else "ranking",
                        "picksPer": max(1, min(10, int(b.get("picksPer") or 5))),
                        "timerSec": max(30, min(1800, int(b.get("timerSec") or 120))), "deadline": None,
                        "spice": b.get("spice") if b.get("spice") in SPICE else "spicy", "show": None, "roastState": None,
                        "anime": [], "players": {}, "revealed": False, "tiers": TIERS, "roasts": [],
                        "created": time.time(), "version": 0}
                rooms[code] = room
                if mode == "classic":
                    add_anime(room, b.get("list") or [])
                changed(room)
                return self.send_json({"code": code, "hostKey": room["hostKey"]})

        if len(parts) < 4 or parts[:2] != ["api", "rooms"]:
            return self.err("Not found", 404)
        code, action = parts[2].upper(), parts[3]

        if action == "roast":
            return self.roast(code, b)

        with lock:
            room = rooms.get(code)
            if not room:
                return self.err("Room not found. Check the code.", 404)
            is_host = b.get("hostKey") == room["hostKey"]
            player = room["players"].get(b.get("pid"))
            if player and player["key"] != b.get("key"):
                player = None

            if action == "join":
                name = (b.get("name") or "").strip()[:24]
                if not name:
                    return self.err("Enter a name to join.")
                # same name rejoins the same board (handy if someone switches device)
                for pid, p in room["players"].items():
                    if p["name"].lower() == name.lower():
                        return self.send_json({"pid": pid, "key": p["key"]})
                if len(room["players"]) >= 30:
                    return self.err("This room is full (30 players).")
                pid = rid(8)
                room["players"][pid] = {"name": name, "key": rid(16), "tiers": {t: [] for t in TIERS},
                                        "joined": time.time(), "done": False}
                changed(room)
                return self.send_json({"pid": pid, "key": room["players"][pid]["key"]})

            if action in ("rank", "pick", "unpick") and not player:
                return self.err("You're not in this room. Rejoin with your name.", 403)

            if action == "rank":
                if room.get("mode") == "picks":
                    if room["phase"] != "ranking" or (room["deadline"] and time.time() > room["deadline"] + 2):
                        return self.err("Time's up. Rankings are locked.", 409)
                player["tiers"] = clean_tiers(room, b.get("tiers"))
                if "done" in b:
                    player["done"] = bool(b["done"])
                changed(room)
                return self.send_json({"ok": True})

            if action == "pick":
                if room.get("phase") != "submit":
                    return self.err("Picks are closed. The ranking has started.", 409)
                name = clean_name(b.get("name") or "")
                if not name:
                    return self.err("Type an anime name.")
                pid = b.get("pid")
                if sum(1 for a in room["anime"] if pid in a.get("by", [])) >= room["picksPer"]:
                    return self.err(f"You already have {room['picksPer']} picks. Remove one to swap it.")
                same = next((a for a in room["anime"] if a["name"].lower() == name.lower()), None)
                if same:
                    if pid in same["by"]:
                        return self.err("You already picked that one.")
                    same["by"].append(pid)
                else:
                    new_item(room, name, by=[pid])
                changed(room)
                return self.send_json({"ok": True})

            if action == "unpick":
                if room.get("phase") != "submit":
                    return self.err("Picks are closed. The ranking has started.", 409)
                item = find(room, b.get("id"))
                if item and b.get("pid") in item.get("by", []):
                    item["by"].remove(b.get("pid"))
                    if not item["by"]:
                        room["anime"].remove(item)
                    changed(room)
                return self.send_json({"ok": True})

            if not is_host:
                return self.err("Only the host can do that.", 403)

            if action == "add":
                add_anime(room, b.get("list") or [])
            elif action == "reveal":
                room["revealed"] = bool(b.get("revealed"))
                if room["revealed"] and not room.get("show"):
                    start_show(room)
            elif action == "slide":
                if not room.get("show"):
                    return self.err("The show hasn't started.")
                room["show"]["slide"] = max(0, int(b.get("to") or 0))
                room["show"]["done"] = bool(b.get("done"))
            elif action == "showagain":
                start_show(room)
            elif action == "retryroast":
                if (room.get("roastState") or {}).get("status") != "working":
                    room["roastState"] = {"status": "working", "error": None}
                    threading.Thread(target=auto_roast, args=(room["code"],), daemon=True).start()
            elif action == "title":
                room["title"] = (b.get("title") or room["title"])[:80]
            elif action == "kick":
                pid = b.get("pid")
                room["players"].pop(pid, None)
                for a in list(room["anime"]):
                    if pid in a.get("by", []):
                        a["by"].remove(pid)
                        if not a["by"] and room.get("phase") == "submit":
                            room["anime"].remove(a)
            elif action == "start":
                if room.get("phase") != "submit":
                    return self.err("The ranking already started.")
                if not room["anime"]:
                    return self.err("Nobody has submitted a pick yet.")
                if "timerSec" in b:
                    room["timerSec"] = max(30, min(1800, int(b["timerSec"])))
                room["phase"] = "ranking"
                room["deadline"] = time.time() + room["timerSec"] + 3  # 3s for everyone's screen to switch
                for p in room["players"].values():
                    p["tiers"], p["done"] = {t: [] for t in TIERS}, False
            elif action == "addtime":
                if room.get("phase") != "ranking" or not room.get("deadline"):
                    return self.err("No timer is running.")
                room["deadline"] += int(b.get("sec") or 30)
            elif action == "end":
                finish(room)
            elif action == "anime" and len(parts) == 5:
                item = find(room, parts[4])
                if not item:
                    return self.err("That anime isn't in the room anymore.", 404)
                if b.get("remove"):
                    room["anime"].remove(item)
                    for p in room["players"].values():
                        p["tiers"] = clean_tiers(room, p["tiers"])
                else:
                    for k in ("title", "img", "url", "year"):
                        if k in b:
                            item[k] = b[k]
                    item["status"] = "ok" if item.get("img") else "missing"
            else:
                return self.err("Unknown action")
            changed(room)
            return self.send_json({"ok": True})

    def roast(self, code, b):
        provider = b.get("provider")
        with lock:
            room = rooms.get(code)
            if not room:
                return self.err("Room not found.", 404)
            if b.get("hostKey") != room["hostKey"]:
                return self.err("Only the host can start the roast.", 403)
            room["roastState"] = {"status": "working", "error": None}
            changed(room)
        try:
            entry = run_roast(code, provider, (b.get("key") or "").strip(), (b.get("model") or "").strip(), b.get("spice"))
        except AIError as e:
            with lock:
                room = rooms.get(code)
                if room and (room.get("roastState") or {}).get("status") == "working":
                    room["roastState"] = {"status": "failed", "error": f"{PROVIDER_NAMES.get(provider, 'The AI')}: {e}"}
                    changed(room)
            return self.err(f"{PROVIDER_NAMES.get(provider, 'The AI')} failed: {e}", 502)
        return self.send_json({"ok": True, "provider": entry["provider"]})


def main():
    load()
    for code, room in rooms.items():  # resume unfinished poster lookups; older rooms predate modes
        room.setdefault("mode", "classic")
        room.setdefault("phase", "ranking")
        room.setdefault("roasts", [])
        if (room.get("roastState") or {}).get("status") == "working":  # the server restarted mid-roast
            room["roastState"] = {"status": "failed", "error": "The server restarted while the AI was writing. Press Try again."}
        for item in room["anime"]:
            if item.get("status") == "searching":
                lookup_q.put((code, item["id"]))
    threading.Thread(target=saver, daemon=True).start()
    threading.Thread(target=lookup_worker, daemon=True).start()
    threading.Thread(target=ticker, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Anime Tier Night running on http://localhost:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()

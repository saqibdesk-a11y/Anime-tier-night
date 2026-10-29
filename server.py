"""Anime Tier Night - tiny multiplayer tier list server (Python stdlib only).

Run:  python server.py  (then open http://localhost:8000)
"""
import base64
import json
import os
import queue
import random
import re
import string
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import draw_game
import imposter_game
import media
import werewolf_game

GAMES = {"draw": draw_game, "werewolf": werewolf_game, "imposter": imposter_game}  # every game module has the same hooks

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

QUERY = """query ($q: String, $n: Int) { Page(perPage: $n) { media(search: $q, type: %s, isAdult: false, sort: [POPULARITY_DESC]) {
  id siteUrl format seasonYear popularity
  title { romaji english native } synonyms coverImage { extraLarge large } } } }"""
CHARACTER_QUERY = """query ($q: String, $n: Int) { Page(perPage: $n) { characters(search: $q, sort: [FAVOURITES_DESC]) {
  id siteUrl favourites name { full alternative } image { large } media(perPage: 1) { nodes { title { english romaji } } } } } }"""


def anilist(q, n, kind="anime"):
    query = (CHARACTER_QUERY if kind == "character" else
             QUERY % ("MANGA, countryOfOrigin: KR" if kind == "manhwa" else "MANGA" if kind == "manga" else "ANIME"))
    body = json.dumps({"query": query, "variables": {"q": q, "n": n}}).encode("utf-8")
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
                page = json.loads(r.read().decode("utf-8"))["data"]["Page"]
                return page.get("characters" if kind == "character" else "media") or []
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


CHAR_QUERY = """query ($p: Int) { Page(page: $p, perPage: 50) { characters(sort: [FAVOURITES_DESC]) {
  name { full } image { large } media(perPage: 1, sort: [POPULARITY_DESC]) { nodes { title { english romaji } } } } } }"""
SHOW_QUERY = """query ($id: Int) { Media(id: $id) { characters(sort: [FAVOURITES_DESC], perPage: 26) { nodes { name { full } image { large } } } } }"""
FEATURED_SHOWS = [(235, "Detective Conan"), (813, "Dragon Ball Z")]  # AniList ids, picked by request
SKIP_CHARACTERS = {"Narrator", "Lum"}
ALIASES = {"Ai Haibara": "Sherry"}  # Sherry is Ai Haibara's Black Organization codename; AniList has no separate entry
_avatars = {"list": None, "at": 0}
_avatars_lock = threading.Lock()
AVATAR_HOST = "https://s4.anilist.co/"


def avatar_gallery():
    """The 100 most-loved anime characters on AniList, cached for a day."""
    with _avatars_lock:
        if _avatars["list"] and time.time() - _avatars["at"] < 86400:
            return _avatars["list"]
        out = []
        for page in (1, 2):
            body = json.dumps({"query": CHAR_QUERY, "variables": {"p": page}}).encode("utf-8")
            try:
                req = urllib.request.Request("https://graphql.anilist.co", data=body, headers={
                    "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "AnimeTierNight/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    chars = json.loads(r.read().decode("utf-8"))["data"]["Page"]["characters"]
            except Exception:
                break
            for c in chars:
                img = (c.get("image") or {}).get("large") or ""
                show = ((((c.get("media") or {}).get("nodes") or [{}])[0] or {}).get("title") or {})
                if img.startswith(AVATAR_HOST) and "default" not in img:
                    out.append({"name": (c.get("name") or {}).get("full") or "", "show": show.get("english") or show.get("romaji") or "", "img": img})
        seen = {c["img"] for c in out}
        for media_id, show in FEATURED_SHOWS:
            body = json.dumps({"query": SHOW_QUERY, "variables": {"id": media_id}}).encode("utf-8")
            try:
                req = urllib.request.Request("https://graphql.anilist.co", data=body, headers={
                    "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "AnimeTierNight/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    nodes = json.loads(r.read().decode("utf-8"))["data"]["Media"]["characters"]["nodes"]
            except Exception:
                continue
            for c in nodes:
                img, nm = (c.get("image") or {}).get("large") or "", (c.get("name") or {}).get("full") or ""
                if img.startswith(AVATAR_HOST) and "default" not in img and nm not in SKIP_CHARACTERS and img not in seen:
                    out.append({"name": nm, "show": show, "img": img})
                    seen.add(img)
        for c in out:
            if c["name"] in ALIASES:
                c["alias"] = ALIASES[c["name"]]
                c["name"] = f'{c["name"]} ({ALIASES[c["name"]]})'
        if out:
            _avatars.update(list=out, at=time.time())
        return out


def character_option(c):
    show = ((c.get("media") or {}).get("nodes") or [{}])[0].get("title") or {}
    return {"mal_id": c.get("id"), "title": (c.get("name") or {}).get("full"), "subtitle": show.get("english") or show.get("romaji"),
            "year": None, "type": "Character", "members": c.get("favourites") or 0,
            "img": (c.get("image") or {}).get("large"), "url": c.get("siteUrl")}


def get_json(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TierNight/1.0 (friends' party game)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def wikipedia(q, n):
    """Wikipedia covers almost anything (people, movies, food, places) and its lead image makes a fine card."""
    d = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrlimit": n,
        "prop": "pageimages|description", "piprop": "thumbnail", "pithumbsize": 500, "pilicense": "any"}))
    pages = sorted(((d or {}).get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    return [{"mal_id": p.get("pageid"), "title": re.sub(r"\s*\([^)]*\)$", "", p.get("title") or ""),  # "Interstellar (film)"
             "subtitle": p.get("description"), "year": None, "type": None,
             "members": 0, "img": (p.get("thumbnail") or {}).get("source"),
             "url": "https://en.wikipedia.org/?curid=%s" % p.get("pageid")} for p in pages]


def tvmaze(q, n):
    out = []
    for r in (get_json("https://api.tvmaze.com/search/shows?q=" + urllib.parse.quote(q)) or [])[:n]:
        s = r.get("show") or {}
        img = s.get("image") or {}
        out.append({"mal_id": s.get("id"), "title": s.get("name"), "subtitle": ", ".join(s.get("genres") or []),
                    "year": int(s["premiered"][:4]) if s.get("premiered") else None, "type": "TV",
                    "members": 0, "img": img.get("original") or img.get("medium"), "url": s.get("url")})
    return out


def app_store(q, n):
    d = get_json("https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": q, "entity": "software", "limit": n, "country": "us"}))
    return [{"mal_id": a.get("trackId"), "title": re.split(r" [-–:|] ", a.get("trackName") or "")[0],  # "TikTok - Videos, Shop & LIVE" "subtitle": a.get("sellerName"), "year": None, "type": "App",
             "members": 0, "img": a.get("artworkUrl512") or a.get("artworkUrl100"), "url": a.get("trackViewUrl")}
            for a in (d or {}).get("results", [])]


KINDS = ("anime", "manga", "manhwa", "character", "movie", "show", "app", "other")


def search(q, limit=12, kind="anime"):
    if kind in ("anime", "manga", "manhwa"):
        return [to_option(a) for a in anilist(q, limit, kind)]
    if kind == "character":
        return [character_option(c) for c in anilist(q, limit, "character")] + wikipedia(q, 4)
    if kind == "show":
        return tvmaze(q, limit) + wikipedia(q, 4)
    if kind == "app":
        return app_store(q, limit)
    return wikipedia(q + " film" if kind == "movie" else q, limit)


def best_match(q, kind="anime"):
    ql = q.strip().lower()
    if kind in ("anime", "manga", "manhwa"):
        items = anilist(q, 8, kind)
        for a in items:
            t = a.get("title") or {}
            names = [t.get("romaji"), t.get("english"), t.get("native")] + (a.get("synonyms") or [])
            if any(n and n.strip().lower() == ql for n in names):
                return to_option(a)
        return to_option(items[0]) if items else None  # results are sorted by popularity
    found = [o for o in search(q, 5, kind) if o.get("img")]
    if not found and kind != "other":
        found = [o for o in wikipedia(q, 3) if o.get("img")]  # e.g. a western character AniList doesn't have
    return next((o for o in found if (o["title"] or "").lower() == ql), found[0] if found else None)


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
        m = best_match(name, item.get("kind") or "anime")
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


# ---------- AI (shared with every game, see ai.py) ----------

from ai import (AIError, BUILTIN_KEYS, BUILTIN_ORDER, BUSY, PROVIDER_NAMES, ask_builtin, builtin_allowed,
                builtin_models, complete, list_models)


SPICE = {
    "wholesome": "Keep it friendly: gentle teasing, mostly hype and compliments.",
    "spicy": "Roast properly: sharp, specific jokes about their picks and rankings, balanced with real compliments where earned.",
    "unhinged": "Go hard: savage, over-the-top roasts like a chaotic friend in the group chat. Still punch at taste, never at identity.",
}


def roast_prompt(room, spice):
    by_id = {a["id"]: a for a in room["anime"]}
    mode = {"picks": "each person secretly submitted picks, then everyone ranked the combined pool",
            "ai": "an AI chose the list" + (f' (theme: {room["aiTheme"]})' if room.get("aiTheme") else "") + ", everyone ranked it"
            }.get(room.get("mode"), "host chose the list, everyone ranked it")
    lines = [f'Room: "{room["title"]}". Ranking: {topic_of(room)}. Mode: {mode}.']
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
    system = (f"You are the hype-man and roaster in a friend group's tier list night ({topic_of(room)}), typing in their group chat "
              "while they record a video. You know the subject deeply: reference real details, plot points, characters, fandom "
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


CATEGORY_KIND = {"anime": "anime", "characters": "character", "manga": "manga", "manhwa": "manhwa",
                 "movies": "movie", "shows": "show", "mix": "other", "custom": "other"}


def new_item(room, name, by=None, kind=None):
    kind = kind if kind in KINDS else CATEGORY_KIND.get(room.get("category"), "anime")
    item = {"id": rid(8), "name": name, "title": name, "img": None, "url": None, "year": None, "status": "searching", "kind": kind}
    if by is not None:
        item["by"] = list(by)
    room["anime"].append(item)
    lookup_q.put((room["code"], item["id"]))
    return item


def add_anime(room, names, kinds=None):
    seen = {x["name"].lower() for x in room["anime"]}
    for i, raw in enumerate(names):
        name = clean_name(raw)
        if not name or name.lower() in seen or len(room["anime"]) >= 150:
            continue
        seen.add(name.lower())
        new_item(room, name, kind=(kinds or {}).get(i))


def topic_of(room):
    """What this tier list ranks, in words: 'anime', 'YouTubers', 'movies'..."""
    return room.get("catLabel") or {"anime": "anime", "characters": "fictional characters", "manga": "manga", "manhwa": "manhwa",
                                    "movies": "movies", "shows": "TV shows",
                                    "mix": "a mix of anime, manga, manhwa, characters, movies and shows"}.get(room.get("category"), "anime")


def ai_list(code):
    """The AI's pick: it chooses what everyone ranks, from the host's category and theme."""
    with lock:
        room = rooms.get(code)
        if not room:
            return
        cat, n, theme, topic = room.get("category"), room.get("aiCount", 15), room.get("aiTheme") or "", topic_of(room)
        have = [a["name"] for a in room["anime"]]
    mixed = cat in ("mix", "custom")
    try:
        out, _, _ = ask_builtin(
            "You pick the items for a friend group's tier list night. Choose things most people in the group will know, "
            "with a fun spread: some undisputed greats, some divisive, a couple of guilty pleasures that will start arguments.",
            f"Pick {n} {topic}" + (f", theme: {theme}" if theme else "") + ". "
            + (f"Don't repeat these: {', '.join(have[:60])}. " if have else "")
            + "Use each item's best-known official name, exactly as it would be titled on "
            + ("AniList" if cat in ("anime", "manga", "manhwa", "characters") else "Wikipedia") + " so a picture can be found. "
            + ("For characters, use their full name. " if cat == "characters" else "")
            + ("Tag each item with what it is: one of anime, manga, manhwa, character, movie, show, app, other. " if mixed else "")
            + 'Return only JSON: {"title": "<short catchy name for this tier list>", "items": [{"name": "...", "kind": "..."}]}',
            timeout=30, text_first=True)
        items = [(clean_name(str(i.get("name") or "")), str(i.get("kind") or "").lower())
                 for i in out.get("items", []) if isinstance(i, dict)]
        items = [(nm, k) for nm, k in items if nm][:n]
        if not items:
            raise AIError("it sent back an empty list")
    except (AIError, ValueError, TypeError, AttributeError) as e:
        with lock:
            room = rooms.get(code)
            if room:
                room["aiState"] = {"status": "failed", "error": f"The AI couldn't make the list: {str(e).rstrip('.')}."}
                changed(room)
        return
    with lock:
        room = rooms.get(code)
        if not room:
            return
        add_anime(room, [nm for nm, _ in items], {i: k for i, (_, k) in enumerate(items)} if mixed else None)
        if out.get("title") and room.get("titleAuto"):
            room["title"] = str(out["title"]).strip()[:80] or room["title"]
        room["aiState"] = {"status": "done", "error": None}
        changed(room)


def start_ai_list(room):
    room["aiState"] = {"status": "working", "error": None}
    threading.Thread(target=ai_list, args=(room["code"],), daemon=True).start()


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
                if room.get("game") in GAMES:
                    if GAMES[room["game"]].tick(room):
                        changed(room)
                    continue
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
        if n > 1_500_000:  # drawings are uploaded as images
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def send_bytes(self, data, ctype, cache):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        qs = urllib.parse.parse_qs(u.query)

        if u.path in PAGES:
            with open(os.path.join(HERE, PAGES[u.path]), "rb") as f:
                return self.send_bytes(f.read(), "text/html; charset=utf-8", "no-store")

        if parts[:2] == ["api", "img"] and len(parts) == 3:
            raw = media.IMAGES.get(parts[2])
            if raw is None:
                return self.err("That drawing is gone.", 404)
            return self.send_bytes(raw, "image/jpeg", "public, max-age=86400, immutable")

        # team canvas: long-poll for strokes after index `since`
        if len(parts) == 4 and parts[:2] == ["api", "draw"] and parts[3] == "strokes":
            code, q = parts[2].upper(), lambda k, d="": (qs.get(k) or [d])[0]
            deadline = time.time() + 20
            with lock:
                room = rooms.get(code)
                p = room and room["players"].get(q("pid"))
                if not room or not p or p["key"] != q("key"):
                    return self.err("You're not in this room.", 403)
                rnd, team, since, gen = room["round"], p.get("team"), int(q("since", "0")), int(q("gen", "0"))
                while time.time() < deadline:
                    out = draw_game.strokes_since(code, rnd, team, since, gen)
                    if out["reset"] or out["strokes"] or rooms.get(code, {}).get("round") != rnd:
                        break
                    lock.wait(timeout=deadline - time.time())
                return self.send_json(out)

        if parts == ["api", "avatars"]:
            return self.send_json({"avatars": avatar_gallery()})

        if u.path in STATIC:
            ctype, cache = STATIC[u.path]
            with open(os.path.join(HERE, u.path.lstrip("/")), "rb") as f:
                return self.send_bytes(f.read(), ctype, cache)

        if parts[:2] == ["api", "search"]:
            q, kind = (qs.get("q") or [""])[0].strip(), (qs.get("kind") or ["anime"])[0]
            return self.send_json({"results": search(q, 12, kind if kind in KINDS else "anime") if q else []})

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
                viewer = pid if p and p["key"] == key else None
                game = GAMES.get(room.get("game"))
                return self.send_json(game.public(room, viewer) if game else public(room, viewer))

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
                if b.get("game") in GAMES:
                    room = {"code": code, "hostKey": rid(16), "title": (b.get("title") or "Game Night")[:80],
                            "players": {}, "created": time.time(), "version": 0}
                    GAMES[b["game"]].create(room, b)
                    rooms[code] = room
                    changed(room)
                    return self.send_json({"code": code, "hostKey": room["hostKey"]})
                mode = b.get("mode") if b.get("mode") in ("picks", "classic", "ai") else "classic"
                category = b.get("category") if b.get("category") in CATEGORY_KIND else "anime"
                room = {"code": code, "hostKey": rid(16), "title": (b.get("title") or "Tier List Night")[:80],
                        "titleAuto": not b.get("title"), "category": category,
                        "catLabel": str(b.get("catLabel") or "").strip()[:40] if category == "custom" else "",
                        "aiTheme": str(b.get("aiTheme") or "").strip()[:120], "aiCount": max(5, min(40, int(b.get("aiCount") or 15))),
                        "aiState": None, "mode": mode, "phase": "submit" if mode == "picks" else "ranking",
                        "picksPer": max(1, min(10, int(b.get("picksPer") or 5))),
                        "timerSec": max(30, min(1800, int(b.get("timerSec") or 120))), "deadline": None,
                        "spice": b.get("spice") if b.get("spice") in SPICE else "spicy", "show": None, "roastState": None,
                        "anime": [], "players": {}, "revealed": False, "tiers": TIERS, "roasts": [],
                        "created": time.time(), "version": 0}
                rooms[code] = room
                if mode == "classic":
                    add_anime(room, b.get("list") or [])
                elif mode == "ai":
                    start_ai_list(room)
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
                if room.get("game") in GAMES:
                    GAMES[room["game"]].on_join(room, pid)
                changed(room)
                return self.send_json({"pid": pid, "key": room["players"][pid]["key"]})

            if room.get("game") in GAMES and action in ("photo", "avatar"):
                if not player:
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                if action == "avatar":
                    url = str(b.get("url") or "")
                    if not url.startswith(media.AVATAR_HOST):
                        return self.err("Pick one of the characters.")
                    media.IMAGES.pop(player.get("photo"), None)
                    player.update(avatar=url[:300], photo=None)
                else:
                    img = str(b.get("img") or "")
                    if not img.startswith("data:image/jpeg;base64,"):
                        return self.err("That picture didn't upload. Try another one.")
                    raw = base64.b64decode(img.split(",", 1)[1])
                    if len(raw) > 400_000:
                        return self.err("That picture is too big.")
                    media.IMAGES.pop(player.get("photo"), None)
                    pic = rid(12)
                    media.IMAGES[pic] = raw
                    player.update(photo=pic, avatar=None)
                changed(room)
                return self.send_json({"ok": True})

            if room.get("game") in GAMES:
                game = GAMES[room["game"]]
                try:
                    if action in game.HOST_ACTIONS:
                        if not is_host:
                            return self.err("Only the host can do that.", 403)
                        touched = game.host_action(room, action, b)
                    elif not player:
                        return self.err("You're not in this room. Rejoin with your name.", 403)
                    else:
                        touched = game.player_action(room, action, b, b.get("pid"))
                except media.Refuse as e:
                    return self.err(str(e), e.status)
                except (ValueError, TypeError):
                    return self.err("That request didn't make sense.")
                if touched:
                    changed(room)
                return self.send_json({"ok": True})

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
                    return self.err("Type a name.")
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
            elif action == "ailist":  # the AI picks (more) items: a retry, or another batch on top
                if room.get("mode") != "ai":
                    return self.err("This room isn't an AI's-pick room.")
                if (room.get("aiState") or {}).get("status") == "working":
                    return self.err("The AI is still picking.")
                if b.get("fresh"):
                    room["anime"] = []
                    for p in room["players"].values():
                        p["tiers"], p["done"] = {t: [] for t in TIERS}, False
                if "theme" in b:
                    room["aiTheme"] = str(b.get("theme") or "").strip()[:120]
                start_ai_list(room)
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
                    return self.err("That one isn't in the room anymore.", 404)
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


STATIC = {  # files the pages load: the shared avatar picker and what makes the site installable as an app
    "/avatars.js": ("text/javascript; charset=utf-8", "no-store"),
    "/backguard.js": ("text/javascript; charset=utf-8", "no-store"),
    "/manifest.webmanifest": ("application/manifest+json", "public, max-age=3600"),
    "/icon-192.png": ("image/png", "public, max-age=86400"),
    "/icon-512.png": ("image/png", "public, max-age=86400"),
}
PAGES = {"/": "hub.html", "/index.html": "hub.html", "/tierlist": "tierlist.html", "/draw": "draw.html", "/werewolf": "werewolf.html", "/imposter": "imposter.html"}


def main():
    load()
    for game in GAMES.values():
        game.setup(rooms, lock, changed, rid)
    for code, room in rooms.items():  # resume unfinished poster lookups; older rooms predate modes
        room.setdefault("mode", "classic")
        room.setdefault("phase", "ranking")
        room.setdefault("roasts", [])
        if (room.get("roastState") or {}).get("status") == "working":  # the server restarted mid-roast
            room["roastState"] = {"status": "failed", "error": "The server restarted while the AI was writing. Press Try again."}
        for item in room.get("anime", []):
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

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
            item = next((x for x in room["anime"] if x["id"] == aid), None) if room else None
            name = item["name"] if item else None
        if not name:
            continue
        m = best_match(name)
        with lock:
            room = rooms.get(code)
            item = next((x for x in room["anime"] if x["id"] == aid), None) if room else None
            if not item:
                continue
            item["status"] = "ok" if m and m["img"] else "missing"
            if m:
                item.update(title=m["title"], img=m["img"], url=m["url"], year=m["year"])
            changed(room)


# ---------- room helpers ----------

def rid(n=6, alphabet=string.ascii_uppercase + string.digits):
    return "".join(random.choice(alphabet) for _ in range(n))


def add_anime(room, names):
    seen = {x["name"].lower() for x in room["anime"]}
    for raw in names:
        name = raw.strip().lstrip("-*0123456789.) ").strip()
        if not name or name.lower() in seen or len(room["anime"]) >= 150:
            continue
        seen.add(name.lower())
        item = {"id": rid(8), "name": name[:120], "title": name[:120], "img": None,
                "url": None, "year": None, "status": "searching"}
        room["anime"].append(item)
        lookup_q.put((room["code"], item["id"]))


def public(room):
    r = {k: v for k, v in room.items() if k != "hostKey"}
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
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
            deadline = time.time() + 25
            with lock:
                while code in rooms and rooms[code]["version"] <= v and time.time() < deadline:
                    lock.wait(timeout=deadline - time.time())
                room = rooms.get(code)
                if not room:
                    return self.err("Room not found. Check the code.", 404)
                return self.send_json(public(room))

        self.err("Not found", 404)

    def do_POST(self):
        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        b = self.body()

        if parts == ["api", "rooms"]:
            with lock:
                code = rid(4, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                while code in rooms:
                    code = rid(4, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                room = {"code": code, "hostKey": rid(16), "title": (b.get("title") or "Anime Tier Night")[:80],
                        "anime": [], "players": {}, "revealed": False, "tiers": TIERS,
                        "created": time.time(), "version": 0}
                rooms[code] = room
                add_anime(room, b.get("list") or [])
                changed(room)
                return self.send_json({"code": code, "hostKey": room["hostKey"]})

        if len(parts) < 4 or parts[:2] != ["api", "rooms"]:
            return self.err("Not found", 404)
        code, action = parts[2].upper(), parts[3]

        with lock:
            room = rooms.get(code)
            if not room:
                return self.err("Room not found. Check the code.", 404)
            is_host = b.get("hostKey") == room["hostKey"]

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

            if action == "rank":
                p = room["players"].get(b.get("pid"))
                if not p or p["key"] != b.get("key"):
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                p["tiers"] = clean_tiers(room, b.get("tiers"))
                if "done" in b:
                    p["done"] = bool(b["done"])
                changed(room)
                return self.send_json({"ok": True})

            if not is_host:
                return self.err("Only the host can do that.", 403)

            if action == "add":
                add_anime(room, b.get("list") or [])
            elif action == "reveal":
                room["revealed"] = bool(b.get("revealed"))
            elif action == "title":
                room["title"] = (b.get("title") or room["title"])[:80]
            elif action == "kick":
                room["players"].pop(b.get("pid"), None)
            elif action == "anime" and len(parts) == 5:
                item = next((x for x in room["anime"] if x["id"] == parts[4]), None)
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


def main():
    load()
    for code, room in rooms.items():  # resume unfinished poster lookups
        for item in room["anime"]:
            if item.get("status") == "searching":
                lookup_q.put((code, item["id"]))
    threading.Thread(target=saver, daemon=True).start()
    threading.Thread(target=lookup_worker, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Anime Tier Night running on http://localhost:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()

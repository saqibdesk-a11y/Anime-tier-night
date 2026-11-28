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

import bluff_game
import clash_game
import codenames_game
import dial_game
import draw_game
import forged_game
import imposter_game
import lantern_game
import mask_game
import media
import op_game
import scroll_game
import silhouette_game
import werewolf_game

GAMES = {
    "draw": draw_game, "forged": forged_game, "scroll": scroll_game,
    "silhouette": silhouette_game, "dial": dial_game, "clash": clash_game,
    "bluff": bluff_game, "mask": mask_game, "op": op_game,
    "werewolf": werewolf_game, "imposter": imposter_game,
    "codenames": codenames_game, "lantern": lantern_game,
}  # every game module has the same hooks

PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "rooms.json")
TIERS = ["S", "A", "B", "C", "D", "F"]
ROOM_TTL_SEC = max(1, int(os.environ.get("ROOM_TTL_DAYS", "14"))) * 86400

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


def changed(room, persist=True):
    """Call with lock held after mutating a room. Pass persist=False for in-memory-only updates (chat, pranks)."""
    room["version"] += 1
    room["lastActive"] = time.time()
    lock.notify_all()
    if persist:
        _save_pending.set()


def live_image_ids():
    """Every image id still referenced by an existing room (player photos and Draw It entries)."""
    keep = set()
    for room in rooms.values():
        for p in room.get("players", {}).values():
            if p.get("photo"):
                keep.add(p["photo"])
        for rd in room.get("roundData", []):
            for e in (rd.get("entries") or {}).values():
                if e.get("img"):
                    keep.add(e["img"])
        for ch in room.get("chains", []):
            for e in ch.get("entries", []):
                if e.get("img"):
                    keep.add(e["img"])
    return keep


def prune_rooms():
    """Call with lock held. Drops rooms inactive past ROOM_TTL_SEC and frees their in-memory media."""
    now = time.time()
    gone = [c for c, r in rooms.items() if now - r.get("lastActive", r.get("created", 0)) > ROOM_TTL_SEC]
    for code in gone:
        rooms.pop(code, None)
        draw_game.cleanup(code)
    media.forget_gone(set(rooms), live_image_ids())
    if gone:
        _save_pending.set()


def safe_int(val, default):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ---------- Discord Open Graph previews, presence & host takeover ----------

STALL_META = {
    "/": ("Anime Game Night", "14 neon multiplayer party games for friends: Guess the OP & Songs, Last Lantern, Fox's Bluff, Codenames, Forged Brush, Broken Scroll, Guess the Silhouette, Festival Dial, Caption Clash, Forehead Mask, Werewolf, Imposter, Tier List & Draw It.", "/img/scenes/arcade-hero.jpg"),
    "/index.html": ("Anime Game Night", "14 neon multiplayer party games for friends: Guess the OP & Songs, Last Lantern, Fox's Bluff, Codenames, Forged Brush, Broken Scroll, Guess the Silhouette, Festival Dial, Caption Clash, Forehead Mask, Werewolf, Imposter, Tier List & Draw It.", "/img/scenes/arcade-hero.jpg"),
    "/op": ("Guess the OP & Songs", "Blast 30-second live music previews of iconic Anime Openings—or switch to Pop, Hip-Hop, K-Pop, Rock, Bollywood, or any custom artist!", "/img/scenes/arcade-op.jpg"),
    "/codenames": ("Codenames", "Two teams, one grid of words. Give one-word clues and find all your agents before the other team.", "/img/scenes/arcade-codenames.jpg"),
    "/lantern": ("Last Lantern", "Match the colour or symbol and empty your hand first. Call your last card before someone catches you.", "/img/scenes/arcade-lantern.jpg"),
    "/forged": ("Forged Brush", "Everyone draws the same secret subject—one brushstroke per turn—except the Forger, who has to fake it.", "/img/scenes/arcade-forged.jpg"),
    "/scroll": ("Broken Scroll", "Write a prompt, draw it, guess the drawing, repeat—then watch every scroll derail in the reveal theater.", "/img/scenes/arcade-scroll.jpg"),
    "/silhouette": ("Guess the Silhouette", "Name the anime character as their shadow, blur, or zoom clears—or battle in Higher or Lower and AI speed trivia.", "/img/scenes/arcade-silhouette.jpg"),
    "/dial": ("Festival Dial", "One Psychic sees the hidden target on a wild spectrum and gives one clue. Everyone else slides the dial to match.", "/img/scenes/arcade-dial.jpg"),
    "/clash": ("Caption Clash", "Write the funniest answer to unhinged prompts, battle head-to-head in the vote, and get roasted by AI.", "/img/scenes/stall-clash.jpg"),
    "/bluff": ("Fox's Bluff", "Place Sakura Blossoms or your Cursed Fox Mask face-down, raise the stakes, and flip—or watch a bluff explode.", "/img/scenes/arcade-bluff.jpg"),
    "/mask": ("Forehead Mask", "Everyone sees the character on your forehead except you. Ask Yes/No questions and guess who you are first.", "/img/scenes/arcade-mask.jpg"),
    "/werewolf": ("Werewolf", "Secret roles. Wolves hunt at night, the village votes by day. 13 roles with built-in chat.", "/img/scenes/stall-werewolf.webp"),
    "/imposter": ("Imposter", "Everyone gets the same secret word except one. Give clues, spot the fake, and roast the round.", "/img/scenes/stall-imposter.webp"),
    "/tierlist": ("Tier List Night", "Rank anime, characters or anything else together. Watch the reveal show and get roasted by AI.", "/img/scenes/stall-tierlist.webp"),
    "/draw": ("Draw It", "The AI picks what everyone draws. Play solo or on a shared team canvas, then friends or AI score it.", "/img/scenes/stall-draw.webp"),
}


def html_esc(s):
    return str(s or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def inject_og(raw_bytes, path, qs, proto, host):
    """Injects Open Graph / Discord embed meta tags so pasted room links unfurl with stall art and live status."""
    title, desc, img = STALL_META.get(path, STALL_META["/"])
    room_code = ((qs.get("room") or [""])[0]).strip().upper()
    if room_code:
        with lock:
            r = rooms.get(room_code)
            if r:
                g = r.get("game") or "tierlist"
                g_title, _, g_img = STALL_META.get("/" + g, (title, desc, img))
                title, img = f"{g_title} · Room {room_code}", g_img
                n = len(r.get("players", {}))
                ph = r.get("phase") or "lobby"
                where = "waiting in the lobby" if ph in ("lobby", "submit") else "playing right now"
                desc = f"{n} player{'s' if n != 1 else ''} {where} — tap to join Anime Game Night!"
    base = f"{proto}://{host}" if host else ""
    img_url = (base + img) if base else img
    tags = (
        f'\n<meta property="og:site_name" content="Anime Game Night">'
        f'\n<meta property="og:type" content="website">'
        f'\n<meta property="og:title" content="{html_esc(title)}">'
        f'\n<meta property="og:description" content="{html_esc(desc)}">'
        f'\n<meta property="og:image" content="{html_esc(img_url)}">'
        f'\n<meta name="twitter:card" content="summary_large_image">'
        f'\n<meta name="twitter:title" content="{html_esc(title)}">'
        f'\n<meta name="twitter:description" content="{html_esc(desc)}">'
        f'\n<meta name="twitter:image" content="{html_esc(img_url)}">'
    ).encode("utf-8")
    idx = raw_bytes.lower().find(b"</head>")
    if idx < 0:
        return raw_bytes
    return raw_bytes[:idx] + tags + raw_bytes[idx:]


def kick_from_room(room, pid):
    """Removes a player using the game's own kick logic so turn order and win states stay intact."""
    if not pid or pid not in room["players"]:
        return
    g = room.get("game")
    if g in GAMES:
        GAMES[g].host_action(room, "kick", {"pid": pid})
    else:
        room["players"].pop(pid, None)
        for a in list(room.get("anime", [])):
            if pid in a.get("by", []):
                a["by"].remove(pid)
                if not a["by"] and room.get("phase") == "submit":
                    room["anime"].remove(a)
    media.HOST_VOTES.get(room["code"], {}).pop(pid, None)
    for v, t in list(media.HOST_VOTES.get(room["code"], {}).items()):
        if t == pid:
            media.HOST_VOTES[room["code"]].pop(v, None)


def host_status(room, now=None):
    """Returns (host_pid, offline_sec, can_vote, eligible_voters, need_votes)."""
    now = time.time() if now is None else now
    code = room["code"]
    hpid = room.get("hostPid")
    if hpid and hpid not in room["players"]:
        hpid = None
    # if no hostPid is tracked yet, wait until someone joins or claims host
    if not hpid:
        return None, 0, False, [], 1
    off_sec = int(media.offline_for(code, hpid, room.get("created", now), now))
    voters = [p for p in room["players"] if p != hpid and media.is_online(code, p, now)]
    can_vote = off_sec >= media.HOST_OFFLINE_SEC and len(voters) >= 1
    need = max(1, (len(voters) // 2) + 1)
    return hpid, off_sec, can_vote, voters, need


def room_meta(room, viewer, hk=""):
    now = time.time()
    code = room["code"]
    hpid, off_sec, can_vote, voters, need = host_status(room, now)
    online = media.online_pids(room, now)
    votes = {v: t for v, t in media.HOST_VOTES.get(code, {}).items() if v in voters and t in room["players"] and t != hpid}
    is_host = bool((hk and hk == room["hostKey"]) or (viewer and viewer == hpid))
    grant = media.HOST_GRANTS.get((code, viewer)) if (viewer and viewer == hpid) else None
    if grant and hk == grant:
        media.HOST_GRANTS.pop((code, viewer), None)
        grant = None
    moved = room.get("movedTo")
    moved_out = None
    if moved:
        nr = rooms.get(moved["code"])
        moved_out = {"game": moved["game"], "code": moved["code"],
                     "hostKey": nr["hostKey"] if (nr and viewer and viewer == nr.get("hostPid")) else None}
    return {
        "roomMeta": {
            "online": online,
            "hostPid": hpid,
            "isHost": is_host,
            "newHostKey": grant,
            "hostOffline": can_vote,
            "hostOfflineSec": off_sec,
            "hostVotes": votes,
            "hostVoteNeed": need,
            "wantSitout": [pid for pid, p in room["players"].items() if p.get("wantSitout")],
        },
        "movedTo": moved_out,
    }


def make_room_dict(code, game, title, b):
    if game in GAMES:
        room = {"code": code, "hostKey": rid(16), "title": (title or "Game Night")[:80],
                "players": {}, "created": time.time(), "version": 0}
        GAMES[game].create(room, b)
        return room
    mode = b.get("mode") if b.get("mode") in ("picks", "classic", "ai") else "classic"
    category = b.get("category") if b.get("category") in CATEGORY_KIND else "anime"
    room = {"code": code, "hostKey": rid(16), "title": (title or "Tier List Night")[:80],
            "titleAuto": not b.get("title"), "category": category,
            "catLabel": str(b.get("catLabel") or "").strip()[:40] if category == "custom" else "",
            "aiTheme": str(b.get("aiTheme") or "").strip()[:120], "aiCount": max(5, min(40, safe_int(b.get("aiCount"), 15))),
            "aiState": None, "mode": mode, "phase": "submit" if mode == "picks" else "lobby", "autoStart": None,
            "picksPer": max(1, min(10, safe_int(b.get("picksPer"), 5))),
            "timerSec": max(30, min(1800, safe_int(b.get("timerSec"), 120 if mode == "picks" else 180))), "deadline": None,
            "spice": b.get("spice") if b.get("spice") in SPICE else "spicy", "show": None, "roastState": None,
            "anime": [], "players": {}, "revealed": False, "tiers": TIERS, "roasts": [],
            "created": time.time(), "version": 0}
    if mode == "classic":
        add_anime(room, b.get("list") or [])
    elif mode == "ai":
        start_ai_list(room)
    return room


def hurry_offline_turn(room, now):
    """Shortens a turn timer when the active player has been offline for 15+ seconds so nobody waits forever."""
    dl = room.get("deadline")
    if not dl or dl <= now + 5:
        return False
    g = room.get("game")
    code = room["code"]
    turn_pid = None
    if g == "lantern" and room.get("phase") == "playing":
        turn_pid = lantern_game.current(room)
    elif g == "imposter" and room.get("phase") == "clues":
        rd = imposter_game.cur(room)
        t = imposter_game.turns(room) if rd else []
        turn_pid = t[rd["turn"]] if rd and rd["turn"] < len(t) else None
    elif g == "forged" and room.get("phase") == "drawing":
        rd = forged_game.cur(room)
        t = forged_game.turns(room) if rd else []
        turn_pid = t[rd["turn"]] if rd and rd["turn"] < len(t) else None
    elif g == "dial" and room.get("phase") == "clue":
        turn_pid = (room.get("current") or {}).get("psychic")
    elif g == "bluff" and room.get("phase") in ("turn", "bid", "flip"):
        bg = room.get("g")
        if bg:
            turn_pid = bg.get("bidder") if room.get("phase") == "flip" else bg.get("turn")
    elif g == "mask" and room.get("phase") == "play":
        mg = room.get("g")
        if mg and mg.get("turnStage") == "choose":
            turn_pid = mask_game.current_pid(room)
    elif g == "scroll" and room.get("phase") == "playing":
        # in Broken Scroll, if all online active players are done and remaining unfinished players are offline 15s+
        act_pids = scroll_game.active_order(room)
        online = [p for p in act_pids if media.is_online(code, p, now)]
        if online and len(online) < len(act_pids):
            step_idx = room["step"]
            all_online_done = all(
                (scroll_game.entry_of(scroll_game.chain_for(room, p, step_idx), step_idx) or {}).get("done")
                for p in online
            )
            missing_offline = all(
                (scroll_game.entry_of(scroll_game.chain_for(room, p, step_idx), step_idx) or {}).get("done")
                or media.offline_for(code, p, room.get("created", now), now) >= 15
                for p in act_pids if p not in online
            )
            if all_online_done and missing_offline:
                room["deadline"] = now + 3
                return True
        return False
    if turn_pid and media.offline_for(code, turn_pid, room.get("created", now), now) >= 15:
        # only speed up when at least one other player is actively watching
        if any(p != turn_pid and media.is_online(code, p, now) for p in room["players"]):
            room["deadline"] = now + 5
            return True
    return False


# ---------- AniList poster lookup ----------

_api_lock = threading.Lock()
_last_call = [0.0]

QUERY = """query ($q: String, $n: Int) { Page(perPage: $n) { media(search: $q, type: %s, isAdult: false, sort: [POPULARITY_DESC]) {
  id siteUrl format seasonYear popularity
  title { romaji english native } synonyms coverImage { extraLarge large } } } }"""
CHARACTER_QUERY = """query ($q: String, $n: Int) { Page(perPage: $n) { characters(search: $q, sort: [FAVOURITES_DESC]) {
  id siteUrl favourites name { full alternative } image { large } media(perPage: 1) { nodes { title { english romaji } } } } } }"""


def anilist_post(query, variables):
    """One AniList GraphQL call, spaced out from the others and retried when AniList is busy. Returns data or None."""
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
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
                return json.loads(r.read().decode("utf-8"))["data"]
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(min(30, int(e.headers.get("Retry-After") or 0) or 2 * (attempt + 1)))
                continue
            return None
        except Exception:
            time.sleep(1)
    return None


def anilist(q, n, kind="anime"):
    query = (CHARACTER_QUERY if kind == "character" else
             QUERY % ("MANGA, countryOfOrigin: KR" if kind == "manhwa" else "MANGA" if kind == "manga" else "ANIME"))
    page = (anilist_post(query, {"q": q, "n": n}) or {}).get("Page") or {}
    return page.get("characters" if kind == "character" else "media") or []


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
  name { full } favourites image { large } media(perPage: 1, sort: [POPULARITY_DESC]) { nodes { title { english romaji } genres seasonYear } } } } }"""
SHOW_QUERY = """query ($id: Int) { Media(id: $id) { genres seasonYear characters(sort: [FAVOURITES_DESC], perPage: 26) { nodes { name { full } favourites image { large } } } } }"""
ANIME_GALLERY_QUERY = """query ($p: Int) { Page(page: $p, perPage: 50) { media(type: ANIME, isAdult: false, sort: [POPULARITY_DESC]) {
  id title { english romaji } synonyms genres seasonYear format episodes averageScore coverImage { extraLarge large } } } }"""
FEATURED_SHOWS = [(235, "Detective Conan"), (813, "Dragon Ball Z")]  # AniList ids, picked by request
SKIP_CHARACTERS = {"Narrator", "Lum"}
ALIASES = {"Ai Haibara": "Sherry"}  # Sherry is Ai Haibara's Black Organization codename; AniList has no separate entry
_avatars = {"list": None, "at": 0}
_avatars_lock = threading.Lock()
_anime_gal = {"list": None, "at": 0}
_anime_gal_lock = threading.Lock()
AVATAR_HOST = "https://s4.anilist.co/"


def anime_gallery():
    """Top 100 most-popular anime series on AniList with posters, genres and years (cached for a day)."""
    with _anime_gal_lock:
        fresh = 86400 if _anime_gal.get("complete") else 180
        if _anime_gal["list"] and time.time() - _anime_gal["at"] < fresh:
            return _anime_gal["list"]
        out, complete = [], True
        for page in (1, 2):
            items = ((anilist_post(ANIME_GALLERY_QUERY, {"p": page}) or {}).get("Page") or {}).get("media")
            if not items:
                complete = False
                continue
            for m in items:
                t = m.get("title") or {}
                nm = t.get("english") or t.get("romaji") or ""
                alt = t.get("romaji") if t.get("english") and t.get("romaji") != t.get("english") else ""
                img = (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or ""
                if nm and img:
                    out.append({
                        "name": nm, "alias": alt, "synonyms": (m.get("synonyms") or [])[:4],
                        "img": img, "genres": m.get("genres") or [],
                        "year": m.get("seasonYear"), "format": m.get("format") or "TV",
                        "episodes": m.get("episodes"), "score": m.get("averageScore"),
                    })
        old = _anime_gal["list"] or []
        if out and (complete or len(out) > len(old)):
            _anime_gal.update(list=out, at=time.time(), complete=complete)
        else:
            _anime_gal["at"] = time.time()
        return _anime_gal["list"] or out


def avatar_gallery():
    """The 100 most-loved anime characters on AniList plus the featured shows, cached for a day.
    If AniList was busy and only part of it loaded, that part is served but retried a few minutes later,
    and a complete list is never swapped for a smaller one."""
    with _avatars_lock:
        fresh = 86400 if _avatars.get("complete") else 180
        if _avatars["list"] and time.time() - _avatars["at"] < fresh:
            return _avatars["list"]
        out, complete = [], True
        for page in (1, 2):
            chars = ((anilist_post(CHAR_QUERY, {"p": page}) or {}).get("Page") or {}).get("characters")
            if not chars:
                complete = False
                continue
            for c in chars:
                img = (c.get("image") or {}).get("large") or ""
                mnode = (((c.get("media") or {}).get("nodes") or [{}])[0] or {})
                show = mnode.get("title") or {}
                if img.startswith(AVATAR_HOST) and "default" not in img:
                    out.append({
                        "name": (c.get("name") or {}).get("full") or "",
                        "show": show.get("english") or show.get("romaji") or "",
                        "img": img, "favs": c.get("favourites") or 0,
                        "genres": mnode.get("genres") or [], "year": mnode.get("seasonYear"),
                    })
        seen = {c["img"] for c in out}
        for media_id, show in FEATURED_SHOWS:
            mdata = ((anilist_post(SHOW_QUERY, {"id": media_id}) or {}).get("Media") or {})
            nodes = ((mdata.get("characters") or {}).get("nodes"))
            if not nodes:
                complete = False
                continue
            mgenres, myear = mdata.get("genres") or [], mdata.get("seasonYear")
            for c in nodes:
                img, nm = (c.get("image") or {}).get("large") or "", (c.get("name") or {}).get("full") or ""
                if img.startswith(AVATAR_HOST) and "default" not in img and nm not in SKIP_CHARACTERS and img not in seen:
                    out.append({"name": nm, "show": show, "img": img, "favs": c.get("favourites") or 0, "genres": mgenres, "year": myear})
                    seen.add(img)
        for c in out:
            if c["name"] in ALIASES:
                c["alias"] = ALIASES[c["name"]]
                c["name"] = f'{c["name"]} ({ALIASES[c["name"]]})'
        old = _avatars["list"] or []
        if out and (complete or len(out) > len(old)):
            _avatars.update(list=out, at=time.time(), complete=complete)
        else:
            _avatars["at"] = time.time()  # keep what we had; try again in a few minutes
        return _avatars["list"] or out


def random_avatar(room):
    """A character nobody in the room has yet, so every new player gets a real face right away.
    Uses the cached list only (joining never waits on AniList); if it isn't loaded yet, starts loading it."""
    chars = _avatars["list"]
    if not chars:
        threading.Thread(target=avatar_gallery, daemon=True).start()
        return None
    taken = {p.get("avatar") for p in room["players"].values()}
    free = [c["img"] for c in chars if c["img"] not in taken]
    return random.choice(free or [c["img"] for c in chars])


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
    return [{"mal_id": a.get("trackId"), "title": re.split(r"\s*[:|]\s|\s[-–]\s", a.get("trackName") or "")[0],  # "TikTok - Videos, Shop & LIVE"
             "subtitle": a.get("sellerName"), "year": None, "type": "App",
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
        try:
            m = best_match(name, item.get("kind") or "anime")
        except Exception:  # one odd result must never stop the pictures for everything after it
            m = None
        with lock:
            room = rooms.get(code)
            item = find(room, aid)
            if not item:
                continue
            item["status"] = "ok" if m and m["img"] else "missing"
            if m:
                item.update(title=m.get("title") or item["title"], img=m.get("img"), url=m.get("url"), year=m.get("year"))
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


def start_ranking(room):
    room["phase"] = "ranking"
    room["autoStart"] = None
    room["deadline"] = time.time() + room["timerSec"] + 3  # 3s for everyone's screen to switch
    for p in room["players"].values():
        p["tiers"], p["done"] = {t: [] for t in TIERS}, False


def show_len(room):
    return len(room["players"]) + 3  # intro, one per player, group verdict, awards


def set_slide(room, i):
    """Every screen shows slide i; the ticker moves on after its time unless the host paused."""
    s = room["show"]
    last = show_len(room) - 1
    s["slide"] = max(0, min(i, last))
    s["at"] = time.time()
    s["dur"] = 9 if s["slide"] == 0 else 18 if s["slide"] == last else 14


def tick_tierlist(room):
    """The tier list runs itself: picks close when everyone is in, ranking ends on time or when all are done,
    and the reveal show steps through its slides. Returns True if anything changed."""
    now, ph, ps = time.time(), room.get("phase"), room["players"].values()
    if ph == "submit" and room.get("mode") == "picks":
        ready = len(ps) >= 2 and all(sum(1 for a in room["anime"] if pid in a.get("by", [])) >= room["picksPer"]
                                     for pid in room["players"])
        if ready and not room.get("autoStart"):
            room["autoStart"] = now + 5  # a short countdown so nobody is surprised
            return True
        if not ready and room.get("autoStart"):
            room["autoStart"] = None
            return True
        if ready and now >= room["autoStart"]:
            start_ranking(room)
            return True
    if ph == "ranking" and room.get("deadline"):
        all_done = ps and all(p.get("done") for p in ps)
        if now > room["deadline"] + 2 or all_done:
            finish(room)
            return True
    s = room.get("show")
    if s and not s.get("done") and not s.get("paused") and s.get("at"):
        waiting = s["slide"] == 0 and (room.get("roastState") or {}).get("status") == "working" and now - s["at"] < 45
        if not waiting and now - s["at"] >= s.get("dur", 12):
            if s["slide"] >= show_len(room) - 1:
                s["done"] = True
            else:
                set_slide(room, s["slide"] + 1)
            return True
    return False


def start_show(room):
    """Puts every screen on the Reveal Show and starts the AI roast in the background. Call with lock held."""
    room["show"] = {"slide": 0, "done": False, "paused": False}
    set_slide(room, 0)
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
    """Ends timed ranking rounds (a 2s grace lets last moves save), and once a minute forgets
    chat and prank memory of rooms that are gone."""
    beat = 0
    while True:
        time.sleep(1)
        beat += 1
        if beat % 60 == 0:
            with lock:
                prune_rooms()
        with lock:
            now = time.time()
            for room in list(rooms.values()):
                code = room["code"]
                # wake clients when host crosses the 20s offline threshold (or returns online)
                hpid, off_sec, can_vote, _, _ = host_status(room, now)
                if not can_vote and media.HOST_VOTES.get(code):
                    media.HOST_VOTES.pop(code, None)
                    changed(room, persist=False)
                was_alerted = bool(media.HOST_ALERTED.get(code))
                if can_vote != was_alerted:
                    media.HOST_ALERTED[code] = can_vote
                    changed(room, persist=False)
                if hurry_offline_turn(room, now):
                    changed(room, persist=False)
                if room.get("game") in GAMES:
                    if GAMES[room["game"]].tick(room):
                        changed(room)
                    continue
                if tick_tierlist(room):
                    changed(room)


# ---------- HTTP ----------

class QuietServer(ThreadingHTTPServer):
    """A phone that closes the page mid-answer is normal; only real errors go to the log."""

    def handle_error(self, request, client_address):
        import sys
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


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
                raw = f.read()
            proto = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip()
            host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").split(",")[0].strip()
            return self.send_bytes(inject_og(raw, u.path, qs, proto, host), "text/html; charset=utf-8", "no-store")

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
                rnd, team = room["round"], p.get("team")
                since, gen = safe_int(q("since", "0"), 0), safe_int(q("gen", "0"), 0)
                while time.time() < deadline:
                    out = draw_game.strokes_since(code, rnd, team, since, gen)
                    if out["reset"] or out["strokes"] or rooms.get(code, {}).get("round") != rnd:
                        break
                    lock.wait(timeout=deadline - time.time())
                return self.send_json(out)

        if parts == ["api", "avatars"]:
            return self.send_json({"avatars": avatar_gallery()})

        # the site's art: Werewolf role cards and festival scenes (made offline, see art/gen.py)
        if len(parts) == 3 and parts[0] == "img" and parts[1] in IMG_DIRS and re.fullmatch(r"[a-z0-9-]+\.(webp|jpg)", parts[2]):
            path = os.path.join(HERE, "img", parts[1], parts[2])
            if os.path.isfile(path):
                ctype = "image/jpeg" if parts[2].endswith(".jpg") else "image/webp"
                with open(path, "rb") as f:
                    return self.send_bytes(f.read(), ctype, "public, max-age=604800")
            return self.err("Not found", 404)

        # prank sound effects: /sounds/fart serves sounds/fart.mp3, .ogg or .wav, whichever is there
        if len(parts) == 2 and parts[0] == "sounds" and re.fullmatch(r"[a-z]+", parts[1]):
            for ext, ctype in (("mp3", "audio/mpeg"), ("ogg", "audio/ogg"), ("wav", "audio/wav")):
                path = os.path.join(HERE, "sounds", f"{parts[1]}.{ext}")
                if os.path.isfile(path):
                    with open(path, "rb") as f:
                        return self.send_bytes(f.read(), ctype, "no-cache")  # swapped sounds show up right away
            return self.err("Not found", 404)

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
            hk = (qs.get("hk") or [""])[0]
            deadline = time.time() + 25
            entered = False
            with lock:
                room = rooms.get(code)
                p = room["players"].get(pid) if room else None
                viewer = pid if p and p["key"] == key else None
                if viewer:
                    media.poll_enter(code, viewer)
                    entered = True
                    if hk and hk == room["hostKey"] and not room.get("hostPid"):
                        room["hostPid"] = viewer
                try:
                    while code in rooms and rooms[code]["version"] <= v and time.time() < deadline:
                        lock.wait(timeout=deadline - time.time())
                    room = rooms.get(code)
                    if not room:
                        return self.err("Room not found. Check the code.", 404)
                    p = room["players"].get(pid)
                    viewer = pid if p and p["key"] == key else None
                    game = GAMES.get(room.get("game"))
                    out = game.public(room, viewer) if game else public(room, viewer)
                    out.pop("lastActive", None)
                    out.update(media.chat_view(game, room, viewer))
                    out.update(media.prank_view(game, room, viewer))
                    out.update(room_meta(room, viewer, hk))
                    return self.send_json(out)
                finally:
                    if entered:
                        media.poll_leave(code, viewer)

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
                room = make_room_dict(code, b.get("game"), b.get("title"), b)
                rooms[code] = room
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
            if player:
                media.touch(code, b.get("pid"))
                if is_host and not room.get("hostPid"):
                    room["hostPid"] = b.get("pid")

            if action == "join":
                name = (b.get("name") or "").strip()[:24]
                if not name:
                    return self.err("Enter a name to join.")
                # same name rejoins the same board ONLY when that player is offline (stops mid-game role/hand peeking)
                for pid, p in room["players"].items():
                    if p["name"].lower() == name.lower():
                        if media.is_online(code, pid):
                            return self.err(f'{p["name"]} is already online in this room. Pick another name.', 409)
                        media.touch(code, pid)
                        if is_host and not room.get("hostPid"):
                            room["hostPid"] = pid
                        return self.send_json({"pid": pid, "key": p["key"]})
                if len(room["players"]) >= 30:
                    return self.err("This room is full (30 players).")
                pid = rid(8)
                first_player = len(room["players"]) == 0
                room["players"][pid] = {"name": name, "key": rid(16), "tiers": {t: [] for t in TIERS},
                                        "joined": time.time(), "done": False}
                if is_host or (first_player and not room.get("hostPid")):
                    room["hostPid"] = pid
                media.touch(code, pid)
                auto = random_avatar(room)
                if auto:  # a stand-in face until they pick their own (avatarAuto lets their saved pick replace it)
                    room["players"][pid].update(avatar=auto, avatarAuto=True)
                if room.get("game") in GAMES:
                    GAMES[room["game"]].on_join(room, pid)
                changed(room)
                return self.send_json({"pid": pid, "key": room["players"][pid]["key"]})

            if action == "sitout":
                if not player:
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                player["wantSitout"] = bool(b.get("sitout"))
                changed(room)
                return self.send_json({"ok": True})

            if action == "votehost":
                if not player:
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                pid = b.get("pid")
                hpid, _, can_vote, voters, need = host_status(room)
                if not can_vote:
                    return self.err("The host is still online (wait 20 seconds after they disconnect).", 409)
                if pid == hpid:
                    return self.err("You are the host.", 409)
                target = b.get("target")
                if target not in room["players"] or target == hpid or not media.is_online(code, target):
                    return self.err("Pick an online player to become the new host.")
                votes = media.HOST_VOTES.setdefault(code, {})
                votes[pid] = target
                tally = sum(1 for v, t in votes.items() if v in voters and t == target)
                if tally >= need:
                    old_host = hpid
                    old_name = room["players"].get(old_host, {}).get("name", "The old host")
                    new_name = room["players"][target]["name"]
                    room["hostKey"] = rid(16)
                    room["hostPid"] = target
                    media.HOST_GRANTS[(code, target)] = room["hostKey"]
                    media.HOST_VOTES.pop(code, None)
                    media.HOST_ALERTED[code] = False
                    if old_host and old_host in room["players"]:
                        kick_from_room(room, old_host)
                    media.chat_say(room, f"{old_name} was offline and kicked. {new_name} is now the host!")
                    changed(room)
                else:
                    changed(room, persist=False)
                return self.send_json({"ok": True})

            if action == "passhost":
                if not is_host:
                    return self.err("Only the host can pass host.", 403)
                target = b.get("target")
                if target not in room["players"] or target == room.get("hostPid"):
                    return self.err("Pick another player to make host.")
                old_name = room["players"].get(room.get("hostPid"), {}).get("name", "The host")
                new_name = room["players"][target]["name"]
                room["hostKey"] = rid(16)
                room["hostPid"] = target
                media.HOST_GRANTS[(code, target)] = room["hostKey"]
                media.HOST_VOTES.pop(code, None)
                media.HOST_ALERTED[code] = False
                media.chat_say(room, f"{old_name} passed host to {new_name}!")
                changed(room)
                return self.send_json({"ok": True})

            if action == "switchgame":
                if not is_host:
                    return self.err("Only the host can switch the game.", 403)
                to = str(b.get("to") or "")
                valid_games = set(GAMES) | {"tierlist"}
                if to not in valid_games:
                    return self.err("Pick a valid stall.")
                new_code = rid(4, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                while new_code in rooms:
                    new_code = rid(4, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                g_title = STALL_META.get("/" + to, ("Game Night",))[0]
                nr = make_room_dict(new_code, None if to == "tierlist" else to, g_title, {"mode": "picks"} if to == "tierlist" else {})
                nr["hostPid"] = room.get("hostPid") or b.get("pid")
                for pid_x, px in room["players"].items():
                    nr["players"][pid_x] = {
                        "name": px["name"], "key": px["key"], "tiers": {t: [] for t in TIERS},
                        "joined": time.time(), "done": False,
                        "wantSitout": bool(px.get("wantSitout")),
                    }
                    if px.get("avatar"):
                        nr["players"][pid_x].update(avatar=px["avatar"], avatarAuto=bool(px.get("avatarAuto")))
                    if px.get("photo"):
                        nr["players"][pid_x]["photo"] = px["photo"]
                    media.touch(new_code, pid_x)
                    if to in GAMES:
                        GAMES[to].on_join(nr, pid_x)
                rooms[new_code] = nr
                room["movedTo"] = {"game": to, "code": new_code}
                changed(nr)
                changed(room)
                return self.send_json({"ok": True, "game": to, "code": new_code, "hostKey": nr["hostKey"]})

            if action == "chat":  # one chat for every game; each game says who may talk where
                if not player:
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                try:
                    media.chat_post(GAMES.get(room.get("game")), room, b.get("pid"), b)
                except media.Refuse as e:
                    return self.err(str(e), e.status)
                changed(room, persist=False)
                return self.send_json({"ok": True})

            if action == "prank":  # throwables for fun; they never change the game
                if not player:
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                try:
                    media.prank_post(GAMES.get(room.get("game")), room, b.get("pid"), b)
                except media.Refuse as e:
                    return self.err(str(e), e.status)
                changed(room, persist=False)
                return self.send_json({"ok": True})

            if action in ("photo", "avatar"):
                if not player:
                    return self.err("You're not in this room. Rejoin with your name.", 403)
                if action == "avatar":
                    url = str(b.get("url") or "")
                    if not url.startswith(AVATAR_HOST):
                        return self.err("Pick one of the characters.")
                    media.IMAGES.pop(player.get("photo"), None)
                    player.update(avatar=url[:300], photo=None, avatarAuto=False)
                else:
                    img = str(b.get("img") or "")
                    if not img.startswith("data:image/jpeg;base64,"):
                        return self.err("That picture didn't upload. Try another one.")
                    try:
                        raw = base64.b64decode(img.split(",", 1)[1])
                    except (ValueError, TypeError):
                        return self.err("That picture didn't upload. Try another one.")
                    if len(raw) > 400_000:
                        return self.err("That picture is too big.")
                    media.IMAGES.pop(player.get("photo"), None)
                    pic = rid(12)
                    media.IMAGES[pic] = raw
                    player.update(photo=pic, avatar=None, avatarAuto=False)
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
                if room.get("phase") == "lobby":
                    return self.err("The ranking hasn't started yet.", 409)
                if room.get("phase") != "ranking" or (room.get("deadline") and time.time() > room["deadline"] + 2):
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
                if "paused" in b:
                    room["show"]["paused"] = bool(b["paused"])
                    room["show"]["at"] = time.time()  # the slide gets its full time again after a pause
                if "to" in b:
                    set_slide(room, int(b.get("to") or 0))
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
                if room.get("phase") not in ("submit", "lobby"):
                    return self.err("The ranking already started.")
                if not room["anime"]:
                    return self.err("Nobody has submitted a pick yet." if room.get("phase") == "submit" else "The list is empty.")
                if "timerSec" in b:
                    room["timerSec"] = max(30, min(1800, int(b["timerSec"])))
                start_ranking(room)
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
    "/theme.js": ("text/javascript; charset=utf-8", "no-store"),
    "/chat.js": ("text/javascript; charset=utf-8", "no-store"),
    "/pranks.js": ("text/javascript; charset=utf-8", "no-store"),
    "/roombar.js": ("text/javascript; charset=utf-8", "no-store"),
    "/howto.js": ("text/javascript; charset=utf-8", "no-store"),
    "/juice.js": ("text/javascript; charset=utf-8", "no-store"),
    "/festival.css": ("text/css; charset=utf-8", "no-store"),
    "/manifest.webmanifest": ("application/manifest+json", "public, max-age=3600"),
    "/icon-192.png": ("image/png", "public, max-age=86400"),
    "/icon-512.png": ("image/png", "public, max-age=86400"),
}
IMG_DIRS = {"roles", "scenes"}
PAGES = {
    "/": "hub.html", "/index.html": "hub.html",
    "/tierlist": "tierlist.html", "/draw": "draw.html",
    "/forged": "forged.html", "/scroll": "scroll.html",
    "/silhouette": "silhouette.html", "/dial": "dial.html",
    "/clash": "clash.html", "/bluff": "bluff.html", "/mask": "mask.html", "/op": "op.html",
    "/werewolf": "werewolf.html", "/imposter": "imposter.html",
    "/codenames": "codenames.html", "/lantern": "lantern.html",
}


def main():
    load()
    for game in GAMES.values():
        game.setup(rooms, lock, changed, rid)
    codenames_game.gallery = avatar_gallery  # anime characters for the picture cards
    silhouette_game.gallery = avatar_gallery
    mask_game.gallery = avatar_gallery
    mask_game.anime_gallery = anime_gallery
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
    threading.Thread(target=avatar_gallery, daemon=True).start()  # warm the character list for random avatars
    threading.Thread(target=lookup_worker, daemon=True).start()
    threading.Thread(target=ticker, daemon=True).start()
    srv = QuietServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Anime Tier Night running on http://localhost:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()

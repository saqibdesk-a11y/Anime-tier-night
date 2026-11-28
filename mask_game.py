"""Forehead Mask: Headbands / "Who Am I?" for Discord voice calls and chat.

Multiple versions built in:
  - Which Character Am I? (AniList characters with portraits + genre filters)
  - Which Anime Am I? (AniList anime series with full cover posters + genre filters)
  - Movies & Games, Animals/Objects, or Custom AI Topics
  - Friends Pick mode (write a secret identity for the player next to you)

Includes a Mystery Scope badge on your hidden card, progressive unlockable hints (Genre/Era,
Word pattern & starting letter, Big Clue), and a live Friend Nudge (1-word hint) + Clue Log!"""
import difflib
import random
import re
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None
gallery = None        # server.py sets this to avatar_gallery (characters)
anime_gallery = None  # server.py sets this to anime_gallery (anime series)

HOST_ACTIONS = ("start", "settings", "next", "skip", "award", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 2, 10
ANSWER_SEC = 15

GENRES = [
    "Action", "Adventure", "Comedy", "Drama", "Fantasy",
    "Romance", "Sci-Fi", "Mystery", "Thriller", "Slice of Life",
    "Sports", "Horror", "Supernatural",
]

FALLBACK_ANIME = [
    {"name": "Attack on Titan", "alias": "Shingeki no Kyojin", "genres": ["Action", "Drama", "Fantasy"], "year": 2013, "format": "TV", "episodes": 89},
    {"name": "Death Note", "genres": ["Mystery", "Thriller", "Supernatural"], "year": 2006, "format": "TV", "episodes": 37},
    {"name": "One Piece", "genres": ["Action", "Adventure", "Comedy", "Fantasy"], "year": 1999, "format": "TV", "episodes": 1100},
    {"name": "Naruto", "genres": ["Action", "Adventure", "Fantasy"], "year": 2002, "format": "TV", "episodes": 220},
    {"name": "Jujutsu Kaisen", "genres": ["Action", "Supernatural", "Fantasy"], "year": 2020, "format": "TV", "episodes": 47},
    {"name": "Demon Slayer", "alias": "Kimetsu no Yaiba", "genres": ["Action", "Fantasy", "Supernatural"], "year": 2019, "format": "TV", "episodes": 55},
    {"name": "Fullmetal Alchemist: Brotherhood", "alias": "FMAB", "genres": ["Action", "Adventure", "Drama", "Fantasy"], "year": 2009, "format": "TV", "episodes": 64},
    {"name": "Hunter x Hunter", "genres": ["Action", "Adventure", "Fantasy"], "year": 2011, "format": "TV", "episodes": 148},
    {"name": "Steins;Gate", "genres": ["Sci-Fi", "Thriller", "Drama"], "year": 2011, "format": "TV", "episodes": 24},
    {"name": "Spy x Family", "genres": ["Action", "Comedy", "Slice of Life"], "year": 2022, "format": "TV", "episodes": 37},
    {"name": "Chainsaw Man", "genres": ["Action", "Horror", "Supernatural"], "year": 2022, "format": "TV", "episodes": 12},
    {"name": "My Hero Academia", "alias": "Boku no Hero Academia", "genres": ["Action", "Adventure", "Comedy"], "year": 2016, "format": "TV", "episodes": 159},
    {"name": "One Punch Man", "genres": ["Action", "Comedy", "Sci-Fi"], "year": 2015, "format": "TV", "episodes": 24},
    {"name": "Dragon Ball Z", "alias": "DBZ", "genres": ["Action", "Adventure", "Fantasy"], "year": 1989, "format": "TV", "episodes": 291},
    {"name": "Bleach", "genres": ["Action", "Adventure", "Supernatural"], "year": 2004, "format": "TV", "episodes": 366},
    {"name": "Tokyo Ghoul", "genres": ["Action", "Horror", "Drama", "Supernatural"], "year": 2014, "format": "TV", "episodes": 48},
    {"name": "Code Geass", "genres": ["Action", "Drama", "Sci-Fi", "Thriller"], "year": 2006, "format": "TV", "episodes": 50},
    {"name": "Vinland Saga", "genres": ["Action", "Adventure", "Drama"], "year": 2019, "format": "TV", "episodes": 48},
    {"name": "Mob Psycho 100", "genres": ["Action", "Comedy", "Supernatural", "Slice of Life"], "year": 2016, "format": "TV", "episodes": 37},
    {"name": "Frieren: Beyond Journey's End", "alias": "Sousou no Frieren", "genres": ["Adventure", "Drama", "Fantasy"], "year": 2023, "format": "TV", "episodes": 28},
    {"name": "Solo Leveling", "genres": ["Action", "Adventure", "Fantasy"], "year": 2024, "format": "TV", "episodes": 25},
    {"name": "Haikyuu!!", "genres": ["Sports", "Comedy", "Drama"], "year": 2014, "format": "TV", "episodes": 85},
    {"name": "Blue Lock", "genres": ["Sports", "Drama", "Thriller"], "year": 2022, "format": "TV", "episodes": 38},
    {"name": "Kaguya-sama: Love is War", "genres": ["Comedy", "Romance", "Slice of Life"], "year": 2019, "format": "TV", "episodes": 37},
    {"name": "Your Name", "alias": "Kimi no Na wa", "genres": ["Romance", "Drama", "Supernatural"], "year": 2016, "format": "MOVIE", "episodes": 1},
    {"name": "Spirited Away", "alias": "Sen to Chihiro", "genres": ["Adventure", "Fantasy", "Supernatural"], "year": 2001, "format": "MOVIE", "episodes": 1},
    {"name": "Horimiya", "genres": ["Romance", "Comedy", "Slice of Life"], "year": 2021, "format": "TV", "episodes": 26},
    {"name": "Fruits Basket", "genres": ["Romance", "Drama", "Fantasy", "Slice of Life"], "year": 2019, "format": "TV", "episodes": 63},
    {"name": "Bocchi the Rock!", "genres": ["Comedy", "Slice of Life"], "year": 2022, "format": "TV", "episodes": 12},
    {"name": "Gintama", "genres": ["Action", "Comedy", "Sci-Fi"], "year": 2006, "format": "TV", "episodes": 367},
    {"name": "Cyberpunk: Edgerunners", "genres": ["Action", "Sci-Fi", "Drama"], "year": 2022, "format": "ONA", "episodes": 10},
    {"name": "Cowboy Bebop", "genres": ["Action", "Adventure", "Sci-Fi", "Drama"], "year": 1998, "format": "TV", "episodes": 26},
    {"name": "Neon Genesis Evangelion", "alias": "Evangelion", "genres": ["Action", "Drama", "Sci-Fi", "Thriller"], "year": 1995, "format": "TV", "episodes": 26},
    {"name": "Re:Zero", "genres": ["Drama", "Fantasy", "Thriller"], "year": 2016, "format": "TV", "episodes": 50},
    {"name": "Sword Art Online", "alias": "SAO", "genres": ["Action", "Adventure", "Fantasy", "Romance"], "year": 2012, "format": "TV", "episodes": 96},
    {"name": "Kuroko's Basketball", "alias": "Kuroko no Basket", "genres": ["Sports", "Comedy"], "year": 2012, "format": "TV", "episodes": 75},
    {"name": "Monster", "genres": ["Drama", "Mystery", "Thriller"], "year": 2004, "format": "TV", "episodes": 74},
    {"name": "Erased", "alias": "Boku dake ga Inai Machi", "genres": ["Mystery", "Thriller", "Supernatural"], "year": 2016, "format": "TV", "episodes": 12},
    {"name": "Another", "genres": ["Horror", "Mystery", "Thriller"], "year": 2012, "format": "TV", "episodes": 12},
    {"name": "Parasyte", "alias": "Kiseijuu", "genres": ["Action", "Horror", "Sci-Fi", "Drama"], "year": 2014, "format": "TV", "episodes": 24},
    {"name": "Violet Evergarden", "genres": ["Drama", "Fantasy", "Slice of Life"], "year": 2018, "format": "TV", "episodes": 13},
    {"name": "A Silent Voice", "alias": "Koe no Katachi", "genres": ["Drama", "Romance"], "year": 2016, "format": "MOVIE", "episodes": 1},
    {"name": "Oshi no Ko", "genres": ["Drama", "Mystery", "Supernatural"], "year": 2023, "format": "TV", "episodes": 24},
    {"name": "JoJo's Bizarre Adventure", "alias": "JoJo", "genres": ["Action", "Adventure", "Supernatural"], "year": 2012, "format": "TV", "episodes": 190},
]

FALLBACK = {
    "characters": [
        {"name": "Naruto Uzumaki", "show": "Naruto", "genres": ["Action", "Adventure", "Fantasy"], "year": 2002},
        {"name": "Monkey D. Luffy", "show": "One Piece", "genres": ["Action", "Adventure", "Comedy"], "year": 1999},
        {"name": "Son Goku", "show": "Dragon Ball Z", "genres": ["Action", "Adventure", "Fantasy"], "year": 1989},
        {"name": "Satoru Gojo", "show": "Jujutsu Kaisen", "genres": ["Action", "Supernatural"], "year": 2020},
        {"name": "Levi Ackerman", "show": "Attack on Titan", "genres": ["Action", "Drama", "Fantasy"], "year": 2013},
        {"name": "Light Yagami", "show": "Death Note", "genres": ["Mystery", "Thriller", "Supernatural"], "year": 2006},
        {"name": "Tanjiro Kamado", "show": "Demon Slayer", "genres": ["Action", "Fantasy", "Supernatural"], "year": 2019},
        {"name": "Anya Forger", "show": "Spy x Family", "genres": ["Action", "Comedy", "Slice of Life"], "year": 2022},
        {"name": "Saitama", "show": "One Punch Man", "genres": ["Action", "Comedy", "Sci-Fi"], "year": 2015},
        {"name": "Roronoa Zoro", "show": "One Piece", "genres": ["Action", "Adventure", "Comedy"], "year": 1999},
        {"name": "Killua Zoldyck", "show": "Hunter x Hunter", "genres": ["Action", "Adventure", "Fantasy"], "year": 2011},
        {"name": "Lelouch Lamperouge", "show": "Code Geass", "genres": ["Action", "Sci-Fi", "Thriller"], "year": 2006},
        {"name": "Shoyo Hinata", "show": "Haikyuu!!", "genres": ["Sports", "Comedy", "Drama"], "year": 2014},
        {"name": "Kaguya Shinomiya", "show": "Kaguya-sama: Love is War", "genres": ["Comedy", "Romance"], "year": 2019},
    ],
    "movies": [
        {"name": "Batman", "show": "DC Comics", "genres": ["Action", "Crime"]},
        {"name": "Spider-Man", "show": "Marvel", "genres": ["Action", "Sci-Fi"]},
        {"name": "Darth Vader", "show": "Star Wars", "genres": ["Sci-Fi", "Adventure"]},
        {"name": "Shrek", "show": "DreamWorks", "genres": ["Comedy", "Fantasy"]},
        {"name": "Harry Potter", "show": "Wizarding World", "genres": ["Fantasy", "Adventure"]},
        {"name": "Iron Man", "show": "Marvel", "genres": ["Action", "Sci-Fi"]},
        {"name": "SpongeBob", "show": "Nickelodeon", "genres": ["Comedy", "Cartoon"]},
        {"name": "Elsa", "show": "Frozen", "genres": ["Fantasy", "Musical"]},
        {"name": "Jack Sparrow", "show": "Pirates of the Caribbean", "genres": ["Adventure", "Comedy"]},
        {"name": "Gandalf", "show": "Lord of the Rings", "genres": ["Fantasy", "Adventure"]},
        {"name": "Mario", "show": "Nintendo", "genres": ["Video Game", "Adventure"]},
        {"name": "Godzilla", "show": "Kaiju", "genres": ["Action", "Sci-Fi"]},
    ],
    "things": [
        {"name": "Penguin", "show": "Animal"}, {"name": "Octopus", "show": "Animal"},
        {"name": "Capybara", "show": "Animal"}, {"name": "Shark", "show": "Animal"},
        {"name": "Panda", "show": "Animal"}, {"name": "Red Fox", "show": "Animal"},
        {"name": "Toaster", "show": "Kitchen Appliance"}, {"name": "Umbrella", "show": "Everyday Object"},
        {"name": "Lightsaber", "show": "Sci-Fi Prop"}, {"name": "Guitar", "show": "Instrument"},
        {"name": "Bubble Tea", "show": "Drink"}, {"name": "Ramen Bowl", "show": "Food"},
        {"name": "Headphones", "show": "Tech"}, {"name": "Skateboard", "show": "Gear"},
    ],
}
FALLBACK["anime"] = FALLBACK["characters"]  # backwards-compatible alias
FALLBACK["animals"] = FALLBACK["things"][:6]
FALLBACK["objects"] = FALLBACK["things"][6:]
FALLBACK["mix"] = FALLBACK["characters"] + FALLBACK["movies"] + FALLBACK["things"]


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    # Support both new "mode" and legacy "category" names cleanly
    raw_mode = b.get("mode", None)
    if raw_mode is None and "category" in b:
        legacy = b.get("category")
        raw_mode = {"anime": "characters", "animals": "things", "objects": "things"}.get(legacy, legacy)
    if raw_mode is None:
        raw_mode = old.get("mode", "characters")
    if raw_mode not in ("characters", "anime_title", "movies", "things", "mix", "custom"):
        raw_mode = "characters"
    raw_genres = pick("genres", [])
    if isinstance(raw_genres, str):
        raw_genres = [raw_genres] if raw_genres else []
    genres = [g for g in (raw_genres or []) if g in GENRES][:4]
    assign = "friends" if pick("assign", "auto") == "friends" else "auto"
    hints = pick("hints", "helpful")
    if hints not in ("off", "subtle", "helpful"):
        hints = "helpful"
    turn_sec = int(pick("turnSec", 30))
    if turn_sec not in (0, 20, 30, 45, 60):
        turn_sec = max(0, min(90, turn_sec))
    return {
        "mode": raw_mode,
        "category": raw_mode,  # kept for compatibility
        "genres": genres,
        "custom": str(pick("custom", "")).strip()[:160],
        "assign": assign,
        "hints": hints,
        "turnSec": turn_sec,
        "rounds": max(1, min(5, int(pick("rounds", 2)))),
    }


def create(room, b):
    room.update({
        "game": "mask", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "round": -1, "scores": {}, "g": None,
    })


def on_join(room, pid):
    room["scores"].setdefault(pid, 0)
    room["players"][pid]["sitout"] = room["phase"] != "lobby"


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def norm(s):
    w = re.sub(r"[^a-z0-9]", "", str(s or "").lower())
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def clean_card_name(nm):
    return re.sub(r"\s*\([^)]*\)$", "", str(nm or "")).strip()


def matches_card(guess, card):
    g = norm(guess)
    if len(g) < 2:
        return False
    cands = [card["name"], clean_card_name(card["name"]), card.get("alias", "")] + list(card.get("synonyms") or [])
    for c in list(cands):
        parts = [p for p in re.split(r"[\s:;\-/]+", str(c or "")) if len(p) >= 4]
        cands.extend(parts)
    for c in cands:
        nc = norm(c)
        if not nc:
            continue
        if g == nc:
            return True
        if len(nc) >= 4 and (nc in g or g in nc) and abs(len(g) - len(nc)) <= 3:
            return True
        # Forgive common misspellings / romanization differences (e.g. Shenron vs Shen Long, Gojou vs Gojo)
        if len(nc) >= 5 and len(g) >= 4 and difflib.SequenceMatcher(None, g, nc).ratio() >= 0.78:
            return True
    return False


def era_label(year):
    if not year:
        return ""
    if year < 1990:
        return "Classic (pre-1990)"
    if year < 2000:
        return "1990s Classic"
    if year < 2010:
        return "2000s"
    if year < 2020:
        return "2010s"
    return "2020s Modern"


def word_pattern(nm):
    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in clean_card_name(nm).split()]
    words = [w for w in words if w]
    if not words:
        return ""
    first = words[0][0].upper()
    if len(words) == 1:
        return f"Starts with '{first}' · 1 word ({len(words[0])} letters)"
    lens = ", ".join(str(len(w)) for w in words[:4])
    return f"Starts with '{first}' · {len(words)} words ({lens} letters)"


def card_hints(card, settings):
    """Builds 3 progressive hints (never directly giving away the exact name)."""
    kind = card.get("kind") or settings.get("mode") or "characters"
    gs = card.get("genres") or []
    era = era_label(card.get("year"))
    h1_parts = []
    if gs:
        h1_parts.append("Genres: " + ", ".join(gs[:3]))
    if era:
        h1_parts.append(era)
    if not h1_parts and card.get("show"):
        h1_parts.append(f"Category: {card['show']}")
    h1 = " · ".join(h1_parts) if h1_parts else "Pop-culture icon"

    h2 = word_pattern(card["name"]) or "Think of a well-known name"

    if kind == "characters" and card.get("show"):
        h3 = f"From the anime: {card['show']}"
    elif kind == "anime_title":
        bits = []
        if card.get("year"):
            bits.append(f"Released {card['year']}")
        if card.get("format"):
            bits.append(card["format"])
        if card.get("episodes"):
            bits.append(f"~{card['episodes']} ep{'s' if card['episodes'] != 1 else ''}")
        h3 = " · ".join(bits) if bits else f"Ends with '{card['name'][-1].upper()}'"
    elif card.get("show"):
        h3 = f"World / Series: {card['show']}"
    else:
        clean = clean_card_name(card["name"])
        h3 = f"Ends with '{clean[-1].upper()}'" if clean else "Ask your friends for a 1-word nudge!"

    return [h1, h2, h3]


def scope_label(settings):
    mode = settings.get("mode", "characters")
    gs = settings.get("genres") or []
    gtxt = (" · " + " / ".join(gs[:2])) if gs else ""
    if settings.get("assign") == "friends":
        return "Friends Pick · Anything Goes"
    return {
        "characters": f"Which Character Am I?{gtxt}",
        "anime_title": f"Which Anime Am I?{gtxt}",
        "movies": "Movies, Games & Pop Culture",
        "things": "Animals, Food & Objects",
        "mix": "Party Mix · Characters & Things",
        "custom": f"Custom: {settings.get('custom') or 'AI Topic'}",
    }.get(mode, "Who Am I?")


def filter_by_genres(items, genres):
    if not genres:
        return items
    gset = {g.lower() for g in genres}
    matched = [x for x in items if any(g.lower() in gset for g in (x.get("genres") or []))]
    return matched if len(matched) >= 2 else items


def build_cards(settings, n):
    mode = settings["mode"]
    genres = settings.get("genres") or []

    if mode == "anime_title":
        live = [a for a in (anime_gallery() if anime_gallery else []) if a.get("img")]
        pool = filter_by_genres(live, genres) if len(live) >= n else []
        if len(pool) < n:
            fb = filter_by_genres(FALLBACK_ANIME, genres)
            pool = fb if len(fb) >= n else FALLBACK_ANIME[:]
        chosen = random.sample(pool, min(n, len(pool)))
        return [{
            "name": clean_card_name(a["name"]),
            "alias": a.get("alias", ""),
            "synonyms": a.get("synonyms") or [],
            "show": " · ".join((a.get("genres") or [])[:2]) + (f" ({a['year']})" if a.get("year") else ""),
            "genres": a.get("genres") or [],
            "year": a.get("year"),
            "format": a.get("format", "TV"),
            "episodes": a.get("episodes"),
            "img": a.get("img"),
            "kind": "anime_title",
        } for a in chosen]

    if mode == "characters":
        chars = [c for c in (gallery() if gallery else []) if c.get("img")]
        pool = filter_by_genres(chars, genres) if len(chars) >= n else []
        if len(pool) >= n:
            return [{
                "name": clean_card_name(c["name"]),
                "show": c.get("show", ""),
                "genres": c.get("genres") or [],
                "year": c.get("year"),
                "img": c["img"],
                "alias": c.get("alias", ""),
                "kind": "characters",
            } for c in random.sample(pool, n)]
        fb = filter_by_genres(FALLBACK["characters"], genres)
        if len(fb) < n:
            fb = FALLBACK["characters"][:]
        return [{**x, "img": None, "kind": "characters"} for x in random.sample(fb, min(n, len(fb)))]

    if mode == "custom" and settings["custom"]:
        try:
            res, _, _ = ai.ask_builtin(
                "You pick well-known secret identities for the party game Headbands / Who Am I.",
                f"Pick {n + 4} famous, easily guessable names/things about: {settings['custom']}. "
                'Return only JSON: {"items":[{"name":"...","show":"short category","genres":["vibe1","vibe2"]}]}',
                timeout=25, text_first=True)
            out = [{
                "name": str(x.get("name") or "").strip()[:44],
                "show": str(x.get("show") or "").strip()[:36],
                "genres": [str(g)[:20] for g in (x.get("genres") or [])][:3],
                "img": None, "kind": "custom",
            } for x in (res.get("items") or []) if isinstance(x, dict) and str(x.get("name") or "").strip()]
            if len(out) >= n:
                random.shuffle(out)
                return out[:n]
        except (ai.AIError, ValueError, TypeError, AttributeError):
            pass

    pool = FALLBACK.get(mode, FALLBACK["mix"])[:]
    random.shuffle(pool)
    return [{**x, "img": None, "kind": mode} for x in pool[:n]]


def begin_round_thread(code, rnd):
    with lock:
        room = rooms.get(code)
        if not room:
            return
        settings = dict(room["settings"])
        pids = [pid for pid, p in room["players"].items() if not p.get("wantSitout")][:MAX_PLAYERS]
        if len(pids) < MIN_PLAYERS:
            pids = list(room["players"])[:MAX_PLAYERS]
    cards = build_cards(settings, len(pids))
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            setup_round(room, rnd, pids, cards)
            changed(room)


def set_turn_timer(room):
    g = room.get("g")
    if not g or room["phase"] != "play":
        return
    sec = room["settings"].get("turnSec", 30)
    if g.get("turnStage") == "answer":
        room["deadline"] = (time.time() + ANSWER_SEC + 1) if sec else None
    else:
        room["deadline"] = (time.time() + sec + 1) if sec else None


def setup_round(room, rnd, pids, cards):
    pids = [p for p in pids if p in room["players"]]
    if len(pids) < MIN_PLAYERS:
        room["phase"] = "lobby"
        return
    random.shuffle(pids)
    for pid in room["players"]:
        room["players"][pid]["sitout"] = pid not in pids
    room["round"] = rnd
    room["g"] = {
        "order": pids,
        "cards": {pid: cards[i % len(cards)] for i, pid in enumerate(pids)} if room["settings"]["assign"] == "auto" else {},
        "assignedBy": {},
        "solved": [],
        "turn": 0,
        "turnStage": "choose",  # "choose" (ask 1 question OR guess) -> "answer" (others vote Yes/No/Kinda)
        "question": None,
        "logs": {pid: [] for pid in pids},
        "hintsUsed": {pid: 0 for pid in pids},
        "nudges": {pid: [] for pid in pids},
        "wrongGuesses": [],
    }
    if room["settings"]["assign"] == "friends":
        room["phase"] = "assign"
        room["deadline"] = time.time() + 45
    else:
        room["phase"] = "play"
        set_turn_timer(room)


def unsolved(room):
    g = room["g"]
    return [pid for pid in g["order"] if pid in room["players"] and pid not in g["solved"]]


def current_pid(room):
    g = room["g"]
    rem = unsolved(room)
    if not rem:
        return None
    return g["order"][g["turn"] % len(g["order"])] if g["order"][g["turn"] % len(g["order"])] in rem else rem[0]


def award_player(room, pid, by_host=False):
    g = room["g"]
    if pid in g["solved"] or pid not in g["order"]:
        return False
    g["solved"].append(pid)
    rank = len(g["solved"])
    base_pts = {1: 5, 2: 3, 3: 2}.get(rank, 1)
    used = g["hintsUsed"].get(pid, 0)
    pts = max(1, base_pts - (1 if used >= 2 else 0))
    room["scores"][pid] = room["scores"].get(pid, 0) + pts
    # Clear any pending wrong-guess banner for this player once awarded
    g["wrongGuesses"] = [w for w in g["wrongGuesses"] if w["pid"] != pid]
    if room["phase"] == "play":
        rem = unsolved(room)
        if not rem or (len(rem) == 1 and len(g["order"]) >= 3 and len(g["solved"]) >= len(g["order"]) - 1):
            q = g.get("question")
            if q:
                g["logs"].setdefault(q["pid"], []).append(q)
                g["question"] = None
            room["phase"] = "roundover"
            room["deadline"] = None
        elif current_pid(room) == pid or (g.get("question") and g["question"]["pid"] == pid):
            advance_turn(room)
    return True


def advance_turn(room):
    g = room["g"]
    q = g.get("question")
    if q:
        g["logs"].setdefault(q["pid"], []).append(q)
        g["question"] = None
    g["turnStage"] = "choose"
    rem = unsolved(room)
    if not rem or (len(rem) == 1 and len(g["order"]) >= 3 and len(g["solved"]) >= len(g["order"]) - 1):
        room["phase"] = "roundover"
        room["deadline"] = None
        return
    for step in range(1, len(g["order"]) + 1):
        idx = (g["turn"] + step) % len(g["order"])
        if g["order"][idx] in rem:
            g["turn"] = idx
            break
    set_turn_timer(room)


def finish_assign(room):
    g = room["g"]
    order = g["order"]
    backup = FALLBACK.get(room["settings"]["mode"], FALLBACK["mix"])[:]
    random.shuffle(backup)
    for i, target in enumerate(order):
        if target not in g["cards"]:
            g["cards"][target] = {**backup[i % len(backup)], "img": None, "kind": "friends"}
    room["phase"] = "play"
    g["turnStage"] = "choose"
    set_turn_timer(room)


def tick(room):
    g = room.get("g")
    if not g:
        return False
    over = room.get("deadline") and time.time() >= room["deadline"]
    if room["phase"] == "assign":
        if over or all(pid in g["cards"] for pid in g["order"]):
            finish_assign(room)
            return True
    elif room["phase"] == "play" and over:
        advance_turn(room)
        return True
    return False


def chat_rules(room, pid):
    g = room.get("g")
    if room["phase"] == "play" and g:
        block = [c["name"] for p, c in g["cards"].items() if p not in g["solved"] and c.get("name")]
        return {"read": ["all"], "write": ["all"], "block": block}
    return {"read": ["all"], "write": ["all"]}


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "g")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["scope"] = scope_label(room["settings"])
    r["allGenres"] = GENRES
    g = room.get("g")
    if g:
        reveal_all = room["phase"] in ("roundover", "final")
        cards_out = {}
        my_hints = []
        max_hints = 0 if room["settings"]["hints"] == "off" else 1 if room["settings"]["hints"] == "subtle" else 3
        for pid, c in g["cards"].items():
            if reveal_all or pid != viewer or pid in g["solved"]:
                cards_out[pid] = c
            else:
                used = g["hintsUsed"].get(pid, 0)
                all_h = card_hints(c, room["settings"])
                my_hints = all_h[:min(used, max_hints)]
                cards_out[pid] = {
                    "hidden": True,
                    "kind": c.get("kind") or room["settings"]["mode"],
                    "hintsUsed": used,
                    "maxHints": max_hints,
                }
        voters_need = len([p for p in g["order"] if p in room["players"] and g.get("question") and p != g["question"]["pid"]]) if g.get("question") else 0
        out = {
            "order": g["order"],
            "cards": cards_out,
            "solved": g["solved"],
            "turnPid": current_pid(room) if room["phase"] == "play" else None,
            "turnStage": g.get("turnStage", "choose"),
            "question": g["question"],
            "votersNeed": voters_need,
            "myLog": g["logs"].get(viewer, []),
            "myHints": my_hints,
            "myNudges": g["nudges"].get(viewer, [])[-6:],
            "wrongGuesses": g["wrongGuesses"][-6:],
        }
        if room["phase"] == "assign" and viewer in g["order"]:
            idx = g["order"].index(viewer)
            target = g["order"][(idx + 1) % len(g["order"])]
            out["assignTarget"] = target
            out["assignedDone"] = target in g["cards"]
            out["assignedCount"] = len(g["cards"])
        r["table"] = out
    return r


def player_action(room, action, b, pid):
    g, ph = room.get("g"), room["phase"]
    if not g or pid not in g["order"]:
        raise Refuse("You're watching this round—you'll get a mask next round!", 409)
    if action == "assign":
        if ph != "assign":
            raise Refuse("Masks are already handed out.", 409)
        idx = g["order"].index(pid)
        target = g["order"][(idx + 1) % len(g["order"])]
        text = " ".join(str(b.get("name") or "").split())[:44]
        if not text:
            raise Refuse("Type an identity for them!")
        vibe = " ".join(str(b.get("show") or "").split())[:32]
        g["cards"][target] = {"name": text, "show": vibe or ("Picked by " + name(room, pid)), "img": None, "kind": "friends"}
        g["assignedBy"][target] = pid
        if all(p in g["cards"] for p in g["order"]):
            finish_assign(room)
        return True
    if ph != "play":
        raise Refuse("Not in play right now.", 409)
    cur = current_pid(room)
    if action == "hint":
        if pid in g["solved"]:
            raise Refuse("You already unmasked yourself!", 409)
        max_h = 0 if room["settings"]["hints"] == "off" else 1 if room["settings"]["hints"] == "subtle" else 3
        used = g["hintsUsed"].get(pid, 0)
        if used >= max_h:
            raise Refuse("No more hints available for this round.", 409)
        g["hintsUsed"][pid] = used + 1
        return True
    if action == "nudge":
        target = b.get("target") or cur
        if not target or target not in g["order"] or target == pid:
            raise Refuse("Pick another player to nudge.", 409)
        text = " ".join(str(b.get("text") or "").split())[:36]
        if not text:
            raise Refuse("Type a short hint first!")
        card = g["cards"].get(target)
        if card and matches_card(text, card):
            raise Refuse("Whoa—that gives away the exact answer! Keep it subtle.", 409)
        g["nudges"].setdefault(target, []).append({"id": rid(6), "by": name(room, pid), "text": text})
        return True
    if action == "ask":
        if pid != cur:
            raise Refuse("Wait for your turn to ask.", 409)
        if g.get("turnStage") != "choose":
            raise Refuse("One question per turn! Wait for answers or end your turn.", 409)
        voice = bool(b.get("voice"))
        text = " ".join(str(b.get("text") or "").split())[:120]
        if not text:
            text = "Asked out loud on Discord voice" if voice else ""
        if not text:
            raise Refuse("Type a question or tap Asked on Voice.")
        g["question"] = {"id": rid(6), "pid": pid, "text": text, "voice": voice, "votes": {}}
        g["turnStage"] = "answer"
        set_turn_timer(room)
        return True
    if action == "reply":
        q = g.get("question")
        if not q or g.get("turnStage") != "answer":
            raise Refuse("No active question right now.", 409)
        if pid == q["pid"]:
            raise Refuse("Let the others answer your question!", 409)
        ans = str(b.get("ans") or "")
        if ans not in ("yes", "no", "kinda"):
            raise Refuse("Pick Yes, No, or Kinda.")
        q["votes"][pid] = ans
        # Once everyone else has answered, lock into the asker's Clue Log & advance to next player!
        others = [p for p in g["order"] if p in room["players"] and p != q["pid"]]
        if others and all(p in q["votes"] for p in others):
            advance_turn(room)
        return True
    if action == "endturn":
        if pid != cur:
            raise Refuse("Wait for your turn.", 409)
        advance_turn(room)
        return True
    if action == "guess":
        if pid != cur:
            raise Refuse("Wait for your turn to guess.", 409)
        if g.get("turnStage") != "choose":
            raise Refuse("Finish your current question before guessing next turn.", 409)
        text = " ".join(str(b.get("text") or "").split())[:50]
        if not text:
            raise Refuse("Type your guess first!")
        card = g["cards"][pid]
        if matches_card(text, card):
            award_player(room, pid)
        else:
            g["wrongGuesses"].append({"id": rid(6), "pid": pid, "text": text})
            advance_turn(room)
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the round starts.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action == "start":
        if ph != "lobby":
            raise Refuse("Game already started.")
        if len(room["players"]) < MIN_PLAYERS:
            raise Refuse(f"You need at least {MIN_PLAYERS} players.")
        room["scores"] = {pid: 0 for pid in room["players"]}
        room["phase"] = "starting"
        threading.Thread(target=begin_round_thread, args=(room["code"], 0), daemon=True).start()
    elif action == "award":
        if ph not in ("play", "roundover") or not room.get("g"):
            raise Refuse("No active round to award.", 409)
        target = b.get("pid")
        if not target or not award_player(room, target, by_host=True):
            raise Refuse("That player is already unmasked or not in this round.", 409)
    elif action in ("next", "skip"):
        if ph == "assign":
            finish_assign(room)
        elif ph == "play":
            if action == "skip":
                advance_turn(room)
            else:
                room["phase"] = "roundover"
        elif ph == "roundover":
            if room["round"] + 1 < room["settings"]["rounds"]:
                room["phase"] = "starting"
                threading.Thread(target=begin_round_thread, args=(room["code"], room["round"] + 1), daemon=True).start()
            else:
                room["phase"] = "final"
        else:
            raise Refuse("Nothing to advance.")
    elif action == "kick":
        pid = b.get("pid")
        room["players"].pop(pid, None)
        g = room.get("g")
        if g and ph == "play" and pid in g["order"]:
            if current_pid(room) == pid:
                advance_turn(room)
    elif action == "playagain":
        for p in room["players"].values():
            p["sitout"] = False
        room.update({"phase": "lobby", "deadline": None, "round": -1, "scores": {pid: 0 for pid in room["players"]}, "g": None})
    return True

"""Forged Brush: a collaborative drawing & deception game (Fake Artist style).

Everyone gets the same secret subject to draw together on one shared canvas—except the Forger.
In "clueless" mode, the Forger sees only the category and must fake it by reading everyone else's
strokes. In "decoy" mode, the Forger gets a closely related decoy subject and doesn't even know
they're the Forger.

Players each get a unique ink colour and take turns adding ONE continuous brushstroke at a time.
After all passes, everyone inspects the painting (isolating individual artists' strokes or
replaying the painting stroke by stroke), debates, and votes on the Forger. If caught, the Forger
gets one last guess at the real subject to steal the round.

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import random
import re
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "next", "skip", "addtime", "kick", "playagain", "settings")
MIN_PLAYERS, MAX_PLAYERS = 3, 10

# 10 vivid, distinct ink colours so every artist's strokes stand apart on white rice paper
INKS = [
    "#E63946",  # crimson
    "#2563EB",  # cobalt
    "#16A34A",  # emerald
    "#D97706",  # amber
    "#9333EA",  # violet
    "#EC4899",  # magenta
    "#0D9488",  # teal
    "#9A3412",  # sienna
    "#4F46E5",  # indigo
    "#1E293B",  # sumi ink
]

CATEGORIES = {
    "mix": ("Mix of everything", "concrete, easily drawable things: anime, food, animals, everyday objects, places and movies"),
    "anime": ("Anime", "iconic anime characters, items and symbols that can be recognized in a simple sketch"),
    "food": ("Food", "distinctive foods, dishes and drinks with recognizable shapes"),
    "animals": ("Animals", "animals with clear silhouettes and features"),
    "objects": ("Everyday objects", "everyday objects with unmistakable shapes"),
    "places": ("Places", "famous landmarks, buildings and places easy to sketch"),
    "movies": ("Movies & TV", "famous movie/TV characters, props and icons easy to sketch"),
}

FALLBACK = {
    "anime": [
        ("Pikachu", "Eevee"), ("Pokeball", "Dragon Ball"), ("Totoro", "Snorlax"),
        ("Naruto", "Goku"), ("Katana", "Kunai"), ("Sharingan", "Rinnegan"),
        ("Straw Hat", "Wizard Hat"), ("Titan", "Gundam"), ("Death Note", "Spellbook"),
        ("Ramen Bowl", "Onigiri"), ("Spirited Away No-Face", "Ghost"), ("Sailor Moon", "Magical Wand"),
    ],
    "food": [
        ("Pizza", "Pie"), ("Ramen", "Spaghetti"), ("Burger", "Sandwich"),
        ("Sushi", "Onigiri"), ("Ice Cream Cone", "Cupcake"), ("Donut", "Bagel"),
        ("Taco", "Burrito"), ("Croissant", "Pretzel"), ("Watermelon", "Pineapple"),
        ("Pancakes", "Waffles"), ("Bubble Tea", "Milkshake"), ("Hot Dog", "Corn Dog"),
    ],
    "animals": [
        ("Cat", "Fox"), ("Shark", "Dolphin"), ("Giraffe", "Camel"),
        ("Penguin", "Owl"), ("Octopus", "Jellyfish"), ("Elephant", "Rhino"),
        ("Butterfly", "Dragonfly"), ("Turtle", "Snail"), ("Lion", "Tiger"),
        ("Flamingo", "Swan"), ("Crocodile", "Dinosaur"), ("Bee", "Spider"),
    ],
    "objects": [
        ("Guitar", "Violin"), ("Umbrella", "Mushroom"), ("Clock", "Compass"),
        ("Lightbulb", "Candle"), ("Glasses", "Binoculars"), ("Bicycle", "Motorcycle"),
        ("Camera", "Television"), ("Scissors", "Pliers"), ("Anchor", "Hook"),
        ("Crown", "Trophy"), ("Backpack", "Suitcase"), ("Key", "Sword"),
    ],
    "places": [
        ("Eiffel Tower", "Lighthouse"), ("Mount Fuji", "Volcano"), ("Pyramids", "Tent"),
        ("Castle", "Haunted House"), ("Torii Gate", "Bridge"), ("Igloo", "Cabin"),
        ("Desert Island", "Oasis"), ("Ferris Wheel", "Windmill"), ("Space Station", "Rocket"),
        ("Statue of Liberty", "Big Ben"),
    ],
    "movies": [
        ("Batman", "Spider-Man"), ("Lightsaber", "Magic Wand"), ("Shrek", "Hulk"),
        ("SpongeBob", "Minion"), ("Darth Vader", "Stormtrooper"), ("Titanic", "Pirate Ship"),
        ("Godzilla", "T-Rex"), ("Iron Man", "Robot"), ("Pacman", "Kirby"),
        ("Mario", "Luigi"),
    ],
}
FALLBACK["mix"] = [pair for k, pairs in FALLBACK.items() for pair in pairs]

SPICE = {
    "wholesome": "Keep it warm, funny and encouraging like a friendly art class.",
    "spicy": "Roast like a sharp, funny art critic in the group chat—joke about suspicious strokes and bad bluffs, with praise where earned.",
    "unhinged": "Go chaotic and dramatic like an unhinged gallery critic roasting a cursed painting. Never attack real-world identity.",
}


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    cat = pick("category", "mix")
    return {
        "mode": "decoy" if pick("mode", "clueless") == "decoy" else "clueless",
        "rounds": max(1, min(8, int(pick("rounds", 3)))),
        "category": cat if cat in CATEGORIES or cat == "custom" else "mix",
        "custom": str(pick("custom", "")).strip()[:200],
        "strokeRounds": max(1, min(3, int(pick("strokeRounds", 2)))),
        "strokeSec": max(10, min(60, int(pick("strokeSec", 20)))),
        "discussSec": max(30, min(240, int(pick("discussSec", 60)))),
        "voteSec": max(20, min(120, int(pick("voteSec", 45)))),
        "forgers": max(0, min(2, int(pick("forgers", 0) or 0))),  # 0 = auto
        "spice": pick("spice", "spicy") if pick("spice", "spicy") in SPICE else "spicy",
    }


def create(room, b):
    room.update({
        "game": "forged", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "pairs": [], "round": -1, "roundData": [], "scores": {},
    })


def on_join(room, pid):
    room["players"][pid].update({"ready": False, "sitout": room["phase"] != "lobby"})
    room["scores"].setdefault(pid, 0)


# ---------- helpers ----------

def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def cur(room):
    return room["roundData"][room["round"]] if 0 <= room["round"] < len(room["roundData"]) else None


def active(room):
    rd = cur(room)
    if rd:
        return [pid for pid in rd["order"] if pid in room["players"]]
    return [pid for pid, p in room["players"].items() if not p.get("sitout")]


def category_label(room):
    s = room["settings"]
    return s["custom"] if s["category"] == "custom" and s["custom"] else CATEGORIES.get(s["category"], CATEGORIES["mix"])[0]


def set_timer(room, secs):
    room["deadline"] = time.time() + secs + 1


def norm(w):
    w = re.sub(r"[^a-z0-9]", "", str(w).lower())
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def guessed(guess, word):
    g, w = norm(guess), norm(word)
    return bool(g) and (g == w or (len(w) > 3 and (w in g or g in w) and abs(len(g) - len(w)) <= 3))


def turns(room):
    rd = cur(room)
    return rd["order"] * room["settings"]["strokeRounds"]


def clean_points(raw):
    """Validates and caps a single brushstroke's polyline so canvas replay stays fast and compact."""
    if not isinstance(raw, list) or not raw:
        return []
    pts = []
    step = max(1, len(raw) // 350)
    for i, item in enumerate(raw):
        if i != 0 and i != len(raw) - 1 and i % step != 0:
            continue
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            x = max(0, min(800, int(round(float(item[0])))))
            y = max(0, min(600, int(round(float(item[1])))))
        except (TypeError, ValueError):
            continue
        if not pts or abs(pts[-1][0] - x) + abs(pts[-1][1] - y) >= 2:
            pts.append([x, y])
    if len(pts) == 1:
        pts.append([pts[0][0], pts[0][1]])  # a single dot still renders cleanly
    return pts[:400]


# ---------- AI ----------

def make_pairs(settings, n):
    s = settings
    about = (f"this, as described by the host: {s['custom']}" if s["category"] == "custom" and s["custom"]
             else CATEGORIES.get(s["category"], CATEGORIES["mix"])[1])
    try:
        out, _, _ = ai.ask_builtin(
            "You make drawable subject pairs for a Fake Artist party drawing game.",
            f"Make {n + 2} pairs of concrete, visually recognizable things about {about} that friends can sketch together "
            "in a few simple strokes. Each pair should be two different things that share similar visual shapes (like Guitar/Violin, "
            "Pikachu/Eevee, Pizza/Pie, Eiffel Tower/Lighthouse) so a decoy sketch blends in at first. 1-3 words each, well known, no repeats. "
            'Return only JSON: {"pairs": [["subject", "similar subject"], ...]}', timeout=25, text_first=True)
        pairs = [(str(a).strip()[:40], str(b).strip()[:40]) for a, b in
                 (p for p in out.get("pairs", []) if isinstance(p, (list, tuple)) and len(p) == 2)
                 if str(a).strip() and str(b).strip()]
    except (ai.AIError, ValueError, TypeError):
        pairs = []
    random.shuffle(pairs)
    backup = FALLBACK.get(s["category"], FALLBACK["mix"])[:]
    random.shuffle(backup)
    used = {norm(a) for a, _ in pairs}
    for a, b in backup:
        if len(pairs) >= n:
            break
        if norm(a) not in used:
            pairs.append((a, b))
            used.add(norm(a))
    while len(pairs) < n:
        pairs.append(backup[len(pairs) % len(backup)])
    return [(a, b) if random.random() < .5 else (b, a) for a, b in pairs[:n]]


def begin_game(code):
    with lock:
        room = rooms.get(code)
        settings = dict(room["settings"]) if room else None
    if not settings:
        return
    pairs = make_pairs(settings, settings["rounds"])
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            room["pairs"] = pairs
            start_round(room, 0)
            changed(room)


def roast_round(code, rnd, cid):
    with lock:
        room = rooms.get(code)
        if not room or rnd >= len(room["roundData"]):
            return
        rd = room["roundData"][rnd]
        forgers = ", ".join(name(room, p) for p in rd["forgers"])
        votes = "; ".join(f"{name(room, v)} voted {name(room, t) if t != 'skip' else 'skip'}" for v, t in rd["votes"].items())
        stroke_info = []
        for pid in rd["order"]:
            mine = [s for s in rd["strokes"] if s["pid"] == pid]
            drawn = sum(1 for s in mine if not s.get("late"))
            missed = sum(1 for s in mine if s.get("late"))
            stroke_info.append(f"{name(room, pid)} ({drawn} stroke{'s' if drawn != 1 else ''}" + (f", {missed} timed out" if missed else "") + ")")
        outcome = ("The forger was caught" if rd["caught"] else "The forger got away") + (
            f" and guessed \"{rd['guess']['text']}\" ({'right' if rd['guess']['correct'] else 'wrong'})" if rd.get("guess") else "")
        names = {p["name"].lower(): p["name"] for p in room["players"].values()}
        system = ("You are the gallery critic hosting Forged Brush, a Fake Artist drawing game for friends. "
                  + SPICE[room["settings"]["spice"]] + " Refer to players by name, never guess anyone's gender (no he/she), "
                  "and stick only to the facts given.")
        prompt = (f"The real subject to draw was \"{rd['word']}\" (category: {category_label(room)}). "
                  f"The forger ({forgers}) "
                  + (f"had the decoy subject \"{rd['decoy']}\" and didn't know they were the forger. " if room["settings"]["mode"] == "decoy"
                     else "had NO word—only the category—and had to improvise strokes. ")
                  + f"Artists: {', '.join(stroke_info)}. Votes: {votes or 'none'}. {outcome}. "
                  + "Write a punchy 2-3 sentence gallery recap, then 1 short funny line for each artist. "
                  'Return only JSON: {"story": "...", "lines": [{"name": "<player name>", "line": "..."}]}')
    try:
        out, _, _ = ai.ask_builtin(system, prompt, timeout=25, text_first=True)
        story = str(out.get("story") or "").strip()[:700]
        lines = [{"name": names[str(l.get("name", "")).lower()], "line": str(l.get("line") or "")[:220]}
                 for l in out.get("lines", []) if isinstance(l, dict) and str(l.get("name", "")).lower() in names]
    except (ai.AIError, ValueError, TypeError, AttributeError):
        story, lines = "", []
    with lock:
        room = rooms.get(code)
        if room and rnd < len(room["roundData"]) and room["roundData"][rnd].get("aiId") == cid:
            rd = room["roundData"][rnd]
            if story:
                rd["ai"] = {"story": story, "lines": lines}
            elif rd["ai"] is None:
                rd["ai"] = {"failed": True}
            changed(room)


def give_up_on_ai(code, rnd, cid):
    with lock:
        room = rooms.get(code)
        if room and rnd < len(room["roundData"]):
            rd = room["roundData"][rnd]
            if rd.get("aiId") == cid and rd["ai"] is None:
                rd["ai"] = {"failed": True}
                changed(room)


# ---------- phases ----------

def start_round(room, rnd):
    pids = [pid for pid, p in room["players"].items() if not p.get("wantSitout")][:MAX_PLAYERS]
    if len(pids) < MIN_PLAYERS:
        pids = list(room["players"])[:MAX_PLAYERS]
    for pid in room["players"]:
        room["players"][pid].update({"sitout": pid not in pids, "ready": False})
    n = len(pids)
    k = room["settings"]["forgers"] or (1 if n < 7 else 2)
    k = max(1, min(k, (n - 1) // 2))
    word, decoy = room["pairs"][rnd]
    order = pids[:]
    random.shuffle(order)
    inks = INKS[:]
    random.shuffle(inks)
    colors = {pid: inks[i % len(inks)] for i, pid in enumerate(order)}
    forgers = random.sample(pids, k)
    room["round"] = rnd
    room["phase"] = "reveal"
    room["deadline"] = None
    room["roundData"].append({
        "word": word, "decoy": decoy, "forgers": forgers, "order": order, "colors": colors,
        "strokes": [], "turn": 0, "votes": {}, "accused": None, "caught": None, "guess": None,
        "ai": None, "aiId": None, "points": {}, "why": {},
    })


def skip_gone(room):
    rd, t = cur(room), turns(room)
    while rd["turn"] < len(t) and t[rd["turn"]] not in room["players"]:
        rd["turn"] += 1


def begin_drawing(room):
    room["phase"] = "drawing"
    cur(room)["turn"] = 0
    skip_gone(room)
    if cur(room)["turn"] >= len(turns(room)):
        begin_discuss(room)
    else:
        set_timer(room, room["settings"]["strokeSec"])


def begin_discuss(room):
    room["phase"] = "discuss"
    set_timer(room, room["settings"]["discussSec"])


def next_turn(room):
    rd = cur(room)
    rd["turn"] += 1
    skip_gone(room)
    if rd["turn"] >= len(turns(room)):
        begin_discuss(room)
    else:
        set_timer(room, room["settings"]["strokeSec"])


def begin_vote(room):
    room["phase"] = "vote"
    set_timer(room, room["settings"]["voteSec"])


def resolve_vote(room):
    rd = cur(room)
    room["deadline"] = None
    tally = {}
    for v, t in rd["votes"].items():
        if v in room["players"]:
            tally[t] = tally.get(t, 0) + 1
    top = max(tally.values()) if tally else 0
    leaders = [t for t, c in tally.items() if c == top]
    accused = leaders[0] if len(leaders) == 1 and leaders[0] != "skip" and top else None
    rd["accused"] = accused
    rd["caught"] = accused in rd["forgers"]
    room["phase"] = "verdict"


def after_verdict(room):
    rd = cur(room)
    if rd["caught"] and rd["guess"] is None:
        room["phase"] = "guess"
        set_timer(room, 30)
    else:
        finish_round(room)


def finish_round(room):
    rd = cur(room)
    room["deadline"] = None
    why = {}

    def add(pid, n, reason):
        why.setdefault(pid, []).append([n, reason])

    forgers, votes, acc = rd["forgers"], rd["votes"], rd["accused"]
    if acc and acc in forgers:
        for v, t in votes.items():
            if t in forgers and v not in forgers:
                add(v, 2, "spotted the forger")
        if rd["guess"] and rd["guess"]["correct"]:
            for f in forgers:
                add(f, 3, "guessed the subject")
    else:
        for f in forgers:
            add(f, 4 if acc else 3, "fooled the gallery" if acc else "slipped away")
        if acc:
            for v, t in votes.items():
                if t == acc and v != acc and v not in forgers:
                    add(v, -1, "framed an innocent artist")
    pts = {}
    for pid, items in why.items():
        items[:] = [x for x in items if x[0]]
        pts[pid] = sum(n for n, _ in items)
        room["scores"][pid] = room["scores"].get(pid, 0) + pts[pid]
    rd["points"], rd["why"] = pts, {p: v for p, v in why.items() if v}
    room["phase"] = "results"
    rd["aiId"] = rid(6)
    threading.Thread(target=roast_round, args=(room["code"], room["round"], rd["aiId"]), daemon=True).start()
    threading.Timer(15, give_up_on_ai, args=(room["code"], room["round"], rd["aiId"])).start()


def tick(room):
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now > room["deadline"]
    if ph == "reveal":
        ps = [room["players"][pid] for pid in active(room)]
        if ps and all(p.get("ready") for p in ps):
            begin_drawing(room)
            return True
    elif ph == "drawing" and over:
        rd = cur(room)
        t = turns(room)
        if rd["turn"] < len(t):
            pid = t[rd["turn"]]
            rd["strokes"].append({
                "id": rid(6), "pid": pid, "c": rd["colors"].get(pid, INKS[0]),
                "w": 0, "p": [], "turn": rd["turn"], "late": True,
            })
        next_turn(room)
        return True
    elif ph == "discuss" and over:
        begin_vote(room)
        return True
    elif ph == "vote" and (over or set(active(room)) <= set(cur(room)["votes"])):
        resolve_vote(room)
        return True
    elif ph == "guess" and over:
        cur(room)["guess"] = {"text": "(no guess)", "correct": False}
        finish_round(room)
        return True
    return False


# ---------- chat ----------

QUIET = {
    "reveal": "Chat opens once the painting is finished. No hints on the side.",
    "drawing": "Keep quiet while everyone paints! Chat opens for discussion.",
    "guess": "The forger is guessing the subject. Chat opens again in a moment.",
}


def chat_rules(room, pid):
    rd = cur(room) if room.get("roundData") else None
    if room["phase"] in QUIET:
        return {"read": ["all"], "write": [], "why": QUIET[room["phase"]]}
    block = []
    if rd and room["phase"] not in ("results", "final") and pid in rd["order"]:
        mine = (None if room["settings"]["mode"] == "clueless" else rd["decoy"]) if pid in rd["forgers"] else rd["word"]
        block = [mine] if mine else []
    return {"read": ["all"], "write": ["all"], "block": block}


# ---------- what each viewer sees ----------

def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "pairs", "roundData")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["categoryLabel"] = category_label(room)
    rounds = []
    for i, rd in enumerate(room["roundData"]):
        live = i == room["round"] and room["phase"] in ("reveal", "drawing", "discuss", "vote", "verdict", "guess")
        out = {
            "order": rd["order"], "colors": rd["colors"], "strokes": rd["strokes"],
            "turn": rd["turn"], "votes": rd["votes"], "accused": rd["accused"],
        }
        if live:
            if room["phase"] in ("verdict", "guess"):
                out["caught"] = rd["caught"]
            if viewer in rd["order"]:
                forger = viewer in rd["forgers"]
                if room["settings"]["mode"] == "clueless" and forger:
                    out["mine"] = {"forger": True, "word": None, "color": rd["colors"].get(viewer, INKS[0])}
                else:
                    out["mine"] = {"forger": False, "word": rd["decoy"] if forger else rd["word"],
                                   "color": rd["colors"].get(viewer, INKS[0])}
                if room["phase"] == "guess" and forger:
                    out["mine"]["guessing"] = True
        else:
            out.update({
                "word": rd["word"], "decoy": rd["decoy"], "forgers": rd["forgers"], "caught": rd["caught"],
                "guess": rd["guess"], "ai": rd["ai"], "points": rd["points"], "why": rd.get("why", {}),
                "aiPending": rd["ai"] is None,
            })
        rounds.append(out)
    r["roundData"] = rounds
    r["turnPid"] = None
    if room["phase"] == "drawing" and cur(room):
        t = turns(room)
        r["turnPid"] = t[cur(room)["turn"]] if cur(room)["turn"] < len(t) else None
        r["totalTurns"] = len(t)
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    p, rd = room["players"][pid], cur(room)
    if action == "ready":
        if room["phase"] != "reveal":
            raise Refuse("Not now.")
        p["ready"] = True
        return True
    if action == "stroke":
        if room["phase"] != "drawing" or not rd:
            raise Refuse("It's not drawing time.", 409)
        t = turns(room)
        if rd["turn"] >= len(t) or t[rd["turn"]] != pid:
            raise Refuse("Wait for your turn to draw.", 409)
        pts = clean_points(b.get("p"))
        if not pts:
            raise Refuse("Draw a stroke on the canvas first.")
        w = max(3, min(24, int(b.get("w") or 8)))
        rd["strokes"].append({
            "id": rid(6), "pid": pid, "c": rd["colors"].get(pid, INKS[0]),
            "w": w, "p": pts, "turn": rd["turn"],
        })
        next_turn(room)
        return True
    if action == "vote":
        if room["phase"] != "vote" or not rd or pid not in rd["order"]:
            raise Refuse("You can't vote right now.", 409)
        t = b.get("target")
        if t != "skip" and t not in rd["order"]:
            raise Refuse("Pick an artist in this round.")
        if t == pid:
            raise Refuse("You can't vote for yourself.")
        rd["votes"][pid] = t
        return True
    if action == "guess":
        if room["phase"] != "guess" or not rd or pid not in rd["forgers"]:
            raise Refuse("Only the caught forger can guess.", 409)
        text = " ".join(str(b.get("text") or "").split())[:40]
        if not text:
            raise Refuse("Type your guess.")
        rd["guess"] = {"text": text, "correct": guessed(text, rd["word"])}
        finish_round(room)
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the game starts.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action == "start":
        if ph != "lobby":
            raise Refuse("The game already started.")
        if len(room["players"]) < MIN_PLAYERS:
            raise Refuse(f"You need at least {MIN_PLAYERS} players ({len(room['players'])} so far).")
        room["phase"] = "starting"
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action == "next":
        if ph == "reveal":
            begin_drawing(room)
        elif ph == "discuss":
            begin_vote(room)
        elif ph == "verdict":
            after_verdict(room)
        elif ph == "results":
            if room["round"] + 1 < len(room["pairs"]):
                start_round(room, room["round"] + 1)
            else:
                room["phase"] = "final"
        else:
            raise Refuse("Nothing to move on from right now.")
    elif action == "skip":
        if ph == "drawing" and cur(room):
            rd, t = cur(room), turns(room)
            if rd["turn"] < len(t):
                pid = t[rd["turn"]]
                rd["strokes"].append({
                    "id": rid(6), "pid": pid, "c": rd["colors"].get(pid, INKS[0]),
                    "w": 0, "p": [], "turn": rd["turn"], "late": True,
                })
            next_turn(room)
        elif ph == "discuss":
            begin_vote(room)
        elif ph == "vote":
            resolve_vote(room)
        elif ph == "guess":
            cur(room)["guess"] = {"text": "(no guess)", "correct": False}
            finish_round(room)
        else:
            raise Refuse("No timer to skip.")
    elif action == "addtime":
        if not room.get("deadline"):
            raise Refuse("No timer is running.")
        room["deadline"] += int(b.get("sec") or 30)
    elif action == "kick":
        pid = b.get("pid")
        was_turn = False
        if ph == "drawing" and cur(room):
            rd, t = cur(room), turns(room)
            was_turn = rd["turn"] < len(t) and t[rd["turn"]] == pid
        room["players"].pop(pid, None)
        if ph == "drawing" and cur(room):
            rd = cur(room)
            skip_gone(room)
            if rd["turn"] >= len(turns(room)):
                begin_discuss(room)
            elif was_turn:
                set_timer(room, room["settings"]["strokeSec"])
    elif action == "playagain":
        for p in room["players"].values():
            p.update({"ready": False, "sitout": False})
        room.update({
            "phase": "lobby", "pairs": [], "round": -1, "roundData": [],
            "deadline": None, "scores": {pid: 0 for pid in room["players"]},
        })
    return True

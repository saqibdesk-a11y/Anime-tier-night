"""Imposter: everyone shares a secret word except the imposter. Players take turns giving one
short clue, argue, vote, and a caught imposter gets one guess at the real word.

Two modes: "undercover" (the imposter gets a similar decoy word and doesn't know they're the
imposter) and "clueless" (the imposter knows, and only sees the category).

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import random
import re
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "next", "skip", "addtime", "kick", "playagain", "settings")
CATEGORIES = {
    "mix": ("Mix of everything", "anything: food, animals, places, objects, jobs, movies, anime"),
    "anime": ("Anime", "anime characters, shows, places and things from anime"),
    "food": ("Food", "foods, dishes and drinks"),
    "animals": ("Animals", "animals"),
    "places": ("Places", "places, cities, countries and landmarks"),
    "objects": ("Everyday objects", "everyday objects"),
    "movies": ("Movies and TV", "movies, TV shows and famous characters"),
    "jobs": ("Jobs", "jobs and professions"),
}
FALLBACK = {
    "mix": [("Pizza", "Burger"), ("Beach", "Pool"), ("Guitar", "Violin"), ("Doctor", "Nurse"), ("Cat", "Tiger"), ("Paris", "London")],
    "anime": [("Naruto", "Boruto"), ("Goku", "Vegeta"), ("Pikachu", "Eevee"), ("Luffy", "Zoro"), ("Death Note", "Code Geass"), ("Totoro", "Ponyo")],
    "food": [("Ramen", "Udon"), ("Pizza", "Lasagna"), ("Sushi", "Onigiri"), ("Pancakes", "Waffles"), ("Ice cream", "Frozen yogurt"), ("Tacos", "Burritos")],
    "animals": [("Lion", "Tiger"), ("Dolphin", "Shark"), ("Owl", "Eagle"), ("Frog", "Toad"), ("Horse", "Zebra"), ("Penguin", "Puffin")],
    "places": [("Beach", "Lake"), ("Paris", "Rome"), ("Library", "Bookstore"), ("Airport", "Train station"), ("Hospital", "Clinic"), ("Japan", "Korea")],
    "objects": [("Fork", "Spoon"), ("Pillow", "Blanket"), ("Phone", "Tablet"), ("Umbrella", "Raincoat"), ("Watch", "Bracelet"), ("Mug", "Glass")],
    "movies": [("Titanic", "Avatar"), ("Batman", "Superman"), ("Shrek", "Toy Story"), ("Harry Potter", "Lord of the Rings"), ("Frozen", "Moana"), ("Star Wars", "Star Trek")],
    "jobs": [("Teacher", "Professor"), ("Chef", "Baker"), ("Pilot", "Astronaut"), ("Firefighter", "Police officer"), ("Dentist", "Doctor"), ("Singer", "Rapper")],
}
SPICE = {
    "wholesome": "Keep it friendly and hype people up.",
    "spicy": "Roast properly: sharp, specific jokes about their clues, with real praise where earned.",
    "unhinged": "Go savage and chaotic like a menace in the group chat, but never about real-world identity.",
}


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    cat = pick("category", "mix")
    return {
        "mode": "clueless" if pick("mode", "undercover") == "clueless" else "undercover",
        "rounds": max(1, min(10, int(pick("rounds", 3)))),
        "category": cat if cat in CATEGORIES or cat == "custom" else "mix",
        "custom": str(pick("custom", "")).strip()[:200],
        "clueRounds": max(1, min(3, int(pick("clueRounds", 1)))),
        "clueSec": max(15, min(90, int(pick("clueSec", 30)))),
        "discussSec": max(30, min(300, int(pick("discussSec", 90)))),
        "voteSec": max(20, min(120, int(pick("voteSec", 45)))),
        "imposters": max(0, min(3, int(pick("imposters", 0) or 0))),  # 0 = pick for me
        "spice": pick("spice", "spicy") if pick("spice", "spicy") in SPICE else "spicy",
    }


def create(room, b):
    room.update({"game": "imposter", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
                 "pairs": [], "round": -1, "roundData": [], "scores": {}})


def on_join(room, pid):
    room["players"][pid].update({"ready": False, "sitout": room["phase"] != "lobby"})
    room["scores"].setdefault(pid, 0)


# ---------- helpers ----------

def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def active(room):
    """Players taking part in this round (late joiners sit out until the next one)."""
    rd = cur(room)
    if rd:
        return [pid for pid in rd["order"] if pid in room["players"]]
    return [pid for pid, p in room["players"].items() if not p.get("sitout")]


def cur(room):
    return room["roundData"][room["round"]] if room["round"] >= 0 and room["round"] < len(room["roundData"]) else None


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


# ---------- AI ----------

def make_pairs(settings, n):
    s = settings
    about = (f"this, as described by the host: {s['custom']}" if s["category"] == "custom" and s["custom"]
             else CATEGORIES.get(s["category"], CATEGORIES["mix"])[1])
    try:
        out, _, _ = ai.ask_builtin(
            "You make word pairs for the party game Imposter (also called Undercover).",
            f"Make {n + 2} word pairs about {about}. In each pair the two words must be different things that are similar "
            "enough that a vague clue fits both (like Ramen/Udon or Batman/Superman), but different enough that a sharp clue "
            "separates them. Everyone should know both words. 1-3 words each, no repeats. "
            'Return only JSON: {"pairs": [["word", "similar word"], ...]}', timeout=25, text_first=True)
        pairs = [(str(a).strip()[:40], str(b).strip()[:40]) for a, b in
                 (p for p in out.get("pairs", []) if isinstance(p, (list, tuple)) and len(p) == 2) if str(a).strip() and str(b).strip()]
    except (ai.AIError, ValueError, TypeError):
        pairs = []
    random.shuffle(pairs)
    backup = FALLBACK.get(s["category"], FALLBACK["mix"])[:]
    random.shuffle(backup)
    while len(pairs) < n:
        pairs.append(backup[len(pairs) % len(backup)])
    # the imposter gets either side of the pair, so the crew's word isn't always the "main" one
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
        if not room:
            return
        rd = room["roundData"][rnd]
        clues = "; ".join(f"{name(room, c['pid'])}: \"{c['text']}\"" for c in rd["clues"]) or "nobody gave clues"
        imps = ", ".join(name(room, p) for p in rd["imposters"])
        votes = "; ".join(f"{name(room, v)} voted {name(room, t) if t != 'skip' else 'skip'}" for v, t in rd["votes"].items())
        outcome = ("The imposter was caught" if rd["caught"] else "The imposter got away") + (
            f" and then guessed the real word (\"{rd['guess']['text']}\") {'correctly' if rd['guess']['correct'] else 'wrong'}" if rd.get("guess") else "")
        names = {p["name"].lower(): p["name"] for p in room["players"].values()}
        system = ("You host a party game of Imposter for friends and comment on the round like a funny group chat. "
                  + SPICE[room["settings"]["spice"]] + " Refer to players by name and never guess anyone's gender (no he/she). "
                  "Only use the facts given.")
        prompt = (f"The crew's word was \"{rd['word']}\". The imposter ({imps}) "
                  + (f"had the decoy word \"{rd['decoy']}\" and didn't know they were the imposter. " if room["settings"]["mode"] == "undercover" else "had no word, only the category. ")
                  + f"Clues in order: {clues}. Votes: {votes or 'none'}. {outcome}. "
                  "Write a 2-3 sentence recap, then one short line for each player roasting or praising their clue (who almost gave it away, "
                  'who bluffed best). Return only JSON: {"story": "...", "lines": [{"name": "<player name>", "line": "..."}]}')
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
                rd["ai"] = {"story": story, "lines": lines}  # replaces a "gave up" marker too: late is better than never
            elif rd["ai"] is None:
                rd["ai"] = {"failed": True}
            changed(room)


def give_up_on_ai(code, rnd, cid):
    """After a while the results stop showing "the AI is writing" so nobody waits on it."""
    with lock:
        room = rooms.get(code)
        if room and rnd < len(room["roundData"]):
            rd = room["roundData"][rnd]
            if rd.get("aiId") == cid and rd["ai"] is None:
                rd["ai"] = {"failed": True}
                changed(room)


# ---------- phases ----------

def start_round(room, rnd):
    pids = [pid for pid, p in room["players"].items()]
    for pid in pids:
        room["players"][pid].update({"sitout": False, "ready": False})
    n = len(pids)
    k = room["settings"]["imposters"] or (1 if n < 7 else 2)
    k = max(1, min(k, (n - 1) // 2))
    word, decoy = room["pairs"][rnd]
    order = pids[:]
    random.shuffle(order)
    room["round"] = rnd
    room["phase"] = "reveal"
    room["deadline"] = None
    room["roundData"].append({"word": word, "decoy": decoy, "imposters": random.sample(pids, k), "order": order,
                              "clues": [], "turn": 0, "votes": {}, "accused": None, "caught": None, "guess": None,
                              "ai": None, "aiId": None, "points": {}})


def turns(room):
    rd = cur(room)
    return rd["order"] * room["settings"]["clueRounds"]


def begin_clues(room):
    room["phase"] = "clues"
    cur(room)["turn"] = 0
    skip_gone(room)
    set_timer(room, room["settings"]["clueSec"])


def skip_gone(room):
    """Skips turns that belong to players who left."""
    rd, t = cur(room), turns(room)
    while rd["turn"] < len(t) and t[rd["turn"]] not in room["players"]:
        rd["turn"] += 1


def next_turn(room):
    rd = cur(room)
    rd["turn"] += 1
    skip_gone(room)
    if rd["turn"] >= len(turns(room)):
        room["phase"] = "discuss"
        set_timer(room, room["settings"]["discussSec"])
    else:
        set_timer(room, room["settings"]["clueSec"])


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
    rd["caught"] = accused in rd["imposters"]
    room["phase"] = "verdict"


def after_verdict(room):
    rd = cur(room)
    if rd["caught"] and rd["guess"] is None:
        room["phase"] = "guess"  # the caught imposter's last chance
        set_timer(room, 30)
    else:
        finish_round(room)


def finish_round(room):
    rd = cur(room)
    room["deadline"] = None
    pts = {}
    if rd["caught"]:
        for v, t in rd["votes"].items():
            if t in rd["imposters"] and v not in rd["imposters"]:
                pts[v] = pts.get(v, 0) + 1
        if rd["guess"] and rd["guess"]["correct"]:
            for imp in rd["imposters"]:
                pts[imp] = pts.get(imp, 0) + 2
    else:
        for imp in rd["imposters"]:
            pts[imp] = pts.get(imp, 0) + 3
    for pid, p in pts.items():
        room["scores"][pid] = room["scores"].get(pid, 0) + p
    rd["points"] = pts
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
            begin_clues(room)
            return True
    elif ph == "clues" and over:
        rd = cur(room)
        t = turns(room)
        if rd["turn"] < len(t):
            rd["clues"].append({"pid": t[rd["turn"]], "text": "(ran out of time)", "turn": rd["turn"], "late": True})
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


# ---------- what each viewer sees ----------

def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "pairs", "roundData")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["categoryLabel"] = category_label(room)
    rounds = []
    for i, rd in enumerate(room["roundData"]):
        live = i == room["round"] and room["phase"] in ("reveal", "clues", "discuss", "vote", "verdict", "guess")
        out = {"order": rd["order"], "clues": rd["clues"], "turn": rd["turn"], "votes": rd["votes"],
               "accused": rd["accused"]}
        if live:
            if room["phase"] in ("verdict", "guess"):
                out["caught"] = rd["caught"]  # the accused's file gets stamped, everything else stays secret
                out["accusedRole"] = "imposter" if rd["caught"] else "crew"
            if viewer in rd["order"]:
                imp = viewer in rd["imposters"]
                if room["settings"]["mode"] == "clueless" and imp:
                    out["mine"] = {"imposter": True, "word": None}
                else:
                    out["mine"] = {"imposter": False, "word": rd["decoy"] if imp else rd["word"]}
                if room["phase"] == "guess" and imp:
                    out["mine"]["guessing"] = True  # caught: now they know, and get one shot at the real word
        else:
            out.update({"word": rd["word"], "decoy": rd["decoy"], "imposters": rd["imposters"], "caught": rd["caught"],
                        "guess": rd["guess"], "ai": rd["ai"], "points": rd["points"], "aiPending": rd["ai"] is None})
        rounds.append(out)
    r["roundData"] = rounds
    r["turnPid"] = None
    if room["phase"] == "clues" and cur(room):
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
    if action == "clue":
        if room["phase"] != "clues":
            raise Refuse("It's not clue time.", 409)
        t = turns(room)
        if rd["turn"] >= len(t) or t[rd["turn"]] != pid:
            raise Refuse("Wait for your turn.", 409)
        text = " ".join(str(b.get("text") or "").split())[:40]
        if not text:
            raise Refuse("Type a clue first.")
        mine = rd["decoy"] if pid in rd["imposters"] else rd["word"]
        if mine and norm(mine) and norm(mine) in norm(text):
            raise Refuse("You can't say your word. Be sneakier.")
        rd["clues"].append({"pid": pid, "text": text, "turn": rd["turn"]})
        next_turn(room)
        return True
    if action == "vote":
        if room["phase"] != "vote" or pid not in rd["order"]:
            raise Refuse("You can't vote right now.", 409)
        t = b.get("target")
        if t != "skip" and t not in rd["order"]:
            raise Refuse("Pick someone in this round.")
        if t == pid:
            raise Refuse("You can't vote for yourself.")
        rd["votes"][pid] = t
        return True
    if action == "guess":
        if room["phase"] != "guess" or pid not in rd["imposters"]:
            raise Refuse("Only the caught imposter can guess.", 409)
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
        if len(room["players"]) < 3:
            raise Refuse(f"You need at least 3 players ({len(room['players'])} so far).")
        room["phase"] = "starting"
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action == "next":
        if ph == "reveal":
            begin_clues(room)
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
        if ph == "clues":
            rd, t = cur(room), turns(room)
            if rd["turn"] < len(t):
                rd["clues"].append({"pid": t[rd["turn"]], "text": "(skipped)", "turn": rd["turn"], "late": True})
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
        room["players"].pop(b.get("pid"), None)
        if ph == "clues":
            skip_gone(room)
    elif action == "playagain":
        for p in room["players"].values():
            p.update({"ready": False, "sitout": False})
        room.update({"phase": "lobby", "pairs": [], "round": -1, "roundData": [], "deadline": None,
                     "scores": {pid: 0 for pid in room["players"]}})
    return True

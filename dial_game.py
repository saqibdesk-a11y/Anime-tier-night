"""Festival Dial: a Wavelength-style spectrum guessing game for friends.

Each turn, one player is the Psychic. They see a hidden target (8..92) on a funny two-sided spectrum
(like "Overrated <-> Underrated" or "Harmless <-> Pure Menace") and give a single clue.
Everyone else slides a semicircular festival dial needle to match where they think the target sits.
Closer guesses score +4 (bullseye), +3, or +2, and the Psychic earns points for clear clues!"""
import random
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "settings", "next", "skip", "addtime", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 2, 12

SPECTRA = {
    "anime": [
        ("Overrated", "Underrated"), ("Weakest", "Strongest"), ("Hero Energy", "Villain Energy"),
        ("Peak Fiction", "Pure Filler"), ("Wholesome", "Traumatizing"), ("Main Character", "Background NPC"),
        ("Smartest", "Zero Braincells"), ("Best Opening", "Skip Intro"), ("Loyal Friend", "Instant Betrayal"),
        ("Cool Power", "Useless Power"), ("Plot Armor", "Dies Episode 1"), ("Calm & Chill", "Screaming for 5 Episodes"),
        ("Best Mentor", "Worst Parent"), ("Iconic", "Forgotten"), ("Sad Backstory", "Just Evil for Fun"),
        ("Fast Fight", "30-Episode Staredown"), ("Broke", "Owns a Castle"), ("Pure Luck", "Pure Skill"),
    ],
    "everyday": [
        ("Harmless", "Pure Menace"), ("Broke", "Billionaire"), ("Cozy", "Cursed"),
        ("Breakfast Food", "3 AM Snack"), ("Good Superpower", "Curse in Disguise"), ("Totally Normal", "Straight to Jail"),
        ("Worst Gift", "Best Gift"), ("Easy to Survive", "Instant Doom"), ("Looks Cheap", "Looks Expensive"),
        ("Hot Take", "Cold Take"), ("Best Smell", "Worst Smell"), ("Low Effort", "Tryhard"),
        ("Acceptable Late", "Never Be Late"), ("Tiny Problem", "End of the World"), ("Good First Date", "Disaster First Date"),
        ("Guilty Pleasure", "Genuine Masterpiece"), ("Soft", "Rock Hard"), ("Quiet", "Deafening"),
        ("Useful in Apocalypse", "Dead on Day 1"), ("Overhyped Movie", "Hidden Gem"), ("Cute", "Terrifying"),
        ("Smart Purchase", "Instant Regret"), ("Good Excuse", "Obvious Lie"), ("Needs Skill", "Pure Chaos"),
    ],
}
SPECTRA["mix"] = SPECTRA["anime"] + SPECTRA["everyday"]


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    pack = pick("pack", "mix")
    if pack not in ("mix", "anime", "everyday", "custom"):
        pack = "mix"
    return {
        "pack": pack,
        "custom": str(pick("custom", "")).strip()[:160],
        "rounds": max(2, min(12, int(pick("rounds", 6)))),
        "clueSec": max(20, min(120, int(pick("clueSec", 45)))),
        "guessSec": max(20, min(120, int(pick("guessSec", 40)))),
    }


def create(room, b):
    room.update({
        "game": "dial", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "deck": [], "order": [], "turn": -1, "scores": {}, "current": None, "history": [],
    })


def on_join(room, pid):
    room["scores"].setdefault(pid, 0)
    if room["phase"] != "lobby" and pid not in room["order"] and not room["players"][pid].get("wantSitout"):
        room["order"].append(pid)  # late joiners can guess immediately and get Psychic turns later!


def active_players(room):
    act = [pid for pid, p in room["players"].items() if not p.get("wantSitout")]
    return act or list(room["players"])


def build_deck(settings):
    n = settings["rounds"] + 2
    out = []
    if settings["pack"] == "custom" and settings["custom"]:
        try:
            res, _, _ = ai.ask_builtin(
                "You create opposite-end spectrum pairs for the party game Wavelength.",
                f"Make {n} funny, debate-sparking opposite spectrum pairs about: {settings['custom']}. "
                "Keep each side 1-3 words (e.g. ['Overrated', 'Underrated']). "
                'Return only JSON: {"pairs":[["Left","Right"],...]}', timeout=25, text_first=True)
            for pair in (res.get("pairs") or []):
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    a, b = str(pair[0]).strip()[:28], str(pair[1]).strip()[:28]
                    if a and b:
                        out.append([a, b])
        except (ai.AIError, ValueError, TypeError, AttributeError):
            pass
    pool = SPECTRA.get(settings["pack"], SPECTRA["mix"])[:]
    random.shuffle(pool)
    for a, b in pool:
        if len(out) >= n:
            break
        out.append([a, b] if random.random() < .5 else [b, a])
    return out[:n]


def begin_game(code):
    with lock:
        room = rooms.get(code)
        settings = dict(room["settings"]) if room else None
    if not settings:
        return
    deck = build_deck(settings)
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            room["deck"] = deck
            order = active_players(room)
            random.shuffle(order)
            room["order"] = order
            room["scores"] = {pid: 0 for pid in room["players"]}
            room["history"] = []
            start_turn(room, 0)
            changed(room)


def start_turn(room, idx):
    room["turn"] = idx
    order = [p for p in room["order"] if p in room["players"] and not room["players"][p].get("wantSitout")] or active_players(room)
    psychic = order[idx % len(order)]
    left, right = room["deck"][idx % len(room["deck"])]
    target = random.randint(8, 92)
    room["current"] = {
        "turn": idx, "psychic": psychic, "left": left, "right": right,
        "target": target, "clue": None, "guesses": {}, "points": {},
    }
    room["phase"] = "clue"
    room["deadline"] = time.time() + room["settings"]["clueSec"] + 1


def begin_guess(room, clue_text):
    room["current"]["clue"] = clue_text
    room["phase"] = "guess"
    room["deadline"] = time.time() + room["settings"]["guessSec"] + 1


def score_diff(diff):
    if diff <= 4:
        return 4
    if diff <= 10:
        return 3
    if diff <= 18:
        return 2
    return 0


def reveal_turn(room):
    cur = room["current"]
    target, psychic = cur["target"], cur["psychic"]
    pts = {}
    hits = 0
    for pid, val in cur["guesses"].items():
        p = score_diff(abs(val - target))
        if p:
            pts[pid] = p
            hits += 1
            room["scores"][pid] = room["scores"].get(pid, 0) + p
    if hits:
        p_pts = min(4, hits + (1 if any(v == 4 for v in pts.values()) else 0))
        pts[psychic] = p_pts
        room["scores"][psychic] = room["scores"].get(psychic, 0) + p_pts
    cur["points"] = pts
    room["history"].append({
        "psychic": psychic, "left": cur["left"], "right": cur["right"],
        "clue": cur["clue"] or "(no clue)", "target": target, "points": pts,
    })
    room["phase"] = "reveal"
    room["deadline"] = None


def guessers_needed(room):
    cur = room["current"]
    return [pid for pid in active_players(room) if pid != cur["psychic"]]


def tick(room):
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now >= room["deadline"]
    if ph == "clue" and over:
        begin_guess(room, "(no clue — pure intuition!)")
        return True
    if ph == "guess":
        need = guessers_needed(room)
        if over or (need and all(pid in room["current"]["guesses"] for pid in need)):
            reveal_turn(room)
            return True
    return False


def chat_rules(room, pid):
    if room["phase"] == "clue" and room.get("current") and pid == room["current"]["psychic"]:
        return {"read": ["all"], "write": [], "why": "Type your clue in the box instead of chat!"}
    return {"read": ["all"], "write": ["all"]}


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "deck", "current")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    cur = room.get("current")
    if cur:
        show_target = room["phase"] in ("reveal", "final") or viewer == cur["psychic"]
        show_guesses = room["phase"] in ("reveal", "final")
        c = {
            "turn": cur["turn"], "psychic": cur["psychic"], "left": cur["left"], "right": cur["right"],
            "clue": cur["clue"], "guessedPids": list(cur["guesses"]),
            "guessNeed": len(guessers_needed(room)),
        }
        if show_target:
            c["target"] = cur["target"]
        if show_guesses:
            c["guesses"] = cur["guesses"]
            c["points"] = cur["points"]
        elif viewer in cur["guesses"]:
            c["myGuess"] = cur["guesses"][viewer]
        r["current"] = c
    return r


def player_action(room, action, b, pid):
    cur = room.get("current")
    if action == "clue":
        if room["phase"] != "clue" or not cur or cur["psychic"] != pid:
            raise Refuse("Only the Psychic can give the clue.", 409)
        text = " ".join(str(b.get("text") or "").split())[:60]
        if not text:
            raise Refuse("Type a clue first.")
        begin_guess(room, text)
        return True
    if action == "guess":
        if room["phase"] != "guess" or not cur or pid == cur["psychic"]:
            raise Refuse("You can't guess right now.", 409)
        val = max(0, min(100, int(round(float(b.get("val"))))))
        cur["guesses"][pid] = val
        need = guessers_needed(room)
        if need and all(p in cur["guesses"] for p in need):
            reveal_turn(room)
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
            raise Refuse(f"You need at least {MIN_PLAYERS} players.")
        room["phase"] = "starting"
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action in ("next", "skip"):
        if ph == "clue":
            begin_guess(room, "(skipped clue — pure chaos!)")
        elif ph == "guess":
            reveal_turn(room)
        elif ph == "reveal":
            if room["turn"] + 1 < room["settings"]["rounds"]:
                start_turn(room, room["turn"] + 1)
            else:
                room["phase"] = "final"
        else:
            raise Refuse("Nothing to skip right now.")
    elif action == "addtime":
        if not room.get("deadline"):
            raise Refuse("No timer is running.")
        room["deadline"] += int(b.get("sec") or 30)
    elif action == "kick":
        pid = b.get("pid")
        room["players"].pop(pid, None)
        if pid in room["order"]:
            room["order"].remove(pid)
        cur = room.get("current")
        if cur and cur["psychic"] == pid and ph in ("clue", "guess"):
            if room["turn"] + 1 < room["settings"]["rounds"] and len(room["players"]) >= MIN_PLAYERS:
                start_turn(room, room["turn"] + 1)
            else:
                room["phase"] = "final"
    elif action == "playagain":
        room.update({
            "phase": "lobby", "deadline": None, "deck": [], "order": [], "turn": -1,
            "scores": {pid: 0 for pid in room["players"]}, "current": None, "history": [],
        })
    return True

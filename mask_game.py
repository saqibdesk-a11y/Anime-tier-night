"""Forehead Mask: Headbands / "Who Am I?" for Discord voice calls and chat.

Every player gets a secret identity card stuck to their forehead—everyone else sees your character
portrait & name, while YOUR own card is hidden behind a festival mask!
On your turn, ask a Yes/No question (typed or out loud on Discord VC!), collect live Yes/No/Kinda
votes into your personal Clue Log, and guess your identity whenever you're ready!"""
import random
import re
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None
gallery = None  # server.py sets this to avatar_gallery

HOST_ACTIONS = ("start", "settings", "next", "skip", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 2, 10

FALLBACK = {
    "anime": [
        {"name": "Naruto Uzumaki", "show": "Naruto"}, {"name": "Monkey D. Luffy", "show": "One Piece"},
        {"name": "Son Goku", "show": "Dragon Ball Z"}, {"name": "Pikachu", "show": "Pokemon"},
        {"name": "Satoru Gojo", "show": "Jujutsu Kaisen"}, {"name": "Levi Ackerman", "show": "Attack on Titan"},
        {"name": "Light Yagami", "show": "Death Note"}, {"name": "Tanjiro Kamado", "show": "Demon Slayer"},
        {"name": "Anya Forger", "show": "Spy x Family"}, {"name": "Totoro", "show": "Studio Ghibli"},
        {"name": "Saitama", "show": "One Punch Man"}, {"name": "Roronoa Zoro", "show": "One Piece"},
    ],
    "movies": [
        {"name": "Batman", "show": "DC"}, {"name": "Spider-Man", "show": "Marvel"},
        {"name": "Darth Vader", "show": "Star Wars"}, {"name": "Shrek", "show": "DreamWorks"},
        {"name": "Harry Potter", "show": "Wizarding World"}, {"name": "Iron Man", "show": "Marvel"},
        {"name": "SpongeBob", "show": "Nickelodeon"}, {"name": "Elsa", "show": "Frozen"},
        {"name": "Jack Sparrow", "show": "Pirates"}, {"name": "Gandalf", "show": "Lord of the Rings"},
        {"name": "Mario", "show": "Nintendo"}, {"name": "Godzilla", "show": "Kaiju"},
    ],
    "animals": [
        {"name": "Penguin", "show": "Animal"}, {"name": "Octopus", "show": "Animal"},
        {"name": "Giraffe", "show": "Animal"}, {"name": "Capybara", "show": "Animal"},
        {"name": "Shark", "show": "Animal"}, {"name": "Flamingo", "show": "Animal"},
        {"name": "Panda", "show": "Animal"}, {"name": "Chameleon", "show": "Animal"},
        {"name": "Sloth", "show": "Animal"}, {"name": "Red Fox", "show": "Animal"},
    ],
    "objects": [
        {"name": "Toaster", "show": "Object"}, {"name": "Umbrella", "show": "Object"},
        {"name": "Lightsaber", "show": "Prop"}, {"name": "Guitar", "show": "Instrument"},
        {"name": "Microwave", "show": "Appliance"}, {"name": "Skateboard", "show": "Gear"},
        {"name": "Bubble Tea", "show": "Drink"}, {"name": "Ramen Bowl", "show": "Food"},
        {"name": "Headphones", "show": "Tech"}, {"name": "Alarm Clock", "show": "Object"},
    ],
}
FALLBACK["mix"] = [x for xs in FALLBACK.values() for x in xs]


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    cat = pick("category", "anime")
    if cat not in ("anime", "movies", "animals", "objects", "mix", "custom"):
        cat = "anime"
    assign = "friends" if pick("assign", "auto") == "friends" else "auto"
    return {
        "category": cat,
        "custom": str(pick("custom", "")).strip()[:160],
        "assign": assign,  # "auto" = AniList/AI/deck picks; "friends" = each player assigns the next player's mask!
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
    cands = [card["name"], clean_card_name(card["name"]), card.get("alias", "")]
    for c in list(cands):
        cands.extend([p for p in str(c or "").split() if len(p) >= 3])
    for c in cands:
        nc = norm(c)
        if nc and (g == nc or (len(nc) >= 4 and (nc in g or g in nc) and abs(len(g) - len(nc)) <= 3)):
            return True
    return False


def build_cards(settings, n):
    cat = settings["category"]
    if cat == "anime":
        chars = [c for c in (gallery() if gallery else []) if c.get("img")]
        if len(chars) >= n:
            return [{"name": clean_card_name(c["name"]), "show": c.get("show", ""), "img": c["img"], "alias": c.get("alias", "")}
                    for c in random.sample(chars, n)]
    if cat == "custom" and settings["custom"]:
        try:
            res, _, _ = ai.ask_builtin(
                "You pick well-known secret identities for the party game Headbands / Who Am I.",
                f"Pick {n + 4} famous, easily guessable names/things about: {settings['custom']}. "
                'Return only JSON: {"items":[{"name":"...","show":"short category"}]}', timeout=25, text_first=True)
            out = [{"name": str(x.get("name") or "").strip()[:40], "show": str(x.get("show") or "").strip()[:30], "img": None}
                   for x in (res.get("items") or []) if isinstance(x, dict) and str(x.get("name") or "").strip()]
            if len(out) >= n:
                random.shuffle(out)
                return out[:n]
        except (ai.AIError, ValueError, TypeError, AttributeError):
            pass
    pool = FALLBACK.get(cat, FALLBACK["mix"])[:]
    random.shuffle(pool)
    return [{**x, "img": None} for x in pool[:n]]


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
        "solved": [],  # pids in order they solved
        "turn": 0,
        "question": None,  # current active question: {id, pid, text, votes:{voter: "yes"|"no"|"kinda"}}
        "logs": {pid: [] for pid in pids},  # personal clue log per player
        "wrongGuesses": [],
    }
    if room["settings"]["assign"] == "friends":
        room["phase"] = "assign"
        room["deadline"] = time.time() + 45
    else:
        room["phase"] = "play"
        room["deadline"] = None


def unsolved(room):
    g = room["g"]
    return [pid for pid in g["order"] if pid in room["players"] and pid not in g["solved"]]


def current_pid(room):
    g = room["g"]
    rem = unsolved(room)
    if not rem:
        return None
    return g["order"][g["turn"] % len(g["order"])] if g["order"][g["turn"] % len(g["order"])] in rem else rem[0]


def advance_turn(room):
    g = room["g"]
    # archive current question into player's clue log
    q = g.get("question")
    if q:
        g["logs"].setdefault(q["pid"], []).append(q)
        g["question"] = None
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


def finish_assign(room):
    g = room["g"]
    order = g["order"]
    backup = FALLBACK.get(room["settings"]["category"], FALLBACK["mix"])[:]
    random.shuffle(backup)
    for i, target in enumerate(order):
        if target not in g["cards"]:
            g["cards"][target] = {**backup[i % len(backup)], "img": None}
    room["phase"] = "play"
    room["deadline"] = None


def tick(room):
    if room["phase"] == "assign" and room.get("g"):
        g = room["g"]
        over = room.get("deadline") and time.time() >= room["deadline"]
        if over or all(pid in g["cards"] for pid in g["order"]):
            finish_assign(room)
            return True
    return False


def chat_rules(room, pid):
    g = room.get("g")
    if room["phase"] == "play" and g:
        # Block accidentally typing someone's secret mask name in chat!
        block = [c["name"] for p, c in g["cards"].items() if p not in g["solved"] and c.get("name")]
        return {"read": ["all"], "write": ["all"], "block": block}
    return {"read": ["all"], "write": ["all"]}


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "g")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    g = room.get("g")
    if g:
        reveal_all = room["phase"] in ("roundover", "final")
        cards_out = {}
        for pid, c in g["cards"].items():
            if reveal_all or pid != viewer or pid in g["solved"]:
                cards_out[pid] = c
            else:
                cards_out[pid] = {"hidden": True}
        out = {
            "order": g["order"],
            "cards": cards_out,
            "solved": g["solved"],
            "turnPid": current_pid(room) if room["phase"] == "play" else None,
            "question": g["question"],
            "myLog": g["logs"].get(viewer, []),
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
        text = " ".join(str(b.get("name") or "").split())[:40]
        if not text:
            raise Refuse("Type an identity for them!")
        g["cards"][target] = {"name": text, "show": "Picked by " + name(room, pid), "img": None}
        g["assignedBy"][target] = pid
        if all(p in g["cards"] for p in g["order"]):
            finish_assign(room)
        return True
    if ph != "play":
        raise Refuse("Not in play right now.", 409)
    cur = current_pid(room)
    if action == "ask":
        if pid != cur:
            raise Refuse("Wait for your turn to ask.", 409)
        text = " ".join(str(b.get("text") or "").split())[:120] or "(Asked out loud on voice!)"
        if g.get("question"):
            g["logs"].setdefault(g["question"]["pid"], []).append(g["question"])
        g["question"] = {"id": rid(6), "pid": pid, "text": text, "votes": {}}
        return True
    if action == "reply":
        q = g.get("question")
        if not q:
            raise Refuse("No active question right now.", 409)
        if pid == q["pid"]:
            raise Refuse("Let the others answer your question!", 409)
        ans = str(b.get("ans") or "")
        if ans not in ("yes", "no", "kinda"):
            raise Refuse("Pick Yes, No, or Kinda.")
        q["votes"][pid] = ans
        return True
    if action == "endturn":
        if pid != cur:
            raise Refuse("Wait for your turn.", 409)
        advance_turn(room)
        return True
    if action == "guess":
        if pid != cur:
            raise Refuse("Wait for your turn to guess.", 409)
        text = " ".join(str(b.get("text") or "").split())[:50]
        if not text:
            raise Refuse("Type your guess first!")
        card = g["cards"][pid]
        if matches_card(text, card):
            g["solved"].append(pid)
            rank = len(g["solved"])
            pts = {1: 5, 2: 3, 3: 2}.get(rank, 1)
            room["scores"][pid] = room["scores"].get(pid, 0) + pts
            advance_turn(room)
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

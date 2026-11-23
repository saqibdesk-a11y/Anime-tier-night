"""Last Lantern: a shedding card game. Match the top card's colour or symbol, play action cards on
the next player, and be the first to empty your hand. When you're down to one card you must call
"Last lantern!"; if someone catches you first, you draw two.

Speed mode: 10-second turns, and anyone holding a card identical to the top card (same colour and
symbol, not a wild) can slam it down out of turn. The turn then carries on from them.

Cards are strings like "r7#12": a colour (r lantern, b fan, g bamboo, y firework), a value
(0-9, S skip, R reverse, D draw two) and a serial so every card is unique. Wilds are "W#n" and
"W4#n" (wild draw four). server.py owns rooms, the lock and HTTP; this module owns the rules."""
import random
import time

from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "settings", "kick", "playagain", "tolobby", "skip")
COLORS = ("r", "b", "g", "y")
MIN_PLAYERS, MAX_PLAYERS = 2, 10
EVENTS_KEEP = 20
SPEED_SEC = 10


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    sec = int(pick("turnSec", 30) or 0)
    return {
        "mode": "speed" if pick("mode", "classic") == "speed" else "classic",
        "hand": max(5, min(10, int(pick("hand", 7)))),
        "stack": bool(pick("stack", True)),          # +2 on +2 and +4 on anything pending
        "drawUntil": bool(pick("drawUntil", False)),  # keep drawing until you can play
        "turnSec": sec if sec in (0, 20, 30, 45, 60) else 30,
    }


def create(room, b):
    room.update({"game": "lantern", "phase": "lobby", "settings": clean_settings(b), "wins": {},
                 "deadline": None, "round": 0, "g": None})


def on_join(room, pid):
    room["wins"].setdefault(pid, 0)  # late joiners watch until the next round


# ---------- cards ----------

def kind(card):
    return card.split("#")[0]


def color_of(card):
    k = kind(card)
    return None if k.startswith("W") else k[0]


def value_of(card):
    k = kind(card)
    return k if k.startswith("W") else k[1:]


def new_deck():
    cards = []
    for c in COLORS:
        cards.append(c + "0")
        for v in "123456789SRD":
            cards += [c + v, c + v]
    cards += ["W"] * 4 + ["W4"] * 4
    deck = [f"{k}#{i}" for i, k in enumerate(cards)]
    random.shuffle(deck)
    return deck


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def event(room, what, pid=None, **extra):
    g = room["g"]
    g["events"].append({"id": rid(6), "what": what, "pid": pid, "t": time.time(), **extra})
    del g["events"][:-EVENTS_KEEP]


# ---------- the round ----------

def start_round(room):
    order = [pid for pid in room["players"]]
    random.shuffle(order)
    deck = new_deck()
    hands = {pid: [deck.pop() for _ in range(room["settings"]["hand"])] for pid in order}
    # the first face-up card is always a plain number
    while not value_of(deck[-1]).isdigit():
        deck.insert(0, deck.pop())
    top = deck.pop()
    room["round"] += 1
    room["phase"] = "playing"
    room["g"] = {"deck": deck, "discard": [top], "hands": hands, "order": order, "turn": 0, "dir": 1,
                 "color": color_of(top), "pending": 0, "pendingKind": None, "drawn": None, "called": [],
                 "exposed": None, "winner": None, "events": []}
    event(room, "start")
    set_timer(room)


def set_timer(room):
    s = SPEED_SEC if room["settings"].get("mode") == "speed" else room["settings"]["turnSec"]
    room["deadline"] = time.time() + s + 1 if s and room["phase"] == "playing" else None


def current(room):
    g = room["g"]
    return g["order"][g["turn"]] if g and g["order"] else None


def step(room, n=1):
    """Moves the turn n seats in the current direction."""
    g = room["g"]
    g["turn"] = (g["turn"] + g["dir"] * n) % len(g["order"])


def draw_cards(room, pid, n):
    g = room["g"]
    got = []
    for _ in range(n):
        if not g["deck"]:
            if len(g["discard"]) <= 1:
                break  # every card is in someone's hand
            top = g["discard"].pop()
            g["deck"] = g["discard"]
            random.shuffle(g["deck"])
            g["discard"] = [top]
        got.append(g["deck"].pop())
    g["hands"][pid] += got
    if len(g["hands"][pid]) > 1 and pid in g["called"]:
        g["called"].remove(pid)
    return got


def playable(room, card):
    g = room["g"]
    top, k, v = g["discard"][-1], kind(card), value_of(card)
    if g["pending"]:
        return k == "W4" or (v == "D" and g["pendingKind"] == "D")
    if k.startswith("W"):
        return True
    return color_of(card) == g["color"] or v == value_of(top)


def can_jump(room, pid, card):
    """Speed mode: an identical card (not a wild) can be played out of turn, unless a draw stack is waiting."""
    g = room["g"]
    return (room["settings"].get("mode") == "speed" and current(room) != pid and not g["pending"]
            and not kind(card).startswith("W") and kind(card) == kind(g["discard"][-1]))


def end_turn(room, extra_steps=0):
    g = room["g"]
    g["drawn"] = None
    step(room, 1 + extra_steps)
    set_timer(room)


def settle_exposure(room, pid):
    """Whoever was left on one card without calling it stays catchable only until the next move."""
    g = room["g"]
    if g["exposed"] and g["exposed"] != pid:
        g["exposed"] = None


def take_pending(room, pid):
    g = room["g"]
    n = g["pending"]
    got = draw_cards(room, pid, n)
    event(room, "drew", pid, n=len(got), forced=True)
    g["pending"], g["pendingKind"] = 0, None
    end_turn(room)


def finish_round(room, pid):
    g = room["g"]
    g["winner"] = pid
    room["wins"][pid] = room["wins"].get(pid, 0) + 1
    room["phase"] = "roundover"
    room["deadline"] = None
    event(room, "won", pid)


def play_card(room, pid, card, color=None):
    g = room["g"]
    hand = g["hands"][pid]
    if card not in hand:
        raise Refuse("That card isn't in your hand.")
    if g["drawn"] and card != g["drawn"]:
        raise Refuse("After drawing you can only play the card you drew, or pass.", 409)
    if not playable(room, card):
        raise Refuse("That card doesn't match. Play the same colour or symbol, or draw.", 409)
    k, v = kind(card), value_of(card)
    if k.startswith("W") and color not in COLORS:
        raise Refuse("Pick a colour for your wild card.")
    settle_exposure(room, pid)
    hand.remove(card)
    g["discard"].append(card)
    g["color"] = color if k.startswith("W") else color_of(card)
    event(room, "play", pid, card=card, color=g["color"])
    if not hand:
        return finish_round(room, pid)
    if len(hand) == 1 and pid not in g["called"]:
        g["exposed"] = pid  # forgot to call: anyone can catch them until the next move
    skip = 0
    if v == "S":
        skip = 1
        event(room, "skip", g["order"][(g["turn"] + g["dir"]) % len(g["order"])])
    elif v == "R":
        if len(g["order"]) == 2:
            skip = 1  # with two players a reverse works like a skip
        g["dir"] *= -1
        event(room, "reverse", pid)
    elif v == "D" or k == "W4":
        n = 4 if k == "W4" else 2
        if room["settings"]["stack"]:
            g["pending"] += n
            g["pendingKind"] = "W4" if k == "W4" else (g["pendingKind"] or "D")
        else:
            victim = g["order"][(g["turn"] + g["dir"]) % len(g["order"])]
            got = draw_cards(room, victim, n)
            event(room, "drew", victim, n=len(got), forced=True)
            skip = 1
    end_turn(room, skip)


def draw_turn(room, pid):
    g = room["g"]
    if g["drawn"]:
        raise Refuse("You already drew. Play that card or pass.", 409)
    settle_exposure(room, pid)
    if g["pending"]:
        return take_pending(room, pid)
    got = []
    while True:
        new = draw_cards(room, pid, 1)
        got += new
        if not new or playable(room, new[0]) or not room["settings"]["drawUntil"]:
            break
    event(room, "drew", pid, n=len(got))
    if got and playable(room, got[-1]):
        g["drawn"] = got[-1]  # they may play it now, or pass
    else:
        end_turn(room)


# ---------- the timer ----------

def tick(room):
    if room["phase"] != "playing" or not room.get("deadline") or time.time() < room["deadline"]:
        return False
    pid, g = current(room), room["g"]
    settle_exposure(room, pid)
    if g["pending"]:
        take_pending(room, pid)
    elif g["drawn"]:
        event(room, "pass", pid, timeout=True)
        end_turn(room)
    else:
        got = draw_cards(room, pid, 1)
        event(room, "drew", pid, n=len(got), timeout=True)
        end_turn(room)
    return True


# ---------- what each viewer sees ----------

def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "g")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    g = room["g"]
    if g:
        mine = g["hands"].get(viewer)
        r["table"] = {
            "order": g["order"], "turn": current(room), "dir": g["dir"], "color": g["color"],
            "top": g["discard"][-1], "under": g["discard"][-4:-1], "deck": len(g["deck"]),
            "counts": {pid: len(h) for pid, h in g["hands"].items()},
            "pending": g["pending"], "called": g["called"], "exposed": g["exposed"],
            "winner": g["winner"], "events": g["events"],
            # everyone sees every hand once the round is over
            "hands": g["hands"] if room["phase"] == "roundover" else None,
        }
        if mine is not None:
            your_turn = current(room) == viewer and room["phase"] == "playing"
            r["me"] = {"hand": mine, "drawn": g["drawn"] if your_turn else None,
                       "canPlay": [c for c in mine if your_turn and playable(room, c) and (not g["drawn"] or c == g["drawn"])],
                       "canJump": [c for c in mine if room["phase"] == "playing" and can_jump(room, viewer, c)]}
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    g = room["g"]
    if room["phase"] != "playing" or not g or pid not in g["hands"]:
        if action in ("play", "draw", "pass", "call", "catch"):
            raise Refuse("You're not in this round. You'll be dealt in next round.", 409)
        raise Refuse("Unknown action")
    turn = current(room)
    if action == "call":
        n = len(g["hands"][pid])
        if n == 1 and g["exposed"] == pid:
            g["exposed"] = None  # called just in time
        elif not (n == 2 and turn == pid):
            raise Refuse("Call it when you're about to play your second-last card.", 409)
        if pid not in g["called"]:
            g["called"].append(pid)
        event(room, "call", pid)
        return True
    if action == "catch":
        target = g["exposed"]
        if not target or target == pid:
            raise Refuse("Nobody to catch right now.", 409)
        got = draw_cards(room, target, 2)
        g["exposed"] = None
        event(room, "caught", target, by=pid, n=len(got))
        return True
    if action == "play" and turn != pid:
        card = str(b.get("card") or "")
        if card not in g["hands"][pid] or not can_jump(room, pid, card):
            raise Refuse("It's not your turn." + (" In Speed you can only jump in with the exact same card." if room["settings"].get("mode") == "speed" else ""), 409)
        g["drawn"] = None  # whoever's turn it was loses it
        g["turn"] = g["order"].index(pid)
        event(room, "jump", pid, card=card, from_=turn)
        play_card(room, pid, card)
        return True
    if turn != pid:
        raise Refuse("It's not your turn.", 409)
    if action == "play":
        play_card(room, pid, str(b.get("card") or ""), b.get("color"))
        return True
    if action == "draw":
        draw_turn(room, pid)
        return True
    if action == "pass":
        if not g["drawn"]:
            raise Refuse("Draw a card first, or play one.", 409)
        event(room, "pass", pid)
        end_turn(room)
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the game starts. Go back to the lobby to change them.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action in ("start", "playagain"):
        if ph == "playing":
            raise Refuse("A round is already going.")
        n = len(room["players"])
        if n < MIN_PLAYERS:
            raise Refuse(f"You need at least {MIN_PLAYERS} players ({n} so far).")
        if n > MAX_PLAYERS:
            raise Refuse(f"Up to {MAX_PLAYERS} players can play. Kick someone or start a second room.")
        start_round(room)
    elif action == "tolobby":
        room.update({"phase": "lobby", "deadline": None, "g": None})
    elif action == "skip":
        if ph != "playing":
            raise Refuse("No turn to skip.")
        room["deadline"] = time.time() - 1
        tick(room)
    elif action == "kick":
        pid = b.get("pid")
        room["players"].pop(pid, None)
        room["wins"].pop(pid, None)
        g = room["g"]
        if g and pid in g["hands"]:
            g["deck"][:0] = g["hands"].pop(pid)  # their cards go back under the deck
            was, turn = g["order"].index(pid), g["turn"]
            g["order"].remove(pid)
            if g["exposed"] == pid:
                g["exposed"] = None
            if pid in g["called"]:
                g["called"].remove(pid)
            if ph == "playing":
                if len(g["order"]) < MIN_PLAYERS:
                    finish_round(room, g["order"][0]) if g["order"] else room.update({"phase": "lobby", "g": None})
                else:
                    if was < turn or (was == turn and g["dir"] == -1):
                        g["turn"] -= 1  # seats after them move up one; going backwards, the turn passes to the seat before
                    g["turn"] %= len(g["order"])
                    if was == turn:  # it was their turn: the next player starts fresh
                        g["drawn"] = None
                        set_timer(room)
    return True

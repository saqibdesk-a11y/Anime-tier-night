"""Fox's Bluff: a fast, tense festival bluffing game (Skull / Coasters style).

Every player starts with 4 festival coasters: 3 Sakura Blossoms (safe) and 1 Cursed Fox Mask (trap).
1. Place: everyone secretly places 1 coaster face-down in front of them.
2. Stack or Bid: on your turn, either add another coaster face-down onto your pile, OR start the
   bidding ("I can flip X safe blossoms!").
3. Bidding war: players raise the bid or pass until one Challenger remains.
4. The Flip: the Challenger MUST flip their own entire stack first, then pick other players' top
   coasters one by one. Flip X blossoms = +1 point (first to 2 points wins!). Flip a Fox = BOOM,
   lose a coaster permanently (out at 0 coasters)!"""
import random
import time

from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "settings", "next", "skip", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 2, 8


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    return {
        "goal": max(1, min(3, int(pick("goal", 2)))),  # wins needed
        "turnSec": max(0, min(60, int(pick("turnSec", 25)))),  # 0 = relaxed no timer
    }


def create(room, b):
    room.update({
        "game": "bluff", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "g": None,
    })


def on_join(room, pid):
    pass


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def alive(room):
    g = room.get("g")
    if not g:
        return []
    return [pid for pid in g["order"] if pid in room["players"] and len(g["deck"][pid]) > 0]


def total_placed(g):
    return sum(len(s) for s in g["stacks"].values())


def set_timer(room):
    sec = room["settings"]["turnSec"]
    room["deadline"] = (time.time() + sec + 1) if (sec and room["phase"] in ("place", "turn", "bid", "flip")) else None


def event(room, text):
    g = room["g"]
    g["log"].append({"id": rid(6), "text": text, "t": time.time()})
    del g["log"][:-15]


def start_match(room):
    pids = [pid for pid, p in room["players"].items() if not p.get("wantSitout")][:MAX_PLAYERS]
    if len(pids) < MIN_PLAYERS:
        pids = list(room["players"])[:MAX_PLAYERS]
    random.shuffle(pids)
    room["g"] = {
        "order": pids,
        "deck": {pid: ["flower", "flower", "flower", "fox"] for pid in pids},
        "points": {pid: 0 for pid in pids},
        "round": 0,
        "starter": pids[0],
        "hands": {}, "stacks": {}, "flipped": {},
        "turn": None, "bid": 0, "bidder": None, "passed": [],
        "flippedSafe": 0, "outcome": None, "winner": None, "log": [],
    }
    start_round(room, pids[0])


def start_round(room, starter):
    g = room["g"]
    al = alive(room)
    if len(al) == 1:
        g["winner"] = al[0]
        room["phase"] = "final"
        room["deadline"] = None
        return
    if starter not in al:
        starter = al[0]
    g["round"] += 1
    g["starter"] = starter
    g["hands"] = {pid: g["deck"][pid][:] for pid in al}
    g["stacks"] = {pid: [] for pid in al}
    g["flipped"] = {pid: [] for pid in al}
    g["turn"] = starter
    g["bid"] = 0
    g["bidder"] = None
    g["passed"] = []
    g["flippedSafe"] = 0
    g["outcome"] = None
    room["phase"] = "place"
    event(room, f"Round {g['round']} — everyone place 1 coaster face-down.")
    set_timer(room)


def next_seat(room, after_pid, skip_passed=False):
    g = room["g"]
    al = alive(room)
    if not al:
        return None
    start_i = al.index(after_pid) if after_pid in al else 0
    for offset in range(1, len(al) + 1):
        cand = al[(start_i + offset) % len(al)]
        if not skip_passed or cand not in g["passed"]:
            return cand
    return al[0]


def enter_flip(room):
    g = room["g"]
    room["phase"] = "flip"
    g["turn"] = g["bidder"]
    g["flippedSafe"] = 0
    event(room, f"{name(room, g['bidder'])} must flip {g['bid']} safe blossom{'s' if g['bid'] != 1 else ''}!")
    set_timer(room)


def end_round(room, success, fox_owner=None):
    g = room["g"]
    challenger = g["bidder"]
    if success:
        g["points"][challenger] = g["points"].get(challenger, 0) + 1
        g["outcome"] = {"win": True, "challenger": challenger, "bid": g["bid"]}
        event(room, f"{name(room, challenger)} flipped {g['bid']} blossoms and scored a point!")
        if g["points"][challenger] >= room["settings"]["goal"]:
            g["winner"] = challenger
            room["phase"] = "final"
            room["deadline"] = None
            return
        g["nextStarter"] = challenger
    else:
        lost = None
        if g["deck"].get(challenger):
            lost = random.choice(g["deck"][challenger])
            g["deck"][challenger].remove(lost)
        elim = len(g["deck"].get(challenger, [])) == 0
        g["outcome"] = {"win": False, "challenger": challenger, "foxOwner": fox_owner, "lost": lost, "eliminated": elim}
        who_fox = "their own Fox" if fox_owner == challenger else f"{name(room, fox_owner)}'s Fox"
        event(room, f"TRAP! {name(room, challenger)} hit {who_fox} and lost a coaster!" + (" Out of the match!" if elim else ""))
        al = alive(room)
        if len(al) == 1:
            g["winner"] = al[0]
            room["phase"] = "final"
            room["deadline"] = None
            return
        g["nextStarter"] = fox_owner if (fox_owner in al) else next_seat(room, challenger)
    room["phase"] = "roundover"
    room["deadline"] = time.time() + 7


def tick(room):
    now, ph = time.time(), room["phase"]
    g = room.get("g")
    if not g:
        return False
    over = room.get("deadline") and now >= room["deadline"]
    if ph == "place":
        al = alive(room)
        if all(len(g["stacks"].get(p, [])) >= 1 for p in al):
            room["phase"] = "turn"
            g["turn"] = g["starter"] if g["starter"] in al else al[0]
            set_timer(room)
            return True
        if over:
            for p in al:
                if not g["stacks"].get(p) and g["hands"].get(p):
                    card = random.choice(g["hands"][p])
                    g["hands"][p].remove(card)
                    g["stacks"][p].append(card)
            room["phase"] = "turn"
            g["turn"] = g["starter"] if g["starter"] in al else al[0]
            set_timer(room)
            return True
    elif ph == "turn" and over:
        pid = g["turn"]
        if g["hands"].get(pid):
            card = random.choice(g["hands"][pid])
            g["hands"][pid].remove(card)
            g["stacks"][pid].append(card)
            g["turn"] = next_seat(room, pid)
            set_timer(room)
        else:
            g["bid"], g["bidder"] = 1, pid
            if total_placed(g) <= 1:
                enter_flip(room)
            else:
                room["phase"] = "bid"
                g["turn"] = next_seat(room, pid, skip_passed=True)
                set_timer(room)
        return True
    elif ph == "bid" and over:
        pid = g["turn"]
        if pid not in g["passed"]:
            g["passed"].append(pid)
        active_bidders = [p for p in alive(room) if p not in g["passed"]]
        if len(active_bidders) <= 1:
            enter_flip(room)
        else:
            g["turn"] = next_seat(room, pid, skip_passed=True)
            set_timer(room)
        return True
    elif ph == "flip" and over:
        # auto-flip required own stack first, else random available stack
        pid = g["bidder"]
        own_left = len(g["stacks"].get(pid, [])) - len(g["flipped"].get(pid, []))
        target = pid if own_left > 0 else next((p for p in alive(room) if len(g["stacks"].get(p, [])) > len(g["flipped"].get(p, []))), None)
        if target:
            do_flip(room, target)
            return True
    elif ph == "roundover" and over:
        start_round(room, g.get("nextStarter") or g["starter"])
        return True
    return False


def do_flip(room, target):
    g = room["g"]
    stack = g["stacks"].get(target, [])
    fl = g["flipped"].setdefault(target, [])
    if len(fl) >= len(stack):
        raise Refuse("All coasters on that mat are already flipped.")
    # flip from the TOP of the stack down!
    card = stack[len(stack) - 1 - len(fl)]
    fl.append(card)
    if card == "fox":
        end_round(room, False, fox_owner=target)
    else:
        g["flippedSafe"] += 1
        if g["flippedSafe"] >= g["bid"]:
            end_round(room, True)
        else:
            set_timer(room)


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "g")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    g = room.get("g")
    if g:
        show_all = room["phase"] in ("roundover", "final")
        r["table"] = {
            "order": g["order"],
            "round": g["round"],
            "points": g["points"],
            "deckCount": {pid: len(d) for pid, d in g["deck"].items()},
            "handCount": {pid: len(h) for pid, h in g["hands"].items()},
            "stackCount": {pid: len(s) for pid, s in g["stacks"].items()},
            "flipped": g["flipped"],
            "allStacks": g["stacks"] if show_all else None,
            "totalPlaced": total_placed(g),
            "turn": g["turn"],
            "bid": g["bid"],
            "bidder": g["bidder"],
            "passed": g["passed"],
            "flippedSafe": g["flippedSafe"],
            "outcome": g["outcome"],
            "winner": g["winner"],
            "log": g["log"][-6:],
        }
        if viewer and viewer in g["hands"]:
            r["me"] = {
                "hand": g["hands"][viewer],
                "myStack": g["stacks"].get(viewer, []),
                "placed": len(g["stacks"].get(viewer, [])) >= 1,
                "ownUnflipped": len(g["stacks"].get(viewer, [])) - len(g["flipped"].get(viewer, [])),
            }
    return r


def player_action(room, action, b, pid):
    g, ph = room.get("g"), room["phase"]
    if not g or pid not in g["hands"]:
        raise Refuse("You're watching this match. You'll join the next one!", 409)
    if action == "place":
        if ph not in ("place", "turn"):
            raise Refuse("You can't place a coaster right now.", 409)
        if ph == "place" and len(g["stacks"][pid]) >= 1:
            raise Refuse("You already placed your starting coaster.", 409)
        if ph == "turn" and g["turn"] != pid:
            raise Refuse("Wait for your turn.", 409)
        card = str(b.get("card") or "")
        if card not in g["hands"][pid]:
            raise Refuse("You don't have that coaster left in your hand.")
        g["hands"][pid].remove(card)
        g["stacks"][pid].append(card)
        if ph == "place":
            if all(len(g["stacks"].get(p, [])) >= 1 for p in alive(room)):
                room["phase"] = "turn"
                event(room, f"All coasters down! {name(room, g['turn'])}'s turn to stack or bid.")
                set_timer(room)
        elif ph == "turn":
            event(room, f"{name(room, pid)} added a coaster face-down.")
            g["turn"] = next_seat(room, pid)
            set_timer(room)
        return True
    if action == "bid":
        if ph not in ("turn", "bid") or g["turn"] != pid:
            raise Refuse("Wait for your turn to bid.", 409)
        val = int(b.get("val", 0))
        mx = total_placed(g)
        if val <= g["bid"] or val > mx:
            raise Refuse(f"Bid between {g['bid'] + 1} and {mx}.")
        g["bid"], g["bidder"] = val, pid
        event(room, f"{name(room, pid)} bids {val} safe blossom{'s' if val != 1 else ''}!")
        if val >= mx or len([p for p in alive(room) if p not in g["passed"]]) <= 1:
            enter_flip(room)
        else:
            room["phase"] = "bid"
            g["turn"] = next_seat(room, pid, skip_passed=True)
            set_timer(room)
        return True
    if action == "pass":
        if ph != "bid" or g["turn"] != pid:
            raise Refuse("You can only pass during a bidding war.", 409)
        if pid == g["bidder"]:
            raise Refuse("You hold the highest bid—you can't pass!", 409)
        g["passed"].append(pid)
        event(room, f"{name(room, pid)} passed.")
        rem = [p for p in alive(room) if p not in g["passed"]]
        if len(rem) <= 1:
            enter_flip(room)
        else:
            g["turn"] = next_seat(room, pid, skip_passed=True)
            set_timer(room)
        return True
    if action == "flip":
        if ph != "flip" or g["bidder"] != pid:
            raise Refuse("Only the Challenger flips coasters.", 409)
        target = b.get("target")
        if target not in g["stacks"]:
            raise Refuse("Pick a stack to flip.")
        own_left = len(g["stacks"][pid]) - len(g["flipped"].get(pid, []))
        if own_left > 0 and target != pid:
            raise Refuse("You must flip all of your own coasters first!", 409)
        do_flip(room, target)
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the match starts.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action == "start":
        if ph != "lobby":
            raise Refuse("Match already started.")
        if len(room["players"]) < MIN_PLAYERS:
            raise Refuse(f"You need at least {MIN_PLAYERS} players.")
        start_match(room)
    elif action in ("next", "skip"):
        if ph == "roundover":
            start_round(room, room["g"].get("nextStarter") or room["g"]["starter"])
        elif ph in ("place", "turn", "bid", "flip"):
            room["deadline"] = time.time() - 1
            tick(room)
        else:
            raise Refuse("Nothing to skip.")
    elif action == "kick":
        pid = b.get("pid")
        room["players"].pop(pid, None)
        g = room.get("g")
        if g and pid in g["order"] and ph not in ("lobby", "final"):
            g["deck"][pid] = []
            al = alive(room)
            if len(al) <= 1:
                g["winner"] = al[0] if al else None
                room["phase"] = "final"
                room["deadline"] = None
            elif g["turn"] == pid or g["bidder"] == pid:
                start_round(room, al[0])
    elif action == "playagain":
        room.update({"phase": "lobby", "deadline": None, "g": None})
    return True

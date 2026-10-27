"""Werewolf: secret roles, night actions, day votes and a final reveal. The game moves on by
itself; the host only has shortcuts (more time, skip ahead, kick).

Roles: Werewolf, Seer (checks one player each night), Doctor (protects one player each night),
Hunter (shoots someone when they die) and Villager. Everyone taps something at night, so
nobody gives their role away by being the only one on their phone.

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import random
import time

from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "next", "skip", "addtime", "kick", "playagain", "settings")
ROLES = {
    "wolf": {"name": "Werewolf", "team": "wolves"},
    "seer": {"name": "Seer", "team": "village"},
    "doctor": {"name": "Doctor", "team": "village"},
    "hunter": {"name": "Hunter", "team": "village"},
    "villager": {"name": "Villager", "team": "village"},
}
ROLE_SEC = 75     # time to read your card before night falls anyway
REVEAL_SEC = 8    # how long a death or verdict stays on screen before the game moves on
HUNTER_SEC = 25


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def create(room, b):
    room.update({
        "game": "werewolf", "phase": "lobby", "day": 0, "deadline": None,
        "settings": clean_settings(b),
        "night": None, "votes": {}, "current": None, "events": [], "seerLog": [],
        "lastProtect": None, "hunter": None, "winner": None,
    })


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    return {
        "wolves": max(0, min(4, int(pick("wolves", 0) or 0))),  # 0 = pick for me
        "seer": bool(pick("seer", True)), "doctor": bool(pick("doctor", True)), "hunter": bool(pick("hunter", False)),
        "nightSec": max(20, min(180, int(pick("nightSec", 45)))),
        "daySec": max(30, min(600, int(pick("daySec", 120)))),
        "voteSec": max(20, min(180, int(pick("voteSec", 60)))),
    }


def on_join(room, pid):
    p = room["players"][pid]
    p.update({"role": None, "alive": room["phase"] == "lobby", "ready": False})
    if room["phase"] != "lobby":
        p["spectator"] = True  # joined mid-game: watches until the next game


# ---------- helpers ----------

def alive(room, role=None):
    return [pid for pid, p in room["players"].items() if p.get("alive") and (role is None or p.get("role") == role)]


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def role_name(room, pid):
    return ROLES[room["players"][pid]["role"]]["name"]


def wolf_count(room):
    n = len([p for p in room["players"].values() if not p.get("spectator")])
    w = room["settings"]["wolves"] or (1 if n <= 6 else 2 if n <= 10 else 3)
    return max(1, min(w, (n - 1) // 2))


def winner(room):
    wolves = len(alive(room, "wolf"))
    others = len(alive(room)) - wolves
    if wolves == 0:
        return "village"
    if wolves >= others:
        return "wolves"
    return None


def set_timer(room, secs):
    room["deadline"] = time.time() + secs + 2  # 2s for every screen to switch


# ---------- phases ----------

def assign_roles(room):
    pids = [pid for pid, p in room["players"].items() if not p.get("spectator")]
    random.shuffle(pids)
    s, roles = room["settings"], []
    roles += ["wolf"] * wolf_count(room)
    for r in ("seer", "doctor", "hunter"):
        if s[r] and len(roles) < len(pids) - 1:
            roles.append(r)
    roles += ["villager"] * (len(pids) - len(roles))
    random.shuffle(roles)
    for pid, role in zip(pids, roles):
        room["players"][pid].update({"role": role, "alive": True, "ready": False})
    room["phase"] = "roles"
    set_timer(room, ROLE_SEC)


def begin_night(room):
    room["day"] += 1
    room["phase"] = "night"
    room["night"] = {"wolf": {}, "doctor": None, "seer": None, "suspect": {}, "acted": []}
    room["current"] = None
    set_timer(room, room["settings"]["nightSec"])


def show_reveal(room, phase, current):
    room["phase"] = phase
    room["current"] = {"id": rid(6), **current}
    set_timer(room, REVEAL_SEC)


def resolve_night(room):
    n = room["night"]
    votes = [t for w, t in n["wolf"].items() if w in alive(room, "wolf") and t in alive(room)]
    victim = None
    if votes:
        counts = {t: votes.count(t) for t in votes}
        top = max(counts.values())
        victim = random.choice([t for t, c in counts.items() if c == top])
    saved = victim is not None and n["doctor"] == victim
    room["lastProtect"] = n["doctor"]
    dead = []
    if victim and not saved:
        room["players"][victim]["alive"] = False
        dead.append(victim)
    if dead:
        story = f"Dawn breaks. {name(room, dead[0])} was found at first light. They were the {role_name(room, dead[0])}."
        if room["players"][dead[0]]["role"] == "hunter":
            room["hunter"] = {"pid": dead[0], "then": "day"}
    elif saved:
        story = f"Claws in the dark, a scream, then silence. {name(room, victim)} wakes up shaken but alive. Someone was watching over them."
    else:
        story = "The night passes in an uneasy quiet. Nobody was taken."
    room["events"].append({"day": room["day"], "kind": "night", "dead": dead, "saved": saved, "target": victim if saved else None})
    show_reveal(room, "dawn", {"kind": "night", "dead": dead, "saved": saved, "story": story,
                               "roles": {pid: room["players"][pid]["role"] for pid in dead}})


def begin_day(room):
    room["phase"] = "day"
    room["votes"] = {}
    set_timer(room, room["settings"]["daySec"])


def begin_vote(room):
    room["phase"] = "vote"
    room["votes"] = {}
    set_timer(room, room["settings"]["voteSec"])


def resolve_vote(room):
    votes = {v: t for v, t in room["votes"].items() if v in alive(room)}
    tally = {}
    for t in votes.values():
        tally[t] = tally.get(t, 0) + 1
    top = max(tally.values()) if tally else 0
    leaders = [t for t, c in tally.items() if c == top]
    out = leaders[0] if len(leaders) == 1 and leaders[0] != "skip" and top > 0 else None
    if out:
        room["players"][out]["alive"] = False
        story = (f"The village has spoken. {name(room, out)} is cast out, and they were the {role_name(room, out)}."
                 + (" A wolf down!" if room["players"][out]["role"] == "wolf" else " Oops."))
        if room["players"][out]["role"] == "hunter":
            room["hunter"] = {"pid": out, "then": "night"}
    else:
        story = "Accusations fly, nobody agrees, and the sun sets on a very suspicious village."
    room["events"].append({"day": room["day"], "kind": "vote", "dead": [out] if out else []})
    show_reveal(room, "verdict", {"kind": "vote", "dead": [out] if out else [], "story": story, "tally": tally, "votes": votes,
                                  "roles": {out: room["players"][out]["role"]} if out else {}})


def begin_hunter(room):
    room["phase"] = "hunter"
    set_timer(room, HUNTER_SEC)


def resolve_hunter(room, target):
    h = room["hunter"]
    dead = []
    if target and target in alive(room):
        room["players"][target]["alive"] = False
        dead = [target]
        story = f"With their last breath, {name(room, h['pid'])} fires. {name(room, target)} falls. They were the {role_name(room, target)}."
    else:
        story = f"{name(room, h['pid'])} raises the crossbow... and the shot goes wide."
    room["events"].append({"day": room["day"], "kind": "hunter", "dead": dead})
    show_reveal(room, "shot", {"kind": "hunter", "dead": dead, "story": story, "shooter": h["pid"],
                               "roles": {t: room["players"][t]["role"] for t in dead}})


def after_reveal(room):
    """Leaving dawn, verdict or the hunter's shot: the hunter fires, or the game ends, or it goes on."""
    if room.get("hunter") and room["phase"] != "shot":
        begin_hunter(room)
        return
    then = (room.get("hunter") or {}).get("then") or ("day" if room["phase"] == "dawn" else "night")
    room["hunter"] = None
    w = winner(room)
    if w:
        room.update({"phase": "final", "winner": w, "deadline": None})
    elif then == "day":
        begin_day(room)
    else:
        begin_night(room)


def tick(room):
    """Called every second with the lock held. Returns True when the room changed."""
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now > room["deadline"]
    if ph == "roles":
        ps = [p for p in room["players"].values() if p.get("role")]
        if over or (ps and all(p.get("ready") for p in ps)):
            begin_night(room)
            return True
    elif ph == "night" and (over or set(alive(room)) <= set(room["night"]["acted"])):
        resolve_night(room)
        return True
    elif ph == "day" and over:
        begin_vote(room)
        return True
    elif ph == "vote" and (over or set(alive(room)) <= set(room["votes"])):
        resolve_vote(room)
        return True
    elif ph == "hunter" and over:
        resolve_hunter(room, None)
        return True
    elif ph in ("dawn", "verdict", "shot") and over:
        after_reveal(room)
        return True
    return False


# ---------- what each viewer sees ----------

def public(room, viewer):
    me = room["players"].get(viewer) if viewer else None
    my_role = me.get("role") if me else None
    ghost = bool(me) and me.get("role") and not me.get("alive")
    show_all = room["phase"] == "final" or ghost  # ghosts and the final screen see every role
    r = {k: v for k, v in room.items() if k not in ("hostKey", "night", "seerLog", "events", "lastProtect")}
    r["now"] = time.time()
    r["roleInfo"] = ROLES
    players = {}
    for pid, p in room["players"].items():
        q = {k: v for k, v in p.items() if k not in ("key", "role")}
        revealed = not p.get("alive") and p.get("role")  # the dead are revealed to everyone
        if pid == viewer or show_all or revealed or (my_role == "wolf" and p.get("role") == "wolf"):
            q["role"] = p.get("role")
        players[pid] = q
    r["players"] = players
    r["me"] = {"role": my_role, "alive": bool(me and me.get("alive")), "ghost": ghost}
    n = room.get("night")
    if room["phase"] == "night" and n:
        r["acted"] = len(set(n["acted"]))
        r["actNeed"] = len(alive(room))
        mine = {}
        if my_role == "wolf":
            mine["wolfVotes"] = dict(n["wolf"])
        if viewer in n["acted"]:
            mine["done"] = True
            mine["target"] = (n["wolf"].get(viewer) if my_role == "wolf" else n["doctor"] if my_role == "doctor"
                              else n["seer"] if my_role == "seer" else n["suspect"].get(viewer))
        if my_role == "doctor":
            mine["noRepeat"] = room.get("lastProtect")
        r["myNight"] = mine
    if my_role == "seer" or show_all:
        r["seerLog"] = room["seerLog"]
    if room["phase"] == "final":
        r["events"] = room["events"]  # the full story of the game for the final screen
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    p = room["players"][pid]
    if action == "ready":
        if room["phase"] != "roles":
            raise Refuse("Not now.")
        p["ready"] = True
        return True
    if action == "night":
        n, t = room["night"], b.get("target")
        if room["phase"] != "night" or not p.get("alive"):
            raise Refuse("You can't act right now.", 409)
        if t not in alive(room):
            raise Refuse("Pick someone who's still alive.")
        role = p["role"]
        if role == "wolf":
            if room["players"][t]["role"] == "wolf":
                raise Refuse("That's one of your pack.")
            n["wolf"][pid] = t  # wolves can keep changing their pick until the night ends
        elif role == "doctor":
            if t == room.get("lastProtect"):
                raise Refuse("You protected them last night. Pick someone else.")
            n["doctor"] = t
        elif role == "seer":
            if n["seer"]:
                raise Refuse("You already had your vision tonight.")
            if t == pid:
                raise Refuse("You already know yourself.")
            n["seer"] = t
            room["seerLog"].append({"night": room["day"], "pid": t, "name": name(room, t), "wolf": room["players"][t]["role"] == "wolf"})
        else:
            n["suspect"][pid] = t
        if pid not in n["acted"]:
            n["acted"].append(pid)
        return True
    if action == "vote":
        t = b.get("target")
        if room["phase"] != "vote" or not p.get("alive"):
            raise Refuse("You can't vote right now.", 409)
        if t != "skip" and t not in alive(room):
            raise Refuse("Pick someone who's still alive.")
        if t == pid:
            raise Refuse("You can't vote for yourself.")
        room["votes"][pid] = t
        return True
    if action == "shoot":
        h = room.get("hunter")
        if room["phase"] != "hunter" or not h or h["pid"] != pid:
            raise Refuse("Only the hunter can shoot now.", 409)
        if b.get("target") not in alive(room):
            raise Refuse("Pick someone who's still alive.")
        resolve_hunter(room, b["target"])
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
        n = len([p for p in room["players"].values() if not p.get("spectator")])
        if n < 4:
            raise Refuse(f"You need at least 4 players ({n} so far).")
        assign_roles(room)
    elif action in ("next", "skip"):
        # one "skip ahead" for every phase: end the current timer right now
        if ph == "roles":
            begin_night(room)
        elif ph == "night":
            resolve_night(room)
        elif ph == "day":
            begin_vote(room)
        elif ph == "vote":
            resolve_vote(room)
        elif ph == "hunter":
            resolve_hunter(room, None)
        elif ph in ("dawn", "verdict", "shot"):
            after_reveal(room)
        else:
            raise Refuse("Nothing to skip right now.")
    elif action == "addtime":
        if not room.get("deadline"):
            raise Refuse("No timer is running.")
        room["deadline"] += int(b.get("sec") or 30)
    elif action == "kick":
        room["players"].pop(b.get("pid"), None)
    elif action == "playagain":
        for p in room["players"].values():
            p.update({"role": None, "alive": True, "ready": False, "spectator": False})
        room.update({"phase": "lobby", "day": 0, "deadline": None, "night": None, "votes": {}, "current": None,
                     "events": [], "seerLog": [], "lastProtect": None, "hunter": None, "winner": None})
    return True

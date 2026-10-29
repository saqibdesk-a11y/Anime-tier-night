"""Werewolf with Plato-style roles, a built-in chat, and a game that moves on by itself.

Good: Villager, Seer (learns Good/Evil), Doctor (saves one player a night), Hunter (75% chance to
take a random Evil player down when killed at night), Knight (survives one night attack), Mayor
(double vote), Assassin (one night kill per game), Necromancer (revives one dead Good player, once),
Jester (counts as Good, also wins if they die; shows randomly as Good or Evil to the Seer).
Evil: Werewolf, Alpha Wolf (shows as Good to the Seer), Wolf Shaman (once, by day, shields another
Evil player from the vote), Siren (if voted out, Good abilities fail the next night).
Rules follow Plato's Werewolf (platoapp.com/en/games/werewolf).

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import random
import time

from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "next", "skip", "addtime", "kick", "playagain", "settings")
ROLES = {
    "wolf": {"name": "Werewolf", "team": "evil"},
    "alpha": {"name": "Alpha Wolf", "team": "evil"},
    "shaman": {"name": "Wolf Shaman", "team": "evil"},
    "siren": {"name": "Siren", "team": "evil"},
    "seer": {"name": "Seer", "team": "good"},
    "doctor": {"name": "Doctor", "team": "good"},
    "hunter": {"name": "Hunter", "team": "good"},
    "knight": {"name": "Knight", "team": "good"},
    "mayor": {"name": "Mayor", "team": "good"},
    "assassin": {"name": "Assassin", "team": "good"},
    "necro": {"name": "Necromancer", "team": "good"},
    "jester": {"name": "Jester", "team": "good"},
    "villager": {"name": "Villager", "team": "good"},
}
GOOD_SPECIALS = ("seer", "doctor", "hunter", "knight", "mayor", "assassin", "necro", "jester")
EVIL_SPECIALS = ("alpha", "shaman", "siren")
ROLE_SEC = 75     # time to read your card before night falls anyway
REVEAL_SEC = 9    # how long dawn or a verdict stays on screen before the game moves on
CHAT = {}         # room code -> recent messages; chat isn't saved, it's gone when the server restarts
CHAT_KEEP = 150


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def create(room, b):
    room.update({"game": "werewolf", "phase": "lobby", "day": 0, "deadline": None, "settings": clean_settings(b)})
    reset_game(room)


def reset_game(room):
    room.update({"night": None, "votes": {}, "current": None, "events": [], "seerLog": [], "winner": None,
                 "used": {}, "sirenNight": False, "shamanShield": None, "jesterWins": []})


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    s = {
        "wolves": max(0, min(5, int(pick("wolves", 0) or 0))),  # size of the Evil team; 0 = pick for me
        "nightSec": max(20, min(180, int(pick("nightSec", 45)))),
        "daySec": max(30, min(600, int(pick("daySec", 120)))),
        "voteSec": max(20, min(180, int(pick("voteSec", 60)))),
    }
    defaults = {"seer": True, "doctor": True}
    for r in GOOD_SPECIALS + EVIL_SPECIALS:
        s[r] = bool(pick(r, defaults.get(r, False)))
    return s


def on_join(room, pid):
    p = room["players"][pid]
    p.update({"role": None, "alive": room["phase"] == "lobby", "ready": False})
    if room["phase"] != "lobby":
        p["spectator"] = True  # joined mid-game: watches until the next game


# ---------- helpers ----------

def team(room, pid):
    return ROLES[room["players"][pid]["role"]]["team"]


def alive(room, team_=None):
    return [pid for pid, p in room["players"].items()
            if p.get("alive") and p.get("role") and (team_ is None or ROLES[p["role"]]["team"] == team_)]


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def role_name(room, pid):
    return ROLES[room["players"][pid]["role"]]["name"]


def evil_count(room):
    n = len([p for p in room["players"].values() if not p.get("spectator")])
    w = room["settings"]["wolves"] or (1 if n <= 6 else 2 if n <= 9 else 3 if n <= 12 else 4)
    return max(1, min(w, (n - 1) // 2))


def winner(room):
    evil = len(alive(room, "evil"))
    good = len(alive(room, "good"))
    if evil == 0:
        return "village"
    if evil >= good:
        return "wolves"
    return None


def set_timer(room, secs):
    room["deadline"] = time.time() + secs + 2  # 2s for every screen to switch


def has(room, pid, power):
    """True if this player still has a once-per-game power."""
    return not room["used"].get(f"{power}:{pid}")


# ---------- phases ----------

def assign_roles(room):
    pids = [pid for pid, p in room["players"].items() if not p.get("spectator")]
    random.shuffle(pids)
    s = room["settings"]
    k = evil_count(room)
    evil = [r for r in EVIL_SPECIALS if s[r]][:k]
    if "alpha" not in evil and len(evil) == k and k >= 1:
        evil = evil[:k - 1]  # always keep at least one killer who acts like a werewolf
    evil += ["wolf"] * (k - len(evil))
    good = [r for r in GOOD_SPECIALS if s[r]][:max(0, len(pids) - k)]
    roles = evil + good + ["villager"] * (len(pids) - len(evil) - len(good))
    random.shuffle(roles)
    for pid, role in zip(pids, roles):
        room["players"][pid].update({"role": role, "alive": True, "ready": False})
    reset_game(room)
    room["phase"] = "roles"
    set_timer(room, ROLE_SEC)


def begin_night(room):
    room["day"] += 1
    room["phase"] = "night"
    room["night"] = {"evil": {}, "doctor": None, "seer": None, "assassin": None, "necro": None, "suspect": {}, "acted": []}
    room["current"] = None
    set_timer(room, room["settings"]["nightSec"])


def show_reveal(room, phase, current):
    room["phase"] = phase
    room["current"] = {"id": rid(6), **current}
    set_timer(room, REVEAL_SEC)


def resolve_night(room):
    n, blocked = room["night"], room["sirenNight"]
    lines, dead, saved, survived = [], [], [], []
    # the Evil team's kill: their most-voted target; a split vote or no vote picks a random target
    votes = [t for e, t in n["evil"].items() if e in alive(room, "evil") and t in alive(room)]
    victim = None
    if votes:
        counts = {t: votes.count(t) for t in votes}
        top = max(counts.values())
        victim = random.choice([t for t, c in counts.items() if c == top])
    elif alive(room, "evil") and alive(room, "good"):
        victim = random.choice(alive(room, "good"))
    attacks = [victim] if victim else []
    if n["assassin"] and not blocked and n["assassin"] in alive(room):
        attacks.append(n["assassin"])
        room["used"][f"assassin:{n['assassinBy']}"] = True
    for t in dict.fromkeys(attacks):
        if n["doctor"] == t and not blocked:
            saved.append(t)
        elif room["players"][t]["role"] == "knight" and has(room, t, "shield") and not blocked:
            room["used"][f"shield:{t}"] = True
            survived.append(t)
        else:
            room["players"][t]["alive"] = False
            dead.append(t)
    # a Hunter killed at night has a 75% chance to take a random Evil player down too
    for h in [d for d in dead if room["players"][d]["role"] == "hunter"]:
        if not blocked and alive(room, "evil") and random.random() < .75:
            shot = random.choice(alive(room, "evil"))
            room["players"][shot]["alive"] = False
            dead.append(shot)
    revived = None
    if n["necro"] and not blocked:
        t = n["necro"]
        room["used"][f"revive:{n['necroBy']}"] = True  # used up even on an Evil corpse: roles are secret, so it's a gamble
        if not room["players"][t]["alive"] and team(room, t) == "good" and t not in dead:
            room["players"][t]["alive"] = True
            revived = t
    room["sirenNight"] = False
    for d in dead:
        if room["players"][d]["role"] == "jester":
            room["jesterWins"].append(d)
    if dead:
        lines.insert(0, "Dawn breaks. " + ", ".join(name(room, d) for d in dead)
                     + (" was" if len(dead) == 1 else " were") + " found at first light.")
    for s in survived:
        lines.append(f"{name(room, s)} survived being attacked by the evil team.")
    if saved:
        lines.append("Someone was attacked in the night, but the Doctor saved them.")
    if revived:
        lines.append(f"{name(room, revived)} rises from the dead!")
    if blocked:
        lines.append("The Siren's song still echoes. Nobody's powers worked last night.")
    if not dead and not survived and not saved and not revived:
        lines.append("The night passes in an uneasy quiet. Nobody was taken.")
    room["events"].append({"day": room["day"], "kind": "night", "dead": dead, "survived": survived, "saved": bool(saved), "revived": revived})
    show_reveal(room, "dawn", {"kind": "night", "dead": dead, "survived": survived, "revived": revived, "saved": bool(saved),
                               "story": " ".join(lines), "roles": {pid: room["players"][pid]["role"] for pid in dead}})


def begin_day(room):
    room["phase"] = "day"
    room["votes"] = {}
    room["shamanShield"] = None
    set_timer(room, room["settings"]["daySec"])


def begin_vote(room):
    room["phase"] = "vote"
    room["votes"] = {}
    set_timer(room, room["settings"]["voteSec"])


def vote_weight(room, pid):
    return 2 if room["players"][pid]["role"] == "mayor" else 1


def resolve_vote(room):
    votes = {v: t for v, t in room["votes"].items() if v in alive(room)}
    tally = {}
    for v, t in votes.items():
        tally[t] = tally.get(t, 0) + vote_weight(room, v)
    top = max(tally.values()) if tally else 0
    leaders = [t for t, c in tally.items() if c == top]
    out = leaders[0] if len(leaders) == 1 and leaders[0] != "skip" and top > 0 else None
    dead = []
    if out and out == room.get("shamanShield"):
        story = f"The village points at {name(room, out)}... but a dark charm protects them. They survive the vote!"
    elif out:
        room["players"][out]["alive"] = False
        dead = [out]
        story = f"The village has spoken. {name(room, out)} is cast out. Their role stays a secret until the game ends."
        role = room["players"][out]["role"]
        if role == "siren":
            room["sirenNight"] = True
        elif role == "jester":
            room["jesterWins"].append(out)
    else:
        story = "Accusations fly, nobody agrees, and the sun sets on a very suspicious village."
    room["events"].append({"day": room["day"], "kind": "vote", "dead": dead, "shielded": out if out and not dead else None})
    show_reveal(room, "verdict", {"kind": "vote", "dead": dead, "story": story, "tally": tally, "votes": votes,
                                  "roles": {d: room["players"][d]["role"] for d in dead}})


def after_reveal(room):
    w = winner(room)
    if w:
        room.update({"phase": "final", "winner": w, "deadline": None})
    elif room["phase"] == "dawn":
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
    elif ph in ("dawn", "verdict") and over:
        after_reveal(room)
        return True
    return False


# ---------- chat ----------

def channels(room, pid):
    """(can read, can write) for a player. All: everyone. Evil: the evil team's private channel.
    Ghosts: the dead and spectators, who can't talk to the living."""
    p = room["players"].get(pid)
    if not p:
        return set(), set()
    if room["phase"] in ("lobby", "final") or not p.get("role"):
        read = {"all"} | ({"ghosts"} if room["phase"] not in ("lobby", "final") else set())
        return read, ({"all"} if room["phase"] in ("lobby", "final") else {"ghosts"})
    if not p.get("alive"):
        return {"all", "ghosts"}, {"ghosts"}
    read = {"all"}
    write = set() if room["phase"] == "night" else {"all"}  # the village sleeps: no public talk at night
    if ROLES[p["role"]]["team"] == "evil":
        read.add("evil")
        write.add("evil")
    return read, write


# ---------- what each viewer sees ----------

def public(room, viewer):
    me = room["players"].get(viewer) if viewer else None
    my_role = me.get("role") if me else None
    my_team = ROLES[my_role]["team"] if my_role else None
    ghost = bool(me) and bool(my_role) and not me.get("alive")
    show_all = room["phase"] == "final" or ghost  # ghosts and the final screen see every role
    r = {k: v for k, v in room.items() if k not in ("hostKey", "night", "seerLog", "events", "used", "shamanShield", "sirenNight")}
    r["now"] = time.time()
    r["roleInfo"] = ROLES
    players = {}
    for pid, p in room["players"].items():
        q = {k: v for k, v in p.items() if k not in ("key", "role")}
        # roles stay hidden after death; only ghosts, the final screen and the evil team (for each other) see them
        if pid == viewer or show_all or (my_team == "evil" and p.get("role") and ROLES[p["role"]]["team"] == "evil"):
            q["role"] = p.get("role")
        players[pid] = q
    r["players"] = players
    cur = room.get("current")
    if cur and cur.get("roles"):
        r["current"] = {**cur, "roles": {d: players[d].get("role") for d in cur["roles"] if d in players}}
    powers = {}
    if my_role:
        powers = {"assassin": my_role == "assassin" and has(room, viewer, "assassin"),
                  "revive": my_role == "necro" and has(room, viewer, "revive"),
                  "shield": my_role == "knight" and has(room, viewer, "shield"),
                  "shamanShield": my_role == "shaman" and has(room, viewer, "shaman")}
    r["me"] = {"role": my_role, "team": my_team, "alive": bool(me and me.get("alive")), "ghost": ghost, "powers": powers}
    n = room.get("night")
    if room["phase"] == "night" and n:
        r["acted"] = len(set(n["acted"]))
        r["actNeed"] = len(alive(room))
        mine = {"blocked": room["sirenNight"] and my_team == "good" and my_role not in ("villager",)}
        if my_team == "evil":
            mine["evilVotes"] = dict(n["evil"])
        if viewer in n["acted"]:
            mine["done"] = True
            mine["target"] = (n["evil"].get(viewer) if my_team == "evil" else n["doctor"] if my_role == "doctor"
                              else n["seer"] if my_role == "seer" else n["assassin"] if my_role == "assassin"
                              else n["necro"] if my_role == "necro" else n["suspect"].get(viewer))
        r["myNight"] = mine
    if my_role == "shaman" and room["phase"] in ("day", "vote"):
        r["myShield"] = room.get("shamanShield")
    if my_role == "seer" or show_all:
        r["seerLog"] = room["seerLog"]
    if room["phase"] == "final":
        r["events"] = room["events"]
    read, write = channels(room, viewer) if viewer else ({"all"}, set())
    r["chat"] = [m for m in CHAT.get(room["code"], []) if m["ch"] in read][-100:]
    r["chatRead"], r["chatWrite"] = sorted(read), sorted(write)
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    p = room["players"][pid]
    if action == "chat":
        ch, text = b.get("ch") or "all", " ".join(str(b.get("text") or "").split())[:300]
        if not text:
            raise Refuse("Type a message first.")
        if ch not in channels(room, pid)[1]:
            if ch == "all" and p.get("role") and not p.get("alive") and room["phase"] not in ("lobby", "final"):
                raise Refuse("Ghosts can't talk to the living. Use the Ghosts chat.", 409)
            raise Refuse({"all": "The village is asleep. No public talking at night.", "evil": "Only the evil team can talk there.",
                          "ghosts": "Only ghosts can talk there."}.get(ch, "You can't talk there right now."), 409)
        log = CHAT.setdefault(room["code"], [])
        log.append({"id": rid(8), "ch": ch, "pid": pid, "name": p["name"], "text": text, "t": time.time()})
        del log[:-CHAT_KEEP]
        return True
    if action == "ready":
        if room["phase"] != "roles":
            raise Refuse("Not now.")
        p["ready"] = True
        return True
    if action == "night":
        return night_action(room, p, pid, b)
    if action == "shamanshield":
        if p.get("role") != "shaman" or not p.get("alive") or room["phase"] not in ("day", "vote"):
            raise Refuse("You can't do that now.", 409)
        if not has(room, pid, "shaman"):
            raise Refuse("You already used your protection.")
        t = b.get("target")
        if t == pid or t not in alive(room, "evil"):
            raise Refuse("Pick another member of the evil team.")
        room["shamanShield"] = t
        room["used"][f"shaman:{pid}"] = True
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
    raise Refuse("Unknown action")


def night_action(room, p, pid, b):
    n, t, role = room["night"], b.get("target"), p.get("role")
    if room["phase"] != "night" or not p.get("alive"):
        raise Refuse("You can't act right now.", 409)
    blocked = room["sirenNight"] and ROLES[role]["team"] == "good"
    power = role in ("doctor", "seer", "assassin", "necro") and not blocked
    if t == "pass":
        if role not in ("assassin", "necro"):
            raise Refuse("Pick someone.")
        n[role] = None  # changed their mind: no kill or revival tonight
    elif role == "necro" and power and has(room, pid, "revive") and t in room["players"] and not room["players"][t].get("alive"):
        if not room["players"][t].get("role"):
            raise Refuse("They weren't in this game.")
        n["necro"], n["necroBy"] = t, pid
    elif t not in alive(room):
        raise Refuse("The Siren's song blocks your power tonight. Pick a suspect instead." if blocked and role == "necro"
                     else "Pick someone who's still alive.")
    elif ROLES[role]["team"] == "evil":
        if team(room, t) == "evil":
            raise Refuse("That's one of your team.")
        n["evil"][pid] = t  # the evil team can keep changing their pick until the night ends
    elif role == "doctor" and power:
        n["doctor"] = t
    elif role == "seer" and power:
        if n["seer"]:
            raise Refuse("You already had your vision tonight.")
        if t == pid:
            raise Refuse("You already know yourself.")
        n["seer"] = t
        tr = room["players"][t]["role"]
        # the Alpha Wolf shows as Good, the Jester randomly as Good or Evil
        evil = False if tr == "alpha" else random.random() < .5 if tr == "jester" else ROLES[tr]["team"] == "evil"
        room["seerLog"].append({"night": room["day"], "pid": t, "name": name(room, t), "evil": evil})
    elif role == "assassin" and power and has(room, pid, "assassin"):
        if t == pid:
            raise Refuse("You can't target yourself.")
        n["assassin"], n["assassinBy"] = t, pid
    else:
        n["suspect"][pid] = t  # everyone else (and a blocked power) just picks a suspect, so nobody stands out
    if pid not in n["acted"]:
        n["acted"].append(pid)
    return True


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
        elif ph in ("dawn", "verdict"):
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
        room.update({"phase": "lobby", "day": 0, "deadline": None})
        reset_game(room)
    return True

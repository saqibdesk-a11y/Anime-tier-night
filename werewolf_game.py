"""Werewolf: secret roles, night actions, an AI narrator, day votes and a final reveal.

Roles: Werewolf, Seer (checks one player each night), Doctor (protects one player each night),
Hunter (shoots someone when they die) and Villager. Everyone taps something at night, so
nobody gives their role away by being the only one on their phone.

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import base64
import random
import threading
import time

import ai
from media import IMAGES, Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "next", "skip", "addtime", "kick", "playagain", "settings")
ROLES = {
    "wolf": {"name": "Werewolf", "team": "wolves"},
    "seer": {"name": "Seer", "team": "village"},
    "doctor": {"name": "Doctor", "team": "village"},
    "hunter": {"name": "Hunter", "team": "village"},
    "villager": {"name": "Villager", "team": "village"},
}
SETTINGS = {
    "classic": "a foggy medieval village surrounded by dark woods",
    "ninja": "a hidden ninja village in the mountains, anime style",
    "school": "a Japanese high school where students stay overnight for a festival, anime style",
    "space": "a space station drifting far from Earth, where the wolves are shapeshifting aliens",
    "pirate": "a pirate ship lost at sea, where the wolves are cursed crew members",
}
SPICE = {
    "wholesome": "Keep it playful and warm.",
    "spicy": "Be dramatic and funny, with a bit of roast.",
    "unhinged": "Go full chaotic: over-the-top drama and savage jokes, never cruel about real people.",
}
MAX_PHOTO = 350_000


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def create(room, b):
    room.update({
        "game": "werewolf", "phase": "lobby", "day": 0, "deadline": None,
        "settings": clean_settings(b),
        "night": None, "votes": {}, "current": None, "events": [], "seerLog": [],
        "lastProtect": None, "hunter": None, "winner": None, "epilogue": None,
    })


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    setting = pick("setting", "ninja")
    return {
        "wolves": max(0, min(4, int(pick("wolves", 0) or 0))),  # 0 = pick for me
        "seer": bool(pick("seer", True)), "doctor": bool(pick("doctor", True)), "hunter": bool(pick("hunter", False)),
        "nightSec": max(20, min(180, int(pick("nightSec", 45)))),
        "daySec": max(30, min(600, int(pick("daySec", 120)))),
        "voteSec": max(20, min(180, int(pick("voteSec", 60)))),
        "setting": setting if setting in SETTINGS or setting == "custom" else "ninja",
        "custom": str(pick("custom", "")).strip()[:200],
        "spice": pick("spice", "spicy") if pick("spice", "spicy") in SPICE else "spicy",
    }


def on_join(room, pid):
    p = room["players"][pid]
    p.update({"photo": None, "role": None, "alive": room["phase"] == "lobby", "ready": False})
    if room["phase"] != "lobby":
        p["spectator"] = True  # joined mid-game: watches until the next game


# ---------- helpers ----------

def alive(room, role=None):
    return [pid for pid, p in room["players"].items() if p.get("alive") and (role is None or p.get("role") == role)]


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def wolf_count(room):
    n = len([p for p in room["players"].values() if not p.get("spectator")])
    w = room["settings"]["wolves"] or (1 if n <= 6 else 2 if n <= 10 else 3)
    return max(1, min(w, (n - 1) // 2))


def setting_text(room):
    s = room["settings"]
    return s["custom"] if s["setting"] == "custom" and s["custom"] else SETTINGS.get(s["setting"], SETTINGS["classic"])


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


# ---------- AI narrator (text only, so it prefers the fast text AIs) ----------

def narrate(code, key, system, prompt, fallback, cid):
    """Fills room['current'][key] with the AI's line, or the fallback if the AI fails."""
    try:
        out, _, _ = ai.ask_builtin(system, prompt, timeout=25, text_first=True)
        text = str(out.get("story") or out.get("text") or "").strip()[:900] or fallback
        awards = out.get("awards")
    except ai.AIError:
        text, awards = fallback, None
    with lock:
        room = rooms.get(code)
        if not room:
            return
        if key == "epilogue":
            room["epilogue"] = {"text": text, "awards": clean_awards(room, awards)}
        elif (room.get("current") or {}).get("id") == cid:  # the host may already have moved on
            room["current"]["story"] = text
        changed(room)


def clean_awards(room, awards):
    names = {p["name"].lower(): p["name"] for p in room["players"].values()}
    out = []
    for a in awards or []:
        if isinstance(a, dict) and str(a.get("name", "")).lower() in names:
            out.append({"name": names[str(a["name"]).lower()], "award": str(a.get("award") or "")[:60]})
    return out[:12]


def narrator_system(room):
    return ("You are the narrator of a Werewolf party game played by friends on their phones, read aloud to the group. "
            f"The story takes place in {setting_text(room)}. {SPICE[room['settings']['spice']]} "
            "Write vivid, short, punchy narration (2-4 sentences). Never reveal anyone's secret role unless told it is revealed. "
            'Return only JSON: {"story": "..."}')


def start_narration(room, key, prompt, fallback):
    cid = (room.get("current") or {}).get("id")
    threading.Thread(target=narrate, args=(room["code"], key, narrator_system(room), prompt, fallback, cid), daemon=True).start()


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


def begin_night(room):
    room["day"] += 1
    room["phase"] = "night"
    room["night"] = {"wolf": {}, "doctor": None, "seer": None, "suspect": {}, "acted": []}
    room["current"] = None
    set_timer(room, room["settings"]["nightSec"])


def night_needs(room):
    return set(alive(room))


def resolve_night(room):
    n, room["deadline"] = room["night"], None
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
    suspects = list(n["suspect"].values())
    most = max(set(suspects), key=suspects.count) if suspects else None
    room["current"] = {"id": rid(6), "kind": "night", "dead": dead, "saved": saved, "story": None,
                       "roles": {pid: room["players"][pid]["role"] for pid in dead}}
    room["events"].append({"day": room["day"], "kind": "night", "dead": dead, "saved": saved,
                           "suspected": most and name(room, most)})
    room["phase"] = "dawn"
    if dead:
        v = dead[0]
        prompt = (f"Night {room['day']}: the werewolves attacked {name(room, v)}, who did not survive. "
                  f"Their role is now revealed: they were the {ROLES[room['players'][v]['role']]['name']}. "
                  f"{len(alive(room))} players are still alive. Narrate the village discovering what happened.")
        fallback = f"Dawn breaks. {name(room, v)} was found at first light, and the village gasps. They were the {ROLES[room['players'][v]['role']]['name']}."
    elif saved:
        prompt = (f"Night {room['day']}: the werewolves attacked {name(room, victim)}, but a mysterious healer saved them. "
                  "Do not say who the healer is. Narrate a close call.")
        fallback = f"Claws in the dark, a scream, and then... silence. {name(room, victim)} wakes up shaken but alive. Someone was watching over them."
    else:
        prompt = f"Night {room['day']}: the werewolves could not agree and nobody was attacked. Narrate an eerie, quiet night."
        fallback = "The night passes in an uneasy quiet. Nobody was taken. The wolves must be getting careless... or patient."
    if dead and room["players"][dead[0]]["role"] == "hunter":
        room["hunter"] = {"pid": dead[0], "then": "day"}
    start_narration(room, "story", prompt, fallback)


def begin_day(room):
    room["phase"] = "day"
    room["votes"] = {}
    set_timer(room, room["settings"]["daySec"])


def begin_vote(room):
    room["phase"] = "vote"
    room["votes"] = {}
    set_timer(room, room["settings"]["voteSec"])


def resolve_vote(room):
    room["deadline"] = None
    votes = {v: t for v, t in room["votes"].items() if v in alive(room)}
    tally = {}
    for t in votes.values():
        tally[t] = tally.get(t, 0) + 1
    top = max(tally.values()) if tally else 0
    leaders = [t for t, c in tally.items() if c == top]
    out = leaders[0] if len(leaders) == 1 and leaders[0] != "skip" and top > 0 else None
    if out:
        room["players"][out]["alive"] = False
    room["current"] = {"id": rid(6), "kind": "vote", "dead": [out] if out else [], "story": None, "tally": tally, "votes": votes,
                       "roles": {out: room["players"][out]["role"]} if out else {}}
    room["events"].append({"day": room["day"], "kind": "vote", "dead": [out] if out else [], "tally": {name(room, k) if k != "skip" else "skip": v for k, v in tally.items()}})
    room["phase"] = "verdict"
    if out:
        role = ROLES[room["players"][out]["role"]]["name"]
        prompt = (f"Day {room['day']}: the village voted out {name(room, out)} ({top} votes). "
                  f"Their role is revealed: they were the {role}. "
                  + ("The village got a werewolf! " if room["players"][out]["role"] == "wolf" else "They were innocent. Oops. ")
                  + "Narrate the verdict in 2-3 sentences.")
        fallback = f"The village has spoken. {name(room, out)} is cast out... and they were the {role}."
        if room["players"][out]["role"] == "hunter":
            room["hunter"] = {"pid": out, "then": "night"}
    else:
        prompt = f"Day {room['day']}: the village argued but could not agree on anyone, so nobody was voted out. Narrate it in 2 sentences."
        fallback = "Accusations fly, nobody agrees, and the sun sets on a very suspicious village."
    start_narration(room, "story", prompt, fallback)


def begin_hunter(room):
    room["phase"] = "hunter"
    set_timer(room, 30)


def resolve_hunter(room, target):
    h = room["hunter"]
    room["deadline"] = None
    dead = []
    if target and target in alive(room):
        room["players"][target]["alive"] = False
        dead = [target]
    room["current"] = {"id": rid(6), "kind": "hunter", "dead": dead, "story": None, "shooter": h["pid"],
                       "roles": {t: room["players"][t]["role"] for t in dead}}
    room["events"].append({"day": room["day"], "kind": "hunter", "dead": dead})
    room["phase"] = "shot"
    if dead:
        role = ROLES[room["players"][dead[0]]["role"]]["name"]
        start_narration(room, "story", f"The dying Hunter, {name(room, h['pid'])}, fires one last shot and takes down "
                        f"{name(room, dead[0])}, who was the {role}. Narrate it in 2 sentences.",
                        f"With their last breath, {name(room, h['pid'])} fires. {name(room, dead[0])} falls. They were the {role}.")
    else:
        room["current"]["story"] = f"{name(room, h['pid'])} raises the crossbow... and the shot goes wide."


def after_reveal(room):
    """Leaving dawn, verdict or the hunter's shot: the hunter fires, or the game ends, or it goes on."""
    if room.get("hunter") and room["phase"] != "shot":
        begin_hunter(room)
        return
    then = (room.get("hunter") or {}).get("then") or ("day" if room["phase"] == "dawn" else "night")
    room["hunter"] = None
    w = winner(room)
    if w:
        finish(room, w)
    elif then == "day":
        begin_day(room)
    else:
        begin_night(room)


def finish(room, w):
    room["phase"] = "final"
    room["winner"] = w
    room["deadline"] = None
    room["epilogue"] = None
    roles = ", ".join(f"{p['name']} ({ROLES[p['role']]['name']}, {'survived' if p['alive'] else 'died'})"
                      for p in room["players"].values() if p.get("role"))
    log = []
    for e in room["events"]:
        who = ", ".join(name(room, d) for d in e["dead"]) or "nobody"
        if e["kind"] == "night":
            log.append(f"Night {e['day']}: wolves took {who}{' (but the doctor saved the target)' if e['saved'] else ''}. Most villagers suspected {e.get('suspected') or 'nobody'}.")
        elif e["kind"] == "vote":
            log.append(f"Day {e['day']}: the vote took out {who}. Votes: {e.get('tally')}.")
        else:
            log.append(f"The hunter shot {who}.")
    seer = "; ".join(f"night {s['night']} checked {s['name']} ({'wolf' if s['wolf'] else 'not a wolf'})" for s in room["seerLog"])
    prompt = (f"The game is over and the {'werewolves' if w == 'wolves' else 'village'} won. Everyone's roles: {roles}. "
              f"What happened: {' '.join(log)} Seer findings: {seer or 'none'}. "
              "Write a funny epilogue (3-5 sentences) that roasts the best liar and the worst detective by name, then give "
              "each player one funny award. Return only JSON: "
              '{"story": "...", "awards": [{"name": "<player name>", "award": "<2-5 words>"}]}')
    fallback = ("The wolves feast tonight. The village never stood a chance." if w == "wolves"
                else "The last wolf is gone and the village finally sleeps in peace.")
    start_narration(room, "epilogue", prompt, fallback)


def tick(room):
    """Called every second with the lock held. Returns True when the room changed."""
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now > room["deadline"]
    if ph == "roles":
        ps = [p for p in room["players"].values() if p.get("role")]
        if ps and all(p.get("ready") for p in ps):
            begin_night(room)
            return True
    elif ph == "night" and (over or night_needs(room) <= set(room["night"]["acted"])):
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
        r["actNeed"] = len(night_needs(room))
        mine = {}
        if my_role == "wolf":
            mine["wolfVotes"] = {w: t for w, t in n["wolf"].items()}
        if viewer in n["acted"]:
            mine["done"] = True
            mine["target"] = (n["wolf"].get(viewer) if my_role == "wolf" else n["doctor"] if my_role == "doctor"
                              else n["seer"] if my_role == "seer" else n["suspect"].get(viewer))
        if my_role == "doctor":
            mine["noRepeat"] = room.get("lastProtect")
        r["myNight"] = mine
    if my_role == "seer" or show_all:
        r["seerLog"] = room["seerLog"]
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    p = room["players"][pid]
    if action == "photo":
        img = str(b.get("img") or "")
        if not img.startswith("data:image/jpeg;base64,"):
            raise Refuse("That photo didn't upload. Try another one.")
        raw = base64.b64decode(img.split(",", 1)[1])
        if len(raw) > MAX_PHOTO:
            raise Refuse("That photo is too big.")
        IMAGES.pop(p.get("photo"), None)
        p["photo"] = rid(12)
        IMAGES[p["photo"]] = raw
        return True
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
        room["phase"] = "roles"
    elif action == "next":
        if ph == "roles":
            begin_night(room)
        elif ph in ("dawn", "verdict", "shot"):
            after_reveal(room)
        elif ph == "day":
            begin_vote(room)
        else:
            raise Refuse("Nothing to move on from right now.")
    elif action == "skip":
        if ph == "night":
            resolve_night(room)
        elif ph == "vote":
            resolve_vote(room)
        elif ph == "day":
            begin_vote(room)
        elif ph == "hunter":
            resolve_hunter(room, None)
        else:
            raise Refuse("No timer to skip.")
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
                     "events": [], "seerLog": [], "lastProtect": None, "hunter": None, "winner": None, "epilogue": None})
    return True

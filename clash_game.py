"""Caption Clash: Quiplash / Jackbox-style head-to-head comedy battles.

Each round, every player gets 2 prompts paired head-to-head against different rivals.
Everyone writes their funniest answer simultaneously, then the room votes one matchup at a time!
Unanimous wins earn a +250 SWEEP bonus, the final round is Double Points, and the AI roasts every
battle!"""
import random
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "settings", "next", "skip", "addtime", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 2, 10

PROMPTS = {
    "anime": [
        "What Gojo's search history actually looks like",
        "The real reason Zoro was 3 hours late to the wedding",
        "Worst thing to yell right before unlocking your final form",
        "A terrible name for an isekai anime",
        "What Pikachu is actually screaming when he says 'Pika Pika'",
        "The most useless Devil Fruit power imaginable",
        "What Levi saw in Eren's bedroom that made him snap",
        "A rejected Hokage campaign slogan",
        "What Goku puts on his resume under 'Special Skills'",
        "The worst anime character to have as your Uber driver",
        "What Ryuk writes in his diary about Light",
        "An anime training arc that would definitely get you arrested",
        "The secret ingredient in Ichiraku Ramen",
        "What Saitama actually thinks about during a boss fight",
        "Worst advice an anime mentor could ever give",
        "The real reason the tournament arc got cancelled",
        "What Luffy would do with a million dollars in 10 minutes",
        "A suspiciously specific filler episode title",
    ],
    "party": [
        "Worst thing to hear from your pilot mid-flight",
        "An honest slogan for your friend group's Discord server",
        "The worst excuse for missing work on Monday",
        "Something you should never whisper at a wedding",
        "A terrible theme for a 5-star restaurant",
        "What aliens report back after spying on humanity for 5 minutes",
        "The worst superpower to get stuck with forever",
        "What your phone would say if it could roast you",
        "The fastest way to ruin a family dinner",
        "An aggressively honest warning label for energy drinks",
        "What ghosts actually do when nobody is looking",
        "Worst thing to accidentally type in the wrong group chat",
        "A terrible idea for a new Olympic sport",
        "What your browser tabs say about your mental state",
        "The real reason dinosaurs went extinct",
        "Something you definitely shouldn't bring to a job interview",
        "A brutally honest fortune cookie message",
        "Worst thing to shout during a quiet exam",
    ],
}
PROMPTS["mix"] = PROMPTS["anime"] + PROMPTS["party"]

SPICE = {
    "wholesome": "Keep it playful and hype both jokes like a fun comedy host.",
    "spicy": "Roast the losing answer sharply and hype the winner like a ruthless comedy club MC.",
    "unhinged": "Go chaotic and savage on the losing joke like a Discord VC roast battle. Never attack real-world identity.",
}


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    pack = pick("pack", "mix")
    if pack not in ("mix", "anime", "party", "custom"):
        pack = "mix"
    return {
        "pack": pack,
        "custom": str(pick("custom", "")).strip()[:160],
        "rounds": max(1, min(5, int(pick("rounds", 3)))),
        "writeSec": max(30, min(120, int(pick("writeSec", 60)))),
        "voteSec": max(15, min(60, int(pick("voteSec", 25)))),
        "spice": pick("spice", "spicy") if pick("spice", "spicy") in SPICE else "spicy",
    }


def create(room, b):
    room.update({
        "game": "clash", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "prompts": [], "round": -1, "matchups": [], "matchIdx": 0, "scores": {},
    })


def on_join(room, pid):
    room["scores"].setdefault(pid, 0)
    room["players"][pid]["sitout"] = room["phase"] != "lobby"


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def active_pids(room):
    act = [pid for pid, p in room["players"].items() if not p.get("wantSitout")]
    return act if len(act) >= MIN_PLAYERS else list(room["players"])


def build_prompts(settings, need):
    out = []
    if settings["pack"] == "custom" and settings["custom"]:
        try:
            res, _, _ = ai.ask_builtin(
                "You write hilarious Quiplash-style fill-in comedy prompts for friends.",
                f"Write {need + 4} funny, open-ended comedy prompts about: {settings['custom']}. "
                "Short (under 90 chars), punchy, easy to answer with a 1-line joke. "
                'Return only JSON: {"prompts":["...",...]}', timeout=25, text_first=True)
            out = [str(x).strip()[:110] for x in (res.get("prompts") or []) if str(x).strip()]
        except (ai.AIError, ValueError, TypeError, AttributeError):
            pass
    pool = PROMPTS.get(settings["pack"], PROMPTS["mix"])[:]
    random.shuffle(pool)
    for p in pool:
        if len(out) >= need + 4:
            break
        if p not in out:
            out.append(p)
    random.shuffle(out)
    return out


def begin_game(code):
    with lock:
        room = rooms.get(code)
        settings = dict(room["settings"]) if room else None
        n_est = max(4, len(room["players"])) if room else 4
    if not settings:
        return
    prompts = build_prompts(settings, n_est * settings["rounds"] + 6)
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            room["prompts"] = prompts
            room["scores"] = {pid: 0 for pid in room["players"]}
            start_round(room, 0)
            changed(room)


def start_round(room, rnd):
    pids = active_pids(room)[:MAX_PLAYERS]
    for pid in room["players"]:
        room["players"][pid]["sitout"] = pid not in pids
    random.shuffle(pids)
    room["round"] = rnd
    room["matchIdx"] = 0
    mult = 2 if (room["settings"]["rounds"] > 1 and rnd == room["settings"]["rounds"] - 1) else 1
    matchups = []
    if len(pids) == 2:
        pairs = [(pids[0], pids[1]), (pids[1], pids[0])]
    else:
        # Every player gets exactly 2 prompts against 2 different opponents (works for odd & even counts!)
        pairs = [(pids[i], pids[(i + 1) % len(pids)]) for i in range(len(pids))]
    for a, b in pairs:
        prompt_txt = room["prompts"].pop(0) if room["prompts"] else random.choice(PROMPTS["mix"])
        matchups.append({
            "id": rid(6), "prompt": prompt_txt, "pair": [a, b], "mult": mult,
            "answers": {}, "votes": {}, "points": {}, "sweep": None, "ai": None, "aiId": None,
        })
    room["matchups"] = matchups
    room["phase"] = "write"
    room["deadline"] = time.time() + room["settings"]["writeSec"] + 1


def all_written(room):
    for m in room["matchups"]:
        for pid in m["pair"]:
            if pid in room["players"] and pid not in m["answers"]:
                return False
    return True


def begin_vote(room, idx):
    room["matchIdx"] = idx
    m = room["matchups"][idx]
    for pid in m["pair"]:
        m["answers"].setdefault(pid, "(stared blankly at the mic)")
    room["phase"] = "vote"
    room["deadline"] = time.time() + room["settings"]["voteSec"] + 1


def eligible_voters(room, m):
    # Everyone in the room NOT in this matchup votes (in a 2-player game, nobody votes -> quick tie/AI roast)
    return [pid for pid in room["players"] if pid not in m["pair"]]


def roast_matchup(code, mid, cid):
    with lock:
        room = rooms.get(code)
        m = next((x for x in (room or {}).get("matchups", []) if x["id"] == mid), None)
        if not room or not m or m.get("aiId") != cid:
            return
        a, b = m["pair"]
        va = sum(1 for v in m["votes"].values() if v == 0)
        vb = sum(1 for v in m["votes"].values() if v == 1)
        system = ("You are the comedy host of Caption Clash. " + SPICE[room["settings"]["spice"]]
                  + " Write ONE punchy 1-2 sentence reaction comparing the two jokes. Never guess gender.")
        prompt = (f'Prompt: "{m["prompt"]}"\n'
                  f'{name(room, a)} ({va} votes): "{m["answers"].get(a, "")}"\n'
                  f'{name(room, b)} ({vb} votes): "{m["answers"].get(b, "")}"\n'
                  'Return only JSON: {"roast": "..."}')
    try:
        out, _, _ = ai.ask_builtin(system, prompt, timeout=20, text_first=True)
        txt = str(out.get("roast") or "").strip()[:260]
    except (ai.AIError, ValueError, TypeError, AttributeError):
        txt = ""
    with lock:
        room = rooms.get(code)
        m = next((x for x in (room or {}).get("matchups", []) if x["id"] == mid), None)
        if room and m and m.get("aiId") == cid:
            m["ai"] = txt or None
            changed(room)


def reveal_matchup(room):
    m = room["matchups"][room["matchIdx"]]
    a, b = m["pair"]
    va = sum(1 for v in m["votes"].values() if v == 0)
    vb = sum(1 for v in m["votes"].values() if v == 1)
    mult = m["mult"]
    pts = {a: va * 100 * mult, b: vb * 100 * mult}
    if va > 0 and vb == 0 and (va + vb) >= 2:
        pts[a] += 250 * mult
        m["sweep"] = a
    elif vb > 0 and va == 0 and (va + vb) >= 2:
        pts[b] += 250 * mult
        m["sweep"] = b
    m["points"] = pts
    for pid, p in pts.items():
        room["scores"][pid] = room["scores"].get(pid, 0) + p
    room["phase"] = "reveal"
    room["deadline"] = None
    m["aiId"] = rid(6)
    threading.Thread(target=roast_matchup, args=(room["code"], m["id"], m["aiId"]), daemon=True).start()


def tick(room):
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now >= room["deadline"]
    if ph == "write" and (over or all_written(room)):
        begin_vote(room, 0)
        return True
    if ph == "vote":
        m = room["matchups"][room["matchIdx"]]
        voters = eligible_voters(room, m)
        if over or (voters and all(v in m["votes"] for v in voters)) or not voters:
            reveal_matchup(room)
            return True
    return False


def chat_rules(room, pid):
    if room["phase"] == "write":
        return {"read": ["all"], "write": [], "why": "Shhh! Write your jokes first—chat opens for the battles!"}
    return {"read": ["all"], "write": ["all"]}


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "prompts", "matchups")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["totalMatchups"] = len(room["matchups"])
    ph = room["phase"]
    if ph == "write":
        r["myPrompts"] = [
            {"id": m["id"], "prompt": m["prompt"], "mine": m["answers"].get(viewer)}
            for m in room["matchups"] if viewer in m["pair"]
        ]
        done_pids = []
        for pid in room["players"]:
            mine = [m for m in room["matchups"] if pid in m["pair"]]
            if mine and all(pid in m["answers"] for m in mine):
                done_pids.append(pid)
        r["donePids"] = done_pids
        r["activePids"] = [pid for pid, p in room["players"].items() if not p.get("sitout")]
    elif ph in ("vote", "reveal") and 0 <= room["matchIdx"] < len(room["matchups"]):
        m = room["matchups"][room["matchIdx"]]
        a, b = m["pair"]
        out = {
            "id": m["id"], "prompt": m["prompt"], "mult": m["mult"],
            "choices": [m["answers"].get(a, ""), m["answers"].get(b, "")],
            "canVote": bool(viewer and viewer not in m["pair"] and viewer in room["players"]),
            "myVote": m["votes"].get(viewer),
            "voteCount": len(m["votes"]),
            "voteNeed": len(eligible_voters(room, m)),
        }
        if ph == "reveal":
            out.update({
                "authors": [a, b], "votes": m["votes"], "points": m["points"],
                "sweep": m["sweep"], "ai": m["ai"],
            })
        r["match"] = out
    return r


def player_action(room, action, b, pid):
    if action == "answer":
        if room["phase"] != "write":
            raise Refuse("Writing time is over.", 409)
        m = next((x for x in room["matchups"] if x["id"] == b.get("id") and pid in x["pair"]), None)
        if not m:
            raise Refuse("That prompt isn't yours.")
        text = " ".join(str(b.get("text") or "").split())[:90]
        if not text:
            raise Refuse("Write an answer first!")
        m["answers"][pid] = text
        if all_written(room):
            begin_vote(room, 0)
        return True
    if action == "vote":
        if room["phase"] != "vote":
            raise Refuse("Voting isn't open right now.", 409)
        m = room["matchups"][room["matchIdx"]]
        if pid in m["pair"]:
            raise Refuse("You can't vote on your own battle!", 409)
        side = int(b.get("side", -1))
        if side not in (0, 1):
            raise Refuse("Pick one of the two answers.")
        m["votes"][pid] = side
        voters = eligible_voters(room, m)
        if voters and all(v in m["votes"] for v in voters):
            reveal_matchup(room)
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the show starts.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action == "start":
        if ph != "lobby":
            raise Refuse("The game already started.")
        if len(room["players"]) < MIN_PLAYERS:
            raise Refuse(f"You need at least {MIN_PLAYERS} players.")
        room["phase"] = "starting"
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action in ("next", "skip"):
        if ph == "write":
            begin_vote(room, 0)
        elif ph == "vote":
            reveal_matchup(room)
        elif ph == "reveal":
            if room["matchIdx"] + 1 < len(room["matchups"]):
                begin_vote(room, room["matchIdx"] + 1)
            elif room["round"] + 1 < room["settings"]["rounds"]:
                start_round(room, room["round"] + 1)
            else:
                room["phase"] = "final"
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
            p["sitout"] = False
        room.update({
            "phase": "lobby", "deadline": None, "prompts": [], "round": -1,
            "matchups": [], "matchIdx": 0, "scores": {pid: 0 for pid in room["players"]},
        })
    return True

"""Drawing game: the AI picks what to draw, everyone draws against a timer (alone or as a team),
then the AI or the players score each drawing, and a host-driven show reveals the results.

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import base64
import random
import threading
import time

import ai

# set by server.setup_games()
rooms = lock = changed = rid = None

IMAGES = {}   # image id -> jpeg bytes (kept in memory only; drawings are gone when the server restarts)
STROKES = {}  # (code, round, team id) -> {"gen": n, "list": [stroke, ...]} for live team canvases
MAX_IMG = 900_000

CATEGORIES = {
    "anime": ("Anime", "anime characters doing funny or unexpected things, and iconic anime moments",
              ["Goku doing his taxes", "Naruto at a job interview", "Pikachu stuck in traffic", "Luffy at an all-you-can-eat buffet",
               "Saitama grocery shopping", "Totoro at the gym", "Levi cleaning a messy bedroom", "Zoro getting lost in a mall",
               "Gojo wearing sunglasses at night", "Light Yagami writing a grocery list", "All Might at the dentist", "A titan in a tiny car"]),
    "objects": ("Everyday objects", "everyday objects, simple and recognizable, sometimes with a funny twist",
                ["A toaster", "An umbrella", "A pair of scissors", "A lightbulb", "A rubber duck", "A grandfather clock",
                 "A shopping cart", "A camera", "Headphones", "A bicycle", "A teapot", "A lamp with a crooked shade"]),
    "food": ("Food", "foods, dishes and drinks from around the world",
             ["A slice of pizza", "Sushi", "A burger with everything on it", "A bowl of ramen", "Tacos", "A birthday cake",
              "Pancakes with syrup", "A pineapple", "Fried chicken", "Ice cream that's melting", "A croissant", "Bubble tea"]),
    "animals": ("Animals", "animals, sometimes doing something funny",
                ["A giraffe", "A penguin", "An octopus", "A sleepy sloth", "A cat knocking a glass off a table", "A shark",
                 "A flamingo on one leg", "A hedgehog", "A kangaroo boxing", "A snail racing", "An owl", "A crab"]),
    "flags": ("Flags", "national flags of real countries (write each as 'Flag of <country>'), from easy to tricky",
              ["Flag of Japan", "Flag of Canada", "Flag of Brazil", "Flag of the United Kingdom", "Flag of South Korea", "Flag of Pakistan",
               "Flag of Italy", "Flag of the USA", "Flag of India", "Flag of Germany", "Flag of Mexico", "Flag of Turkey"]),
    "places": ("Places and landmarks", "famous landmarks, cities and places people would recognize",
               ["The Eiffel Tower", "The pyramids of Giza", "The Statue of Liberty", "Mount Fuji", "A lighthouse", "The Great Wall of China",
                "A desert island", "A haunted house", "The Leaning Tower of Pisa", "A volcano", "A space station", "Big Ben"]),
    "movies": ("Movies and TV", "famous movies, TV shows and characters people would recognize",
               ["Titanic", "Shrek", "Spider-Man", "Jaws", "SpongeBob", "Harry Potter", "Darth Vader", "The Simpsons",
                "Finding Nemo", "Batman", "Frozen", "Pac-Man"]),
    "funny": ("Funny situations", "funny, absurd everyday situations and actions",
              ["A dog driving a car", "Someone slipping on a banana", "A cat at a job interview", "A snowman at the beach",
               "A vampire at the dentist", "A robot falling in love with a toaster", "Grandma on a skateboard", "A ghost doing laundry",
               "A cow on a trampoline", "A dinosaur at a birthday party", "Pizza delivery in the rain", "A frog proposing"]),
    "mix": ("Mix of everything", "a random mix: objects, food, animals, places, flags, movies and funny situations",
            []),
}
CATEGORIES["mix"] = (CATEGORIES["mix"][0], CATEGORIES["mix"][1], [p for k, v in CATEGORIES.items() if k != "mix" for p in v[2]])
SPICE = {
    "wholesome": "Be warm and encouraging: gentle jokes, lots of hype.",
    "spicy": "Roast properly: specific, funny jokes about what you actually see, balanced with real compliments.",
    "unhinged": "Go savage: chaotic, over-the-top roasts like a menace in the group chat. Punch at the drawing, never at the person.",
}


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


# ---------- room setup ----------

def create(room, b):
    room.update({
        "game": "draw",
        "mode": "team" if b.get("mode") == "team" else "solo",
        "judge": "players" if b.get("judge") == "players" else "ai",
        "rounds": max(1, min(6, int(b.get("rounds") or 3))),
        "drawSec": max(30, min(300, int(b.get("drawSec") or 90))),
        "rateSec": 90,
        "category": b.get("category") if b.get("category") in CATEGORIES or b.get("category") == "custom" else "mix",
        "theme": (b.get("theme") or "").strip()[:200],  # what the host typed for a custom category
        "spice": b.get("spice") if b.get("spice") in SPICE else "spicy",
        "teams": [{"id": "t1", "name": "Team Red"}, {"id": "t2", "name": "Team Blue"}],
        "phase": "lobby", "round": -1, "prompts": [], "deadline": None, "roundData": [], "show": None,
    })


TEAM_NAMES = ["Team Red", "Team Blue", "Team Green", "Team Gold"]


def owners(room):
    """Who makes a drawing this round: each player (solo) or each team that has members."""
    if room["mode"] == "solo":
        return {pid: [pid] for pid in room["players"]}
    out = {}
    for pid, p in room["players"].items():
        if p.get("team"):
            out.setdefault(p["team"], []).append(pid)
    return out


def owner_name(room, owner):
    if room["mode"] == "solo":
        p = room["players"].get(owner)
        return p["name"] if p else "Someone who left"
    return next((t["name"] for t in room["teams"] if t["id"] == owner), "A team")


def owner_of(room, pid):
    return pid if room["mode"] == "solo" else (room["players"].get(pid) or {}).get("team")


def on_join(room, pid):
    if room["mode"] == "team":
        # put newcomers on the smallest team
        counts = {t["id"]: 0 for t in room["teams"]}
        for p in room["players"].values():
            if p.get("team") in counts:
                counts[p["team"]] += 1
        room["players"][pid]["team"] = min(counts, key=counts.get)


# ---------- AI ----------

def make_prompts(room):
    n, cat = room["rounds"], room.get("category", "mix")
    if cat == "custom" and room.get("theme"):
        about, backup = f"this, as described by the host: {room['theme']}", CATEGORIES["mix"][2]
    else:
        _, about, backup = CATEGORIES.get(cat, CATEGORIES["mix"])
    try:
        out, _, _ = ai.ask_builtin(
            "You write prompts for a party drawing game played by friends.",
            f"Write {n + 2} drawing prompts about {about}. Each must be drawable in {room['drawSec']} seconds by an "
            "average person, recognizable once drawn, 1-7 words, and no two alike. Mix easy ones with a few that are fun to attempt. "
            'Return only JSON: {"prompts": ["...", "..."]}', timeout=25)
        prompts = [str(x).strip()[:80] for x in out.get("prompts", []) if str(x).strip()]
    except ai.AIError:
        prompts = []
    random.shuffle(prompts)
    if len(prompts) < n:
        prompts += random.sample(backup, min(len(backup), n - len(prompts)))
    return prompts[:n]


def category_label(room):
    if room.get("category") == "custom":
        return room.get("theme") or "Custom"
    return CATEGORIES.get(room.get("category", "mix"), CATEGORIES["mix"])[0]


def judge_round(code, rnd):
    with lock:
        room = rooms.get(code)
        if not room:
            return
        rd = room["roundData"][rnd]
        entries = [(eid, e) for eid, e in rd["entries"].items() if e.get("img") in IMAGES]
        images = [("image/jpeg", IMAGES[e["img"]]) for _, e in entries]
        scoring = room["judge"] == "ai"
        spice, prompt_word = room["spice"], rd["prompt"]
    if not entries:
        result = {"status": "failed", "error": "No drawings were submitted."}
    else:
        try:
            out, provider, model = ai.ask_builtin(
                "You are the judge of a party drawing game played by friends. You look closely at each "
                "drawing and say exactly what you see, then joke about it. " + SPICE[spice] +
                " Keep each comment to 1-2 short sentences, casual like a group chat.",
                f'Everyone had {room_secs(code)} seconds to draw: "{prompt_word}". There are {len(images)} drawings, '
                "attached in order as Drawing 1, Drawing 2, and so on. "
                + ("Score each from 1 to 10 for how well it shows the prompt plus effort and creativity (use the whole range). " if scoring else "")
                + "Return only JSON: "
                + ('{"results":[{"n":1,"score":7,"comment":"..."}]}' if scoring else '{"results":[{"n":1,"comment":"..."}]}'),
                images=images, timeout=60)
            res = {}
            for r in out.get("results", []):
                try:
                    i = int(r.get("n")) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(entries):
                    score = r.get("score")
                    try:
                        score = max(1, min(10, round(float(score)))) if scoring else None
                    except (TypeError, ValueError):
                        score = None
                    res[entries[i][0]] = {"score": score, "comment": str(r.get("comment") or "")[:400]}
            result = {"status": "done" if res else "failed", "by": f"{provider}", "results": res,
                      "error": None if res else "The AI replied without usable results."}
        except ai.AIError as e:
            result = {"status": "failed", "error": str(e)[:500]}
    with lock:
        room = rooms.get(code)
        if not room or rnd >= len(room["roundData"]):
            return
        room["roundData"][rnd]["ai"] = result
        if room["phase"] == "judging" and rnd == room["round"]:
            begin_show(room)
        changed(room)


def room_secs(code):
    room = rooms.get(code)
    return room["drawSec"] if room else 90


# ---------- phases ----------

def begin_game(code):
    with lock:
        room = rooms.get(code)
        snapshot = dict(room) if room else None
    if not snapshot:
        return
    prompts = make_prompts(snapshot)
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            room["prompts"] = prompts
            start_round(room, 0)
            changed(room)


def start_round(room, rnd):
    for k in [k for k in STROKES if k[0] == room["code"]]:
        del STROKES[k]  # last round's team canvases
    room["round"] = rnd
    room["phase"] = "drawing"
    room["deadline"] = time.time() + room["drawSec"] + 3  # 3s for screens to switch
    room["show"] = None
    room["roundData"].append({"prompt": room["prompts"][rnd], "entries": {}, "ratings": {},
                              "ai": {"status": "waiting"}})


def end_drawing(room):
    rd = room["roundData"][room["round"]]
    room["deadline"] = None
    if not rd["entries"]:
        rd["ai"] = {"status": "failed", "error": "Nobody submitted a drawing."}
        begin_show(room)
        return
    rd["ai"] = {"status": "working"}
    threading.Thread(target=judge_round, args=(room["code"], room["round"]), daemon=True).start()
    if room["judge"] == "players" and len(rd["entries"]) > 1:
        room["phase"] = "rating"
        room["deadline"] = time.time() + room["rateSec"]
    elif room["judge"] == "players":
        begin_show(room)  # nothing to rate against
    else:
        room["phase"] = "judging"


def begin_show(room):
    room["phase"] = "show"
    room["deadline"] = None
    room["show"] = {"slide": 0}


def tick(room):
    """Called every second with the lock held. Returns True when the room changed."""
    now = time.time()
    if room["phase"] == "drawing" and room["deadline"]:
        rd = room["roundData"][room["round"]]
        all_in = owners(room) and all(o in {e["owner"] for e in rd["entries"].values()} for o in owners(room))
        if now > room["deadline"] + 6 or (all_in and now > room["deadline"] - room["drawSec"] + 2):
            end_drawing(room)
            return True
    if room["phase"] == "rating" and room["deadline"] and (now > room["deadline"] + 1 or everyone_rated(room)):
        begin_show(room)
        return True
    return False


def everyone_rated(room):
    rd = room["roundData"][room["round"]]
    for pid in room["players"]:
        mine = owner_of(room, pid)
        need = [eid for eid, e in rd["entries"].items() if e["owner"] != mine]
        if any(eid not in rd["ratings"].get(pid, {}) for eid in need):
            return False
    return True


# ---------- scores ----------

def entry_score(room, rd, eid):
    if room["judge"] == "ai":
        r = (rd.get("ai") or {}).get("results", {}).get(eid)
        return r and r.get("score")
    vals = [rr[eid]["s"] for rr in rd["ratings"].values() if eid in rr and rr[eid].get("s")]
    return round(sum(vals) / len(vals), 1) if vals else None


def standings(room, upto):
    tot = {}
    for rd in room["roundData"][:upto + 1]:
        for eid, e in rd["entries"].items():
            s = entry_score(room, rd, eid) or 0
            t = tot.setdefault(e["owner"], {"owner": e["owner"], "name": owner_name(room, e["owner"]), "points": 0, "drawings": 0})
            t["points"] = round(t["points"] + s, 1)
            t["drawings"] += 1
    return sorted(tot.values(), key=lambda t: -t["points"])


# ---------- what each viewer sees ----------

def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "roundData", "prompts")}  # future prompts stay secret
    r["now"] = time.time()
    r["categoryLabel"] = category_label(room)
    r["visionAI"] = [p for p in ai.BUILTIN_ORDER if p in ("gemini", "mistral")]
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["myOwner"] = owner_of(room, viewer) if viewer else None
    rounds = []
    for i, rd in enumerate(room["roundData"]):
        live = i == room["round"] and room["phase"] in ("drawing", "rating", "judging")
        out = {"prompt": rd["prompt"], "aiStatus": (rd.get("ai") or {}).get("status"),
               "aiError": (rd.get("ai") or {}).get("error"), "aiBy": (rd.get("ai") or {}).get("by")}
        if live and room["phase"] == "drawing":
            out["done"] = sorted({e["owner"] for e in rd["entries"].values()})
        elif live:
            # anonymous while people judge: no names, and you only see your own ratings
            mine = r["myOwner"]
            out["entries"] = [{"eid": eid, "img": e["img"], "mine": e["owner"] == mine} for eid, e in rd["entries"].items()]
            random.Random(room["code"] + str(i) + str(viewer)).shuffle(out["entries"])
            out["myRatings"] = rd["ratings"].get(viewer, {}) if viewer else {}
            out["raters"] = {pid: len(v) for pid, v in rd["ratings"].items()}
        else:
            ai_res = (rd.get("ai") or {}).get("results", {})
            names = {pid: p["name"] for pid, p in room["players"].items()}
            ents = []
            for eid, e in rd["entries"].items():
                ents.append({"eid": eid, "img": e["img"], "owner": e["owner"], "name": owner_name(room, e["owner"]),
                             "members": [names.get(m, "?") for m in e.get("members", [])],
                             "score": entry_score(room, rd, eid), "ai": ai_res.get(eid),
                             "comments": [{"name": names.get(rp, "Someone"), "s": rr[eid].get("s"), "c": rr[eid].get("c", "")}
                                          for rp, rr in rd["ratings"].items() if eid in rr]})
            # reveal from the lowest score up, so the winner comes last
            ents.sort(key=lambda x: (x["score"] is not None, x["score"] or 0))
            out["entries"] = ents
        rounds.append(out)
    r["roundData"] = rounds
    if room["round"] >= 0 and room["phase"] in ("show", "final"):
        r["standings"] = standings(room, room["round"])
    return r


def strokes_since(code, rnd, team, since, gen):
    s = STROKES.get((code, rnd, team)) or {"gen": 0, "list": []}
    if s["gen"] != gen:
        return {"gen": s["gen"], "reset": True, "strokes": s["list"], "total": len(s["list"])}
    return {"gen": s["gen"], "reset": False, "strokes": s["list"][since:], "total": len(s["list"])}


# ---------- actions (lock held) ----------

class Refuse(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


def player_action(room, action, b, pid):
    rnd = room["round"]
    if action == "team":
        if room["phase"] not in ("lobby", "show") or room["mode"] != "team":
            raise Refuse("You can only switch teams between rounds.")
        if b.get("team") not in {t["id"] for t in room["teams"]}:
            raise Refuse("That team doesn't exist.")
        room["players"][pid]["team"] = b["team"]
        return True
    if action in ("stroke", "undo", "clearcanvas"):
        if room["phase"] != "drawing" or room["mode"] != "team":
            raise Refuse("You can't draw right now.", 409)
        key = (room["code"], rnd, owner_of(room, pid))
        s = STROKES.setdefault(key, {"gen": 0, "list": []})
        if action == "stroke":
            for st in (b.get("strokes") or [])[:20]:
                pts = [[int(x), int(y)] for x, y in (st.get("p") or [])[:2000]]
                if pts:
                    s["list"].append({"by": pid, "c": str(st.get("c") or "#000")[:9], "w": max(1, min(80, int(st.get("w") or 6))), "p": pts})
        elif action == "undo":
            for i in range(len(s["list"]) - 1, -1, -1):
                if s["list"][i]["by"] == pid:
                    del s["list"][i]
                    s["gen"] += 1
                    break
        else:
            s["list"].clear()
            s["gen"] += 1
        lock.notify_all()
        return False  # canvas changes don't touch the shared room state
    if action == "submit":
        if room["phase"] != "drawing" or not room["deadline"] or time.time() > room["deadline"] + 6:
            raise Refuse("Time's up. Drawings are locked.", 409)
        img = str(b.get("img") or "")
        if not img.startswith("data:image/jpeg;base64,"):
            raise Refuse("The drawing didn't upload. Try again.")
        raw = base64.b64decode(img.split(",", 1)[1])
        if len(raw) > MAX_IMG:
            raise Refuse("That drawing is too big to upload.")
        owner = owner_of(room, pid)
        if not owner:
            raise Refuse("Join a team first.")
        rd = room["roundData"][rnd]
        eid = next((k for k, e in rd["entries"].items() if e["owner"] == owner), None) or rid(8)
        img_id = rid(12)
        IMAGES[img_id] = raw
        old = rd["entries"].get(eid, {}).get("img")
        if old and old != img_id:
            IMAGES.pop(old, None)
        rd["entries"][eid] = {"owner": owner, "img": img_id, "members": owners(room).get(owner, [pid])}
        return True
    if action == "rate":
        if room["phase"] != "rating":
            raise Refuse("Rating is closed.", 409)
        rd = room["roundData"][rnd]
        e = rd["entries"].get(b.get("eid"))
        if not e:
            raise Refuse("That drawing isn't here anymore.")
        if e["owner"] == owner_of(room, pid):
            raise Refuse("You can't rate your own drawing.")
        mine = rd["ratings"].setdefault(pid, {})
        score = int(b.get("s") or 0)
        mine[b["eid"]] = {"s": max(1, min(10, score)) if score else None, "c": str(b.get("c") or "").strip()[:140]}
        if not mine[b["eid"]]["s"]:
            mine.pop(b["eid"])  # a comment alone doesn't count as rated
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    if action == "start":
        if room["phase"] != "lobby":
            raise Refuse("The game already started.")
        if len(room["players"]) < 1:
            raise Refuse("Nobody has joined yet.")
        if room["mode"] == "team" and len(owners(room)) < 2:
            raise Refuse("You need at least two teams with players in them.")
        # the AI writes the prompts off the lock so the rest of the server keeps answering
        room["phase"] = "starting"
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action == "shuffle":
        if room["mode"] != "team" or room["phase"] not in ("lobby", "show"):
            raise Refuse("Teams can only be shuffled between rounds.")
        pids = list(room["players"])
        random.shuffle(pids)
        for i, pid in enumerate(pids):
            room["players"][pid]["team"] = room["teams"][i % len(room["teams"])]["id"]
    elif action == "teams":
        n = max(2, min(4, int(b.get("n") or 2)))
        room["teams"] = [{"id": f"t{i + 1}", "name": TEAM_NAMES[i]} for i in range(n)]
        valid = {t["id"] for t in room["teams"]}
        for pid, p in room["players"].items():
            if p.get("team") not in valid:
                p["team"] = None
                on_join(room, pid)
    elif action == "addtime":
        if room["phase"] not in ("drawing", "rating") or not room["deadline"]:
            raise Refuse("No timer is running.")
        room["deadline"] += int(b.get("sec") or 30)
    elif action == "end":
        if room["phase"] == "drawing":
            room["deadline"] = time.time() - 4  # leaves a 2s grace for the last uploads, then the ticker moves on
        elif room["phase"] == "rating":
            begin_show(room)
        else:
            raise Refuse("Nothing to end right now.")
    elif action == "slide":
        if room["phase"] != "show" or not room.get("show"):
            raise Refuse("The show isn't on.")
        room["show"]["slide"] = max(0, int(b.get("to") or 0))
    elif action == "nextround":
        if room["phase"] != "show":
            raise Refuse("Finish the show first.")
        if room["round"] + 1 < room["rounds"]:
            start_round(room, room["round"] + 1)
        else:
            room["phase"] = "final"
    elif action == "rejudge":
        rd = room["roundData"][room["round"]] if room["round"] >= 0 else None
        if not rd or (rd.get("ai") or {}).get("status") == "working":
            raise Refuse("The AI is already working on it.")
        rd["ai"] = {"status": "working"}
        threading.Thread(target=judge_round, args=(room["code"], room["round"]), daemon=True).start()
    elif action == "playagain":
        for rd in room["roundData"]:
            for e in rd["entries"].values():
                IMAGES.pop(e.get("img"), None)
        room.update({"phase": "lobby", "round": -1, "prompts": [], "deadline": None, "roundData": [], "show": None})
    elif action == "kick":
        room["players"].pop(b.get("pid"), None)
    else:
        raise Refuse("Unknown action")
    return True

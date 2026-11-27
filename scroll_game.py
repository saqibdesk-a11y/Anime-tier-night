"""Broken Scroll: a drawing telephone / Gartic Phone party game for friends.

Every player starts a scroll with a funny prompt. Each step, scrolls pass around the table:
- Classic Telephone: Write -> Draw -> Guess -> Draw -> Guess...
- Speed Chaos: Same telephone relay with frantic short timers!
- Memory Knock-Off: Write -> Draw -> Peek at the last drawing for 7 seconds -> Redraw from memory!

After the final pass, everyone watches the synchronized Scroll Reveal Theater one panel at a time
(with live emoji reactions, AI mutation commentary, and comic-strip PNG export).

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import base64
import random
import threading
import time

import ai
from media import IMAGES, Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "settings", "addtime", "skip", "reveal", "playagain", "kick")
MIN_PLAYERS, MAX_PLAYERS = 2, 12  # works with 2+ (great at 4-10)
MAX_IMG = 650_000
REACTIONS = ("😂", "💀", "🔥", "🎨", "❓")

STARTERS = [
    "Goku paying his electricity bill",
    "Naruto failing a driving test",
    "Pikachu drinking way too much coffee",
    "Luffy locked inside a salad bar",
    "Gojo losing his sunglasses in a puddle",
    "Levi fighting a single cockroach",
    "Totoro trying to fit on a skateboard",
    "Zoro getting lost inside a bathroom",
    "A cat running for president",
    "A shark taking a bubble bath",
    "An alien trying ramen for the first time",
    "A penguin robbing a bank",
    "A T-Rex trying to make a bed",
    "A ghost doing its laundry",
    "A frog proposing with an onion ring",
    "Grandma winning a karate tournament",
    "A robot falling in love with a toaster",
    "A dog driving a fire truck",
    "A snowman sunbathing on a beach",
    "A vampire at the dentist",
    "Saitama struggling to open a pickle jar",
    "A ninja sneaking through a ball pit",
    "A wizard forgetting how to ride a bike",
    "A duck judging a cooking show",
    "A dragon blowing out birthday candles",
    "A pigeon stealing an entire pizza",
    "An octopus playing the drums",
    "A skeleton drinking milk",
    "A ninja turtle ordering sushi",
    "A knight jousting on a shopping cart",
    "A sloth winning a marathon",
    "A raccoon running a five-star restaurant",
]

SPICE = {
    "wholesome": "Keep it warm, joyful and celebratory, laughing along with how silly the drawings got.",
    "spicy": "Be a witty, sharp comedy narrator roasting how hilariously the prompt mutated along the chain.",
    "unhinged": "Go chaotic and dramatic like an unhinged anime narrator reacting to a cursed telephone chain. Never attack real-world identity.",
}


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    mode = pick("mode", "classic")
    if mode not in ("classic", "speed", "knockoff"):
        mode = "classic"
    steps = int(pick("steps", 0) or 0)  # 0 = auto (matches player count, min 4, max 8)
    if steps not in (0, 4, 6, 8):
        steps = 0
    return {
        "mode": mode,
        "drawSec": max(25, min(150, int(pick("drawSec", 75)))),
        "writeSec": max(15, min(90, int(pick("writeSec", 35)))),
        "steps": steps,
        "spice": pick("spice", "spicy") if pick("spice", "spicy") in SPICE else "spicy",
    }


def create(room, b):
    room.update({
        "game": "scroll", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "order": [], "step": -1, "totalSteps": 0, "chains": [], "show": None,
        "ai": None, "aiId": None, "reacts": {}, "reactLog": [],
    })


def on_join(room, pid):
    room["players"][pid].update({"sitout": room["phase"] != "lobby"})


# ---------- helpers ----------

def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def step_kind(room, step_idx):
    """Step 0 is always writing a starting prompt.
    Classic/Speed alternate draw/write; Knock-Off is write (0) then draw every step after."""
    if step_idx == 0:
        return "write"
    if room["settings"]["mode"] == "knockoff":
        return "draw"
    return "draw" if step_idx % 2 == 1 else "write"


def step_duration(room, kind):
    s = room["settings"]
    if s["mode"] == "speed":
        return 45 if kind == "draw" else 20
    return s["drawSec"] if kind == "draw" else s["writeSec"]


def set_timer(room, secs):
    room["deadline"] = time.time() + secs + 2  # 2s grace for screen transitions


def active_order(room):
    return [pid for pid in room["order"] if pid in room["players"]]


def chain_for(room, pid, step_idx):
    """Which scroll chain `pid` works on during `step_idx` (rotates cleanly around the table)."""
    order = room["order"]
    if pid not in order or not room["chains"]:
        return None
    n = len(order)
    idx = (order.index(pid) - step_idx) % n
    return room["chains"][idx]


def entry_of(chain, step_idx):
    return next((e for e in chain["entries"] if e["step"] == step_idx), None)


def everyone_done(room):
    step_idx = room["step"]
    order = active_order(room)
    if not order:
        return False
    for pid in order:
        ch = chain_for(room, pid, step_idx)
        e = ch and entry_of(ch, step_idx)
        if not e or not e.get("done"):
            return False
    return True


def free_images(room):
    for ch in room.get("chains", []):
        for e in ch.get("entries", []):
            if e.get("img"):
                IMAGES.pop(e["img"], None)


# ---------- game lifecycle ----------

def start_game(room):
    free_images(room)
    pids = list(room["players"])[:MAX_PLAYERS]
    for pid in room["players"]:
        room["players"][pid]["sitout"] = pid not in pids
    random.shuffle(pids)
    n = len(pids)
    want = room["settings"]["steps"]
    if want:
        total = want
    else:
        # auto: matches player count (between 4 and 8 steps); even count in classic ends on a drawing or balanced chain
        total = max(4 if n <= 3 else n, n)
        total = min(8, total)
    room["order"] = pids
    room["totalSteps"] = total
    room["chains"] = [{"id": rid(6), "owner": pid, "entries": []} for pid in pids]
    room["show"] = None
    room["ai"] = None
    room["aiId"] = None
    room["reacts"] = {}
    room["reactLog"] = []
    begin_step(room, 0)


def begin_step(room, step_idx):
    room["step"] = step_idx
    kind = step_kind(room, step_idx)
    room["phase"] = "playing"
    set_timer(room, step_duration(room, kind))


def fill_missing_entries(room, step_idx):
    """Fills any unfinished slots when a step ends so no chain has a broken link."""
    kind = step_kind(room, step_idx)
    for pid in room["order"]:
        ch = chain_for(room, pid, step_idx)
        if not ch:
            continue
        e = entry_of(ch, step_idx)
        if e:
            e["done"] = True
            continue
        if kind == "write":
            if step_idx == 0:
                text = random.choice(STARTERS)
                ch["entries"].append({"step": step_idx, "kind": "write", "pid": pid, "text": text, "done": True, "auto": True})
            else:
                ch["entries"].append({"step": step_idx, "kind": "write", "pid": pid, "text": "(no guess in time)", "done": True, "late": True})
        else:
            ch["entries"].append({"step": step_idx, "kind": "draw", "pid": pid, "img": None, "done": True, "late": True})


def finish_step(room):
    fill_missing_entries(room, room["step"])
    if room["step"] + 1 < room["totalSteps"]:
        begin_step(room, room["step"] + 1)
    else:
        begin_show(room)


def begin_show(room):
    room["phase"] = "show"
    room["deadline"] = None
    room["show"] = {"chain": 0, "panel": 0}
    room["ai"] = None
    room["aiId"] = rid(6)
    threading.Thread(target=roast_chains, args=(room["code"], room["aiId"]), daemon=True).start()
    threading.Timer(18, give_up_on_ai, args=(room["code"], room["aiId"])).start()


def roast_chains(code, cid):
    with lock:
        room = rooms.get(code)
        if not room or room.get("aiId") != cid:
            return
        summaries = []
        for idx, ch in enumerate(room["chains"]):
            texts = [f'Step {e["step"]+1} ({name(room, e["pid"])}): "{e["text"]}"'
                     for e in ch["entries"] if e["kind"] == "write" and e.get("text")]
            draws = sum(1 for e in ch["entries"] if e["kind"] == "draw" and e.get("img"))
            summaries.append(f'Scroll {idx + 1} (started by {name(room, ch["owner"])}, {draws} drawings): ' + " -> ".join(texts))
        mode = room["settings"]["mode"]
        system = ("You are the comedy narrator for Broken Scroll (a drawing telephone party game). "
                  + SPICE[room["settings"]["spice"]] + " Keep each scroll's roast to 1-2 punchy sentences. "
                  "Refer to players by name, never guess gender (no he/she).")
        prompt = (f"Game mode: {mode}.\nHere are all the scrolls and how the written prompts mutated:\n"
                  + "\n".join(summaries)
                  + '\n\nWrite one funny comment per scroll reacting to how it transformed (or stayed shockingly accurate), '
                  'plus a 1-sentence overall award for the night\'s funniest/most cursed scroll. '
                  'Return only JSON: {"scrolls": [{"n": 1, "line": "..."}], "award": "..."}')
    try:
        out, _, _ = ai.ask_builtin(system, prompt, timeout=25, text_first=True)
        lines = {}
        for item in (out.get("scrolls") or []):
            if isinstance(item, dict) and item.get("line"):
                try:
                    k = int(item.get("n")) - 1
                    lines[str(k)] = str(item.get("line")).strip()[:260]
                except (TypeError, ValueError):
                    pass
        award = str(out.get("award") or "").strip()[:260]
        if not lines and not award:
            raise ValueError("empty")
    except (ai.AIError, ValueError, TypeError, AttributeError):
        lines, award = {}, ""
    with lock:
        room = rooms.get(code)
        if room and room.get("aiId") == cid:
            room["ai"] = {"lines": lines, "award": award} if (lines or award) else {"failed": True}
            changed(room)


def give_up_on_ai(code, cid):
    with lock:
        room = rooms.get(code)
        if room and room.get("aiId") == cid and room["ai"] is None:
            room["ai"] = {"failed": True}
            changed(room)


def tick(room):
    if room["phase"] != "playing" or not room.get("deadline"):
        return False
    now = time.time()
    # 3s grace after deadline lets clients finish auto-uploading their canvas JPEG
    if now > room["deadline"] + 3 or everyone_done(room):
        finish_step(room)
        return True
    return False


# ---------- chat ----------

def chat_rules(room, pid):
    if room["phase"] == "playing":
        return {"read": ["all"], "write": [], "why": "Shhh! No spoilers while the scrolls are passing. Chat opens for the reveal show!"}
    return {"read": ["all"], "write": ["all"]}


# ---------- what each viewer sees ----------

def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "chains", "reactLog")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["starters"] = STARTERS
    now = time.time()
    r["reactBurst"] = [x for x in room.get("reactLog", []) if now - x["t"] < 8]

    ph = room["phase"]
    if ph == "playing":
        step_idx = room["step"]
        kind = step_kind(room, step_idx)
        done_pids = []
        for pid in active_order(room):
            ch = chain_for(room, pid, step_idx)
            e = ch and entry_of(ch, step_idx)
            if e and e.get("done"):
                done_pids.append(pid)
        r["stepKind"] = kind
        r["donePids"] = done_pids
        r["activePids"] = active_order(room)

        ch = chain_for(room, viewer, step_idx) if viewer else None
        if ch:
            prev_e = entry_of(ch, step_idx - 1) if step_idx > 0 else None
            my_e = entry_of(ch, step_idx)
            # In knock-off mode step >= 2, player studies the previous drawing briefly before redrawing
            peek_sec = 7 if (room["settings"]["mode"] == "knockoff" and step_idx >= 2) else 0
            r["myTask"] = {
                "step": step_idx,
                "kind": kind,
                "peekSec": peek_sec,
                "prev": ({"kind": prev_e["kind"], "text": prev_e.get("text"), "img": prev_e.get("img"),
                          "late": bool(prev_e.get("late"))} if prev_e else None),
                "mine": ({"done": bool(my_e.get("done")), "text": my_e.get("text"), "img": my_e.get("img")} if my_e else None),
            }
    elif ph in ("show", "gallery"):
        r["chains"] = room["chains"]
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    ph = room["phase"]
    if action == "react":
        if ph not in ("show", "gallery"):
            raise Refuse("Reactions open during the reveal show.", 409)
        emoji = str(b.get("emoji") or "")
        if emoji not in REACTIONS:
            raise Refuse("Pick a reaction.")
        ci = str(int(b.get("chain") if b.get("chain") is not None else (room.get("show") or {}).get("chain", 0)))
        counts = room.setdefault("reacts", {}).setdefault(ci, {})
        counts[emoji] = counts.get(emoji, 0) + 1
        log = room.setdefault("reactLog", [])
        log.append({"id": rid(6), "pid": pid, "emoji": emoji, "chain": int(ci), "t": time.time()})
        del log[:-30]
        return True

    if ph != "playing":
        raise Refuse("Not taking submissions right now.", 409)
    step_idx = room["step"]
    ch = chain_for(room, pid, step_idx)
    if not ch:
        raise Refuse("You're spectating this round. You'll join the next game!", 409)
    kind = step_kind(room, step_idx)

    if action == "unsubmit":
        e = entry_of(ch, step_idx)
        if e:
            e["done"] = False
        return True

    if action == "submit":
        if room.get("deadline") and time.time() > room["deadline"] + 4:
            raise Refuse("Time's up for this step.", 409)
        if kind == "write":
            text = " ".join(str(b.get("text") or "").split())[:90]
            if not text:
                raise Refuse("Write a short prompt or guess first.")
            e = entry_of(ch, step_idx)
            if e:
                e.update(text=text, done=True, late=False, auto=False)
            else:
                ch["entries"].append({"step": step_idx, "kind": "write", "pid": pid, "text": text, "done": True})
            return True
        else:
            img = str(b.get("img") or "")
            if not img.startswith("data:image/jpeg;base64,"):
                raise Refuse("The drawing didn't upload. Try again.")
            try:
                raw = base64.b64decode(img.split(",", 1)[1])
            except (ValueError, TypeError):
                raise Refuse("The drawing didn't upload. Try again.")
            if len(raw) > MAX_IMG:
                raise Refuse("That drawing is too big.")
            e = entry_of(ch, step_idx)
            img_id = rid(12)
            IMAGES[img_id] = raw
            if e:
                if e.get("img"):
                    IMAGES.pop(e["img"], None)
                e.update(img=img_id, done=True, late=False)
            else:
                ch["entries"].append({"step": step_idx, "kind": "draw", "pid": pid, "img": img_id, "done": True})
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
            raise Refuse(f"You need at least {MIN_PLAYERS} players ({len(room['players'])} so far).")
        start_game(room)
    elif action == "addtime":
        if ph != "playing" or not room.get("deadline"):
            raise Refuse("No timer is running.")
        room["deadline"] += int(b.get("sec") or 30)
    elif action == "skip":
        if ph != "playing":
            raise Refuse("Nothing to skip right now.")
        finish_step(room)
    elif action == "reveal":
        if ph not in ("show", "gallery"):
            raise Refuse("The reveal show isn't on.")
        if b.get("gallery"):
            room["phase"] = "gallery"
            return True
        room["phase"] = "show"
        total_chains = len(room["chains"])
        if not total_chains:
            return True
        ci = max(0, min(total_chains - 1, int(b.get("chain") if b.get("chain") is not None else room["show"]["chain"])))
        max_panel = max(0, len(room["chains"][ci]["entries"]) - 1)
        pi = max(0, min(max_panel, int(b.get("panel") if b.get("panel") is not None else room["show"]["panel"])))
        room["show"] = {"chain": ci, "panel": pi}
    elif action == "kick":
        pid = b.get("pid")
        room["players"].pop(pid, None)
        if ph == "playing" and everyone_done(room):
            finish_step(room)
    elif action == "playagain":
        free_images(room)
        for p in room["players"].values():
            p["sitout"] = False
        room.update({
            "phase": "lobby", "deadline": None, "order": [], "step": -1, "totalSteps": 0,
            "chains": [], "show": None, "ai": None, "aiId": None, "reacts": {}, "reactLog": [],
        })
    return True

"""Bits every game shares: uploaded pictures (drawings, player photos), the room chat, and the
error a game raises to refuse a move."""
import random
import string
import time

IMAGES = {}  # image id -> jpeg bytes, kept in memory only (gone when the server restarts)


class Refuse(Exception):
    """A move the game won't allow; the message is shown to the player."""

    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


# ---------- chat ----------
# Every game has the same chat. A game says who can read and write which channel with a
# chat_rules(room, pid) hook; without one, everyone reads and writes "all".
# Rules: {"read": [...], "write": [...], "names": {ch: label}, "why": reason you can't write,
#         "block": [words a message may not contain]}. A message on channel "*" is a game event
# that shows in every channel. Chat lives in memory only: a server restart clears it.

CHAT = {}  # room code -> messages
CHAT_KEEP = 150
DEFAULT_RULES = {"read": ["all"], "write": ["all"], "names": {"all": "Everyone"}, "why": "", "block": []}


def _rid(n):
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def chat_rules(game, room, pid):
    hook = getattr(game, "chat_rules", None) if game else None
    rules = dict(DEFAULT_RULES, **(hook(room, pid) if hook else {}))
    if pid not in room["players"]:  # spectators and people still joining only read
        rules["write"] = []
    return rules


def chat_say(room, text, ch="*", pid=None):
    """Adds a line to the room's chat. pid None means a game event."""
    log = CHAT.setdefault(room["code"], [])
    p = room["players"].get(pid) if pid else None
    log.append({"id": _rid(8), "ch": ch, "pid": pid, "name": p["name"] if p else "", "text": text, "t": time.time(), "sys": pid is None})
    del log[:-CHAT_KEEP]


def chat_view(game, room, viewer):
    rules = chat_rules(game, room, viewer)
    read = set(rules["read"])
    msgs = [m for m in CHAT.get(room["code"], []) if m["ch"] in read or (m["ch"] == "*" and read)][-100:]
    return {"chat": msgs, "chatRead": rules["read"], "chatWrite": rules["write"], "chatNames": rules["names"], "chatWhy": rules["why"]}


def chat_post(game, room, pid, b):
    p = room["players"][pid]
    rules = chat_rules(game, room, pid)
    ch = str(b.get("ch") or (rules["write"] or ["all"])[0])
    text = " ".join(str(b.get("text") or "").split())[:300]
    if not text:
        raise Refuse("Type a message first.")
    if ch not in rules["write"]:
        raise Refuse(rules["why"] or "You can't write there right now.", 409)
    low = text.lower()
    for w in rules["block"]:
        if w and w.lower() in low:
            raise Refuse("That message gives away the secret word. Try saying it another way.", 409)
    if time.time() - p.get("lastChat", 0) < .4:
        raise Refuse("Slow down a little.", 429)
    p["lastChat"] = time.time()
    chat_say(room, text, ch, pid)


# ---------- pranks ----------
# Things players throw at each other for fun (a fart, a water balloon, a kiss, a "FAHHH"...). They never
# change the game. A game may say which ones a player can throw with a prank_rules(room, pid) hook
# returning {"kinds": [...]}; otherwise everyone gets LIVING. Kept in memory only.

LIVING = ["fart", "firecracker", "balloon", "curse", "goldfish", "takoyaki", "kiss", "fahhh", "hearts", "crown"]
GHOSTLY = ["boo", "chill", "fart", "fahhh"]
PRANK_KINDS = set(LIVING) | set(GHOSTLY)
PRANKS = {}       # room code -> recent pranks
PRANK_STATS = {}  # room code -> {"sent": {pid: n}, "got": {pid: n}, "kinds": {pid: {kind: n}}}
PRANK_SHOW = 12   # seconds a prank stays in the room view (long enough for every phone to see it)
COOLDOWN = 6      # seconds between your throws
BURST = (4, 30)   # at most 4 throws in 30 seconds per player, even with the cooldown
TARGET = (6, 20)  # nobody gets hit more than 6 times in 20 seconds


def _kinds(game, room, pid):
    hook = getattr(game, "prank_rules", None) if game else None
    return hook(room, pid)["kinds"] if hook else LIVING


def _ready_at(room, pid, now):
    """When this player may throw again: the cooldown, or the burst limit, whichever is later."""
    p = room["players"].get(pid) or {}
    mine = sorted(x["t"] for x in PRANKS.get(room["code"], []) if x["from"] == pid and now - x["t"] < BURST[1])
    ready = p.get("lastPrank", 0) + COOLDOWN
    if len(mine) >= BURST[0]:
        ready = max(ready, mine[-BURST[0]] + BURST[1])
    return ready


def prank_post(game, room, pid, b):
    kind, to = str(b.get("kind") or ""), str(b.get("to") or "")
    if kind not in PRANK_KINDS or kind not in _kinds(game, room, pid):
        raise Refuse("You can't throw that right now.", 409)
    if to == pid or to not in room["players"]:
        raise Refuse("Pick someone else to prank.")
    now = time.time()
    wait = _ready_at(room, pid, now) - now
    if wait > 0:
        raise Refuse(f"Reloading. Ready in {int(wait) + 1}s.", 429)
    log = [x for x in PRANKS.get(room["code"], []) if now - x["t"] < 60]
    if sum(1 for x in log if x["to"] == to and now - x["t"] < TARGET[1]) >= TARGET[0]:
        raise Refuse(f'{room["players"][to]["name"]} has had enough for now. Pick someone else.', 429)
    room["players"][pid]["lastPrank"] = now
    log.append({"id": _rid(8), "from": pid, "to": to, "kind": kind, "t": now, "back": bool(b.get("back"))})
    PRANKS[room["code"]] = log[-40:]
    st = PRANK_STATS.setdefault(room["code"], {"sent": {}, "got": {}, "kinds": {}})
    st["sent"][pid] = st["sent"].get(pid, 0) + 1
    st["got"][to] = st["got"].get(to, 0) + 1
    st["kinds"].setdefault(to, {})[kind] = st["kinds"].get(to, {}).get(kind, 0) + 1


def prank_view(game, room, viewer):
    now = time.time()
    joined = viewer in room["players"]
    return {"pranks": [x for x in PRANKS.get(room["code"], []) if now - x["t"] < PRANK_SHOW],
            "prankKinds": _kinds(game, room, viewer) if joined else [],
            "prankWait": max(0, _ready_at(room, viewer, now) - now) if joined else 0,
            "prankCooldown": COOLDOWN,
            "prankStats": PRANK_STATS.get(room["code"], {"sent": {}, "got": {}, "kinds": {}})}


def prank_reset(room):
    """A new game starts the prank awards from zero."""
    PRANK_STATS.pop(room["code"], None)

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

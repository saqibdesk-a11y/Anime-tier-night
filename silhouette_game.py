"""Guess the Silhouette: fast-paced anime & pop-culture speed quiz.

Modes:
- "reveal": an AniList character portrait starts obscured (silhouette, heavy blur, or dramatic zoom)
  and clears smoothly over the countdown. Answer via 4-choice buttons or hardcore text typing!
- "higher": Higher or Lower—two iconic AniList characters side-by-side; pick who has more favourites!
- "trivia": 4-choice speed trivia (AI-generated on any topic, with a built-in anime/pop-culture bank).

Faster correct answers earn more points + streak bonuses. server.py plugs in avatar_gallery."""
import random
import re
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None
gallery = None  # server.py sets this to avatar_gallery

HOST_ACTIONS = ("start", "settings", "next", "skip", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 1, 12
REVEAL_SEC = 7

TRIVIA_BANK = {
    "anime": [
        ("What is the name of Naruto's signature spinning chakra attack?", ["Rasengan", "Chidori", "Kamehameha", "Getsuga Tensho"], 0),
        ("Which anime features the Survey Corps fighting giant humanoids?", ["Attack on Titan", "Tokyo Ghoul", "Bleach", "Vinland Saga"], 0),
        ("What is the name of the Shinigami who drops the Death Note?", ["Ryuk", "Rem", "L", "Mello"], 0),
        ("In One Piece, what fruit did Luffy eat?", ["Gum-Gum Fruit", "Flame-Flame Fruit", "Op-Op Fruit", "Dark-Dark Fruit"], 0),
        ("Who is the strongest Jujutsu sorcerer wearing a blindfold?", ["Satoru Gojo", "Megumi Fushiguro", "Kento Nanami", "Yuta Okkotsu"], 0),
        ("What alchemy law states something of equal value must be lost?", ["Equivalent Exchange", "Soul Resonance", "Nen Contract", "Law of Karma"], 0),
        ("Which Studio Ghibli film features a bathhouse for spirits?", ["Spirited Away", "Howl's Moving Castle", "My Neighbor Totoro", "Ponyo"], 0),
        ("What is Goku's Saiyan birth name?", ["Kakarot", "Bardock", "Broly", "Raditz"], 0),
        ("In Demon Slayer, what is Tanjiro's sister's name?", ["Nezuko", "Shinobu", "Mitsuri", "Kanao"], 0),
        ("Which anime is about a telepathic little girl named Anya?", ["Spy x Family", "Oshi no Ko", "Bocchi the Rock", "Mob Psycho 100"], 0),
        ("In Hunter x Hunter, what is Gon's Nen category?", ["Enhancer", "Transmuter", "Emitter", "Specialist"], 0),
        ("What sport is Haikyuu!! about?", ["Volleyball", "Basketball", "Soccer", "Tennis"], 0),
    ],
    "pop": [
        ("Which video game features Creepers and the Nether?", ["Minecraft", "Terraria", "Roblox", "Fortnite"], 0),
        ("What is the name of Tony Stark's AI assistant before Friday?", ["J.A.R.V.I.S.", "Ultron", "Cortana", "HAL 9000"], 0),
        ("Which K-pop group released 'Dynamite' and 'Butter'?", ["BTS", "BLACKPINK", "Stray Kids", "EXO"], 0),
        ("What color pill does Neo take in The Matrix?", ["Red", "Blue", "Green", "Gold"], 0),
        ("Which planet is Luke Skywalker's homeworld?", ["Tatooine", "Coruscant", "Naboo", "Hoth"], 0),
        ("In Mario Kart, which item targets the player in 1st place?", ["Blue Shell", "Red Shell", "Star", "Bullet Bill"], 0),
        ("What is the name of the fictional African nation in Black Panther?", ["Wakanda", "Genosha", "Sokovia", "Latveria"], 0),
        ("Which Hogwarts house has a badger as its mascot?", ["Hufflepuff", "Ravenclaw", "Slytherin", "Gryffindor"], 0),
        ("Who lives in a pineapple under the sea?", ["SpongeBob", "Patrick", "Squidward", "Mr. Krabs"], 0),
        ("Which movie features the song 'Let It Go'?", ["Frozen", "Tangled", "Moana", "Encanto"], 0),
    ],
    "food": [
        ("Which Japanese dish consists of wheat noodles in rich broth?", ["Ramen", "Sushi", "Tempura", "Onigiri"], 0),
        ("Guacamole is primarily made from which fruit?", ["Avocado", "Mango", "Lime", "Tomato"], 0),
        ("Which country is the birthplace of pizza Margherita?", ["Italy", "Greece", "Spain", "France"], 0),
        ("What gives biryani its classic yellow-orange aroma and color?", ["Saffron", "Paprika", "Cinnamon", "Oregano"], 0),
        ("Takoyaki is a Japanese festival snack filled with what?", ["Octopus", "Salmon", "Chicken", "Tofu"], 0),
        ("Which nut is used to make traditional marzipan?", ["Almond", "Peanut", "Cashew", "Walnut"], 0),
        ("What are the chewy pearls in classic bubble tea made from?", ["Tapioca", "Rice flour", "Gelatin", "Cornstarch"], 0),
        ("Which spice is the world's most expensive by weight?", ["Saffron", "Cardamom", "Vanilla", "Clove"], 0),
    ],
}
TRIVIA_BANK["mix"] = [q for qs in TRIVIA_BANK.values() for q in qs]

FALLBACK_CHARS = [
    {"name": "Naruto Uzumaki", "show": "Naruto", "img": "", "favs": 82000},
    {"name": "Monkey D. Luffy", "show": "One Piece", "img": "", "favs": 145000},
    {"name": "Son Goku", "show": "Dragon Ball Z", "img": "", "favs": 69000},
    {"name": "Levi Ackerman", "show": "Attack on Titan", "img": "", "favs": 132000},
    {"name": "Satoru Gojo", "show": "Jujutsu Kaisen", "img": "", "favs": 110000},
    {"name": "Killua Zoldyck", "show": "Hunter x Hunter", "img": "", "favs": 124000},
    {"name": "Roronoa Zoro", "show": "One Piece", "img": "", "favs": 105000},
    {"name": "L Lawliet", "show": "Death Note", "img": "", "favs": 118000},
]


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    mode = pick("mode", "reveal")
    if mode not in ("reveal", "higher", "trivia"):
        mode = "reveal"
    style = pick("style", "mix")
    if style not in ("mix", "silhouette", "blur", "zoom"):
        style = "mix"
    input_mode = "type" if pick("input", "choices") == "type" else "choices"
    topic = pick("topic", "anime")
    if topic not in ("anime", "pop", "food", "mix", "custom"):
        topic = "anime"
    return {
        "mode": mode,
        "style": style,
        "input": input_mode,
        "topic": topic,
        "custom": str(pick("custom", "")).strip()[:160],
        "rounds": max(3, min(15, int(pick("rounds", 8)))),
        "sec": max(10, min(30, int(pick("sec", 18)))),
    }


def create(room, b):
    room.update({
        "game": "silhouette", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "questions": [], "qIndex": -1, "scores": {}, "streaks": {}, "answers": {}, "startedAt": 0,
    })


def on_join(room, pid):
    room["scores"].setdefault(pid, 0)
    room["streaks"].setdefault(pid, 0)


def active_pids(room):
    act = [pid for pid, p in room["players"].items() if not p.get("wantSitout")]
    return act or list(room["players"])


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def clean_char_name(name):
    return re.sub(r"\s*\([^)]*\)$", "", str(name or "")).strip()


def char_matches(guess, answer, alias=""):
    g = norm(guess)
    if len(g) < 2:
        return False
    cands = [answer, clean_char_name(answer), alias]
    for c in list(cands):
        parts = [p for p in str(c or "").split() if len(p) >= 3]
        cands.extend(parts)
    for c in cands:
        nc = norm(c)
        if not nc:
            continue
        if g == nc or (len(nc) >= 4 and (nc in g or g in nc) and abs(len(g) - len(nc)) <= 3):
            return True
    return False


def build_questions(settings):
    n = settings["rounds"]
    mode = settings["mode"]
    chars = [c for c in (gallery() if gallery else []) if c.get("img")]
    if mode == "reveal" and len(chars) >= 6:
        pool = random.sample(chars, min(len(chars), n))
        styles = ["silhouette", "blur", "zoom"]
        qs = []
        for i, c in enumerate(pool):
            st = settings["style"] if settings["style"] != "mix" else styles[i % len(styles)]
            distractors = random.sample([x for x in chars if x["name"] != c["name"]], 3)
            opts = [clean_char_name(c["name"])] + [clean_char_name(d["name"]) for d in distractors]
            random.shuffle(opts)
            qs.append({
                "kind": "reveal", "style": st, "img": c["img"], "show": c.get("show", ""),
                "answer": clean_char_name(c["name"]), "alias": c.get("alias", ""),
                "options": opts, "correctIdx": opts.index(clean_char_name(c["name"])),
                "zx": random.randint(25, 75), "zy": random.randint(15, 55),
            })
        return qs

    if mode == "higher" and len(chars) >= 8:
        # Use favs if populated, else inverse rank order (AniList returns sorted by FAVOURITES_DESC)
        ranked = []
        for idx, c in enumerate(chars):
            favs = c.get("favs") or max(1000, 160000 - idx * 1200)
            ranked.append({**c, "favs": favs})
        qs = []
        used = set()
        attempts = 0
        while len(qs) < n and attempts < 200:
            attempts += 1
            a, b = random.sample(ranked, 2)
            pair_key = tuple(sorted([a["name"], b["name"]]))
            if pair_key in used or a["favs"] == b["favs"]:
                continue
            used.add(pair_key)
            winner = 0 if a["favs"] > b["favs"] else 1
            qs.append({
                "kind": "higher",
                "left": {"name": clean_char_name(a["name"]), "show": a.get("show", ""), "img": a["img"], "favs": a["favs"]},
                "right": {"name": clean_char_name(b["name"]), "show": b.get("show", ""), "img": b["img"], "favs": b["favs"]},
                "correctIdx": winner,
                "answer": clean_char_name(a["name"] if winner == 0 else b["name"]),
            })
        if qs:
            return qs

    # Trivia mode (or fallback if AniList gallery hasn't loaded yet)
    qs = []
    topic_txt = settings["custom"] if settings["topic"] == "custom" and settings["custom"] else settings["topic"]
    try:
        out, _, _ = ai.ask_builtin(
            "You write fun, punchy multiple-choice trivia questions for a friends' game night.",
            f"Write {n} distinct multiple-choice trivia questions about: {topic_txt}. "
            "Each question has 4 short choices and 1 indisputable right answer. Keep questions under 110 characters. "
            'Return only JSON: {"questions":[{"q":"...","options":["A","B","C","D"],"answer":0}]}',
            timeout=25, text_first=True)
        for item in (out.get("questions") or []):
            if not isinstance(item, dict):
                continue
            q = str(item.get("q") or "").strip()[:140]
            opts = [str(x).strip()[:50] for x in (item.get("options") or [])][:4]
            try:
                ans = int(item.get("answer"))
            except (TypeError, ValueError):
                ans = -1
            if q and len(opts) == 4 and 0 <= ans < 4:
                correct_txt = opts[ans]
                random.shuffle(opts)
                qs.append({"kind": "trivia", "q": q, "options": opts, "correctIdx": opts.index(correct_txt), "answer": correct_txt})
    except (ai.AIError, ValueError, TypeError, AttributeError):
        pass
    bank = TRIVIA_BANK.get(settings["topic"], TRIVIA_BANK["mix"])[:]
    random.shuffle(bank)
    for q, opts, ans in bank:
        if len(qs) >= n:
            break
        o = opts[:]
        correct_txt = o[ans]
        random.shuffle(o)
        qs.append({"kind": "trivia", "q": q, "options": o, "correctIdx": o.index(correct_txt), "answer": correct_txt})
    return qs[:n]


def begin_game(code):
    with lock:
        room = rooms.get(code)
        settings = dict(room["settings"]) if room else None
    if not settings:
        return
    qs = build_questions(settings)
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            room["questions"] = qs
            room["scores"] = {pid: 0 for pid in room["players"]}
            room["streaks"] = {pid: 0 for pid in room["players"]}
            start_question(room, 0)
            changed(room)


def start_question(room, idx):
    room["qIndex"] = idx
    room["phase"] = "question"
    room["answers"] = {}
    room["startedAt"] = time.time()
    room["deadline"] = room["startedAt"] + room["settings"]["sec"] + 1


def finish_question(room):
    q = room["questions"][room["qIndex"]]
    sec = room["settings"]["sec"]
    for pid in active_pids(room):
        ans = room["answers"].get(pid)
        if ans and ans.get("correct"):
            streak = room["streaks"].get(pid, 0) + 1
            room["streaks"][pid] = streak
            elapsed = max(0.0, ans["t"] - room["startedAt"])
            ratio = max(0.0, min(1.0, 1.0 - elapsed / max(1, sec)))
            pts = int(round(350 + 650 * ratio)) + (150 * (streak - 1) if streak >= 2 else 0)
            ans["pts"] = pts
            room["scores"][pid] = room["scores"].get(pid, 0) + pts
        else:
            room["streaks"][pid] = 0
            if ans:
                ans["pts"] = 0
    room["phase"] = "reveal"
    room["deadline"] = time.time() + REVEAL_SEC


def advance_after_reveal(room):
    if room["qIndex"] + 1 < len(room["questions"]):
        start_question(room, room["qIndex"] + 1)
    else:
        room["phase"] = "final"
        room["deadline"] = None


def tick(room):
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now >= room["deadline"]
    if ph == "question":
        act = active_pids(room)
        if over or (act and all(pid in room["answers"] for pid in act)):
            finish_question(room)
            return True
    elif ph == "reveal" and over:
        advance_after_reveal(room)
        return True
    return False


def chat_rules(room, pid):
    if room["phase"] == "question":
        q = room["questions"][room["qIndex"]] if 0 <= room["qIndex"] < len(room["questions"]) else None
        block = [q["answer"]] if q and q.get("answer") else []
        return {"read": ["all"], "write": ["all"], "block": block}
    return {"read": ["all"], "write": ["all"]}


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "questions", "answers")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["totalQuestions"] = len(room["questions"])
    if 0 <= room["qIndex"] < len(room["questions"]):
        q = room["questions"][room["qIndex"]]
        if room["phase"] == "question":
            pub_q = {k: v for k, v in q.items() if k not in ("answer", "alias", "correctIdx")}
            if q["kind"] == "higher":
                pub_q["left"] = {k: v for k, v in q["left"].items() if k != "favs"}
                pub_q["right"] = {k: v for k, v in q["right"].items() if k != "favs"}
            r["question"] = pub_q
            r["answeredPids"] = list(room["answers"])
            mine = room["answers"].get(viewer)
            r["myAnswer"] = {"locked": True, "choice": mine.get("choice"), "text": mine.get("text")} if mine else None
        else:
            r["question"] = q
            r["answers"] = room["answers"]
    return r


def player_action(room, action, b, pid):
    if action != "answer":
        raise Refuse("Unknown action")
    if room["phase"] != "question":
        raise Refuse("Not taking answers right now.", 409)
    if pid in room["answers"]:
        raise Refuse("You already locked in your answer.", 409)
    q = room["questions"][room["qIndex"]]
    now = time.time()
    if q["kind"] == "reveal" and room["settings"]["input"] == "type":
        text = " ".join(str(b.get("text") or "").split())[:50]
        if not text:
            raise Refuse("Type a character name.")
        ok = char_matches(text, q["answer"], q.get("alias", ""))
        room["answers"][pid] = {"text": text, "correct": ok, "t": now}
    else:
        choice = int(b.get("choice", -1))
        max_c = 2 if q["kind"] == "higher" else 4
        if not 0 <= choice < max_c:
            raise Refuse("Pick one of the options.")
        room["answers"][pid] = {"choice": choice, "correct": choice == q["correctIdx"], "t": now}
    act = active_pids(room)
    if act and all(p in room["answers"] for p in act):
        finish_question(room)
    return True


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the quiz starts.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action == "start":
        if ph != "lobby":
            raise Refuse("The quiz already started.")
        if len(room["players"]) < MIN_PLAYERS:
            raise Refuse("Wait for at least 1 player to join.")
        room["phase"] = "starting"
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action in ("next", "skip"):
        if ph == "question":
            finish_question(room)
        elif ph == "reveal":
            advance_after_reveal(room)
        else:
            raise Refuse("Nothing to skip right now.")
    elif action == "kick":
        room["players"].pop(b.get("pid"), None)
        room["answers"].pop(b.get("pid"), None)
    elif action == "playagain":
        room.update({
            "phase": "lobby", "deadline": None, "questions": [], "qIndex": -1,
            "scores": {pid: 0 for pid in room["players"]}, "streaks": {pid: 0 for pid in room["players"]},
            "answers": {},
        })
    return True

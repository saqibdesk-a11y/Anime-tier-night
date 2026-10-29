"""Codenames: two teams race to find their agents on a grid of words. Each team's spymaster sees the
secret key and gives one-word clues with a number; their operatives tap cards to guess. Hit the
assassin and your team loses on the spot.

Extras: anime packs and anime picture cards, AI-made boards on any topic, an AI spymaster for a team
without one (so even 2 people can play), timers, guess marks your team can see, and a series score.

server.py owns rooms, the lock and HTTP; this module owns the game's rules."""
import random
import re
import threading
import time

import ai
from media import Refuse

rooms = lock = changed = rid = None
gallery = None  # server.py plugs in the anime character list for picture cards

HOST_ACTIONS = ("start", "settings", "shuffle", "kick", "playagain", "skip", "addtime", "tolobby")
TEAMS = ("red", "blue")
UNLIMITED = 10  # a clue of "infinity" (or 0): guess as many as you like

WORDS = {
    "classic": """Africa Agent Air Alien Alps Amazon Ambulance America Angel Antarctica Apple Arm Atlantis Australia
        Back Ball Band Bank Bar Bark Bat Battery Beach Bear Beat Bed Beijing Bell Belt Berlin Bermuda Berry Bill
        Block Board Bolt Bomb Bond Boom Boot Bottle Bow Box Bridge Brush Buck Buffalo Bug Bugle Button Calf
        Canada Cap Capital Car Card Carrot Casino Cast Cat Cell Centaur Center Chair Change Charge Check Chest
        Chick China Chocolate Church Circle Cliff Cloak Club Code Cold Comic Compound Concert Conductor Contract
        Cook Copper Cotton Court Cover Crane Crash Cricket Cross Crown Cycle Czech Dance Date Day Death Deck
        Degree Diamond Dice Dinosaur Disease Doctor Dog Draft Dragon Dress Drill Drop Duck Dwarf Eagle Egypt
        Embassy Engine England Europe Eye Face Fair Fall Fan Fence Field Fighter Figure File Film Fire Fish Flute
        Fly Foot Force Forest Fork France Game Gas Genius Germany Ghost Giant Glass Glove Gold Grace Grass Greece
        Green Ground Ham Hand Hawk Head Heart Helicopter Himalayas Hole Hollywood Honey Hood Hook Horn Horse
        Hospital Hotel Ice Iron Jack Jam Jet Jupiter Kangaroo Ketchup Key Kid King Kiwi Knife Knight Lab Lap Laser
        Lawyer Lead Lemon Leprechaun Life Light Limousine Line Link Lion Litter Lock Log London Luck Mail Mammoth
        Maple Marble March Mass Match Mercury Mexico Microscope Millionaire Mine Mint Missile Model Mole Moon Moscow
        Mount Mouse Mouth Mug Nail Needle Net Night Ninja Note Novel Nurse Nut Octopus Oil Olive Olympus Opera
        Orange Organ Palm Pan Pants Paper Parachute Park Part Pass Paste Penguin Phoenix Piano Pie Pilot Pin Pipe
        Pirate Pistol Pit Pitch Plane Plastic Plate Platypus Play Plot Point Poison Pole Police Pool Port Post
        Pound Press Princess Pumpkin Pupil Pyramid Queen Rabbit Racket Ray Revolution Ring Robin Robot Rock Rome
        Root Rose Roulette Round Row Ruler Satellite Saturn Scale School Scientist Scorpion Screen Scuba Seal
        Server Shadow Shakespeare Shark Ship Shoe Shop Shot Sink Skyscraper Slip Slug Smuggler Snow Snowman Sock
        Soldier Soul Sound Space Spell Spider Spike Spine Spot Spring Spy Square Stadium Staff Star State Stick
        Stock Straw Stream Strike String Sub Suit Superhero Swing Switch Table Tablet Tag Tail Tap Teacher
        Telescope Temple Theater Thief Thumb Tick Tie Time Tokyo Tooth Torch Tower Track Train Triangle Trip
        Trunk Tube Turkey Undertaker Unicorn Vacuum Van Vet Wake Wall War Washer Washington Watch Water Wave Web
        Well Whale Whip Wind Witch Worm Yard""",
    "anime": """Naruto Goku Luffy Zoro Pikachu Totoro Titan Shinigami Hokage Bankai Chakra Ramen Sharingan Kunai
        Katana Ninja Samurai Senpai Isekai Mecha Gundam Eva Hollow Quirk Nen Devil Fruit Straw Hat Pirate King
        Dragon Ball Scouter Kamehameha Saiyan Namek Bulma Vegeta Gohan Frieza Cell Buu Death Note Kira Ryuk Apple
        Shinji Rei Asuka Akatsuki Itachi Sasuke Kakashi Hinata Gaara Jiraiya Rasengan Scroll Clone Toad Fox
        Demon Slayer Tanjiro Nezuko Hashira Breathing Sunrise Mask Titan Wall Scout Levi Eren Mikasa Survey
        Jujutsu Gojo Sukuna Domain Curse Finger Blindfold Hunter Gon Killua Spider Chimera Ant Exam Alchemist
        Philosopher Stone Automail Homunculus Equivalent Exchange One Piece Grand Line Marine Yonko Haki Rubber
        Sword Cola Robot Ghoul Kagune Coffee Mask Spirit Bathhouse Castle Witch Broom Cat Bus Forest Ponyo
        Soul Gem Magical Girl Transformation Moon Prism Sailor Tuxedo Pokemon Pokeball Gym Badge Evolution
        Trainer Tournament Rival Power Up Training Arc Filler Opening Ending Beach Episode Festival Fireworks
        Kimono Shrine Fox Cherry Blossom Bento Onigiri Sushi Mochi Dango Tsundere Yandere Waifu Chibi Manga
        Volume Chapter Cliffhanger Hiatus Studio Ghibli Shonen Jump Akira Bike Neo Tokyo Cowboy Bebop Spike Jet
        Spirit Gun Hollow Mask Zanpakuto Quincy Espada Chainsaw Devil Makima Denji Power Spy Family Anya Peanut
        Bond Loid Yor Frieren Elf Mage Hero Demon King Slime Overlord Skeleton Sword Art Online Kirito Game Over
        Log Horizon Re Zero Return Death Steins Gate Microwave Banana Time Leap Code Geass Geass Zero Knightmare""",
    "pop": """Netflix TikTok Instagram YouTube Twitter Snapchat Discord Twitch Spotify Meme Emoji Selfie Influencer
        Podcast Livestream Viral Hashtag Filter Story Reel Streamer Gamer Esports Marvel Avengers Batman Joker
        Superman Spider-Man Thanos Iron Man Hulk Thor Loki Wakanda Hogwarts Wizard Wand Dumbledore Voldemort
        Hobbit Ring Gollum Jedi Sith Lightsaber Vader Yoda Wookiee Droid Minion Shrek Donkey Elsa Olaf Simba
        Nemo Dory Buzz Woody Barbie Ken Oppenheimer Titanic Avatar Matrix Neo Terminator Godzilla Kong Jaws
        Dinosaur Jurassic Stranger Things Upside Down Squid Game Breaking Bad Office Friends Simpsons SpongeBob
        Patrick Krabby Patty Mario Luigi Peach Bowser Zelda Link Sonic Pac-Man Tetris Minecraft Creeper Fortnite
        Roblox Among Us Imposter Pokemon Taylor Swift Beyonce Drake Rihanna Eminem BTS Blackpink Kpop Grammy
        Oscar Red Carpet Paparazzi Celebrity Billionaire Elon Rocket Tesla iPhone Android Apple Google Amazon
        Prime Uber Airbnb Crypto Bitcoin NFT AI Robot Chatbot Algorithm Cloud Password Wifi Charger Battery""",
    "food": """Pizza Burger Sushi Ramen Taco Burrito Pasta Lasagna Steak Chicken Wings Nuggets Fries Ketchup Mustard
        Mayo Pickle Onion Garlic Pepper Chili Curry Biryani Kebab Shawarma Falafel Hummus Naan Samosa Pakora
        Dumpling Noodle Rice Bread Toast Bagel Croissant Donut Muffin Pancake Waffle Syrup Honey Butter Cheese
        Milk Yogurt Egg Bacon Sausage Ham Salad Soup Sandwich Wrap Popcorn Chips Cookie Brownie Cake Cupcake
        Pie Candy Chocolate Caramel Vanilla Ice Cream Sundae Cone Sprinkles Jelly Gum Mint Lemon Lime Orange
        Apple Banana Mango Grape Cherry Strawberry Watermelon Pineapple Coconut Avocado Tomato Potato Carrot
        Corn Mushroom Broccoli Peanut Almond Coffee Tea Juice Soda Smoothie Milkshake Boba Water Lemonade""",
    "games": """Mario Zelda Link Sonic Kirby Pikachu Creeper Steve Herobrine Diamond Pickaxe Sword Shield Potion
        Health Mana Boss Level Checkpoint Respawn Lag Noob Pro Speedrun Glitch Cheat Code Easter Egg Loot Chest
        Quest Dungeon Dragon Knight Mage Archer Tank Healer Sniper Headshot Grenade Battle Royale Storm Zone
        Victory Royale Emote Skin Battle Pass Controller Joystick Console Arcade Coin Token Cartridge Pixel
        Fortnite Roblox Minecraft Among Us Valorant Apex Overwatch League Dota Tetris Pac-Man Ghost Cherry
        Kart Banana Shell Star Mushroom Pipe Castle Princess Bowser Yoshi Donkey Kong Barrel Hammer Portal
        Cake Companion Cube Elden Ring Souls Bonfire Dark Halo Master Chief Kratos Axe Ellie Joel Mushroom
        Zombie Crafting Farm Village Trade Raid Clan Lobby Ranked Elo Smurf Tryhard Clutch Ace GG""",
}
WORDS["mix"] = " ".join(WORDS.values())
PACKS = {"classic": "Classic", "anime": "Anime", "pictures": "Anime characters (pictures)", "pop": "Pop culture",
         "food": "Food", "games": "Video games", "mix": "Mix of everything", "custom": "Custom (AI)"}


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    pack = pick("pack", "classic")
    return {
        "pack": pack if pack in PACKS else "classic",
        "custom": str(pick("custom", "")).strip()[:200],
        "size": 16 if int(pick("size", 25)) == 16 else 25,
        "assassins": 2 if int(pick("assassins", 1)) == 2 else 1,
        "clueSec": max(0, min(300, int(pick("clueSec", 0)))),  # 0 = no timer
        "guessSec": max(0, min(300, int(pick("guessSec", 0)))),
        "aiSpy": bool(pick("aiSpy", True)),  # an AI spymaster fills a team's empty spymaster seat
        "chat": pick("chat", "teams") if pick("chat", "teams") in ("teams", "all", "off") else "teams",
    }


def create(room, b):
    room.update({"game": "codenames", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
                 "cards": [], "turn": None, "clue": None, "log": [], "marks": {}, "winner": None, "why": None,
                 "wins": {"red": 0, "blue": 0}, "aiThinking": None, "aiNote": None, "gameNo": 0, "chat": []})


def on_join(room, pid):
    # land on the smaller team so teams stay even; late joiners become operatives
    sizes = {t: sum(1 for p in room["players"].values() if p.get("team") == t) for t in TEAMS}
    team = min(TEAMS, key=lambda t: (sizes[t], random.random()))
    room["players"][pid].update({"team": team, "role": "op"})


# ---------- helpers ----------

def other(team):
    return "blue" if team == "red" else "red"


def name(room, pid):
    p = room["players"].get(pid)
    return p["name"] if p else "Someone"


def members(room, team, role=None):
    return [pid for pid, p in room["players"].items() if p.get("team") == team and (role is None or p.get("role") == role)]


def spymaster(room, team):
    """The human spymaster's id, 'ai' for the AI, or None for nobody."""
    s = members(room, team, "spy")
    if s:
        return s[0]
    return "ai" if room["settings"]["aiSpy"] and ai.BUILTIN_ORDER else None


def left(room, team):
    return sum(1 for c in room["cards"] if c["key"] == team and not c["revealed"])


def norm(w):
    w = re.sub(r"[^a-z0-9]", "", str(w).lower())
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def label(c):
    return c["w"]


def clue_clash(room, word):
    """A clue can't be a word on the board, or part of one (or the other way round)."""
    n = norm(word)
    if not n:
        return "Type a clue."
    for c in room["cards"]:
        if c["revealed"]:
            continue
        for part in [c["w"]] + c["w"].split():
            m = norm(part)
            if m and len(m) > 2 and (m == n or (len(n) > 3 and (m in n or n in m))):
                return (f'"{c["w"]}" is on the board. Pick another word.' if m == n
                        else f'"{word}" is too close to "{c["w"]}" on the board.')
    return None


def say(room, text, ch="both", pid=None):
    """Adds a chat line. ch is "all", a team, or "both" (game events everyone should see in their own chat)."""
    room.setdefault("chat", []).append({"id": rid(6), "pid": pid, "ch": ch, "text": text, "at": time.time(), "sys": pid is None})
    del room["chat"][:-150]


def set_timer(room, secs):
    room["deadline"] = time.time() + secs + 1 if secs else None


def stat(room, pid, k):
    s = room.setdefault("stats", {}).setdefault(pid, {"right": 0, "wrong": 0, "assassin": 0, "clues": 0})
    s[k] += 1


# ---------- the board ----------

def make_words(settings, n):
    pack = settings["pack"]
    if pack == "custom" and settings["custom"]:
        try:
            out, _, _ = ai.ask_builtin(
                "You make word boards for the party game Codenames.",
                f"Give {n + 10} different Codenames words about: {settings['custom']}. Mostly single words (2 words at most), "
                "concrete and well known, with lots of overlap potential so clever clues can link several. No repeats. "
                'Return only JSON: {"words": ["...", ...]}', timeout=25, text_first=True)
            words = []
            for w in out.get("words", []):
                w = " ".join(str(w).split())[:22]
                if w and norm(w) not in {norm(x) for x in words}:
                    words.append(w)
            if len(words) >= n:
                random.shuffle(words)
                return [{"w": w} for w in words[:n]]
        except (ai.AIError, ValueError, TypeError, AttributeError):
            pass
        pack = "mix"
    if pack == "pictures":
        chars = [c for c in (gallery() if gallery else []) if c.get("img")]
        if len(chars) >= n:
            picked = random.sample(chars, n)
            return [{"w": (c.get("alias") or c["name"].split(" (")[0]), "img": c["img"], "show": c.get("show", "")} for c in picked]
        pack = "anime"
    pool, seen = [], set()
    for w in re.findall(r"[^\s]+", WORDS[pack]):
        if norm(w) not in seen:
            seen.add(norm(w))
            pool.append(w)
    return [{"w": w} for w in random.sample(pool, n)]


def deal(room, words):
    s = room["settings"]
    n = s["size"]
    first = random.choice(TEAMS)
    agents = 9 if n == 25 else 6
    keys = [first] * agents + [other(first)] * (agents - 1) + ["assassin"] * s["assassins"]
    keys += ["neutral"] * (n - len(keys))
    random.shuffle(keys)
    room["cards"] = [{**w, "key": k, "revealed": False, "by": None} for w, k in zip(words, keys)]
    room.update({"turn": first, "first": first, "clue": None, "log": [], "marks": {}, "winner": None, "why": None,
                 "stats": {}, "aiNote": None, "aiThinking": None, "dealId": rid(6)})
    room["gameNo"] += 1
    begin_clue(room)


def begin_game(code):
    with lock:
        room = rooms.get(code)
        settings = dict(room["settings"]) if room else None
    if not settings:
        return
    words = make_words(settings, settings["size"])
    with lock:
        room = rooms.get(code)
        if room and room["phase"] == "starting":
            deal(room, words)
            changed(room)


# ---------- turns ----------

def begin_clue(room):
    room["phase"] = "clue"
    room["clue"] = None
    room["marks"] = {}
    sm = spymaster(room, room["turn"])
    if sm == "ai":
        set_timer(room, 0)
        room["aiThinking"] = rid(6)
        threading.Thread(target=ai_clue, args=(room["code"], room["aiThinking"]), daemon=True).start()
    else:
        set_timer(room, room["settings"]["clueSec"])


def give_clue(room, word, n, by, targets=None):
    room["clue"] = {"word": word, "n": n, "by": by, "team": room["turn"], "guesses": 0, "right": 0, "id": rid(6)}
    if targets:
        room["clue"]["targets"] = targets  # the AI's plan: shown to everyone when the game ends
    room["log"].append({"kind": "clue", "team": room["turn"], "word": word, "n": n, "by": by,
                        "targets": targets or None, "right": 0, "id": room["clue"]["id"]})
    room["phase"] = "guess"
    room["aiThinking"] = None
    say(room, f'{"AI spymaster" if by == "ai" else name(room, by)} gave {room["turn"].title()} the clue: {word} {"∞" if n == UNLIMITED else n}')
    set_timer(room, room["settings"]["guessSec"])


def end_turn(room, why=None):
    room["log"].append({"kind": "end", "team": room["turn"], "why": why})
    room["turn"] = other(room["turn"])
    begin_clue(room)


def win(room, team, why):
    room.update({"phase": "over", "winner": team, "why": why, "deadline": None, "aiThinking": None, "marks": {}})
    room["wins"][team] = room["wins"].get(team, 0) + 1


def reveal(room, i, pid):
    c = room["cards"][i]
    team, clue = room["turn"], room["clue"]
    c["revealed"], c["by"] = True, pid
    room["marks"].pop(str(i), None)
    clue["guesses"] += 1
    room["log"].append({"kind": "guess", "team": team, "by": pid, "i": i, "w": c["w"], "key": c["key"]})
    room["lastReveal"] = {"i": i, "key": c["key"], "team": team, "id": rid(6)}
    what = {"assassin": "the ASSASSIN", "neutral": "a bystander", team: "their own agent"}.get(c["key"], f"a {c['key'].title()} agent")
    say(room, f"{name(room, pid)} locked {c['w']}: {what}")
    if c["key"] == "assassin":
        stat(room, pid, "assassin")
        win(room, other(team), "assassin")
        return
    if c["key"] == team:
        stat(room, pid, "right")
        clue["right"] += 1
        for e in reversed(room["log"]):
            if e["kind"] == "clue":
                e["right"] = clue["right"]
                break
    else:
        stat(room, pid, "wrong")
    for t in TEAMS:  # finding your last agent wins, even when the other team turned it over for you
        if not left(room, t):
            win(room, t, "agents")
            return
    if c["key"] != team:
        end_turn(room, "wrong")
    elif clue["n"] not in (0, UNLIMITED) and clue["guesses"] >= clue["n"] + 1:
        end_turn(room, "out")


# ---------- the AI spymaster ----------

def ai_clue(code, tid):
    with lock:
        room = rooms.get(code)
        if not room or room.get("aiThinking") != tid:
            return
        team = room["turn"]
        desc = lambda c: c["w"] + (f' ({c["show"]})' if c.get("show") else "")
        live = [c for c in room["cards"] if not c["revealed"]]
        mine = [desc(c) for c in live if c["key"] == team]
        theirs = [desc(c) for c in live if c["key"] == other(team)]
        neutral = [desc(c) for c in live if c["key"] == "neutral"]
        assassin = [desc(c) for c in live if c["key"] == "assassin"]
        past = [e["word"] for e in room["log"] if e["kind"] == "clue"]
        pics = room["settings"]["pack"] == "pictures"
        theme = room["settings"]["custom"] if room["settings"]["pack"] == "custom" else ""
        cards = {norm(c["w"]): c["w"] for c in live}
    system = ("You are a brilliant Codenames spymaster. Give one clue word that links as many of your team's cards as "
              "you safely can, while steering clear of the other team's cards and above all the assassin. "
              "The clue must be a single word (a well-known name is fine), not any word on the board and not part of one. "
              + ("The cards are anime characters; their show is in brackets. Clues can be about their show, powers, looks or personality. " if pics else ""))
    prompt = (f"Your team's cards: {', '.join(mine)}.\nOther team's cards: {', '.join(theirs)}.\n"
              f"Neutral cards: {', '.join(neutral) or 'none'}.\nASSASSIN (never point near it): {', '.join(assassin)}.\n"
              + (f"Clues already given: {', '.join(past)}.\n" if past else "")
              + (f"Every card is about {theme}, so '{theme}' and words like it are useless as clues. Be more specific.\n" if theme else "")
              + "Aim for 2 or 3 cards when a link is strong; 1 is fine when only a weak link exists. "
              'Return only JSON: {"clue": "word", "number": 2, "targets": ["card", "card"]}')
    word = n = targets = None
    err = ""
    for attempt in range(2):
        try:
            out, _, _ = ai.ask_builtin(system, prompt + err, timeout=30, text_first=True)
            w = " ".join(str(out.get("clue") or "").split())[:30]
            k = max(1, min(9, int(out.get("number") or 1)))
            t = [cards.get(norm(x), str(x)) for x in (out.get("targets") or [])][:9]
            with lock:
                room = rooms.get(code)
                if not room or room.get("aiThinking") != tid:
                    return
                clash = clue_clash(room, w) if w else "It was empty."
            if clash:
                err = f"\nYour last clue was rejected: {clash} Pick a different clue."
                continue
            word, n, targets = w, k, t
            break
        except (ai.AIError, ValueError, TypeError, AttributeError):
            err = ""
    with lock:
        room = rooms.get(code)
        if not room or room.get("aiThinking") != tid or room["phase"] != "clue":
            return
        if word:
            give_clue(room, word, n, "ai", targets)
        else:
            room["aiThinking"] = None
            room["aiNote"] = "The AI spymaster couldn't come up with a clue. Someone take the spymaster seat, or the host can retry."
            room["aiFailed"] = room["turn"]
        changed(room)


# ---------- the clock ----------

def tick(room):
    if room["phase"] not in ("clue", "guess") or not room.get("deadline") or time.time() < room["deadline"]:
        return False
    if room["phase"] == "clue":
        room["log"].append({"kind": "end", "team": room["turn"], "why": "clue-timeout"})
        room["turn"] = other(room["turn"])
        begin_clue(room)
    else:
        end_turn(room, "timeout")
    return True


# ---------- what each viewer sees ----------

def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "cards", "clue", "log")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    me = room["players"].get(viewer) if viewer else None
    over = room["phase"] == "over"
    sees_key = over or bool(me and me.get("role") == "spy" and me.get("team") in TEAMS)
    r["cards"] = [{k: v for k, v in c.items() if k != "key"} | ({"key": c["key"]} if c["revealed"] or sees_key else {})
                  for c in room["cards"]]
    clue = room.get("clue")
    r["clue"] = {k: v for k, v in clue.items() if k != "targets" or over} if clue else None
    r["log"] = [{k: v for k, v in e.items() if k != "targets" or over} for e in room["log"]]
    r["left"] = {t: left(room, t) for t in TEAMS}
    r["total"] = {t: sum(1 for c in room["cards"] if c["key"] == t) for t in TEAMS}
    r["spymasters"] = {t: spymaster(room, t) for t in TEAMS}
    r["aiReady"] = bool(ai.BUILTIN_ORDER)
    r["packs"] = PACKS
    # chat: everyone sees the "all" channel; with team chats you only see your own team's
    team = me.get("team") if me else None
    mode = room["settings"]["chat"]
    r["chat"] = [] if mode == "off" else [m for m in room.get("chat", [])
                                         if m["ch"] == "both" or (mode == "all" and m["ch"] == "all") or (mode == "teams" and m["ch"] == team)]
    return r


# ---------- actions (lock held) ----------

def player_action(room, action, b, pid):
    p, ph = room["players"][pid], room["phase"]
    if action == "team":
        team, role = b.get("team"), b.get("role", "op")
        if team not in TEAMS or role not in ("op", "spy"):
            raise Refuse("Pick a team.")
        live = ph in ("starting", "clue", "guess")
        if live and p.get("role") == "spy" and (role, team) != ("spy", p.get("team")):
            raise Refuse("You've seen the key, so you stay put until this game ends.")
        if role == "spy":
            taken = [q for q in members(room, team, "spy") if q != pid]
            if taken:
                raise Refuse(f"{name(room, taken[0])} is already the {team} spymaster.")
        p.update({"team": team, "role": role})
        if role == "spy" and ph == "clue" and room["turn"] == team:  # a human takes over from the AI
            room["aiNote"] = room["aiFailed"] = room["aiThinking"] = None
            set_timer(room, room["settings"]["clueSec"])
        return True
    if action == "chat":
        mode = room["settings"]["chat"]
        if mode == "off":
            raise Refuse("Chat is off in this game.")
        if p.get("role") == "spy" and ph in ("clue", "guess"):
            raise Refuse("Spymasters can't chat mid-game. Your clues do the talking.")
        text = " ".join(str(b.get("text") or "").split())[:200]
        if not text:
            raise Refuse("Type a message.")
        if time.time() - p.get("lastChat", 0) < .5:
            raise Refuse("Slow down a little.")
        p["lastChat"] = time.time()
        say(room, text, "all" if mode == "all" else p.get("team"), pid)
        return True
    if action == "clue":
        if ph != "clue" or p.get("team") != room["turn"] or p.get("role") != "spy":
            raise Refuse("It's not your turn to give a clue.", 409)
        word = " ".join(str(b.get("word") or "").split())[:30]
        clash = clue_clash(room, word)
        if clash:
            raise Refuse(clash)
        n = int(b.get("n") if b.get("n") is not None else 1)
        if n < 0 or n > UNLIMITED:
            raise Refuse("Pick a number.")
        stat(room, pid, "clues")
        give_clue(room, word, n, pid)
        return True
    if action in ("mark", "reveal", "endturn"):
        if ph != "guess" or p.get("team") != room["turn"] or p.get("role") != "op":
            raise Refuse("It's not your team's turn to guess." if p.get("role") != "spy" else "Spymasters don't guess.", 409)
        if action == "endturn":
            if not room["clue"]["guesses"]:
                raise Refuse("Make at least one guess first.")
            end_turn(room, "pass")
            return True
        i = int(b.get("i", -1))
        if not 0 <= i < len(room["cards"]) or room["cards"][i]["revealed"]:
            raise Refuse("Pick a hidden card.")
        if action == "mark":
            marks = room["marks"].setdefault(str(i), [])
            if pid in marks:
                marks.remove(pid)
            else:
                marks.append(pid)
            if not marks:
                room["marks"].pop(str(i), None)
            return True
        reveal(room, i, pid)
        return True
    raise Refuse("Unknown action")


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph not in ("lobby", "over"):
            raise Refuse("Settings lock while a game is on.")
        room["settings"] = clean_settings(b, room["settings"])
    elif action == "shuffle":
        if ph not in ("lobby", "over"):
            raise Refuse("Shuffle teams between games.")
        ps = list(room["players"])
        random.shuffle(ps)
        for k, pid in enumerate(ps):
            room["players"][pid].update({"team": TEAMS[k % 2], "role": "op"})
        if b.get("spies"):  # one spymaster per team, picked at random
            for t in TEAMS:
                m = members(room, t)
                if len(m) >= 2 or not (room["settings"]["aiSpy"] and ai.BUILTIN_ORDER):
                    if m:
                        room["players"][m[0]]["role"] = "spy"
    elif action == "start" or action == "playagain":
        if ph not in ("lobby", "over"):
            raise Refuse("A game is already on.")
        if action == "playagain" and b.get("rotate"):
            for t in TEAMS:  # the next person on each team takes a turn as spymaster
                m = members(room, t)
                if len(m) >= 2:
                    s = members(room, t, "spy")
                    nxt = m[(m.index(s[0]) + 1) % len(m)] if s else m[0]
                    for pid in m:
                        room["players"][pid]["role"] = "spy" if pid == nxt else "op"
        for t in TEAMS:
            if not members(room, t, "op"):
                raise Refuse(f"{t.title()} team needs at least one guesser.")
            if not spymaster(room, t):
                raise Refuse(f"{t.title()} team needs a spymaster" + (" (or turn on the AI spymaster)." if ai.BUILTIN_ORDER else "."))
        room["phase"] = "starting"
        room["deadline"] = None
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action == "skip":
        if ph == "guess":
            end_turn(room, "host")
        elif ph == "clue":
            if room.get("aiFailed") == room["turn"] or spymaster(room, room["turn"]) == "ai":
                room["aiNote"] = room["aiFailed"] = None
                begin_clue(room)  # the AI tries again
            else:
                end_turn(room, "host")
        else:
            raise Refuse("Nothing to skip right now.")
    elif action == "addtime":
        if not room.get("deadline"):
            raise Refuse("No timer is running.")
        room["deadline"] += int(b.get("sec") or 30)
    elif action == "kick":
        room["players"].pop(b.get("pid"), None)
        for k in list(room["marks"]):
            room["marks"][k] = [x for x in room["marks"][k] if x != b.get("pid")]
    elif action == "tolobby":
        room.update({"phase": "lobby", "deadline": None, "aiThinking": None})
    return True

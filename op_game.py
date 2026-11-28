"""OP Beat Clash: Guess the Anime Opening OR Normal Song from live 30-second music previews!

Uses Apple's free public iTunes Search API (zero API keys, zero Python deps) to fetch real
30-second HTTPS .m4a previews + high-res cover artwork for:
  - Anime OPs & EDs (Shounen Bangers, Modern Hits, Classics, Movies & Romance, or All)
  - Global Pop, Hip-Hop & Rap, K-Pop, Rock & Throwbacks, Bollywood & Desi
  - Any Custom Artist / Franchise / Song search!
Supports both fast 4-Choice and Hardcore Type-Answer modes with fuzzy typo tolerance and
speed + streak scoring."""
import concurrent.futures
import difflib
import json
import random
import re
import threading
import time
import urllib.parse
import urllib.request

from media import Refuse

rooms = lock = changed = rid = None

HOST_ACTIONS = ("start", "settings", "next", "skip", "kick", "playagain")
MIN_PLAYERS, MAX_PLAYERS = 1, 12
REVEAL_SEC = 7

# Curated Anime OPs: (search_query, anime_title, song_title, artist, era_tag)
ANIME_OPS = [
    ("Unravel TK from Ling Tosite Sigure", "Tokyo Ghoul", "Unravel", "TK from Ling tosite sigure", "classic"),
    ("Gurenge LiSA", "Demon Slayer", "Gurenge", "LiSA", "modern"),
    ("Idol YOASOBI", "Oshi no Ko", "Idol", "YOASOBI", "modern"),
    ("Bling Bang Bang Born Creepy Nuts", "Mashle", "Bling-Bang-Bang-Born", "Creepy Nuts", "modern"),
    ("Kick Back Kenshi Yonezu", "Chainsaw Man", "KICK BACK", "Kenshi Yonezu", "modern"),
    ("Kaikai Kitan Eve", "Jujutsu Kaisen", "Kaikai Kitan", "Eve", "modern"),
    ("SPECIALZ King Gnu", "Jujutsu Kaisen", "SPECIALZ", "King Gnu", "modern"),
    ("Where Our Blue Is Tatsuya Kitani", "Jujutsu Kaisen", "Where Our Blue Is", "Tatsuya Kitani", "modern"),
    ("Blue Bird Ikimonogakari", "Naruto Shippuden", "Blue Bird", "Ikimonogakari", "shounen"),
    ("Silhouette KANA-BOON", "Naruto Shippuden", "Silhouette", "KANA-BOON", "shounen"),
    ("Haruka Kanata ASIAN KUNG-FU GENERATION", "Naruto", "Haruka Kanata", "ASIAN KUNG-FU GENERATION", "shounen"),
    ("Sign FLOW", "Naruto Shippuden", "Sign", "FLOW", "shounen"),
    ("We Are Hiroshi Kitadani", "One Piece", "We Are!", "Hiroshi Kitadani", "shounen"),
    ("Guren no Yumiya Linked Horizon", "Attack on Titan", "Guren no Yumiya", "Linked Horizon", "shounen"),
    ("Shinzou wo Sasageyo Linked Horizon", "Attack on Titan", "Shinzou wo Sasageyo!", "Linked Horizon", "shounen"),
    ("The Rumbling SiM", "Attack on Titan", "The Rumbling", "SiM", "modern"),
    ("My War Shinsei Kamattechan", "Attack on Titan", "My War", "Shinsei Kamattechan", "modern"),
    ("A Cruel Angel's Thesis Yoko Takahashi", "Neon Genesis Evangelion", "A Cruel Angel's Thesis", "Yoko Takahashi", "classic"),
    ("Again YUI", "Fullmetal Alchemist: Brotherhood", "Again", "YUI", "classic"),
    ("Crossing Field LiSA", "Sword Art Online", "Crossing Field", "LiSA", "classic"),
    ("Peace Sign Kenshi Yonezu", "My Hero Academia", "Peace Sign", "Kenshi Yonezu", "shounen"),
    ("THE DAY Porno Graffitti", "My Hero Academia", "THE DAY", "Porno Graffitti", "shounen"),
    ("The World Nightmare", "Death Note", "the WORLD", "Nightmare", "classic"),
    ("Departure Masatoshi Ono", "Hunter x Hunter", "Departure!", "Masatoshi Ono", "shounen"),
    ("Inferno Mrs GREEN APPLE", "Fire Force", "Inferno", "Mrs. GREEN APPLE", "shounen"),
    ("Black Catcher Vickeblanka", "Black Clover", "Black Catcher", "Vickeblanka", "shounen"),
    ("Black Rover Vickeblanka", "Black Clover", "Black Rover", "Vickeblanka", "shounen"),
    ("Cry Baby Official HIGE DANdism", "Tokyo Revengers", "Cry Baby", "Official HIGE DANdism", "modern"),
    ("Mixed Nuts Official HIGE DANdism", "Spy x Family", "Mixed Nuts", "Official HIGE DANdism", "modern"),
    ("Otonoke Creepy Nuts", "Dandadan", "Otonoke", "Creepy Nuts", "modern"),
    ("Yuusha YOASOBI", "Frieren: Beyond Journey's End", "Yuusha", "YOASOBI", "modern"),
    ("LEveL SawanoHiroyuki TOMORROW X TOGETHER", "Solo Leveling", "LEveL", "SawanoHiroyuki[nZk]:TXT", "modern"),
    ("THE HERO JAM Project", "One Punch Man", "THE HERO!!", "JAM Project", "shounen"),
    ("99 MOB CHOIR", "Mob Psycho 100", "99", "MOB CHOIR", "shounen"),
    ("Colors FLOW", "Code Geass", "COLORS", "FLOW", "classic"),
    ("Kyouran Hey Kids THE ORAL CIGARETTES", "Noragami", "Kyouran Hey Kids!!", "THE ORAL CIGARETTES", "classic"),
    ("Imagination SPYAIR", "Haikyuu!!", "Imagination", "SPYAIR", "shounen"),
    ("Fly High BURNOUT SYNDROMES", "Haikyuu!!", "FLY HIGH!!", "BURNOUT SYNDROMES", "shounen"),
    ("CHA-LA HEAD-CHA-LA Hironobu Kageyama", "Dragon Ball Z", "CHA-LA HEAD-CHA-LA", "Hironobu Kageyama", "classic"),
    ("Tank Seatbelts", "Cowboy Bebop", "Tank!", "Seatbelts", "classic"),
    ("Hacking to the Gate Kanako Ito", "Steins;Gate", "Hacking to the Gate", "Kanako Ito", "classic"),
    ("Sparkle RADWIMPS", "Your Name", "Sparkle", "RADWIMPS", "romance"),
    ("Zenzenzense RADWIMPS", "Your Name", "Zenzenzense", "RADWIMPS", "romance"),
    ("Suzume RADWIMPS", "Suzume", "Suzume", "RADWIMPS", "romance"),
    ("Hikaru Nara Goose house", "Your Lie in April", "Hikaru Nara", "Goose house", "romance"),
    ("DADDY DADDY DO Masayuki Suzuki", "Kaguya-sama: Love is War", "DADDY! DADDY! DO!", "Masayuki Suzuki", "romance"),
    ("Love Dramatic Masayuki Suzuki", "Kaguya-sama: Love is War", "Love Dramatic", "Masayuki Suzuki", "romance"),
    ("Renai Circulation Kana Hanazawa", "Bakemonogatari", "Renai Circulation", "Kana Hanazawa", "romance"),
    ("I Really Want to Stay at Your House Rosa Walton", "Cyberpunk: Edgerunners", "I Really Want to Stay at Your House", "Rosa Walton", "romance"),
    ("Mukanjyo Survive Said The Prophet", "Vinland Saga", "Mukanjyo", "Survive Said The Prophet", "modern"),
    ("Zankyosanka Aimer", "Demon Slayer", "Zankyosanka", "Aimer", "modern"),
    ("Asterisk ORANGE RANGE", "Bleach", "*~Asterisk~*", "ORANGE RANGE", "classic"),
    ("Change the World V6", "Inuyasha", "Change the World", "V6", "classic"),
    ("Bloody Stream Coda", "JoJo's Bizarre Adventure", "BLOODY STREAM", "Coda", "shounen"),
]

# Normal Song Playlists: (search_query, display_title, artist)
SONG_PLAYLISTS = {
    "pop": [
        ("Blinding Lights The Weeknd", "Blinding Lights", "The Weeknd"),
        ("Levitating Dua Lipa", "Levitating", "Dua Lipa"),
        ("As It Was Harry Styles", "As It Was", "Harry Styles"),
        ("Cruel Summer Taylor Swift", "Cruel Summer", "Taylor Swift"),
        ("Uptown Funk Bruno Mars", "Uptown Funk", "Mark Ronson ft. Bruno Mars"),
        ("Bad Guy Billie Eilish", "bad guy", "Billie Eilish"),
        ("Shape of You Ed Sheeran", "Shape of You", "Ed Sheeran"),
        ("Espresso Sabrina Carpenter", "Espresso", "Sabrina Carpenter"),
        ("Drivers License Olivia Rodrigo", "drivers license", "Olivia Rodrigo"),
        ("Starboy The Weeknd", "Starboy", "The Weeknd"),
        ("Flowers Miley Cyrus", "Flowers", "Miley Cyrus"),
        ("Rolling in the Deep Adele", "Rolling in the Deep", "Adele"),
        ("Bad Romance Lady Gaga", "Bad Romance", "Lady Gaga"),
        ("Umbrella Rihanna", "Umbrella", "Rihanna"),
        ("Stay The Kid LAROI Justin Bieber", "STAY", "The Kid LAROI & Justin Bieber"),
        ("Watermelon Sugar Harry Styles", "Watermelon Sugar", "Harry Styles"),
        ("Birds of a Feather Billie Eilish", "BIRDS OF A FEATHER", "Billie Eilish"),
        ("Die With A Smile Lady Gaga Bruno Mars", "Die With A Smile", "Lady Gaga & Bruno Mars"),
        ("Save Your Tears The Weeknd", "Save Your Tears", "The Weeknd"),
        ("Take On Me a-ha", "Take On Me", "a-ha"),
    ],
    "hiphop": [
        ("Not Like Us Kendrick Lamar", "Not Like Us", "Kendrick Lamar"),
        ("HUMBLE Kendrick Lamar", "HUMBLE.", "Kendrick Lamar"),
        ("SICKO MODE Travis Scott", "SICKO MODE", "Travis Scott"),
        ("God's Plan Drake", "God's Plan", "Drake"),
        ("Lose Yourself Eminem", "Lose Yourself", "Eminem"),
        ("Without Me Eminem", "Without Me", "Eminem"),
        ("FE!N Travis Scott", "FE!N", "Travis Scott"),
        ("Goosebumps Travis Scott", "goosebumps", "Travis Scott"),
        ("Sunflower Post Malone Swae Lee", "Sunflower", "Post Malone & Swae Lee"),
        ("No Role Modelz J Cole", "No Role Modelz", "J. Cole"),
        ("Kill Bill SZA", "Kill Bill", "SZA"),
        ("Stronger Kanye West", "Stronger", "Kanye West"),
        ("Heartless Kanye West", "Heartless", "Kanye West"),
        ("Mask Off Future", "Mask Off", "Future"),
        ("Rockstar Post Malone", "rockstar", "Post Malone"),
        ("In Da Club 50 Cent", "In Da Club", "50 Cent"),
        ("Still D.R.E. Dr Dre Snoop Dogg", "Still D.R.E.", "Dr. Dre"),
        ("Creepin Metro Boomin The Weeknd", "Creepin'", "Metro Boomin & The Weeknd"),
    ],
    "kpop": [
        ("Dynamite BTS", "Dynamite", "BTS"),
        ("Butter BTS", "Butter", "BTS"),
        ("DDU-DU DDU-DU BLACKPINK", "DDU-DU DDU-DU", "BLACKPINK"),
        ("How You Like That BLACKPINK", "How You Like That", "BLACKPINK"),
        ("APT ROSE Bruno Mars", "APT.", "ROSÉ & Bruno Mars"),
        ("Super Shy NewJeans", "Super Shy", "NewJeans"),
        ("OMG NewJeans", "OMG", "NewJeans"),
        ("God's Menu Stray Kids", "God's Menu", "Stray Kids"),
        ("Seven Jung Kook", "Seven", "Jung Kook"),
        ("Gangnam Style PSY", "Gangnam Style", "PSY"),
        ("ANTIFRAGILE LE SSERAFIM", "ANTIFRAGILE", "LE SSERAFIM"),
        ("Next Level aespa", "Next Level", "aespa"),
        ("Supernova aespa", "Supernova", "aespa"),
        ("FANCY TWICE", "FANCY", "TWICE"),
        ("Magnetic ILLIT", "Magnetic", "ILLIT"),
        ("LOVE DIVE IVE", "LOVE DIVE", "IVE"),
        ("Cupid FIFTY FIFTY", "Cupid", "FIFTY FIFTY"),
        ("Kill This Love BLACKPINK", "Kill This Love", "BLACKPINK"),
    ],
    "rock": [
        ("Bohemian Rhapsody Queen", "Bohemian Rhapsody", "Queen"),
        ("In the End Linkin Park", "In the End", "Linkin Park"),
        ("Numb Linkin Park", "Numb", "Linkin Park"),
        ("Smells Like Teen Spirit Nirvana", "Smells Like Teen Spirit", "Nirvana"),
        ("Do I Wanna Know Arctic Monkeys", "Do I Wanna Know?", "Arctic Monkeys"),
        ("Believer Imagine Dragons", "Believer", "Imagine Dragons"),
        ("Viva La Vida Coldplay", "Viva La Vida", "Coldplay"),
        ("Mr Brightside The Killers", "Mr. Brightside", "The Killers"),
        ("Livin on a Prayer Bon Jovi", "Livin' on a Prayer", "Bon Jovi"),
        ("Back in Black AC/DC", "Back in Black", "AC/DC"),
        ("Sweet Child O Mine Guns N Roses", "Sweet Child O' Mine", "Guns N' Roses"),
        ("Never Gonna Give You Up Rick Astley", "Never Gonna Give You Up", "Rick Astley"),
        ("Seven Nation Army The White Stripes", "Seven Nation Army", "The White Stripes"),
        ("Boulevard of Broken Dreams Green Day", "Boulevard of Broken Dreams", "Green Day"),
        ("Chop Suey System of a Down", "Chop Suey!", "System of a Down"),
        ("Bring Me to Life Evanescence", "Bring Me to Life", "Evanescence"),
    ],
    "bollywood": [
        ("Tum Hi Ho Arijit Singh", "Tum Hi Ho", "Arijit Singh"),
        ("Kesariya Arijit Singh Pritam", "Kesariya", "Arijit Singh"),
        ("Channa Mereya Arijit Singh", "Channa Mereya", "Arijit Singh"),
        ("Chaleya Arijit Singh", "Chaleya", "Arijit Singh"),
        ("Pasoori Ali Sethi Shae Gill", "Pasoori", "Ali Sethi & Shae Gill"),
        ("Excuses AP Dhillon", "Excuses", "AP Dhillon"),
        ("Brown Munde AP Dhillon", "Brown Munde", "AP Dhillon"),
        ("Tera Ban Jaunga Akhil Sachdeva", "Tera Ban Jaunga", "Akhil Sachdeva"),
        ("Badtameez Dil Benny Dayal", "Badtameez Dil", "Benny Dayal"),
        ("Kala Chashma Badshah Neha Kakkar", "Kala Chashma", "Amar Arshi & Badshah"),
        ("Tujh Mein Rab Dikhta Hai Roop Kumar Rathod", "Tujh Mein Rab Dikhta Hai", "Roop Kumar Rathod"),
        ("Kal Ho Naa Ho Sonu Nigam", "Kal Ho Naa Ho", "Sonu Nigam"),
        ("Chaiyya Chaiyya Sukhwinder Singh", "Chaiyya Chaiyya", "Sukhwinder Singh"),
        ("Lover Diljit Dosanjh", "Lover", "Diljit Dosanjh"),
        ("Raataan Lambiyan Jubin Nautiyal", "Raataan Lambiyan", "Jubin Nautiyal"),
        ("Apna Bana Le Arijit Singh", "Apna Bana Le", "Arijit Singh"),
    ],
}

# In-memory cache of iTunes previews so repeated games start instantaneously!
_PREVIEW_CACHE = {}
_CACHE_LOCK = threading.Lock()


def setup(rooms_, lock_, changed_, rid_):
    global rooms, lock, changed, rid
    rooms, lock, changed, rid = rooms_, lock_, changed_, rid_


def clean_settings(b, old=None):
    old = old or {}
    pick = lambda k, d: b.get(k, old.get(k, d))
    pack = pick("pack", "anime_op")
    if pack not in ("anime_op", "pop", "hiphop", "kpop", "rock", "bollywood", "mix_songs", "custom"):
        pack = "anime_op"
    sub = pick("sub", "all")
    if sub not in ("all", "shounen", "modern", "classic", "romance"):
        sub = "all"
    inp = "type" if pick("input", "choices") == "type" else "choices"
    return {
        "pack": pack,
        "sub": sub,
        "custom": str(pick("custom", "")).strip()[:120],
        "input": inp,
        "rounds": max(5, min(20, int(pick("rounds", 10)))),
        "sec": max(10, min(28, int(pick("sec", 18)))),
    }


def create(room, b):
    room.update({
        "game": "op", "phase": "lobby", "settings": clean_settings(b), "deadline": None,
        "startedAt": 0, "tracks": [], "qIndex": -1, "scores": {}, "streaks": {}, "answers": {},
        "loadErr": None,
    })


def on_join(room, pid):
    room["scores"].setdefault(pid, 0)
    room["streaks"].setdefault(pid, 0)


def norm(s):
    w = re.sub(r"[^a-z0-9]", "", str(s or "").lower())
    return w


def clean_title(t):
    # Strip trailing "(feat. ...)", "- Single", "[TV Size]", etc. for cleaner display & matching
    t = re.sub(r"\s*[\(\[](feat\.|ft\.|from |tv size|remaster|radio edit|single|explicit|original).*?[\)\]]", "", str(t or ""), flags=re.I)
    return t.strip()[:60] or str(t or "").strip()[:60]


def matches_answer(guess, track):
    g = norm(guess)
    if len(g) < 2:
        return False
    cands = [track["answer"], track.get("song", ""), track.get("anime", ""), track.get("artist", "")]
    for c in list(cands):
        cands.append(clean_title(c))
        for part in re.split(r"[\s:;\-/]+", str(c or "")):
            if len(part) >= 4:
                cands.append(part)
    for c in cands:
        nc = norm(c)
        if not nc:
            continue
        if g == nc:
            return True
        if len(nc) >= 4 and (nc in g or g in nc) and abs(len(g) - len(nc)) <= 4:
            return True
        if len(nc) >= 5 and len(g) >= 4 and difflib.SequenceMatcher(None, g, nc).ratio() >= 0.78:
            return True
    return False


def itunes_search(term, limit=5):
    """Fetches songs with playable 30-second HTTPS .m4a previews from Apple's free iTunes Search API."""
    key = (term.lower().strip(), limit)
    with _CACHE_LOCK:
        hit = _PREVIEW_CACHE.get(key)
        if hit and time.time() - hit[0] < 86400:
            return hit[1]
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode({
        "term": term, "media": "music", "entity": "song", "limit": limit, "country": "us",
    })
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AnimeGameNight/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = (json.loads(r.read().decode("utf-8")) or {}).get("results") or []
    except Exception:
        return []
    out = []
    for x in rows:
        prev = x.get("previewUrl") or ""
        if not prev.startswith("https://"):
            continue
        art = (x.get("artworkUrl100") or "").replace("100x100bb", "400x400bb")
        out.append({
            "preview": prev,
            "art": art,
            "song": clean_title(x.get("trackName") or ""),
            "artist": str(x.get("artistName") or "").strip()[:50],
        })
    if out:
        with _CACHE_LOCK:
            _PREVIEW_CACHE[key] = (time.time(), out)
    return out


def fetch_curated_entry(entry, is_anime):
    if is_anime:
        q, anime, song, artist, era = entry
        hits = itunes_search(q, limit=3)
        if not hits:
            return None
        h = hits[0]
        return {
            "kind": "anime_op", "answer": anime, "anime": anime,
            "song": song, "artist": artist, "preview": h["preview"], "art": h["art"], "era": era,
        }
    else:
        q, song, artist = entry
        hits = itunes_search(q, limit=3)
        if not hits:
            return None
        h = hits[0]
        return {
            "kind": "song", "answer": song, "anime": "",
            "song": song, "artist": artist, "preview": h["preview"], "art": h["art"],
        }


def build_tracks(settings):
    n = settings["rounds"]
    pack = settings["pack"]

    if pack == "custom" and settings["custom"]:
        hits = itunes_search(settings["custom"], limit=min(45, n * 3))
        seen, uniq = set(), []
        for h in hits:
            k = norm(h["song"])
            if k and k not in seen and h["preview"]:
                seen.add(k)
                uniq.append({
                    "kind": "song", "answer": h["song"], "anime": "",
                    "song": h["song"], "artist": h["artist"], "preview": h["preview"], "art": h["art"],
                })
        random.shuffle(uniq)
        chosen = uniq[:n]
        pool_answers = [x["answer"] for x in uniq]
    elif pack == "anime_op":
        sub = settings["sub"]
        pool = [x for x in ANIME_OPS if sub == "all" or x[4] == sub]
        if len(pool) < n:
            pool = ANIME_OPS[:]
        random.shuffle(pool)
        sample = pool[:min(len(pool), n + 6)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            fetched = [r for r in ex.map(lambda e: fetch_curated_entry(e, True), sample) if r]
        # Avoid duplicate anime titles in same match if possible
        seen_a, chosen = set(), []
        for t in fetched:
            if t["anime"] not in seen_a or len(fetched) <= n:
                seen_a.add(t["anime"])
                chosen.append(t)
            if len(chosen) >= n:
                break
        pool_answers = list({x[1] for x in ANIME_OPS})
    else:
        if pack == "mix_songs":
            raw_pool = [x for xs in SONG_PLAYLISTS.values() for x in xs]
        else:
            raw_pool = SONG_PLAYLISTS.get(pack, SONG_PLAYLISTS["pop"])[:]
        random.shuffle(raw_pool)
        sample = raw_pool[:min(len(raw_pool), n + 6)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            chosen = [r for r in ex.map(lambda e: fetch_curated_entry(e, False), sample) if r][:n]
        pool_answers = list({x[1] for x in raw_pool})

    if not chosen:
        return []

    # Build 4 crisp choices per track
    for t in chosen:
        distractors = [a for a in pool_answers if norm(a) != norm(t["answer"])]
        random.shuffle(distractors)
        opts = [t["answer"]] + distractors[:3]
        while len(opts) < 4:
            opts.append(f"Track #{len(opts) + 1}")
        random.shuffle(opts)
        t["options"] = opts
        t["correctIdx"] = opts.index(t["answer"])
    return chosen


def begin_game(code):
    with lock:
        room = rooms.get(code)
        settings = dict(room["settings"]) if room else None
    if not settings:
        return
    tracks = build_tracks(settings)
    with lock:
        room = rooms.get(code)
        if not room or room["phase"] != "starting":
            return
        if not tracks:
            room["phase"] = "lobby"
            room["loadErr"] = "Couldn't load music previews for that topic right now. Try another playlist or search term!"
            changed(room)
            return
        room["loadErr"] = None
        room["tracks"] = tracks
        room["scores"] = {pid: 0 for pid in room["players"]}
        room["streaks"] = {pid: 0 for pid in room["players"]}
        start_track(room, 0)
        changed(room)


def active_pids(room):
    act = [pid for pid, p in room["players"].items() if not p.get("wantSitout")]
    return act or list(room["players"])


def start_track(room, idx):
    room["qIndex"] = idx
    room["phase"] = "question"
    room["answers"] = {}
    room["startedAt"] = time.time()
    room["deadline"] = room["startedAt"] + room["settings"]["sec"] + 1


def finish_track(room):
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
    if room["qIndex"] + 1 < len(room["tracks"]):
        start_track(room, room["qIndex"] + 1)
    else:
        room["phase"] = "final"
        room["deadline"] = None


def tick(room):
    now, ph = time.time(), room["phase"]
    over = room.get("deadline") and now >= room["deadline"]
    if ph == "question":
        act = active_pids(room)
        if over or (act and all(pid in room["answers"] for pid in act)):
            finish_track(room)
            return True
    elif ph == "reveal" and over:
        advance_after_reveal(room)
        return True
    return False


def chat_rules(room, pid):
    if room["phase"] == "question" and 0 <= room["qIndex"] < len(room["tracks"]):
        t = room["tracks"][room["qIndex"]]
        block = [x for x in (t.get("answer"), t.get("song"), t.get("anime")) if x]
        return {"read": ["all"], "write": ["all"], "block": block}
    return {"read": ["all"], "write": ["all"]}


def public(room, viewer):
    r = {k: v for k, v in room.items() if k not in ("hostKey", "tracks", "answers")}
    r["now"] = time.time()
    r["players"] = {pid: {k: v for k, v in p.items() if k != "key"} for pid, p in room["players"].items()}
    r["totalTracks"] = len(room["tracks"])
    if 0 <= room["qIndex"] < len(room["tracks"]):
        t = room["tracks"][room["qIndex"]]
        if room["phase"] == "question":
            r["track"] = {
                "kind": t["kind"],
                "preview": t["preview"],
                "options": t["options"],
            }
            r["answeredPids"] = list(room["answers"])
            mine = room["answers"].get(viewer)
            r["myAnswer"] = {"locked": True, "choice": mine.get("choice"), "text": mine.get("text")} if mine else None
        else:
            r["track"] = t
            r["answers"] = room["answers"]
    return r


def player_action(room, action, b, pid):
    if action != "answer":
        raise Refuse("Unknown action")
    if room["phase"] != "question":
        raise Refuse("Not taking answers right now.", 409)
    if pid in room["answers"]:
        raise Refuse("You already locked in your answer.", 409)
    t = room["tracks"][room["qIndex"]]
    now = time.time()
    if room["settings"]["input"] == "type":
        text = " ".join(str(b.get("text") or "").split())[:60]
        if not text:
            raise Refuse("Type your guess!")
        ok = matches_answer(text, t)
        room["answers"][pid] = {"text": text, "correct": ok, "t": now}
    else:
        choice = int(b.get("choice", -1))
        if not 0 <= choice < 4:
            raise Refuse("Pick one of the 4 choices.")
        room["answers"][pid] = {"choice": choice, "correct": choice == t["correctIdx"], "t": now}
    act = active_pids(room)
    if act and all(p in room["answers"] for p in act):
        finish_track(room)
    return True


def host_action(room, action, b):
    ph = room["phase"]
    if action == "settings":
        if ph != "lobby":
            raise Refuse("Settings lock once the quiz starts.")
        room["settings"] = clean_settings(b, room["settings"])
        room["loadErr"] = None
    elif action == "start":
        if ph != "lobby":
            raise Refuse("The quiz already started.")
        if len(room["players"]) < MIN_PLAYERS:
            raise Refuse("Wait for at least 1 player to join.")
        room["phase"] = "starting"
        room["loadErr"] = None
        threading.Thread(target=begin_game, args=(room["code"],), daemon=True).start()
    elif action in ("next", "skip"):
        if ph == "question":
            finish_track(room)
        elif ph == "reveal":
            advance_after_reveal(room)
        else:
            raise Refuse("Nothing to skip right now.")
    elif action == "kick":
        room["players"].pop(b.get("pid"), None)
        room["answers"].pop(b.get("pid"), None)
    elif action == "playagain":
        room.update({
            "phase": "lobby", "deadline": None, "tracks": [], "qIndex": -1, "loadErr": None,
            "scores": {pid: 0 for pid in room["players"]}, "streaks": {pid: 0 for pid in room["players"]},
            "answers": {},
        })
    return True

"""Bits every game module shares: uploaded pictures (drawings, player photos) and the
error a game raises to refuse a move."""

AVATAR_HOST = "https://s4.anilist.co/"  # character avatars must come from AniList's image server
IMAGES = {}  # image id -> jpeg bytes, kept in memory only (gone when the server restarts)


class Refuse(Exception):
    """A move the game won't allow; the message is shown to the player."""

    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status

"""Vibe + lyric-line engine for Shorts captions.

Psychology baked in (from short-form research):
  - Card 1 is a HOOK (curiosity gap / direct recognition) — first 2-3 seconds
    decide everything.
  - Lines are short (3-7 words) so they're readable at a glance, sound on OR off.
  - The last line is chosen to loop emotionally back into the hook.
"""
from __future__ import annotations

import random

HOOKS = [
    "no one talks about this part of the song",
    "POV: it's 3am and this comes on",
    "this is what missing someone sounds like",
    "you weren't supposed to hear this one",
    "the part everyone replays",
    "if this played on a midnight drive…",
    "this beat knows your secrets",
    "sound on. trust me.",
]

LINES = {
    "drift_phonk": [
        "headlights blur the city away",
        "we outran everything but the night",
        "your name still rides shotgun",
        "120 on an empty freeway of thoughts",
        "the streetlights keep your secrets",
        "gasoline and unsent messages",
        "drift past what you can't forget",
        "midnight owes me one more lap",
    ],
    "deep_pop": [
        "you left the porch light on",
        "i rehearse your goodbye daily",
        "golden hour never felt this cold",
        "we were almost a home",
        "your sweater still smells like sundays",
        "love quietly left the room",
        "i dance with the echo of you",
        "soft hearts take the longest fall",
    ],
    "dark_ambient": [
        "the house remembers us",
        "static hums where you slept",
        "every door here opens inward",
        "the rain learned your name",
        "silence kept your side warm",
        "we were smoke in a hallway",
        "the fog never asks questions",
        "somewhere, a light stays on purpose",
    ],
    "lofi": [
        "rain on the window, tea gone cold",
        "another page, another almost",
        "the city hums us to sleep",
        "stay a little longer, the record's warm",
        "we count slow afternoons like spare change",
        "my plants know all my secrets",
        "homework and heartbreak at 2am",
        "the kettle sings our little song",
    ],
    "baroque_waltz": [
        "candlelight forgives everything",
        "we waltzed the moon out of the parlour",
        "dust settles where the music was",
        "an old house learning our names",
        "six steps to forget the century",
        "the chandelier kept time for us",
        "silk curtains, slow centuries",
        "dance like the gramophone's dying",
    ],
    "disco_house": [
        "sneakers squeaking on starlight",
        "the floor remembers every step",
        "spin until the mirrorball cries",
        "one more song the night owes us",
        "glitter in the soles of my shoes",
        "we polished this night ourselves",
        "the bassline holds your hand",
        "midnight's open 'til we say so",
    ],
}

LOOP_BRIDGES = [
    "…and it starts all over again",
    "…like nothing ever happened",
    "…again. again. again.",
]

# Comment-bait closers — engagement signal, appended to some shorts.
BAITS = [
    "rate this drop 1-10 🌙",
    "what song does this remind you of?",
    "where would you play this at 3am?",
    "first word this beat gives you?",
    "save this for your next night drive",
]


def build_lines(genre_key: str, name: str, rng: random.Random, n: int = 5) -> list[str]:
    """Return [hook, *lines...] — card 1 is always the scroll-stopper."""
    hook = rng.choice(HOOKS)
    lines = rng.sample(LINES[genre_key], k=min(len(LINES[genre_key]), max(2, n - 2)))
    out = [hook] + lines
    if len(out) < n and rng.random() < 0.6:
        out.append(rng.choice(LOOP_BRIDGES))
    return out[:n]

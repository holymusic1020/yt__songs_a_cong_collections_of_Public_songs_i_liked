"""Vibe + sung-lyrics engine.

Two jobs:
  1) Shorts caption lines (banks below) — used when a day has no sung words.
  2) REAL sung lyrics for the ACE-Step space songs (`song_lyrics`) in
     English + World Tour languages, with `[verse]/[chorus]` structure tags
     the singer follows. copy_ai writes fresh ones with Gemini; these banks
     are the no-key fallback. `cards_from_lyrics` turns the sung words into
     the short's lyric cards — viewers read what they actually hear 🎧

Psychology baked in (unchanged from research):
  - Card 1 is a HOOK (curiosity gap / direct recognition).
  - Lines are short (3-7 words) — readable at a glance, sound on OR off.
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


# ==================================================================
# SUNG VOCALS — languages, voice + lyric banks, card extractor
# ==================================================================

# channel identity = English; World Tour drops rotate these flavors.
# (ja/ko supported but kept OUT of the default wheel: their cards would need
#  CJK fonts; opt-in via WORLD_LANGS and lyrics come back romanized latin.)
LANGS = {
    "en":    {"label": "english",              "hint": ""},
    "pt-BR": {"label": "brazilian portuguese", "hint": "brazilian slang welcome"},
    "es":    {"label": "spanish",              "hint": ""},
    "fr":    {"label": "french",               "hint": ""},
    "tr":    {"label": "turkish",              "hint": ""},
    "ja":    {"label": "japanese",
              "hint": "write in romanized latin script (romaji), no kanji/kana"},
    "ko":    {"label": "korean",
              "hint": "write in romanized latin script, no hangul"},
}

SONG_BANKS = {
    "en": {
        "verse": ["i left my headlights on the freeway",
                  "your ghost still riding next to me",
                  "the dashboard glows like last july",
                  "nothing moves but memories"],
        "chorus": ["so take the night, take it slow",
                   "every mile just lets you go",
                   "i keep your name on my radio",
                   "singing low, low, low"],
        "bridge": ["if morning comes, don't wake me yet",
                   "let the dark hold what we left"],
    },
    "pt-BR": {
        "verse": ["rua vazia, neon no chão",
                  "teu cheiro ainda no meu casaco",
                  "a cidade inteira em câmera lenta",
                  "eu e a saudade, passo a passo"],
        "chorus": ["vem, vem, a noite é nossa",
                   "joga a mão pra lua, esquece a outra",
                   "se o mundo acabar de madrugada",
                   "a gente dança devagar na calçada"],
        "bridge": ["quando o sol nascer, me acorda não",
                   "deixa a saudade na minha mão"],
    },
    "es": {
        "verse": ["la luna sabe dónde estás",
                  "tu nombre escrito en el cristal",
                  "conduzco lento sin mirar atrás",
                  "buscando tu luz en la ciudad"],
        "chorus": ["quédate un poco más",
                   "que la noche nos da alas",
                   "si el sol nos quiere encontrar",
                   "que nos busque mañana"],
        "bridge": ["apaga la radio, quédate aquí",
                   "la madrugada sabe de ti y de mí"],
    },
    "fr": {
        "verse": ["sous la pluie de néon pâle",
                  "ton ombre danse sur le pavé",
                  "je conduis vers nulle part",
                  "ton nom en bouche à répéter"],
        "chorus": ["reste encore une chanson",
                   "la nuit nous appartient",
                   "si le monde tourne trop vite",
                   "nous on ralentit"],
        "bridge": ["le jour se lève, pas encore",
                   "une danse de plus, je t'adore"],
    },
    "tr": {
        "verse": ["gece yarısı boş sokaklar",
                  "neon ışıklar yüzünde",
                  "seni düşünmeden geçmiyor",
                  "bir dakika bile, bilesin"],
        "chorus": ["kal benimle bu gece",
                   "şehir uyurken ikimiz",
                   "yarın güneş doğsa bile",
                   "biz bu şarkıyı söyleriz"],
        "bridge": ["sabah olmasın, biraz daha",
                   "kalbim sana yar ola"],
    },
    "ja": {  # romaji by design (font-safe cards, still sung)
        "verse": ["ame no naka kimi no koe",
                  "neon gairo de kietanda",
                  "ano yoru no yakusoku dake",
                  "mada mune ni nokotteru"],
        "chorus": ["konya mo hoshi ga ochiteku",
                   "kimi no namae wo yobunda",
                   "toki wo tomete one more night",
                   "zutto soba ni ite"],
        "bridge": ["asa ga kitara wasurenai",
                   "kono uta dake nokoshite"],
    },
    "ko": {  # romanized, same reason
        "verse": ["neon bulbit arae honja",
                  "ni saenggage bameul dallyeo",
                  "moratdeon ireumcheoreom neon",
                  "nae mame sarajijil ana"],
        "chorus": ["oneul bamen nohji ma",
                   "son kkwak jaba nal bwa",
                   "achimi wado urin yeogi",
                   "ttodasi chumeul chwo tonight"],
        "bridge": ["shigani meomchwojundamyeon",
                   "i bam soge salge neowa na"],
    },
}


def build_lines(genre_key: str, name: str, rng: random.Random, n: int = 5) -> list[str]:
    """Return [hook, *lines...] — card 1 is always the scroll-stopper."""
    hook = rng.choice(HOOKS)
    lines = rng.sample(LINES[genre_key], k=min(len(LINES[genre_key]), max(2, n - 2)))
    out = [hook] + lines
    if len(out) < n and rng.random() < 0.6:
        out.append(rng.choice(LOOP_BRIDGES))
    return out[:n]


def song_lyrics(genre_key: str, title: str, rng: random.Random,
                lang: str = "en") -> str:
    """Tagged sung lyrics for the ACE-Step space — bank fallback shape.

    Always: verse / chorus / verse / chorus / bridge / chorus (~24 sung
    lines ≈ 2-3 min of song). Genre only seasons one swapped-in line so the
    fallback stays genre-aware without pretending to be poetry.
    """
    b = SONG_BANKS.get(lang, SONG_BANKS["en"])
    flavor = rng.choice(LINES.get(genre_key, LINES["drift_phonk"]))
    if lang == "en":                      # steal one bank caption for cohesion
        verse2 = [flavor] + rng.sample(b["verse"], 3)
    else:
        verse2 = list(b["verse"])
        verse2[rng.randrange(4)] = b["bridge"][0]   # rotate, keep language pure
    parts = [
        "[verse]", *b["verse"],
        "[chorus]", *b["chorus"],
        "[verse]", *verse2,
        "[chorus]", *b["chorus"],
        "[bridge]", *b["bridge"],
        "[chorus]", *b["chorus"],
    ]
    return "\n".join(parts)


def cards_from_lyrics(lyrics_text: str, k: int = 7) -> list[str]:
    """The short's cards = the words the viewer ACTUALLY hears sung.

    Chorus lines first (that's the part that hooks), then verse lines to
    fill. Tags removed, screen-filler kept short so quick-cut chunking works.
    """
    sections: dict[str, list[str]] = {}
    cur = None
    for raw in lyrics_text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith("[") and ln.endswith("]"):
            cur = ln.strip("[]").lower()
            sections.setdefault(cur, [])
            continue
        if cur:
            sections[cur].append(ln)
    chorus = sections.get("chorus", [])[:4]
    pool = (sections.get("verse", []) + sections.get("bridge", [])
            + sections.get("pre-chorus", []) + sections.get("outro", []))
    out = chorus + [ln for ln in pool if ln not in chorus]
    return out[:max(1, k)]

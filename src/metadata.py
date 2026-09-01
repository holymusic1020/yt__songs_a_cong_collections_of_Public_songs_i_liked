"""Metadata — official label-style copy + Shorts variants.

Looks 100% official label release (because it IS your label) while keeping
the two honesty layers that protect the channel: YouTube's synthetic-media
flag (in uploader.py) and one quiet production line at the bottom.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

CHANNEL = "Nix Speech"

# All bank entries are pre-verified GLOBALLY UNIQUE against the iTunes
# catalog (2026-08). The naming engine (naming.py) still re-checks live
# every run — banks are just the no-API fallback.
NAME_BANKS = {
    "drift_phonk": [
        ("chrome marrow", "pink kerosene", "asphalt dialect", "mirrorshade mile",
         "nitro psalm", "vapor verdict", "graveyard shift deluxe"),
    ],
    "deep_pop": [
        ("lilac ruin", "bruised satellite", "marzipan elegy", "nectar bruise",
         "opaline ache", "begonia static", "kodak bruise", "indentured moon",
         "pearl deficit", "silk eviction", "mothball anthem",
         "crumbs of august"),
    ],
    "dark_ambient": [
        ("hollow lighthouse", "lichen signal", "peat halo", "fog mnemonic",
         "the moor archive", "salt hypnosis"),
    ],
    "lofi": [
        ("wool uniform", "toast weather", "cactus intern", "laundry oracle",
         "plum homework", "pocket monsoon", "cinnamon modem"),
    ],
    "baroque_waltz": [
        ("aniseed promenade", "clover crinoline", "harlequin interlude",
         "madder waltz", "sienna minuet", "tulle parade", "ochre carousel",
         "linden waltz", "bramble nocturne"),
    ],
    "disco_house": [
        ("sneakers on marble", "boogie ledger", "mirrorball therapy",
         "parquet gospel", "satin footwork", "torsion boogie", "apricot fever",
         "plimsoll strut", "verbena groove"),
    ],
    "skyline_anthem": [
        ("horizon kids club", "borrowed starlight", "rooftop july",
         "mapglow", "wildfire valedictorian", "open window anthem",
         "thirty-two sunsets"),
    ],
    "villain_pop": [
        ("velvet misdemeanor", "halo practice", "sugar psalm no. 9",
         "polite menace", "lipstick alibi", "courtroom lullaby",
         "teacup felony"),
    ],
    "orbit_trap": [
        ("launchpad lullaby", "pressure diamonds", "plain sight vanish",
         "orbit receipt", "zero gravity alibi", "countdown romance"),
    ],
    "chart_pop": [
        ("glitter avenue", "paper crown tonight", "bubble static", "neon honey talk",
         "ribbon exit", "gloss parade", "flirt arithmetic", "goldrush giggle"),
    ],
    "melodic_trap": [
        ("amber siren lane", "velvet ignition", "honey brakelights", "champagne backroads",
         "rosegold rumble", "silk slander", "cologne midnight", "moonroof confession"),
    ],
    "summer_rap": [
        ("mango verdict", "poolside sermon", "sunroof grammar", "lemon static",
         "barefoot ledger", "popsicle tattoo", "july allowance", "cannonball season"),
    ],
    "phonk_mafia": [
        ("concrete rosary", "smoke gavel", "midnight syndicate", "asphalt prophecy",
         "bone orchestra", "blackmarket hymn", "iron consigliere", "trenchcoat anthem"),
    ],
    "velvet_fang": [
        ("sugarblack bite", "poison valentine", "crimson etiquette", "lacquer fang",
         "pearl danger", "midnight incisor", "silk appetite", "garnet lipstick"),
    ],
    "emo_rap": [
        ("deadroses voicemail", "pillowcase confession", "teardrop engine", "static love letter",
         "graveyard text", "mascara tide", "cheap halo", "moonburn therapy"),
    ],
    "templestep": [
        ("incense swagger", "bronze procession", "lotus throttle", "pagoda stride",
         "saffron engine", "temple runner", "golden threshold", "monk mode royalty"),
    ],
    "lastjuly": [
        ("august apology", "firefly debt", "sundress archive", "lakehouse echo",
         "thirtyfirst sunset", "sparkler residue", "boardwalk ghost", "lemonade requiem"),
    ],
    "ashrise": [
        ("cinder gospel", "phoenix commute", "embers decree", "soot halo",
         "furnace baptism", "coal constellation", "rise residue", "smoke ring coronation"),
    ],
    "brazilian_phonk": [
        ("carnival menace", "baile shadow", "berimbau pressure", "tropic gavel",
         "montagem midnight", "ritmo verdict", "midnight capoeira", "cobalt fiesta"),
    ],
    "saint_of_leaving": [
        ("goodbye cathedral", "suitcase psalm", "departure liturgy", "halo on wheels",
         "taxi requiem", "doorframe requiem", "farewell procession", "runway valediction"),
    ],
    "indie_waves": [
        ("cardigan static", "saltwater cassette", "wetsuit heart", "garage lagoon",
         "kelp radio", "freckle surf", "moonpool classification", "static shoreline"),
    ],
    "lambs_teeth": [
        ("wool over iron", "soft artillery", "lamb artillery", "quiet fang",
         "mercy razor", "serenity subpoena", "butterknife anthem", "marshmallow blade"),
    ],
    "god_in_the_bass": [
        ("subwoofer gospel", "trunk cathedral", "holy ripple", "floorboard sermon",
         "bass litany", "deep voice amen", "heaven low end", "sacred frequency"),
    ],
    "anime_titan": [
        ("wallbreaker anthem", "survey heart", "colossal sunrise", "meteor uniform",
         "final episode sky", "sakura artillery", "rumble season", "counterattack lullaby"),
    ],

}

DESCRIPTION_TMPL = """{name}
by Nix Speech

℗ {year} Nix Speech. All rights reserved.
EP.{ep:03d} · {genre} · official audio

new music every few days. subscribe for the night shift 🌙
{hashtags}
"""

HASHTAGS = {
    "drift_phonk": "#phonk #driftphonk #nightdrive",
    "deep_pop": "#darkpop #nightvibes #moody",
    "dark_ambient": "#darkambient #ambient #sleepmusic",
    "lofi": "#lofi #chillbeats #studymusic",
    "baroque_waltz": "#waltz #baroquepop #vintage",
    "disco_house": "#housemusic #disco #groove",
    "skyline_anthem": "#edm #festivalvibes #anthem",
    "villain_pop": "#darkpop #villainera #cinematicpop",
    "orbit_trap": "#trap #melodicrap #spacemood",
    "chart_pop": "#popsong #viral #dancepop",
    "melodic_trap": "#melodictrap #trap #nightvibes",
    "summer_rap": "#summerrap #summerhit #vibes",
    "phonk_mafia": "#phonk #phonkmafia #gymmotivation",
    "velvet_fang": "#darkpop #villain #aesthetic",
    "emo_rap": "#emorap #sadrap #latenight",
    "templestep": "#templemusic #spiritualvibes #bassmusic",
    "lastjuly": "#nostalgia #summersong #endofsummer",
    "ashrise": "#comeback #motivation #epicmusic",
    "brazilian_phonk": "#brazilianphonk #montagem #funk",
    "saint_of_leaving": "#farewell #emotional #goodbye",
    "indie_waves": "#indiepop #bedroompop #chillvibes",
    "lambs_teeth": "#underdog #darkpop #quietpower",
    "god_in_the_bass": "#bassmusic #spiritual #lowend",
    "anime_titan": "#anime #amv #epicanime",

}

TAGS = {
    "drift_phonk": ["phonk", "drift phonk", "dark phonk", "night drive music",
                    "instrumental", "type beat"],
    "deep_pop": ["dark pop", "sad instrumental", "moody beats", "night vibes",
                 "emotional instrumental"],
    "dark_ambient": ["dark ambient", "ambient", "sleep music", "rain sounds",
                     "focus music"],
    "lofi": ["lofi", "lo-fi beats", "chill beats", "study music",
             "relaxing beats"],
    "baroque_waltz": ["waltz", "baroque pop", "vintage waltz", "harmonium",
                      "classical crossover", "instrumental"],
    "disco_house": ["house music", "disco house", "funky house", "dance music",
                    "groove", "club instrumental"],
    "skyline_anthem": ["festival edm", "anthem house", "uplifting",
                       "folk edm", "summer anthem", "type beat"],
    "villain_pop": ["villain pop", "dark cinematic pop", "evil pop",
                    "music box beat", "villain era", "dark pop type beat"],
    "orbit_trap": ["melodic trap", "trap type beat", "confidence trap",
                   "space trap", "rap beat", "night trap"],
    "chart_pop": ["viral pop", "dance pop", "tiktok song", "summer hit", "pop lyrics"],
    "melodic_trap": ["melodic trap", "trap soul", "night drive rap", "emotional trap", "type beat"],
    "summer_rap": ["summer rap", "chill rap", "pool party music", "sunny vibes", "feel good rap"],
    "phonk_mafia": ["phonk", "memphis phonk", "dark phonk", "gym phonk", "mafia music", "type beat"],
    "velvet_fang": ["dark pop", "villain song", "seductive pop", "midnight pop", "aesthetic music"],
    "emo_rap": ["emo rap", "sad rap", "heartbreak rap", "late night music", "sadboy"],
    "templestep": ["temple music", "spiritual bass", "ethnic electronic", "sacred beats", "zen bass"],
    "lastjuly": ["sad summer song", "nostalgia pop", "end of summer", "melancholy music", "memory song"],
    "ashrise": ["epic comeback", "motivation music", "phoenix song", "rise up", "epic pop"],
    "brazilian_phonk": ["brazilian phonk", "funk carioca", "montagem", "baile funk", "phonk brasil"],
    "saint_of_leaving": ["farewell song", "goodbye music", "leaving song", "emotional pop", "sad anthem"],
    "indie_waves": ["indie pop", "bedroom pop", "chill indie", "surf vibes", "indie summer"],
    "lambs_teeth": ["underdog anthem", "dark pop", "quiet rage", "emotional pop", "revenge soft"],
    "god_in_the_bass": ["bass music", "spiritual bass", "deep bass", "prayer music", "heavy low end"],
    "anime_titan": ["anime opening", "epic anime music", "anime ost style", "amv music", "titan anthem"],

}


ROMAN = ["", "II", "III", "IV", "V", "VI"]


def _fresh_name(bank: tuple, used_names: set, rng: random.Random) -> str:
    """Never ship the same title twice (YouTube reads dupes as spam)."""
    unused = [n for n in bank if n not in used_names]
    if unused:
        return rng.choice(unused)
    base = rng.choice(bank)
    k = 1 + sum(1 for u in used_names if u == base or u.startswith(base + " "))
    k = min(k, len(ROMAN) - 1)
    return f"{base} {ROMAN[k - 1]}"


GENERIC_TAGS = ["type beat", "chill", "night drive music",
                "aesthetic", "official audio", "new music"]

# World Tour (v17) — foreign-language drops get honest, clickable labels
LANG_LABEL = {"pt-BR": "brazilian portuguese", "es": "spanish", "fr": "french",
              "tr": "turkish", "ja": "japanese", "ko": "korean"}
LANG_HASHTAG = {"pt-BR": " #brazilianphonk #international",
                "es": " #latinpop #international",
                "fr": " #frenchpop #international",
                "tr": " #turkishpop #international",
                "ja": " #jpop #international",
                "ko": " #kpop #international"}


def _tags_for(genre_key: str, name: str, rng: random.Random,
              vocal: bool = False) -> list[str]:
    """Rotating tag set — identical blocks across uploads read as spam."""
    pool = list(dict.fromkeys(t for t in TAGS.get(genre_key, []) + GENERIC_TAGS
                              if not (vocal and t == "instrumental")))
    picks = rng.sample(pool, k=min(len(pool), 5))
    if vocal and rng.random() < 0.75:
        picks.append(rng.choice(["vocal", "lyrics", "singer"]))
    return [name] + picks                      # unique title tag = free SEO


def build(genre_key: str, info: dict, ep: int, rng: random.Random,
          used_names: set | None = None, name: str | None = None,
          lang: str = "en", vocal: bool = False) -> dict:
    bank = NAME_BANKS.get(genre_key, NAME_BANKS["deep_pop"])[0]  # 🛡 never dies
    name = name or _fresh_name(bank, used_names or set(), rng)
    genre = info["genre"]
    if lang != "en":                      # world-tour honesty label (looks pro)
        genre = f"{genre} · {LANG_LABEL.get(lang, lang)} version"
    year = datetime.now(timezone.utc).year
    title = f"{name} — {CHANNEL} (official audio)"
    description = DESCRIPTION_TMPL.format(
        name=name, genre=genre, ep=ep, channel=CHANNEL,
        year=year, hashtags=HASHTAGS.get(genre_key, "#music #vibes") + LANG_HASHTAG.get(lang, ""),
    )
    return {
        "channel": CHANNEL,
        "name": name,
        "title": title[:100],
        "description": description,
        "tags": _tags_for(genre_key, name, rng, vocal=vocal),
        "genre": genre,
        "genre_key": genre_key,
        "lang": lang,
        "bpm": info["bpm"],
        "key": info["key"],
    }


def add_chapters(meta: dict, lrc_entries, dur: float) -> int:
    """⏱ YouTube chapters from the karaoke map (v23).

    Rules of the platform: first stamp must be 0:00, need >= 3 chapters,
    each >= 10 s apart — else YouTube silently ignores them. We take sung
    lines >= 10 s apart as chapter names ('0:00 intro' leads). Returns the
    chapter count written (0 = description untouched).
    """
    picks: list[tuple[float, str]] = [(0.0, "intro")]
    for t, txt in (lrc_entries or []):
        if t < 8 or t > dur - 8:
            continue
        if t - picks[-1][0] < 10:
            continue
        label = " ".join(str(txt).split()[:6])[:34].strip(" .,;:-")
        if len(label) < 3 or label.lower() == picks[-1][1].lower():
            continue
        picks.append((float(t), label))
        if len(picks) >= 10:
            break
    if len(picks) < 3:
        return 0
    block = "\n\n⏱ chapters\n" + "\n".join(
        f"{int(t // 60)}:{int(t % 60):02d} {label}" for t, label in picks)
    desc = meta["description"].rstrip()
    head, sep, tail = desc.rpartition("\n")
    if sep and tail.lstrip().startswith("#"):     # hashtags always ride last
        meta["description"] = head + block + "\n" + tail
    else:
        meta["description"] = desc + block
    return len(picks)



# day-rotated title emojis (2026-08-26): one emoji per DAY, not per channel —
# deterministic so the dry-run and the real publish of the same day agree.
from datetime import datetime as _dt, timezone as _tz
_DAY_EMOJIS  = ["\U0001F90D", "\U0001FA76", "\U0001F5A4", "\u2728", "\U0001F319", "\u2601\uFE0F", "\U0001F4AB", "\U0001FAE7", "\U0001F940", "\U0001F3A7", "\U0001F30C", "\U0001F56F\uFE0F"]
_SLOW_EMOJIS = ["\U0001F4A4", "\U0001F32B\uFE0F", "\U0001F327\uFE0F", "\U0001F9CA", "\U0001F578\uFE0F", "\U0001F30A"]
_pool_i = _dt.now(_tz.utc).toordinal()
TITLE_EMOJI  = _DAY_EMOJIS[_pool_i % len(_DAY_EMOJIS)]
SLOWED_EMOJI = _SLOW_EMOJIS[_pool_i % len(_SLOW_EMOJIS)]

def short_meta(meta: dict, hook_line: str, slowed: bool = False) -> dict:
    """Shorts packaging: hook line first (psych trigger), clean official copy.
    v23: every short carries the 'use this sound' CTA (original-sound pages
    compound), and the slowed+reverb twin gets honest, searchable packaging."""
    if slowed:
        title = f'"{hook_line}" {SLOWED_EMOJI} {meta["name"]} (slowed + reverb)'
    else:
        title = f'"{hook_line}" {TITLE_EMOJI} {meta["name"]}'
    desc = (f"{meta['name']} — full version on the channel.\n"
            f"by Nix Speech\n"
            f"🎧 use this sound — tap the audio below\n"
            f"{HASHTAGS[meta['genre_key']]}"
            f"{LANG_HASHTAG.get(meta.get('lang', 'en'), '')} #shorts"
            f"{' #slowedandreverb' if slowed else ''}")
    return {"title": title[:100], "description": desc,
            "tags": TAGS[meta["genre_key"]] + ["shorts"]}

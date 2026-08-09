"""Full-auto AI songs from the free ACE-Step spaces. Boss's queue design:

    run N  : publish today's song → cook TOMORROW's song on a Space →
             hold it (artifact 'next-song' — zero repo bloat, auto-expires)
    run N+1: eats the queued song → publishes → cooks the next one 🔁

v17 — HUMAN-VOICE mode 🎤 + V1.5 UPGRADE:
  - primary space is the official ACE-Step v1.5 (turbo: 8-step DiT, native
    per-song settings for BPM + vocal language + lyric-timestamp return),
    with the classic v1 space as automatic fallback.
  - pass `lyrics` (tagged [verse]/[chorus] text) → the space SINGS. `lang`
    seasons prompt + voice + the v1.5 vocal-language dial so World Tour
    drops (brazilian phonk etc.) sound native, not cosplay.

Safety philosophy: ANY space failure (asleep, rate-limited, broken deploy)
returns None and the built-in engine takes over. Spaces can NEVER kill a run.

License: ACE-Step is Apache-2.0 → commercial-safe. ZeroGPU quota is shared;
an optional FREE HF account token (env HF_TOKEN) raises it. No card needed.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

# v1.5 first (better vocals + per-song BPM/lang dials), v1 as fallback
SPACES = ["ACE-Step/Ace-Step-v1.5", "ACE-Step/ACE-Step"]

# genre wheel → Space prompts (tags-first, the style ACE-Step responds to)
PROMPTS = {
    "drift_phonk":    ("drift phonk, dark memphis phonk, distorted 808 bass, "
                       "phonk cowbell melody, night drive, "
                       "ominous, saturated, {bpm} bpm"),
    "deep_pop":       ("melancholic alt pop, deep pulsing synth bass, "
                       "airy detuned pads, slow burn build, emotional, rainy window, "
                       "{bpm} bpm"),
    "dark_ambient":   ("dark ambient drone, slow evolving textures, "
                       "distant thunder, tape hiss, cinematic vastness, unsettling calm"),
    "lofi":           ("lofi hip hop, dusty vinyl crackle, warm rhodes "
                       "chords, soft boom bap drums, rain on the window, {bpm} bpm"),
    "baroque_waltz":  ("playful baroque waltz, harpsichord and string quartet, "
                       "vintage ballroom tape recording, whimsical, 3/4 time"),
    "disco_house":    ("french house disco, funky filtered bassline, "
                       "four on the floor, lush string stabs, feel-good groove, "
                       "{bpm} bpm"),
}

# the HUMAN in the machine: per-genre vocal identity, so every drop sounds
# like the same fictional artiste maturing, not a random karaoke night
VOICE = {
    "drift_phonk":   ("deep raspy male vocals, dark memphis rap energy, "
                      "hushed menace in verses, melodic chorus, ad libs"),
    "deep_pop":      ("soft airy female vocals, intimate and breathy, "
                      "sad-pretty, big emotional chorus"),
    "dark_ambient":  ("haunting whispered vocals, distant reverb, fragile"),
    "lofi":          ("mellow hummed vocals, lazy smoky delivery, daydreamy"),
    "baroque_waltz": ("chamber duet vocals, operetta charm, vintage tape warmth"),
    "disco_house":   ("soulful diva vocals, celebratory, funky ad libs"),
}

# language words for prompts → plus v1.5's native vocal-language codes
LANG_TOKEN = {"en": "english", "pt-BR": "portuguese", "es": "spanish",
              "fr": "french", "tr": "turkish", "ja": "japanese", "ko": "korean"}
LANG_CODE = {"en": "en", "pt-BR": "pt", "es": "es", "fr": "fr",
             "tr": "tr", "ja": "ja", "ko": "ko"}

GENRE_BPM = {"drift_phonk": 130, "deep_pop": 96, "dark_ambient": 60,
             "lofi": 78, "baroque_waltz": 172, "disco_house": 118}


def _client(space: str):
    from gradio_client import Client
    token = os.environ.get("HF_TOKEN", "").strip() or None
    return Client(space, token=token, verbose=False)


def build_prompt(genre_key: str, lang: str = "en", vocals: bool = True) -> str:
    base = PROMPTS.get(genre_key, "moody, atmospheric").format(
        bpm=GENRE_BPM.get(genre_key, 100))
    if not vocals:
        return base + ", instrumental"
    voice = VOICE.get(genre_key, "expressive vocals")
    lang_tok = LANG_TOKEN.get(lang, "english")
    return f"{base}, {voice}, {lang_tok} lyrics, {lang_tok} song"


_TAGS = {"verse", "chorus", "pre-chorus", "bridge", "outro", "hook",
         "inst", "instrumental", "intro"}


def parse_lrc(text: str | None) -> list[tuple[float, str]]:
    """ACE v1.5 'Lyrics Timestamps' → [(start_s, line), ...] karaoke map.

    Forgiving about the exact flavour: '[mm:ss.xx] line', 'mm:ss - line',
    with/without brackets. Structure tags are dropped — only sung words stay.
    """
    out: list[tuple[float, str]] = []
    for ln in (text or "").splitlines():
        m = re.match(r"\s*\[?(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]?\s*"
                     r"[-–—]?\s*(.+?)\s*$", ln)
        if not m:
            continue
        mm, ss, frac, txt = m.groups()
        t = int(mm) * 60 + int(ss)
        if frac:
            t += float("0." + frac.strip()) if frac.strip() else 0.0
        txt = re.sub(r"[\[\]]", "", txt).strip().strip('"').strip()
        if len(txt) < 2 or txt.lower() in _TAGS:
            continue
        out.append((round(t, 2), txt[:90]))
    out.sort(key=lambda e: e[0])
    dedup: list[tuple[float, str]] = []
    for t, txt in out:                    # repeated-section echoes → keep first
        if dedup and t - dedup[-1][0] < 0.6 and txt == dedup[-1][1]:
            continue
        dedup.append((t, txt))
    return dedup


def _pick_file(payload):
    """gradio FileData payload → local path, whatever its costume."""
    if isinstance(payload, (list, tuple)):
        payload = payload[0] if payload else None
    if isinstance(payload, dict):
        payload = payload.get("path") or payload.get("value")
    return payload


def _cook_v15(client, genre_key, seconds, prompt, lyr, lang):
    """Official v1.5 turbo: native BPM + vocal-language + fast 8-step DiT."""
    res = client.predict(
        "acestep-v15-xl-turbo",        # selected_model
        "custom",                      # generation_mode
        None, "unknown",               # simple-mode fields (unused)
        prompt, lyr,
        float(GENRE_BPM.get(genre_key, 0)),  # BPM dial 🎚
        "", "",                        # key / time signature (auto)
        LANG_CODE.get(lang, "unknown"),      # vocal language dial 🌍
        8.0,                           # DiT steps (turbo)
        7.0, True, "-1",               # cfg-ish, random seed
        None,                          # no reference audio
        float(seconds),                # duration
        1.0,                           # batch size = one perfect take
        None, None, 0.0, -1.0,         # repaint/extend (unused)
        "Fill the audio semantic mask based on the given conditions:",
        1.0, "text2music", False, 0.0, 1.0, 3.0, "ode", "", "mp3",
        0.85, False, 2.0, 0.0, 0.9, "NO USER INPUT",
        True, True, True, False, True,
        True, True,                    # get scores + LRC timestamps
        0.5, 8.0, None, [], False,
        api_name="/generation_wrapper",
    )
    # returns: 8 samples, zip, details, status, seed, 8 scores, 8 lm codes,
    # 8 lyric-timestamp strings, … → sample 1 timestamps sit at index 28
    audio = _pick_file(res[0])
    lrc = None
    try:
        cand = res[28]
        cand = cand.get("value") if isinstance(cand, dict) else cand
        if isinstance(cand, str) and re.search(r"\d{1,2}:\d{2}", cand):
            lrc = cand
    except (IndexError, TypeError):
        lrc = None
    return audio, lrc


def _cook_v1(client, seconds, prompt, lyr, infer_step):
    audio, _params = client.predict(
        audio_duration=float(seconds), prompt=prompt, lyrics=lyr,
        infer_step=float(infer_step), api_name="/__call__")
    return audio, None


def generate(genre_key: str, seconds: float, out_path: Path,
             retries: int = 2, infer_step: int = 32,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None) -> Path | None:
    """Cook one song. Returns the file on success, else None.

    lyrics=None → instrumental ('[inst]'). lyrics=tagged text → SUNG track
    in `lang`. lrc_out: when the v1.5 space returns lyric timestamps
    (karaoke map 🎤⏱), they're written there for video_render's overlay.
    Same failure contract as always: None means 'engine, take over'.
    """
    vocals = bool(lyrics and lyrics.strip())
    prompt = build_prompt(genre_key, lang, vocals)
    lyr = lyrics if vocals else "[inst]"
    seconds = float(max(45, min(int(seconds), 240)))
    last = None

    for si, space in enumerate(SPACES):
        tries = retries if si == 0 else 1
        for attempt in range(1, tries + 1):
            try:
                client = _client(space)
                if space.endswith("v1.5"):
                    audio_path, lrc = _cook_v15(client, genre_key, seconds,
                                                prompt, lyr, lang)
                else:
                    audio_path, lrc = _cook_v1(client, seconds, prompt,
                                               lyr, infer_step)
                audio_path = _pick_file(audio_path)
                if not audio_path:
                    raise RuntimeError("space returned no audio")
                shutil.copy(audio_path, out_path)
                if out_path.stat().st_size < 80_000:
                    raise RuntimeError(f"suspiciously small audio "
                                       f"({out_path.stat().st_size} B)")
                if lrc and lrc_out:
                    lrc_out.write_text(lrc, encoding="utf-8")
                    n = len(parse_lrc(lrc))
                    if n:
                        print(f"  ⏱ karaoke map captured: {n} timed lines")
                mode = f"{lang} vocals 🎤" if vocals else "instrumental"
                print(f"  🎁 {space.split('/')[-1]} cooked {seconds:.0f}s of "
                      f"'{genre_key}' ({mode}, "
                      f"{out_path.stat().st_size // 1024} KB)")
                return out_path
            except Exception as e:
                last = e
                print(f"  ⚠ {space.split('/')[-1]} attempt {attempt}/{tries} "
                      f"failed: {str(e)[:140]}")
    print(f"  ⚠ all spaces unreachable today ({last}) — engine takes over, no harm")
    return None

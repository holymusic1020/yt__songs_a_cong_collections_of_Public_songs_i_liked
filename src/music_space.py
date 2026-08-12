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
from datetime import datetime, timezone
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
    "skyline_anthem": ("anthemic folk-edm, progressive house festival lift, "
                       "big piano stabs, euphoric crowd energy, {bpm} bpm"),
    "villain_pop":    ("dark cinematic pop, villain aesthetic, music-box "
                       "bells, heavy 808 sub, halftime drums, menacing "
                       "elegance, {bpm} bpm"),
    "orbit_trap":     ("melodic trap, confident rap-sung bounce, rolling "
                       "hi-hats, sliding 808 bass, brass stabs, spacey "
                       "pads, {bpm} bpm"),
}

# the HUMAN in the machine: per-genre vocal identity, so every drop sounds
# like the same fictional artiste maturing, not a random karaoke night
VOICE = {
    "drift_phonk":   ["deep raspy male vocals, dark memphis rap energy, "
                      "hushed menace in verses, melodic autotuned hook, "
                      "distant ad libs",
                      "smoky femme-fatale vocal chops, siren hooks over a "
                      "dark memphis bounce",
                      "stacked gang-vocal hook shouts, whispered verses, "
                      "chopped vocal fills"],
    "deep_pop":      ["soft airy female vocals, intimate and breathy, "
                      "sad-pretty verses, big emotional chorus",
                      "velvet male baritone, close-mic'd and minimal, "
                      "falsetto lift on the hook"],
    "dark_ambient":  ["haunting whispered vocals, distant reverb, fragile",
                      "wordless ethereal choir, glass-like soprano fragments"],
    "lofi":          ["mellow hummed vocals, lazy smoky delivery, daydreamy",
                      "dusty old-radio croon, half-sung half-spoken"],
    "baroque_waltz": ["chamber duet vocals, operetta charm, vintage tape warmth",
                      "playful baroque tenor, ornamented music-hall sparkle"],
    "disco_house":   ["soulful diva vocals, celebratory, funky ad libs",
                      "silky male disco falsetto, talkbox echoes, glitter"],
    "skyline_anthem": ["euphoric male tenor, crowd-ready chants, hands-up "
                       "whoa-ohs",
                       "bright female anthem lead, gang harmonies on the hook"],
    "villain_pop":   ["silken dangerous female lead, playful menace, "
                      "whispered taunts, big villain chorus",
                      "smooth male croon with a smirk, theatrical shadows"],
    "orbit_trap":    ["laid-back male melodic-rap flow, confident pockets, "
                      "airy autotuned ad libs",
                      "cold minimal female flow, spaced-out melodic hook"],
}


def _voice_for(genre_key: str) -> str:
    """Pick the day's singer — the same genre never wears the same voice
    two days in a row (rotates daily, zero extra state)."""
    bank = VOICE.get(genre_key) or ["expressive vocals"]
    if isinstance(bank, str):
        return bank
    day = int(datetime.now(timezone.utc).strftime("%j"))
    return bank[day % len(bank)]

# language words for prompts → plus v1.5's native vocal-language codes
LANG_TOKEN = {"en": "english", "pt-BR": "portuguese", "es": "spanish",
              "fr": "french", "tr": "turkish", "ja": "japanese", "ko": "korean"}
LANG_CODE = {"en": "en", "pt-BR": "pt", "es": "es", "fr": "fr",
             "tr": "tr", "ja": "ja", "ko": "ko"}

GENRE_BPM = {"drift_phonk": 130, "deep_pop": 96, "dark_ambient": 60,
             "lofi": 78, "baroque_waltz": 172, "disco_house": 118,
             "skyline_anthem": 128, "villain_pop": 142, "orbit_trap": 148}


def _client(space: str):
    """Version-proof dial: gradio renamed the auth kwarg between releases
    (token= -> hf_token=). The 2026-08-10 run died on exactly this BEFORE
    it could spend a single quota second — try both, then anonymous."""
    from gradio_client import Client
    token = os.environ.get("HF_TOKEN", "").strip() or None
    attempts = ({"token": token}, {"hf_token": token}, {}) if token else ({},)
    last = None
    for kw in attempts:
        kw = {k: v for k, v in kw.items() if v}
        try:
            return Client(space, verbose=False, **kw)
        except TypeError as e:                 # wrong kwarg name -> next style
            last = e
            continue
    raise RuntimeError(f"gradio_client refused every auth style: {last}")


def build_prompt(genre_key: str, lang: str = "en", vocals: bool = True) -> str:
    base = PROMPTS.get(genre_key, "moody, atmospheric").format(
        bpm=GENRE_BPM.get(genre_key, 100))
    if not vocals:
        return base + ", instrumental"
    voice = _voice_for(genre_key)
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
    """Official v1.5 turbo: native BPM + vocal-language + fast 8-step DiT.

    Field order verified 2026-08-11 against the LIVE space (99 endpoints,
    redesigned). The wrapper's args order (after the 4 simple-mode params):
      captions(4) lyrics(5) bpm(6) key_scale(7) time_signature(8)
      vocal_language(9) inference_steps(10) guidance_scale(11)
      random_seed_checkbox(12) seed(13) reference_audio(14)
      audio_duration(15) batch_size_input(16) src_audio(17)
      text2music_audio_code_string(18) repainting_start(19)
      repainting_end(20) instruction_display_gen(21) audio_cover_strength(22)
      task_type(23) use_adg(24) cfg_interval_start(25) cfg_interval_end(26)
      shift(27) infer_method(28) custom_timesteps(29) audio_format(30)
      lm_temperature(31) think_checkbox(32) lm_cfg_scale(33) lm_top_k(34)
      lm_top_p(35) lm_negative_prompt(36) use_cot_metas(37)
      use_cot_caption(38) use_cot_language(39) constrained_decoding_debug(41)
      allow_lm_batch(42) auto_score(43) auto_lrc(44) score_scale(45)
      lm_batch_chunk_size(46) track_name(47) complete_track_classes(48)
      autogen_checkbox(49)   (states at 40/50-53 are hidden by the client)
    Returns (visible): 0-7 audio, 8 all-files, 9 details, 10 status, 11 seed,
      12-19 scores, 20-27 codes, 28-35 lyrics-timestamps, 36 batch, 37 status.
    """
    res = client.predict(
        "acestep-v15-xl-turbo",        # 0 selected_model
        "custom",                      # 1 generation_mode
        "",                            # 2 simple_query_input
        LANG_CODE.get(lang, "en"),     # 3 simple_vocal_language
        prompt,                        # 4 captions (LM style guide)
        lyr,                           # 5 lyrics (tagged text or "[inst]")
        float(GENRE_BPM.get(genre_key, 0)),  # 6 bpm
        "",                            # 7 key_scale (auto)
        "",                            # 8 time_signature (auto)
        LANG_CODE.get(lang, "en"),     # 9 vocal_language dial 🌍
        8.0,                           # 10 DiT steps (turbo)
        7.0,                           # 11 guidance_scale
        True,                          # 12 random_seed_checkbox
        "-1",                          # 13 seed
        None,                          # 14 reference_audio
        float(seconds),                # 15 duration
        1.0,                           # 16 batch size = one perfect take
        None,                          # 17 src_audio
        "",                            # 18 text2music_audio_code_string
        0.0,                           # 19 repainting_start
        -1.0,                          # 20 repainting_end
        "",                            # 21 instruction_display_gen
        1.0,                           # 22 audio_cover_strength
        "text2music",                  # 23 task_type
        False,                         # 24 use_adg
        0.0,                           # 25 cfg_interval_start
        1.0,                           # 26 cfg_interval_end
        3.0,                           # 27 shift
        "ode",                         # 28 infer_method
        "",                            # 29 custom_timesteps
        "mp3",                         # 30 audio_format
        0.85,                          # 31 lm_temperature
        True,                          # 32 think_checkbox (LM writes the music)
        2.0,                           # 33 lm_cfg_scale
        0.0,                           # 34 lm_top_k
        0.9,                           # 35 lm_top_p
        "",                            # 36 lm_negative_prompt
        True,                          # 37 use_cot_metas
        True,                          # 38 use_cot_caption
        True,                          # 39 use_cot_language
        False,                         # 40 constrained_decoding_debug
        False,                         # 41 allow_lm_batch
        False,                         # 42 auto_score (saves GPU quota)
        True,                          # 43 auto_lrc → karaoke timestamps 🎤⏱
        0.5,                           # 44 score_scale
        8.0,                           # 45 lm_batch_chunk_size
        None,                          # 46 track_name (hidden dropdown)
        None,                          # 47 complete_track_classes (hidden)
        False,                         # 48 autogen_checkbox
        api_name="/generation_wrapper",
    )
    audio = _pick_file(res[0])
    lrc = None
    try:
        cand = res[28]                 # Lyrics Timestamps (Sample 1)
        cand = cand.get("value") if isinstance(cand, dict) else cand
        if isinstance(cand, str) and re.search(r"\d{1,2}:\d{2}", cand):
            lrc = cand
    except (IndexError, TypeError):
        lrc = None
    if not audio:
        # say WHY — quota-exhausted spaces are the usual culprit
        try:
            why = str(res[9]) or str(res[10])
        except Exception:
            why = ""
        raise RuntimeError(f"space returned no audio" + (f" ({why[:120]})" if why else ""))
    return audio, lrc


def _cook_v1(client, seconds, prompt, lyr, infer_step):
    """Classic v1 space fallback — signature verified 2026-08-11 against the
    LIVE space (the old 4-kwarg call died with TypeError: the space now
    exposes the full 22-param /__call__)."""
    audio, _params = client.predict(
        audio_duration=float(seconds),
        prompt=prompt,
        lyrics=lyr,
        infer_step=float(infer_step),
        guidance_scale=15.0,
        scheduler_type="euler",
        cfg_type="apg",
        omega_scale=10.0,
        manual_seeds="-1",
        guidance_interval=0.5,
        guidance_interval_decay=0.0,
        min_guidance_scale=3.0,
        use_erg_tag=True,
        use_erg_lyric=True,
        use_erg_diffusion=True,
        oss_steps="",
        guidance_scale_text=0.0,
        guidance_scale_lyric=0.0,
        audio2audio_enable=False,
        ref_audio_strength=0.5,
        ref_audio_input=None,
        lora_name_or_path="none",
        api_name="/__call__",
    )
    return audio, None


def generate(genre_key: str, seconds: float, out_path: Path,
             retries: int = 2, infer_step: int = 32,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None,
             spaces: list[str] | None = None) -> Path | None:
    """Cook one song. Returns the file on success, else None.

    lyrics=None → instrumental ('[inst]'). lyrics=tagged text → SUNG track
    in `lang`. lrc_out: when the v1.5 space returns lyric timestamps
    (karaoke map 🎤⏱), they're written there for video_render's overlay.
    Same failure contract as always: None means 'engine, take over'.

    `spaces`: optional subset of SPACES to try (v23.4 POWER GRID uses this
    so the grid can treat v1.5 and v1 as two separate retryable lanes).
    """
    vocals = bool(lyrics and lyrics.strip())
    prompt = build_prompt(genre_key, lang, vocals)
    lyr = lyrics if vocals else "[inst]"
    seconds = float(max(45, min(int(seconds), 240)))
    last = None
    active = spaces if spaces else SPACES

    for si, space in enumerate(active):
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
                msg = str(e)
                if "quota" in msg.lower() or "ZeroGPU" in msg:
                    print(f"  ⚠ {space.split('/')[-1]} attempt {attempt}/{tries} "
                          f"failed: ZEROGPU QUOTA exhausted — free-vocal lane "
                          f"sleeping (HF_TOKEN raises it; engine takes over today)")
                else:
                    print(f"  ⚠ {space.split('/')[-1]} attempt {attempt}/{tries} "
                          f"failed: {msg[:140]}")
    print(f"  ⚠ all spaces unreachable today ({last}) — engine takes over, no harm")
    return None

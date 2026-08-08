"""Full-auto AI songs from the free ACE-Step Space. Boss's queue design:

    run N  : publish today's song → cook TOMORROW's song on the Space →
             hold it (artifact 'next-song' — zero repo bloat, auto-expires)
    run N+1: eats the queued song → publishes → cooks the next one 🔁

Safety philosophy: ANY Space failure (asleep, rate-limited, gone) returns
None and the built-in engine takes over. The Space can NEVER kill a run.

License: ACE-Step is Apache-2.0 → commercial-safe. ZeroGPU quota is shared;
an optional FREE HF account token (env HF_TOKEN) raises it. No card needed.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SPACE = "ACE-Step/ACE-Step"

# genre wheel → Space prompts (tags-first, the style ACE-Step responds to)
PROMPTS = {
    "drift_phonk":    ("drift phonk, dark memphis phonk, distorted 808 bass, "
                       "phonk cowbell melody, chopped vocal chops, night drive, "
                       "ominous, saturated, {bpm} bpm"),
    "deep_pop":       ("melancholic alt pop instrumental, deep pulsing synth bass, "
                       "airy detuned pads, slow burn build, emotional, rainy window, "
                       "{bpm} bpm"),
    "dark_ambient":   ("dark ambient drone instrumental, slow evolving textures, "
                       "distant thunder, tape hiss, cinematic vastness, unsettling calm"),
    "lofi":           ("lofi hip hop instrumental, dusty vinyl crackle, warm rhodes "
                       "chords, soft boom bap drums, rain on the window, {bpm} bpm"),
    "baroque_waltz":  ("playful baroque waltz, harpsichord and string quartet, "
                       "vintage ballroom tape recording, whimsical, 3/4 time"),
    "disco_house":    ("french house disco instrumental, funky filtered bassline, "
                       "four on the floor, lush string stabs, feel-good groove, "
                       "{bpm} bpm"),
}
GENRE_BPM = {"drift_phonk": 130, "deep_pop": 96, "dark_ambient": 60,
             "lofi": 78, "baroque_waltz": 172, "disco_house": 118}


def _client():
    from gradio_client import Client
    token = os.environ.get("HF_TOKEN", "").strip() or None
    return Client(SPACE, token=token, verbose=False)


def generate(genre_key: str, seconds: float, out_path: Path,
             retries: int = 2, infer_step: int = 32) -> Path | None:
    """Cook one instrumental up to 240 s. Returns the file on success, else None."""
    bpm = GENRE_BPM.get(genre_key, 100)
    prompt = PROMPTS.get(genre_key,
                         "instrumental, moody, atmospheric").format(bpm=bpm)
    seconds = float(max(45, min(int(seconds), 240)))
    last = None
    for attempt in range(1, retries + 1):
        try:
            audio_path, _params = _client().predict(
                audio_duration=seconds,
                prompt=prompt,
                lyrics="[inst]",
                infer_step=float(infer_step),
                api_name="/__call__",
            )
            shutil.copy(audio_path, out_path)
            if out_path.stat().st_size < 80_000:
                raise RuntimeError(f"suspiciously small audio "
                                   f"({out_path.stat().st_size} B)")
            print(f"  🎁 space cooked {seconds:.0f}s of '{genre_key}' "
                  f"({out_path.stat().st_size // 1024} KB)")
            return out_path
        except Exception as e:
            last = e
            print(f"  ⚠ space gen attempt {attempt}/{retries} failed: {e}")
    print(f"  ⚠ space is unreachable today ({last}) — engine takes over, no harm")
    return None

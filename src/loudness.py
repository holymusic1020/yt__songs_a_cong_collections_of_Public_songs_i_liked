"""Per-song loudness matching to the streaming standard (2026-09-19).

WHY (research, not taste):
  · YouTube, Spotify, Tidal and Amazon all normalise to **-14 LUFS integrated**;
    Apple Music uses -16. YouTube only turns loud tracks DOWN — it never boosts
    quiet ones. So a hot master loses dynamics for nothing, and a quiet master
    plays *quieter than every other video in the feed*.
  · True peak must stay under **-1 dBTP** or the AAC encode clips between
    samples — audible distortion that was not in the master.
  · This is PER SONG. It changes level only — never tone, structure, genre
    character. Every track keeps its own dynamics and personality; they just
    all land at the same perceived volume, like a real album.

HOW: two-pass ffmpeg `loudnorm` (measure, then apply with the measured values).
Kill-switch: LOUDNORM=0. NEVER raises: any error returns the wav untouched,
because a missing loudness pass must never cost a release.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TARGET_I = -14.0        # LUFS integrated — the streaming standard
TARGET_TP = -1.0        # dBTP true-peak ceiling
TARGET_LRA = 11.0       # loudness range: keeps dynamics, tames wild swings


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def measure(path: Path) -> dict | None:
    ff = _ffmpeg()
    if not ff:
        return None
    cmd = [ff, "-hide_banner", "-nostats", "-i", str(path),
           "-af", f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
           "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600)
        txt = r.stderr.decode(errors="replace")
        i = txt.rfind("{")
        return json.loads(txt[i:]) if i >= 0 else None
    except Exception:
        return None


def normalize_wav(path: Path) -> Path:
    """Two-pass loudnorm. Returns the (possibly rewritten) path. Never raises."""
    if os.environ.get("LOUDNORM", "1").strip() == "0":
        print("  🔉 loudnorm: OFF by dial")
        return path
    ff = _ffmpeg()
    if not ff:
        print("  🔉 loudnorm: no ffmpeg — skipped (release unaffected)")
        return path
    m = measure(path)
    if not m or "input_i" not in m:
        print("  🔉 loudnorm: measure failed — skipped (release unaffected)")
        return path
    before = float(m["input_i"])
    if abs(before - TARGET_I) < 0.3 and float(m["input_tp"]) <= TARGET_TP:
        print(f"  🔉 loudnorm: already {before:.1f} LUFS / {float(m['input_tp']):.1f} dBTP — untouched")
        return path
    cmd = [ff, "-hide_banner", "-y", "-i", str(path),
           "-af", (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"
                   f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                   f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
                   f":offset={m['target_offset']}:linear=true"),
           "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le"]
    tmp = Path(tempfile.mktemp(suffix=".wav"))
    try:
        subprocess.run(cmd + [str(tmp)], check=True, capture_output=True, timeout=900)
        chk = measure(tmp)
        after = float(chk["input_i"]) if chk else float("nan")
        os.replace(tmp, path)
        print(f"  🔉 loudnorm: {before:.1f} → {after:.1f} LUFS (target {TARGET_I:.0f}, "
              f"TP ≤ {TARGET_TP:.0f} dBTP) — level only, character untouched")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        print(f"  🔉 loudnorm: apply failed ({e}) — original kept")
    return path

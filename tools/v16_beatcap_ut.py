#!/usr/bin/env python3
"""v16 🎵 MUSICAL CAPTIONS UT — boss 2026-08-31:
"lines isnt matching… dont make all the line matching like it feels lame."

Proves, offline, on synthetic audio with a KNOWN groove:
  1. 🥁 grid recovery: beat length honoured, drum phase recovered from flux
  2. 🎵 flips snap to the grid and LEAD it by anticipation (groove, not lag)
  3. ✂️ NOT every line flips — fast lines pair into couplets; punch lines
     (title words) stay solo → the screen breathes
  4. 🛡 any doubt (silence / no audio) → input map returned unchanged (v8 law)
Run:  python tools/v16_beatcap_ut.py
"""
import sys, wave, tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import beatcap  # noqa: E402


def wav_with_drums(path: Path, sr=44100, secs=30.0, bpm=100.0, phase=0.420):
    beat = 60.0 / bpm
    n = int(sr * secs)
    t = np.arange(n) / sr
    pcm = 0.12 * np.sin(2 * np.pi * 220 * t).astype(np.float32)   # quiet melody
    k = 0
    while phase + k * beat < secs - 0.05:                          # drum grid
        c = int((phase + k * beat) * sr)
        m = min(int(0.030 * sr), n - c)
        pcm[c:c + m] += 0.9 * np.random.default_rng(7).standard_normal(m).astype(np.float32) * 0.02
        k += 1
    pcm = np.clip(pcm, -1, 1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return beat, phase


def silent_wav(path: Path, sr=44100, secs=8.0):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00" * int(sr * secs) * 2)


fails = 0


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v16ut_"))
    drum = tmp / "drums.wav"
    beat, phase = wav_with_drums(drum)                            # 100 bpm grid

    # ── 1 · grid recovery ────────────────────────────────────────────────
    got = beatcap.beat_grid(beatcap._read_mono(drum)[0], 44100, 100.0)
    chk(got is not None, "grid recovered from drum audio")
    gb, gp = got
    chk(abs(gb - beat) < 0.02, f"beat length honoured ({gb:.3f}s vs {beat:.3f}s)")
    chk(abs((gp - phase + beat / 2) % beat - beat / 2) < 0.05,
        f"drum phase recovered ({gp:.3f}s vs {phase:.3f}s)")

    # ── 2+3 · musicalize: snap + anticipation + couplets + punch solos ──
    words = [f"walking through the city {i}" for i in range(14)]
    words[4] = "you are my midnight caller"                       # punch lines
    words[9] = "still the midnight in me"
    entries = [(round(2.10 + i * 1.03, 3), w) for i, w in enumerate(words)]
    hooks = beatcap.title_words("Midnight Rain")
    out = beatcap.musicalize(entries, 100.0, drum, hook_words=hooks)

    chk(len(out) < len(entries), f"NOT all lines flip: {len(entries)} lines → {len(out)} flips")
    starts = [a for a, _ in out]
    on_grid = [abs(((a + beatcap.ANTICIPATION) - gp + beat / 2) % beat - beat / 2) < 0.03
               for a in starts]
    chk(all(on_grid), "every flip lands ON the drum grid (±30ms)")
    leads = [(2.10 + i * 1.03) - min(starts, key=lambda s: abs(s - (2.10 + i * 1.03))) < 1.0
             for i in (0, 1)]
    chk(all(leads), "flips stay close to their kernel phrase (no wild jumps)")
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    chk(all(g >= beatcap.MIN_GAP - 1e-3 for g in gaps),
        f"flips breathe — min gap {min(gaps):.3f}s ≥ {beatcap.MIN_GAP}s")
    txt = " || ".join(t for _, t in out)
    chk("walking through the city 0 walking through the city 1" in txt,
        "fast lines pair into couplets")
    solos = [t for _, t in out]
    chk(any(t == "you are my midnight caller" for t in solos),
        "punch line (title word) keeps a SOLO card")
    chk(not any("midnight caller walking" in t for t in solos),
        "punch line is never swallowed into a couplet")

    # ── 4 · doubt-paths return the input unchanged (v8 law) ─────────────
    sil = tmp / "silence.wav"
    silent_wav(sil)
    out2 = beatcap.musicalize(entries, 100.0, sil, hook_words=hooks)
    chk(out2 == entries, "silent audio → kernel map untouched")
    out3 = beatcap.musicalize(entries, 100.0, None, hook_words=hooks)
    chk(out3 == entries, "no audio handled → kernel map untouched")
    chk(beatcap.musicalize([(0.0, "only")], 100.0, drum) == [(0.0, "only")],
        "tiny map passes through")

    print()
    if fails:
        print(f"❌ v16 musical-caption UT: {fails} FAIL")
        return 1
    print("✅ v16 UT green — captions land on the groove, screens breathe, doubt never regresses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

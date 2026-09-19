"""🌀 The dimensional moment — ONE orbiting window per song (boss 2026-09-19).

His spec, verbatim in spirit: not the whole track — a 5–22 s "needy part" where the
sound orbits your head on earbuds, and plain stereo everywhere else.

HONEST ENGINEERING (why this implementation and not real "8D"):
  · True binaural 8D uses phase/HRTF tricks. Those COLLAPSE on mono downmixes
    (TikTok/IG/phone speaker) — parts of the song get cancelled. Unacceptable.
  · This is **level-only equal-power orbiting**: the mix's pan angle oscillates
    gently around centre. No phase games, so mono survives.
  · A per-angle mono compensation keeps the mono sum *exactly* dry for mono
    material, and within ~1 dB for real stereo material. Verified by UT-29.
  · Depth is modest (±~28°) and the rate slow (~one orbit / 5.5 s): perceptible
    on earbuds as "the song opened up", never a gimmick swirl.
  · Edges are 0.6 s cosine crossfades — no click, no seam.

Window choice: the loudest 12 s after the first fifth of the track (the drop /
second hook), computed per song from its own energy — so every track's moment
lands in a different musical place. Uniqueness law respected.

Dial: SPIN=1 enables — and 1 is now the DEFAULT (boss 2026-09-19: "turn on the
dimensional movement… only in the needy songs, not all songs"). SPIN=0 disables
everything. "Only the needy songs" is enforced by the taste gate below, not by
the dial: the dial decides IF the feature exists, the gate decides WHO gets it.

THE TASTE GATE (boss 2026-09-19: "only the song that really needs it — on most
songs it feels awkward"):
  · genre allow-list only (dark_ambient / lofi / orbit_trap) — driving vocal
    genres (phonk, disco, anthem, pop) never orbit;
  · the window must be INSTRUMENTAL: if sung lines occupy >25% of it, skip.
    Real mixing law: the lead voice stays centre; a circling voice is uncanny.
  So most episodes skip it and print why. The moment stays special.
"""
from __future__ import annotations

import os
import numpy as np

DEPTH = 0.35          # radians of pan swing (~20°): audible on earbuds, keeps the
                    # mono-sum swell under ~1 dB on phone speakers (UT-29 measures it)
RATE = 0.18           # Hz — one full orbit every ~5.5 s
WIN_S = 12.0          # window length
EDGE_S = 0.6          # crossfade at both edges
MIN_DUR_S = 20.0      # never spin a clip shorter than this


def _pick_window(x: np.ndarray, sr: int) -> tuple[int, int] | None:
    n = len(x)
    if n < MIN_DUR_S * sr:
        return None
    hop = sr // 2
    mono = x.mean(axis=1) if x.ndim > 1 else x
    frames = np.lib.stride_tricks.sliding_window_view(mono, hop)[::hop]
    rms = np.sqrt((frames ** 2).mean(axis=1))
    if rms.size < 8:
        return None
    win = int(WIN_S / 0.5)
    lo = int(rms.size * 0.20)                 # skip the first fifth
    hi = max(lo + 1, int(rms.size * 0.80) - win)
    if hi <= lo:
        return None
    scores = np.array([rms[i:i + win].mean() for i in range(lo, hi)])
    start_f = lo + int(np.argmax(scores))
    a = start_f * hop
    b = min(n, a + int(WIN_S * sr))
    return a, b


def _orbit(x: np.ndarray, sr: int, a: int, b: int) -> np.ndarray:
    n = b - a
    t = np.arange(n) / sr
    phi = np.pi / 4 + DEPTH * np.sin(2 * np.pi * RATE * t)
    gl, gr = np.cos(phi), np.sin(phi)
    comp = 2.0 / (gl + gr)                    # mono-sum compensation
    gl, gr = gl * comp, gr * comp
    seg = x[a:b].copy()
    if seg.ndim == 1:
        seg = np.stack([seg, seg], axis=1)
    wet = np.stack([seg[:, 0] * gl, seg[:, 1] * gr], axis=1)
    e = int(EDGE_S * sr)
    w = np.ones(n)
    w[:e] = 0.5 - 0.5 * np.cos(np.pi * np.arange(e) / e)
    w[-e:] = w[:e][::-1]
    w2 = w[:, None]
    x[a:b] = (wet * w2 + seg * (1 - w2)).astype(np.float32)
    return x


ALLOW_GENRES = {"dark_ambient", "lofi", "orbit_trap"}
VOCAL_MAX = 0.25          # fraction of the window that may be sung


def _vocal_fraction(win: tuple[int, int], sr: int, sung_starts) -> float:
    a, b = win[0] / sr, win[1] / sr
    ss = sorted(float(t) for t in (sung_starts or []))
    if not ss:
        return 0.0
    spans = [(ss[i], ss[i + 1] if i + 1 < len(ss) else ss[i] + 4.0)
             for i in range(len(ss))]
    ov = 0.0
    for s0, s1 in spans:
        ov += max(0.0, min(b, s1) - max(a, s0))
    return ov / max(1e-6, b - a)


def apply(path, genre_key: str = "", sung_starts=()) -> object:
    """Spin one window of the wav in place. Never raises; dial-gated."""
    from pathlib import Path
    import wave
    p = Path(path)
    # 🌀 DEFAULT ON (boss verdict 2026-09-19: "turn on the dimensional movement,
    #    but only in the needy songs"). SPIN=0 kills it for every run. The
    #    taste gate right below is what makes "only the needy songs" true.
    if os.environ.get("SPIN", "1").strip() != "1":
        return p
    if genre_key and genre_key not in ALLOW_GENRES:
        print(f"  🌀 spin: skipped — {genre_key} doesn't earn an orbit (vocal-driven)")
        return p
    try:
        with wave.open(str(p), "rb") as w:
            n, sw, sr = w.getnframes(), w.getsampwidth(), w.getframerate()
            ch = w.getnchannels()
            raw = w.readframes(n)
        if sw != 2 or ch != 2:
            print("  🌀 spin: not 16-bit stereo — skipped")
            return p
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32).reshape(n, 2) / 32768.0
        win = _pick_window(x, sr)
        if not win:
            print("  🌀 spin: track too short for a moment — skipped")
            return p
        a, b = win
        vf = _vocal_fraction(win, sr, sung_starts)
        if vf > VOCAL_MAX:
            print(f"  🌀 spin: skipped — window is {vf:.0%} sung; the voice stays centre")
            return p
        x = _orbit(x, sr, a, b)
        pcm = (np.clip(x, -0.999, 0.999) * 32767.0).astype(np.int16)
        with wave.open(str(p), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        print(f"  🌀 spin: this one earns it — dimensional moment {a/sr:.1f}s → "
              f"{b/sr:.1f}s ({genre_key or '?'}, {vf:.0%} sung, ±{np.degrees(DEPTH):.0f}° orbit)")
    except Exception as e:
        print(f"  🌀 spin: skipped ({e}) — original kept")
    return p

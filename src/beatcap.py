"""v16 🎵 MUSICAL CAPTIONS — boss 2026-08-31: "lines isnt matching…
dont make all the line matching like it feels lame."

The failure he heard: v15 cards flip on EVERY kernel-lrc line at the kernel's
own timestamps. Kernel times are an even split — not the music — so captions
drift off the groove AND flip like a teleprompter. Lame either way.

The musical contract (what the eye should feel):
  1. LINES LAND ON BEATS — every caption flip snaps to the drum grid
     (grid recovered from the audio itself: flux onsets → BPM-quantized
     phase). Text and kick move together; nothing floats between beats.
  2. NOT EVERY LINE FLIPS — fast lines pair into couplets; only punch
     lines (title/hook words) get a solo card. The screen breathes.
  3. ANTICIPATION — a caption lands ~160 ms BEFORE its beat, the way real
     lyric videos pre-sage the singer. Anticipation reads as groove;
     reaction reads as lag.

Pure numpy, deterministic, $0. Any failure path returns the input unchanged
— a good karaoke is never made worse (v8 law).
"""
from __future__ import annotations

import wave
import numpy as np

ANTICIPATION = 0.16      # seconds the text leads its beat
MERGE_SPAN = 1.6         # a sung line shorter than this pairs into a couplet
MIN_GAP = 0.8            # two flips never land closer than this
PROBE_S = 24.0           # grid estimation window


def _read_mono(path) -> tuple[np.ndarray, int] | None:
    try:
        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch and ch > 1:
            pcm = pcm.reshape(-1, ch).mean(axis=1)
        return pcm, sr
    except Exception:
        return None


def beat_grid(pcm: np.ndarray, sr: int, bpm: float
              ) -> tuple[float, float] | None:
    """(beat_len_s, phase_s) of the drum grid, or None when no grid is
    trustworthy. Energy-flux onsets → onset phases mod beat → weighted
    circular peak. beat_len comes FROM the arrangement's own bpm (known),
    only the phase is recovered from audio."""
    if pcm is None or len(pcm) < sr * 2 or not bpm:
        return None
    beat = 60.0 / float(bpm)
    blk = pcm[: int(sr * PROBE_S)]
    win, hop = 1024, 512
    nfr = (len(blk) - win) // hop
    if nfr < 32:
        return None
    idx = np.arange(win)
    seg = np.lib.stride_tricks.as_strided(
        blk, shape=(nfr, win),
        strides=(blk.strides[0] * hop, blk.strides[0]), writeable=False)
    rms = np.sqrt((seg ** 2).sum(axis=1) / win)
    flux = np.diff(rms, prepend=rms[0])
    flux[flux < 0] = 0
    med, std = float(np.median(flux)), float(flux.std())
    if std <= 1e-9:
        return None
    thr = med + 1.05 * std
    refr = int(0.30 * beat * sr / hop)
    peaks, last = [], -10 ** 9
    for i in range(1, nfr - 1):
        if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] \
                and i - last >= refr:
            peaks.append(i)
            last = i
    if len(peaks) < 6:
        return None
    times = (np.array(peaks) * hop + win / 2) / sr
    w = flux[peaks]
    phases = times % beat
    bins = np.linspace(0, beat, 65)          # 64 phase bins
    hist = np.zeros(64)
    k = np.clip(np.digitize(phases, bins) - 1, 0, 63)
    np.add.at(hist, k, w)
    # circular 3-tap smoothing, then take the peak neighbourhood's mean
    h3 = np.convolve(np.r_[hist[-1], hist, hist[0]], np.ones(3) / 3)[1:-1]
    pk = int(h3.argmax())
    sel = np.abs(k - pk) <= 1
    if not sel.any():
        return None
    d = phases[sel] - (pk + 0.5) * (beat / 64)
    d = (d + beat / 2) % beat - beat / 2     # wrap distances to peak bin
    phase = float((pk + 0.5) * (beat / 64) + np.average(d, weights=w[sel])) % beat
    return beat, phase


def title_words(name: str | None) -> frozenset:
    """Hook tokens: the song's own name = the punch words (≥4 letters)."""
    import re
    return frozenset(w for w in re.findall(r"[a-z']+", (name or "").lower())
                     if len(w) >= 4)


def musicalize(entries: list, bpm: float, audio_path=None,
               hook_words: frozenset = frozenset(),
               anticipation: float = ANTICIPATION) -> list:
    """Kernel/ACE lrc map → MUSICAL karaoke map.

    Fast lines pair into couplets (fewer flips, more breath); punch lines
    with a hook word stay solo; every flip snaps floor-biased to the beat
    grid and leads it by `anticipation`. Input order/count shape: returns a
    NEW list of (t_abs, text). Falls back to the input unchanged."""
    if len(entries or []) < 4:
        return entries or []
    grid = None
    if audio_path is not None:
        got = _read_mono(audio_path)
        if got:
            grid = beat_grid(got[0], got[1], bpm)
    if grid is None:
        print("  🎵 v16 captions: no trustworthy drum grid — kernel map stands")
        return entries
    beat, phase = grid

    # 1 · group: couplets for fast lines, solo for punch lines
    groups: list[tuple[int, str]] = []       # (first-line index, merged text)
    i = 0
    while i < len(entries):
        t0, txt = entries[i][0], entries[i][1].strip()
        span = (entries[i + 1][0] - t0) if i + 1 < len(entries) else MERGE_SPAN
        punch = hook_words and any(w in txt.lower() for w in hook_words)
        nxt_punch = i + 1 < len(entries) and hook_words and any(
            w in entries[i + 1][1].lower() for w in hook_words)
        if not punch and not nxt_punch and span < MERGE_SPAN and i + 1 < len(entries):
            groups.append((i, txt + " " + entries[i + 1][1].strip()))
            i += 2
        else:
            groups.append((i, txt))
            i += 1

    # 2 · snap each group's start to the grid (floor-biased) + anticipation
    out, prev_a = [], -1e9
    for i0, txt in groups:
        nominal = entries[i0][0]
        k = np.floor((nominal - phase) / beat + 0.15)
        a = phase + k * beat - anticipation
        bumps = 0
        while a < prev_a + MIN_GAP and bumps < 2:
            a += beat
            bumps += 1
        if a < prev_a + MIN_GAP:
            continue                        # grid too crowded → drop flip
        prev_a = a
        out.append((round(float(max(a, 0.0)), 3), txt))

    if len(out) < 3:
        return entries
    print(f"  🎵 v16 captions MUSICALIZED: {len(entries)} lines → {len(out)} flips "
          f"(beat {beat:.3f}s @ phase {phase:.3f}s, lead {anticipation:.2f}s)")
    return out

"""Procedural music engine — drift phonk / deep dark-pop / dark ambient.

Every sound is synthesized from scratch with numpy (no samples, no external
models, no copyrighted material), so every track is 100% license-clean:
safe to upload, safe to monetize later.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MINOR_PENT = [0, 3, 5, 7, 10]
MAJOR_PENT = [0, 2, 4, 7, 9]      # anthem bright side

# ------------------------------------------------------------------ helpers

def midi(note: float) -> float:
    return 440.0 * 2.0 ** ((note - 69.0) / 12.0)


def adsr(n, a, d, s, r, sr=SR):
    a_n, d_n, r_n = (max(1, int(x * sr)) for x in (a, d, r))
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([
        np.linspace(0.0, 1.0, a_n, endpoint=False),
        np.linspace(1.0, s, d_n, endpoint=False),
        np.full(s_n, s, dtype=np.float32),
        np.linspace(s, 0.0, r_n),
    ]).astype(np.float32)
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n]


def osc(kind, freq, n, sr=SR):
    ph = ((np.arange(n, dtype=np.float32) / sr) * float(freq)) % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    if kind == "square":
        return np.where(ph < 0.5, 1.0, -1.0).astype(np.float32)
    if kind == "saw":
        return (2.0 * ph - 1.0)
    if kind == "tri":
        return (2.0 * np.abs(2.0 * ph - 1.0) - 1.0)
    raise ValueError(kind)


def noise(n, rng):
    return rng.standard_normal(n).astype(np.float32)


def lowpass(x, window=801):
    k = np.ones(window, dtype=np.float32) / window
    return np.convolve(x, k, mode="same").astype(np.float32)


def echo(sig, delay_s, gains=(0.32, 0.16), sr=SR):
    sig = sig.astype(np.float32)
    out = sig.copy()
    d = max(1, int(delay_s * sr))
    for i, g in enumerate(gains, start=1):
        off = d * i
        if off < len(out):
            out[off:] += sig[: len(sig) - off] * g
    return out

# ------------------------------------------------------------------
# v19 "PRODUCED, NOT PROGRAMMED" toolkit — answers the roast:
# human groove, sidechain pocket, moving filters, real builds & drops.
# ------------------------------------------------------------------

def human(rng, gain, spread=0.18):
    """No two hits share a velocity. spread=0.18 -> +/-18% loudness wobble."""
    return float(gain) * float(1.0 + rng.uniform(-spread, spread))


def jit(rng, sr=SR, ms=6.0):
    """Micro-timing wobble in samples — off the grid, into the groove."""
    return int(rng.uniform(-ms, ms) * sr / 1000.0)


def sidechain(buf, hits, sr=SR, depth=0.55, attack=0.004, release=0.22):
    """The pocket: duck `buf` for a breath at every kick so 50-60 Hz has ONE owner."""
    if not hits:
        return buf
    n = len(buf)
    env = np.ones(n, dtype=np.float32)
    a_n, r_n = max(1, int(attack * sr)), max(1, int(release * sr))
    shape = np.concatenate([
        np.linspace(1.0, 1.0 - depth, a_n, endpoint=False),
        np.linspace(1.0 - depth, 1.0, r_n),
    ]).astype(np.float32)
    for h in hits:
        h = int(h)
        if h >= n:
            break
        end = min(n, h + len(shape))
        env[h:end] = np.minimum(env[h:end], shape[: end - h])
    return (buf * env).astype(np.float32)


def chorus(x, sr=SR, base_ms=14.0, depth_ms=6.0, rate=0.9, mix=0.35):
    """Detuned ghost copy via a wandering delay line — kills 'static preset' death."""
    n = len(x)
    if n < sr // 4:
        return x
    idx = np.arange(n, dtype=np.float32)
    d = (base_ms + depth_ms * np.sin(2 * np.pi * rate * idx / sr)) * sr / 1000.0
    wet = np.interp(idx - d, np.arange(n, dtype=np.float32), x)
    return (x * (1.0 - mix) + wet * mix).astype(np.float32)


def sweep_filter(x, sr, cut, frame=2048, hop=512):
    """Time-varying smooth low-pass. `cut` = (f0, f1) ramp or per-sample array."""
    n = len(x)
    if n < frame:
        return x
    if np.isscalar(cut):
        cut = (float(cut), float(cut))
    cut = np.asarray(cut, dtype=np.float32)
    if cut.ndim == 0:
        cut = np.full(n, float(cut), dtype=np.float32)
    elif cut.size == 2:
        cut = np.linspace(float(cut[0]), float(cut[1]), n, dtype=np.float32)
    elif cut.size != n:
        cut = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, cut.size),
                        cut).astype(np.float32)
    win = np.hanning(frame).astype(np.float32)
    freqs = np.fft.rfftfreq(frame, 1.0 / sr)
    out = np.zeros(n + frame, dtype=np.float32)
    wsum = np.zeros(n + frame, dtype=np.float32)
    nfr = 1 + (n - frame) // hop
    for i in range(nfr):
        s = i * hop
        seg = x[s:s + frame] * win
        f = max(120.0, float(cut[s + frame // 2]))
        taper = np.clip((f * 1.5 - freqs) / (f * 0.5), 0.0, 1.0)
        out[s:s + frame] += np.fft.irfft(np.fft.rfft(seg) * taper, frame) * win
        wsum[s:s + frame] += win
    out_n = out[:n]
    wsum_n = wsum[:n]
    nz = wsum_n > 1e-6
    out_n[nz] /= wsum_n[nz]
    out_n[~nz] = x[~nz]
    return out_n.astype(np.float32)


def riser(rng, dur, sr=SR):
    """A breath rising 500->8000 Hz — the crowd hears the drop coming."""
    n = max(int(dur * sr), 4096)
    x = sweep_filter(noise(n, rng), sr, (500.0, 8000.0))
    env = np.linspace(0.0, 1.0, n, dtype=np.float32) ** 2
    return (x * env * 0.8).astype(np.float32)


def snare_roll(rng, dur, sr=SR):
    """Accelerating roll with a velocity ramp — 'here it comes' in drum language."""
    n = int(dur * sr)
    m = Mix(max(1, n))
    k = 24
    for i in range(k):
        at = int(n * (i / k) ** 1.6)          # ease-in: gaps shrink toward the drop
        g = 0.12 + 0.55 * (i / (k - 1))
        m.add(snare(rng), at + jit(rng, sr, ms=3.0), gain=human(rng, g, 0.15))
    return m.buf


def crash(rng, sr=SR):
    """Airy cymbal wash that lands WITH the first kick of a hook."""
    n = int(1.4 * sr)
    t = np.arange(n, dtype=np.float32) / sr
    x = noise(n, rng) * np.exp(-t * 2.8)
    x = x - lowpass(x, 801)                       # no low rumble, all shimmer
    peak = float(np.max(np.abs(x)))
    return (x / peak * 0.8).astype(np.float32) if peak > 1e-6 else x.astype(np.float32)


def _build_map(hook, intro_b):
    """Last 2 bars before a hook block = build (riser+roll); kick takes a breath."""
    bars = len(hook)
    build_open = np.zeros(bars, dtype=bool)
    build_last = np.zeros(bars, dtype=bool)
    for b in range(bars - 1):
        if not hook[b] and hook[b + 1] and b >= max(0, intro_b - 1):
            build_last[b] = True
            build_open[max(0, b - 1)] = True
    return build_open, build_last


def bell(note, dur=0.8, sr=SR):
    """Music-box bell — sine + inharmonic partials, fast decay. Villain candy."""
    n = max(64, int(dur * sr))
    tt = np.arange(n, dtype=np.float32) / sr
    f = midi(note)
    sig = (np.sin(2 * np.pi * f * tt)
           + 0.45 * np.sin(2 * np.pi * f * 2.99 * tt)
           + 0.18 * np.sin(2 * np.pi * f * 4.92 * tt))
    env = np.minimum(1.0, tt / 0.003) * np.exp(-tt * 3.2)
    return (sig * env * 0.8).astype(np.float32)


def stab(notes, dur=0.28, sr=SR):
    """Detuned saw stack hit — brass-ish hook punctuation."""
    n = max(64, int(dur * sr))
    out = np.zeros(n, dtype=np.float32)
    for note in notes:
        f = midi(note)
        for det in (-0.9, 0.7):
            out += osc("saw", f * (1 + det / 100), n)
    out = out * adsr(n, 0.004, 0.06, 0.4, 0.10)
    return (out * 0.22).astype(np.float32)


def clap(rng, sr=SR):
    """Three tight noise bursts read as one handclap."""
    n = int(0.09 * sr)
    tt = np.arange(n, dtype=np.float32) / sr
    e = (np.exp(-tt * 60)
         + 0.7 * np.exp(-np.clip(tt - 0.012, 0, None) * 60) * (tt > 0.012)
         + 0.7 * np.exp(-np.clip(tt - 0.024, 0, None) * 40) * (tt > 0.024))
    return (noise(n, rng) * e).astype(np.float32)


def kick(rng, sr=SR):
    n = int(0.24 * sr)
    t = np.arange(n, dtype=np.float32) / sr
    fenv = (45.0 + 75.0 * np.exp(-t * 28.0)).astype(np.float32)
    phase = np.cumsum(fenv) / sr * 2 * np.pi
    body = np.sin(phase) * np.exp(-t * 10.0)
    click = noise(n, rng) * np.exp(-t * 300.0) * 0.3
    return (body + click).astype(np.float32)


def hat(rng, open_=False, sr=SR):
    dur = 0.26 if open_ else 0.05
    n = int(dur * sr)
    t = np.arange(n, dtype=np.float32) / sr
    return (noise(n, rng) * np.exp(-t * (12 if open_ else 90))).astype(np.float32)


def snare(rng, sr=SR):
    n = int(0.18 * sr)
    t = np.arange(n, dtype=np.float32) / sr
    nz = noise(n, rng) * np.exp(-t * 16)
    bd = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30) * 0.5
    return (nz + bd).astype(np.float32)


def cowbell(rng, note=None, sr=SR):
    n = int(0.5 * sr)
    t = np.arange(n, dtype=np.float32) / sr
    if note is None:
        f1 = float(rng.choice([540, 560, 580]))
    else:
        f1 = midi(note)
    f2 = f1 * 1.48
    sig = (np.sign(np.sin(2 * np.pi * f1 * t)) + np.sign(np.sin(2 * np.pi * f2 * t))) * 0.5
    return (sig * np.exp(-t * 6.5)).astype(np.float32)


def sub808(note, dur, sr=SR):
    n = int(dur * sr)
    t = np.arange(n, dtype=np.float32) / sr
    f = midi(note)
    sig = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1.0, t / 0.008) * np.exp(-t * (2.0 / max(dur, 0.4)))
    return (sig * env).astype(np.float32)

# ---------------------------------------------------------------- melodic

def pluck(note, sr=SR):
    n = int(0.55 * sr)
    f = midi(note)
    sig = osc("saw", f, n) * 0.5 + osc("square", f * 2, n) * 0.16
    return (sig * adsr(n, 0.003, 0.16, 0.15, 0.2)).astype(np.float32)


def piano(note, sr=SR):
    n = int(1.4 * sr)
    f = midi(note)
    t = np.arange(n, dtype=np.float32) / sr
    sig = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t)
           + 0.22 * np.sin(6 * np.pi * f * t))
    env = np.minimum(1.0, t / 0.004) * np.exp(-t * 2.4)
    return (sig * env).astype(np.float32)


def pad(notes, dur, sr=SR, swell=0.35):
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    for note in notes:
        f = midi(note)
        for det in (-0.07, 0.0, 0.06):
            out += osc("saw", f * (1 + det / 100), n) * 0.33
    e = adsr(n, swell, 0.3, 0.7, min(0.6, dur * 0.3))
    return (out * e * 0.12).astype(np.float32)

# ------------------------------------------------------------------ mixing

class Mix:
    def __init__(self, n):
        self.n = n
        self.buf = np.zeros(n, dtype=np.float32)

    def add(self, sig, at, gain=1.0):
        at = int(at)
        if at >= self.n or at + len(sig) <= 0:
            return
        src0 = 0
        if at < 0:                       # pre-roll jitter before t=0: clip the head
            src0 = -at
            at = 0
        end = min(self.n, at + len(sig) - src0)
        self.buf[at:end] += (sig[src0: src0 + end - at] * gain).astype(np.float32)


def sonic_logo(sr=SR):
    """🔔 The Nix Speech station chime — 0.75 s, descending bell motif + sub
    tick. Played over the head of EVERY master (engine & queue alike) and at
    every short's loop point. Deterministic: same notes, same gain, every
    episode — that's what makes it a logo. Kill-switch: CHIME_OFF=1."""
    n = int(0.75 * sr)
    seg = np.zeros(n, dtype=np.float32)
    for note, at, amp in ((93, 0.00, 0.30), (88, 0.14, 0.26),
                          (81, 0.30, 0.22), (76, 0.46, 0.18)):
        b = bell(note, 0.40, sr) * amp
        s = int(at * sr)
        m = min(len(b), n - s)
        seg[s:s + m] += b[:m]
    th = bell(52, 0.18, sr) * 0.16                 # sub 'thup' under the head
    seg[:min(len(th), n)] += th[:n]
    return np.clip(seg, -0.9, 0.9)


def mix_logo(path: Path, sr=SR):
    """Stamp the station chime onto an EXISTING master (queue songs skip
    master(); the chime still has to open them)."""
    import os as _os
    if _os.environ.get("CHIME_OFF", "") == "1":
        return path
    with wave.open(str(path), "rb") as w:
        n, sw, fs = w.getnframes(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw != 2:
        return path
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if fs != sr:                                   # queue wavs arrive 44.1k
        m = max(sr, int(len(x) * sr / fs))
        x = np.interp(np.linspace(0, len(x) - 1, m),
                      np.arange(len(x)), x).astype(np.float32)
    logo = sonic_logo(sr)
    m = min(len(logo), len(x))
    x[:m] = np.clip(x[:m] + logo, -0.99, 0.99)
    return write_wav(path, x, sr)


def master(bus, fade_s=3.0, sr=SR):
    x = np.tanh(bus * 1.15).astype(np.float32)
    peak = max(1e-6, float(np.max(np.abs(x))))
    x = x / peak * 0.92
    f = int(fade_s * sr)
    if len(x) > 2 * f:
        x[:f] *= np.linspace(0, 1, f, dtype=np.float32)
        x[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    import os as _os
    if _os.environ.get("CHIME_OFF", "") != "1":
        logo = sonic_logo(sr)
        m = min(len(logo), len(x))
        x[:m] = np.clip(x[:m] + logo, -0.99, 0.99)
    return x


# ------------------------------------------------------------------
# human-voice layer — formant vox chops (phonk's ghost "singer") 🎤
# Synthesized vowel-ish voice: the engine's own tracks stop sounding
# 100% robotic WITHOUT any samples. Full sung words come from the
# free space; this is the offline engine's human seasoning.
# ------------------------------------------------------------------
_VOWELS = {"a": (730, 1090), "e": (530, 1840), "i": (270, 2290),
           "o": (570, 840), "u": (300, 870)}


def _bq(x, freq, q, sr=SR):
    """RBJ bandpass biquad (zero-DC) — one vocal-tract resonance."""
    w = 2 * np.pi * float(freq) / sr
    alpha = np.sin(w) / (2 * q)
    b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * np.cos(w), 1 - alpha
    y = np.empty_like(x)
    z1 = z2 = 0.0
    for i in range(len(x)):
        xs = x[i]
        ys = (b0 / a0) * xs + z1
        z1 = (b1 / a0) * xs - (a1 / a0) * ys + z2
        z2 = (b2 / a0) * xs - (a2 / a0) * ys
        y[i] = ys
    return y


def vox_chop(rng, note: float, dur: float, vowel=("a", "e"), sr=SR):
    """One sung vowel-chop: saw voice + vibrato through morphing formants."""
    n = max(64, int(dur * sr))
    f0 = midi(note)
    t = np.arange(n, dtype=np.float32) / sr
    vib = 1.0 + 0.006 * np.sin(2 * np.pi * 5.2 * t)       # human wobble
    ph = np.cumsum(f0 * vib / sr) % 1.0
    saw = 2.0 * ph - 1.0
    sine = np.sin(2 * np.pi * ph)
    src = (saw * 0.7 + sine * 0.3 +
           rng.standard_normal(n).astype(np.float32) * 0.04)
    out = np.zeros(n, dtype=np.float32)
    per = max(1, n // len(vowel))
    for i, v in enumerate(vowel):
        f1, f2 = _VOWELS.get(v, _VOWELS["a"])
        sl = slice(i * per, min(n, (i + 1) * per))
        out[sl] = _bq(src[sl], f1, 7) * 1.6 + _bq(src[sl], f2, 9)
    out = out - lowpass(out, 201)                          # crud high-pass
    out *= adsr(n, 0.015, 0.05, 0.75, 0.06)                # sung envelope
    peak = float(np.max(np.abs(out)))
    return (out / peak * 0.9) if peak > 1e-6 else out


def walk(rng, scale, n, span=7):
    """Random-walk melody over a scale (semitone offsets)."""
    seq, idx = [], 0
    for _ in range(n):
        idx = int(np.clip(idx + rng.choice([-2, -1, -1, 0, 1, 1, 2]), -span, span))
        seq.append(scale[idx % len(scale)] + 12 * (idx // len(scale)))
    return seq


def _bars_for_target(target_s, bpm):
    return max(24, int(round(target_s * bpm / 240.0)))


def _hook_map(bars, intro_bars, outro_bars):
    hook = np.zeros(bars, dtype=bool)
    for i in range(intro_bars, bars - outro_bars):
        block = (i - intro_bars) // 8
        hook[i] = block % 2 == 1
    return hook

# ------------------------------------------------------------------ genres

def drift_phonk(rng, target_s):
    bpm = int(rng.integers(126, 142))
    root = int(rng.choice([41, 43, 45, 47, 48]))
    bars = _bars_for_target(target_s, bpm)
    bar_n = int(4 * 60 / bpm * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b, outro_b = max(2, bars // 8), max(2, bars // 10)
    hook = _hook_map(bars, intro_b, outro_b)
    build_open, build_last = _build_map(hook, intro_b)
    prog = [0, -4, -7, -5]
    melody = walk(rng, MINOR_PENT, bars * 8)

    drums, music, lead, vox, fx = (Mix(total) for _ in range(5))
    kicks, events = [], {"risers": 0, "rolls": 0, "crashes": 0}
    vox_shapes = [("a", "e"), ("o", "a"), ("u", "i"), ("e", "a")]
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        breath = build_last[b]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 4 * 60 / bpm, swell=0.6),
                  base, gain=0.5)
        if hook[b] and b % 2 == 0:                       # ghost singer answers
            note = root + 12 + melody[(b * 8) % len(melody)]
            vox.add(vox_chop(rng, note, 1.8 * 60 / bpm,
                             vowel=vox_shapes[(b // 2) % len(vox_shapes)]),
                    base, gain=0.55)
            vox.add(vox_chop(rng, note - 3, 0.9 * 60 / bpm,
                             vowel=vox_shapes[(b // 2 + 1) % len(vox_shapes)]),
                    base + bar_n // 2, gain=0.4)
        for s in range(16):
            at = base + s * step
            jd = jit(rng)
            if b >= intro_b:
                if s in (0, 7, 11) and not (breath and s == 11):
                    drums.add(kick(rng), at + jd, gain=human(rng, 0.95, 0.08))
                    kicks.append(at)
                if s == 8 and not breath:
                    drums.add(snare(rng), at + jd, gain=human(rng, 0.55, 0.15))
                if s in (0, 10) and not (breath and s == 10):
                    music.add(sub808(croot - 12, 1.5 * 60 / bpm), at + jit(rng, ms=4),
                              gain=human(rng, 0.75, 0.1))
            if s % 2 == 0 and b >= max(1, intro_b // 2):
                accent = 0.17 if s % 4 == 0 else 0.11
                drums.add(hat(rng, open_=(s == 14)), at + jd,
                          gain=human(rng, accent, 0.22))
            if hook[b] and s % 2 == 0:
                note = root + 24 + melody[(b * 8 + s // 2) % len(melody)]
                lead.add(cowbell(rng, note=note), at + jit(rng, ms=5),
                         gain=human(rng, 0.26, 0.2))
            elif not hook[b] and b >= intro_b and b % 2 == 0 and s % 4 == 2:
                arp = [0, 3, 7, 12]
                lead.add(pluck(croot + 12 + arp[(s // 4) % 4]), at,
                         gain=human(rng, 0.15, 0.2))
        if build_open[b]:
            fx.add(riser(rng, 2 * 60 / bpm * 4), base, gain=0.7)
            events["risers"] += 1
        if build_last[b]:
            fx.add(snare_roll(rng, 4 * 60 / bpm), base, gain=0.9)
            events["rolls"] += 1
        if b > 0 and hook[b] and not hook[b - 1]:
            fx.add(crash(rng), base, gain=0.55)
            events["crashes"] += 1

    lead.buf = chorus(lead.buf)
    lead.buf = echo(lead.buf, 0.75 * 60 / bpm)
    vox.buf = echo(vox.buf, 0.5 * 60 / bpm, gains=(0.28, 0.1))
    music.buf = sidechain(music.buf, kicks, SR, depth=0.5)
    lead.buf = sidechain(lead.buf, kicks, SR, depth=0.3, release=0.16)
    vox.buf = sidechain(vox.buf, kicks, SR, depth=0.3, release=0.16)
    out = master(drums.buf * 0.9 + music.buf + lead.buf * 0.85 + vox.buf * 0.8 + fx.buf)
    return out, {"genre": "drift phonk", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR,
                 "events": events}


def deep_pop(rng, target_s):
    bpm = int(rng.integers(98, 113))
    root = int(rng.choice([45, 47, 48, 50]))
    bars = _bars_for_target(target_s, bpm)
    bar_n = int(4 * 60 / bpm * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b = 4
    prog = [0, -4, -7, -2]
    phrase = walk(rng, [0, 2, 3, 7, 8], bars * 4, span=6)
    arp = [0, 3, 7, 10, 12, 10, 7, 3]

    drums, music, lead = Mix(total), Mix(total), Mix(total)
    kicks = []
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 4 * 60 / bpm, swell=0.9),
                  base, gain=0.45)
        for s in range(16):
            at = base + s * step
            if b >= intro_b and s % 4 == 0:
                drums.add(lowpass(kick(rng)), at + jit(rng), gain=human(rng, 0.7, 0.08))
                kicks.append(at)
            if s % 4 == 2:
                drums.add(hat(rng, open_=(s == 14)), at + jit(rng),
                          gain=human(rng, 0.13, 0.22))
            if b >= intro_b * 2 and s == 8:
                drums.add(snare(rng), at + jit(rng), gain=human(rng, 0.4, 0.15))
            if s in (0, 10):
                music.add(sub808(croot - 12 + (7 if s == 10 else 0), 1.2 * 60 / bpm),
                          at + jit(rng, ms=4), gain=human(rng, 0.7, 0.1))
            if b >= intro_b and s % 2 == 0:
                lead.add(pluck(croot + 12 + arp[(s // 2) % 8]), at + jit(rng, ms=4),
                         gain=human(rng, 0.13, 0.2))
        if b >= intro_b * 2 and b % 2 == 0:
            for k, st in enumerate((0, 6, 10)):
                note = root + 12 + phrase[(b * 2 + k) % len(phrase)]
                lead.add(piano(note), base + st * step + jit(rng, ms=5),
                         gain=human(rng, 0.5, 0.15))

    lead.buf = chorus(lead.buf)
    lead.buf = echo(lead.buf, 0.75 * 60 / bpm, gains=(0.4, 0.2))
    music.buf = sidechain(music.buf, kicks, SR, depth=0.45)
    lead.buf = sidechain(lead.buf, kicks, SR, depth=0.25, release=0.16)
    out = master(drums.buf + music.buf + lead.buf * 0.8)
    return out, {"genre": "deep dark-pop", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR}


def dark_ambient(rng, target_s):
    bpm = int(rng.integers(70, 84))
    root = int(rng.choice([38, 40, 41, 43]))
    bars = _bars_for_target(target_s, bpm)
    bar_n = int(4 * 60 / bpm * SR)
    total = bars * bar_n
    prog = [0, -2, -4, -7]
    t = np.arange(total, dtype=np.float32) / SR

    music, lead = Mix(total), Mix(total)
    drone = (np.sin(2 * np.pi * midi(root - 12) * t)
             + 0.6 * np.sin(2 * np.pi * midi(root - 7) * t))
    drone *= 0.13 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.04 * t))
    music.add(drone.astype(np.float32), 0)

    for b in range(0, bars, 2):
        croot = root + prog[(b // 2) % 4]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 2 * 4 * 60 / bpm, swell=1.4),
                  b * bar_n, gain=0.55)
        if rng.random() < 0.6:
            for _ in range(int(rng.integers(1, 3))):
                note = root + 24 + int(rng.choice([0, 3, 5, 7, 10, 12]))
                at = (b + rng.random()) * bar_n
                lead.add(piano(note), int(at), gain=0.4)

    rain = lowpass(noise(total, rng), window=1601)
    rain *= (0.05 + 0.04 * np.sin(2 * np.pi * 0.06 * t)).astype(np.float32)

    lead.buf = echo(lead.buf, 0.9, gains=(0.45, 0.22))
    out = master(music.buf + rain + lead.buf, fade_s=6.0)
    return out, {"genre": "dark ambient", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR}


def lofi(rng, target_s):
    """Golden-hour lo-fi: swung hats, vinyl crackle, rhodes-y chords."""
    bpm = int(rng.integers(72, 87))
    root = int(rng.choice([40, 41, 43, 45, 47]))
    bars = _bars_for_target(target_s, bpm)
    bar_n = int(4 * 60 / bpm * SR)
    step = bar_n // 16
    total = bars * bar_n
    swing = int(0.09 * (60 / bpm) * SR)
    prog = [0, -3, -7, -5]
    melody = walk(rng, [0, 2, 3, 7, 10], bars * 4, span=6)

    drums, music, lead = Mix(total), Mix(total), Mix(total)
    kicks = []
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        # rhodes-ish min7(+9) chord stab
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10, 14)],
                      4 * 60 / bpm, swell=0.25), base, gain=0.62)
        music.add(sub808(croot - 12, 2 * 60 / bpm), base, gain=human(rng, 0.55, 0.08))
        for s in range(16):
            at = base + s * step + (swing if s % 2 else 0)
            if s in (0, 8):
                drums.add(lowpass(kick(rng), 1201), at + jit(rng, ms=5),
                          gain=human(rng, 0.72, 0.08))
                kicks.append(base + s * step)
            if s == 8:
                drums.add(lowpass(snare(rng), 1601), at + jit(rng, ms=5),
                          gain=human(rng, 0.42, 0.15))
            if s % 2 == 0:
                drums.add(hat(rng, open_=(s == 14)), at + jit(rng, ms=8),
                          gain=human(rng, 0.10, 0.25))
        if b % 2 == 1:
            for st in (2, 11):
                if rng.random() < 0.7:
                    note = root + 24 + melody[(b * 2 + st) % len(melody)]
                    lead.add(piano(note), base + st * step + jit(rng, ms=9),
                             gain=human(rng, 0.34, 0.2))

    # vinyl crackle: noise bed + random pops
    crackle = rng.standard_normal(total).astype(np.float32) * 0.006
    pops = np.zeros(total, dtype=np.float32)
    for i in rng.integers(0, total - 900, size=int(total / SR * 1.1)):
        pops[i] = rng.uniform(0.4, 1.0) * rng.choice([-1.0, 1.0])
    crackle += lowpass(pops, 61) * 0.5

    lead.buf = echo(lead.buf, 0.75 * 60 / bpm, gains=(0.35, 0.18))
    music.buf = sidechain(music.buf, kicks, SR, depth=0.35, release=0.3)
    out = master(drums.buf + music.buf + lead.buf * 0.8 + crackle)
    return out, {"genre": "lo-fi", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR}


def baroque_waltz(rng, target_s):
    """Amber vintage waltz — 6/8 lilt, harpsichord arps, warm organ."""
    tempo = int(rng.integers(170, 191))          # eighth-note pulse
    step = int(60.0 / tempo * SR)                # one eighth
    bar_n = 6 * step                             # 6/8 bar
    root = int(rng.choice([45, 47, 48, 50, 52]))
    bars = max(24, int(round(target_s / (6 * 60.0 / tempo))))
    total = bars * bar_n
    prog = [0, -4, -7, -3]
    melody = walk(rng, [0, 2, 3, 7, 8], bars * 3, span=6)

    drums, music, lead = Mix(total), Mix(total), Mix(total)
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[b % 4]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 6 * 60.0 / tempo,
                      swell=0.45), base, gain=0.42)
        for s in range(6):
            at = base + s * step
            # harpsichord arp — up-down cycling chord tones, accents on 0 & 3
            tones = [0, 3, 7, 12, 7, 3]
            g = 0.20 if s in (0, 3) else 0.13
            music.add(pluck(croot + 12 + tones[s]), at, gain=g)
            if s in (0, 3):
                music.add(lowpass(sub808(croot - 12, 0.8), 601), at, gain=0.55)
            if s == 0:
                drums.add(lowpass(kick(rng), 801), at, gain=0.6)
            if s == 3:
                drums.add(hat(rng, open_=True), at, gain=0.28)
            else:
                drums.add(hat(rng), at, gain=0.045)
        if b % 2 == 1:
            for s in (0, 2, 3, 5):
                note = root + 24 + melody[(b * 4 + s) % len(melody)]
                sig = osc("sine", midi(note), int(1.0 * SR)) * 0.7 + \
                      osc("tri", midi(note), int(1.0 * SR)) * 0.3
                lead.add(sig * adsr(int(1.0 * SR), 0.03, 0.2, 0.6, 0.3),
                         base + s * step, gain=0.30)

    lead.buf = echo(lead.buf, 0.45, gains=(0.3, 0.15))
    out = master(drums.buf + music.buf + lead.buf * 0.85, fade_s=4.0)
    return out, {"genre": "baroque waltz", "bpm": tempo,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR}


def disco_house(rng, target_s):
    """Saturday-night groove — humanized four-floor, sidechain pump, real builds."""
    bpm = int(rng.integers(118, 125))
    root = int(rng.choice([41, 43, 45, 46, 48]))
    bars = _bars_for_target(target_s, bpm)
    bar_s = 4 * 60.0 / bpm
    bar_n = int(bar_s * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b = max(2, bars // 8)
    hook = _hook_map(bars, intro_b, max(2, bars // 10))
    build_open, build_last = _build_map(hook, intro_b)
    prog = [0, -2, -4, -2]
    riff_a = walk(rng, MINOR_PENT, 18, span=6)      # two riffs → hooks converse,
    riff_b = walk(rng, MINOR_PENT, 18, span=6)      # not one 4-bar loop on repeat
    bass_steps = {0: 0, 3: 12, 6: 0, 8: 7, 11: 0, 14: 12}
    sw = int(0.07 * step)                            # house swing on odd 16ths
    vox_shapes = [("a", "e"), ("o", "a"), ("u", "i"), ("e", "a")]

    drums, music, lead, vox, fx = (Mix(total) for _ in range(5))
    kicks, events = [], {"risers": 0, "rolls": 0, "crashes": 0}
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        riff = riff_a if ((max(0, b - intro_b) // 8) % 2 == 0) else riff_b
        breath = build_last[b]                       # kick/bass step out before drop
        for s in range(16):
            at = base + s * step + (sw if s % 2 else 0)
            jd = jit(rng)
            if b >= intro_b and s % 4 == 0 and not (breath and s >= 12):
                drums.add(kick(rng), at + jd, gain=human(rng, 0.85, 0.08))
                kicks.append(at)
            if b >= intro_b and s in (4, 12) and not breath:
                drums.add(snare(rng), at + jd, gain=human(rng, 0.5, 0.15))
            if s % 4 == 2:
                drums.add(hat(rng, open_=True), at + int(jd * 1.5),
                          gain=human(rng, 0.15, 0.2))
            elif s % 2 == 0 and not breath:
                accent = 0.10 if s in (0, 8) else 0.045
                drums.add(hat(rng), at + jd, gain=human(rng, accent, 0.25))
            if s in bass_steps and b >= intro_b and not (breath and s >= 12):
                off = bass_steps[s]
                music.add(sub808(croot - 12 + off, 0.32), at + jit(rng, ms=4),
                          gain=human(rng, 0.5, 0.12))
                music.add(lowpass(pluck(croot + off), 1001), at,
                          gain=human(rng, 0.16, 0.2))
            if s in (6, 14) and b % 2 == 1:
                for tv in (0, 3, 7, 14):
                    music.add(pluck(croot + 12 + tv), at + jit(rng, ms=4),
                              gain=human(rng, 0.07, 0.25))
            if hook[b] and s in (0, 3, 6, 10, 12):
                note = root + 24 + riff[(b * 5 + s) % len(riff)]
                vel = 0.30 if s in (0, 6) else 0.22
                lead.add(piano(note), at + jit(rng, ms=5), gain=human(rng, vel, 0.18))
        # ghost singer sings a PHRASE on the hook — call & answer, no stray shouts
        if hook[b] and b % 2 == 0:
            for k, s in enumerate((0, 6)):
                note = root + 12 + riff[(b * 5 + s) % len(riff)]
                vox.add(vox_chop(rng, note, 0.45 * 60 / bpm,
                                 vowel=vox_shapes[(b // 2 + k) % 4]),
                        base + s * step, gain=0.5)
        elif hook[b] and b % 2 == 1:
            note = root + 12 + riff[(b * 5 + 10) % len(riff)]
            vox.add(vox_chop(rng, note - 3, 0.9 * 60 / bpm, vowel=("e", "a")),
                    base + 8 * step, gain=0.42)
        # tension & release machinery
        if build_open[b]:
            fx.add(riser(rng, 2 * bar_s), base, gain=0.75)
            events["risers"] += 1
        if build_last[b]:
            fx.add(snare_roll(rng, bar_s), base, gain=1.0)
            events["rolls"] += 1
        if b > 0 and hook[b] and not hook[b - 1]:
            fx.add(crash(rng), base, gain=0.6)
            events["crashes"] += 1

    # movement: chorus + hook-synced filter sweep + tremolo shimmer on the lead
    lead.buf = chorus(lead.buf)
    t_bars = np.arange(len(lead.buf), dtype=np.float32) / SR / bar_s
    cut = 1800.0 * (7000.0 / 1800.0) ** (0.5 - 0.5 * np.cos(2 * np.pi * t_bars / 8.0))
    lead.buf = sweep_filter(lead.buf, SR, cut)
    trem = (0.9 + 0.1 * np.sin(2 * np.pi * 5.0 *
            np.arange(len(lead.buf), dtype=np.float32) / SR)).astype(np.float32)
    lead.buf = (lead.buf * trem).astype(np.float32)

    lead.buf = echo(lead.buf, 0.375 * 60 / bpm * 2, gains=(0.35, 0.18))
    vox.buf = echo(vox.buf, 0.5 * 60 / bpm, gains=(0.25, 0.1))

    # the pocket: bass & melody duck for every kick → ONE owner of 50-60 Hz
    music.buf = sidechain(music.buf, kicks, SR, depth=0.55)
    lead.buf = sidechain(lead.buf, kicks, SR, depth=0.30, release=0.16)
    vox.buf = sidechain(vox.buf, kicks, SR, depth=0.30, release=0.16)

    out = master(drums.buf * 0.95 + music.buf + lead.buf + vox.buf * 0.85 + fx.buf)
    return out, {"genre": "disco house", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR,
                 "events": events}


def skyline_anthem(rng, target_s):
    """Bright-side anthem — folk-EDM lift, festival build, hands-up hook."""
    bpm = int(rng.integers(126, 132))
    root = int(rng.choice([45, 47, 48, 50, 52]))
    bars = _bars_for_target(target_s, bpm)
    bar_s = 4 * 60.0 / bpm
    bar_n = int(bar_s * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b = max(2, bars // 8)
    hook = _hook_map(bars, intro_b, max(2, bars // 10))
    build_open, build_last = _build_map(hook, intro_b)
    prog = [0, 7, 9, 5]                          # I V vi IV — the anthem road
    hook_mel = walk(rng, MAJOR_PENT, 18, span=6)
    arp = [0, 4, 7, 12, 7, 4]

    drums, music, lead, vox, fx = (Mix(total) for _ in range(5))
    kicks, events = [], {"risers": 0, "rolls": 0, "crashes": 0}
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        breath = build_last[b]
        music.add(pad([croot + i for i in (0, 4, 7, 14)], 4 * 60 / bpm,
                      swell=0.5), base, gain=0.4)
        for s in range(16):
            at = base + s * step
            jd = jit(rng)
            if b >= intro_b and s % 4 == 0 and not (breath and s >= 12):
                drums.add(kick(rng), at + jd, gain=human(rng, 0.9, 0.08))
                kicks.append(at)
            if b >= intro_b and s in (4, 12) and not breath:
                drums.add(clap(rng), at + jd, gain=human(rng, 0.5, 0.15))
            if s % 4 == 2 and not breath:
                drums.add(hat(rng, open_=True), at + jd,
                          gain=human(rng, 0.14, 0.2))
            elif s % 2 == 0 and not breath:
                drums.add(hat(rng), at + jd,
                          gain=human(rng, 0.10 if s % 4 == 0 else 0.05, 0.25))
            if s in (0, 8) and b >= intro_b and not (breath and s == 8):
                music.add(sub808(croot - 12 + (7 if s == 8 else 0),
                                 1.4 * 60 / bpm), at + jit(rng, ms=4),
                          gain=human(rng, 0.7, 0.1))
            if hook[b] and s in (0, 6, 10, 12):      # piano anthem stabs
                for iv in (0, 4, 7, 12):
                    lead.add(piano(croot + 12 + iv), at + jit(rng, ms=5),
                             gain=human(rng, 0.30, 0.15))
            elif b >= intro_b and s % 2 == 1:        # folk arp tickles verses
                lead.add(pluck(croot + 12 + arp[(s % 6)]), at + jit(rng, ms=5),
                         gain=human(rng, 0.13, 0.2))
        if hook[b]:                                  # the whoa-oh squad
            if b % 2 == 0:
                for k, s in enumerate((0, 8)):
                    note = root + 12 + hook_mel[(b * 4 + s) % len(hook_mel)]
                    vox.add(vox_chop(rng, note, 0.9 * 60 / bpm,
                                     vowel=("o", "a") if k == 0 else ("a", "o")),
                            base + s * step, gain=0.5)
            else:
                note = root + 12 + hook_mel[(b * 4 + 3) % len(hook_mel)]
                vox.add(vox_chop(rng, note, 1.4 * 60 / bpm, vowel=("o",)),
                        base + 2 * step, gain=0.4)
        if build_open[b]:
            fx.add(riser(rng, 2 * bar_s), base, gain=0.8)
            events["risers"] += 1
        if build_last[b]:
            fx.add(snare_roll(rng, bar_s), base, gain=1.0)
            events["rolls"] += 1
        if b > 0 and hook[b] and not hook[b - 1]:
            fx.add(crash(rng), base, gain=0.6)
            events["crashes"] += 1

    lead.buf = chorus(lead.buf)
    t_bars = np.arange(len(lead.buf), dtype=np.float32) / SR / bar_s
    cut = 2000.0 * (7500.0 / 2000.0) ** (0.5 - 0.5 *
                                         np.cos(2 * np.pi * t_bars / 8.0))
    lead.buf = sweep_filter(lead.buf, SR, cut)
    lead.buf = echo(lead.buf, 0.375 * 60 / bpm * 2, gains=(0.35, 0.18))
    vox.buf = echo(vox.buf, 0.5 * 60 / bpm, gains=(0.28, 0.12))
    music.buf = sidechain(music.buf, kicks, SR, depth=0.5)
    lead.buf = sidechain(lead.buf, kicks, SR, depth=0.3, release=0.16)
    vox.buf = sidechain(vox.buf, kicks, SR, depth=0.3, release=0.16)
    out = master(drums.buf * 0.95 + music.buf + lead.buf + vox.buf * 0.85
                 + fx.buf)
    return out, {"genre": "skyline anthem", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} major",
                 "duration_s": total / SR, "events": events}


def villain_pop(rng, target_s):
    """Villain pop — music-box menace over halftime 808s. Smiles, with teeth."""
    bpm = int(rng.integers(140, 150))
    root = int(rng.choice([38, 40, 41, 43, 44]))
    bars = _bars_for_target(target_s, bpm)
    bar_s = 4 * 60.0 / bpm
    bar_n = int(bar_s * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b = max(2, bars // 9)
    hook = _hook_map(bars, intro_b, max(2, bars // 10))
    build_open, build_last = _build_map(hook, intro_b)
    prog = [0, -4, -2, -6]
    riff = walk(rng, MINOR_PENT, 18, span=6)

    drums, music, lead, vox, fx = (Mix(total) for _ in range(5))
    kicks, events = [], {"risers": 0, "rolls": 0, "crashes": 0}
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        breath = build_last[b]
        # slow tense pad, barely breathing
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 4 * 60 / bpm,
                      swell=1.0), base, gain=0.32)
        for s in range(16):
            at = base + s * step
            jd = jit(rng)
            if b >= intro_b and s in (0, 10) and not (breath and s == 10):
                drums.add(lowpass(kick(rng), 901), at + jd,
                          gain=human(rng, 0.9, 0.08))
                kicks.append(at)
            if b >= intro_b and s == 8 and not breath:
                drums.add(snare(rng), at + jd, gain=human(rng, 0.55, 0.15))
            if not breath and (
                    s % 2 == 0 or (s % 4 == 3 and rng.random() < 0.7)):
                g = 0.085 if s % 4 == 0 else 0.05
                drums.add(hat(rng, open_=(s == 14)), at + jd,
                          gain=human(rng, g, 0.25))
            if s % 4 == 3 and rng.random() < 0.35:   # triplet flurry
                for k in range(3):
                    drums.add(hat(rng), at + int(k * step / 3),
                              gain=0.028 + 0.01 * k)
            if s == 0 and b >= intro_b and not breath:
                music.add(sub808(croot - 12, 2.2 * 60 / bpm), at,
                          gain=human(rng, 0.8, 0.08))
            if s == 10 and b >= intro_b and not breath:
                music.add(sub808(croot - 12 + (5 if rng.random() < 0.5 else 7),
                                 1.1 * 60 / bpm), at, gain=human(rng, 0.65, 0.1))
            if hook[b] and s in (0, 3, 6, 8, 11, 14):   # the music box confesses
                note = root + 24 + riff[(b * 5 + s) % len(riff)]
                lead.add(bell(note), at + jit(rng, ms=5),
                         gain=human(rng, 0.34, 0.18))
            elif not hook[b] and b >= intro_b and b % 2 == 0 and s in (6, 14):
                lead.add(bell(croot + 24), at, gain=human(rng, 0.2, 0.2))
        if hook[b] and b % 2 == 1:                   # villain's sighs
            vox.add(vox_chop(rng, root + 12 + riff[(b * 5) % len(riff)],
                             1.2 * 60 / bpm, vowel=("o", "a")),
                    base + 12 * step, gain=0.42)
            vox.add(vox_chop(rng, root + 12, 0.5 * 60 / bpm, vowel=("u",)),
                    base + 15 * step, gain=0.3)
        if build_open[b]:
            fx.add(riser(rng, 2 * bar_s), base, gain=0.7)
            events["risers"] += 1
        if build_last[b]:
            fx.add(snare_roll(rng, bar_s), base, gain=0.85)
            events["rolls"] += 1
        if b > 0 and hook[b] and not hook[b - 1]:
            fx.add(crash(rng), base, gain=0.5)
            events["crashes"] += 1

    lead.buf = chorus(lead.buf, mix=0.3)
    lead.buf = echo(lead.buf, 0.75 * 60 / bpm, gains=(0.3, 0.15))
    vox.buf = echo(vox.buf, 0.5 * 60 / bpm, gains=(0.25, 0.1))
    music.buf = sidechain(music.buf, kicks, SR, depth=0.5)
    lead.buf = sidechain(lead.buf, kicks, SR, depth=0.3, release=0.16)
    vox.buf = sidechain(vox.buf, kicks, SR, depth=0.3, release=0.16)
    out = master(drums.buf * 0.9 + music.buf + lead.buf * 0.9 + vox.buf * 0.8
                 + fx.buf)
    return out, {"genre": "villain pop", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor",
                 "duration_s": total / SR, "events": events}


def orbit_trap(rng, target_s):
    """Orbit trap — confident bounce, sliding 808s, brass in zero gravity."""
    bpm = int(rng.integers(146, 153))
    root = int(rng.choice([41, 43, 44, 46]))
    bars = _bars_for_target(target_s, bpm)
    bar_s = 4 * 60.0 / bpm
    bar_n = int(bar_s * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b = max(2, bars // 9)
    hook = _hook_map(bars, intro_b, max(2, bars // 10))
    build_open, build_last = _build_map(hook, intro_b)
    prog = [0, -2, -4, -7]
    riff = walk(rng, MINOR_PENT, 18, span=6)

    drums, music, lead, vox, fx = (Mix(total) for _ in range(5))
    kicks, events = [], {"risers": 0, "rolls": 0, "crashes": 0}
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        breath = build_last[b]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 4 * 60 / bpm,
                      swell=0.8), base, gain=0.3)
        for s in range(16):
            at = base + s * step
            jd = jit(rng)
            if b >= intro_b and s in (0, 7, 10) and not (breath and s >= 10):
                drums.add(kick(rng), at + jd, gain=human(rng, 0.95, 0.08))
                kicks.append(at)
            if b >= intro_b and s == 8 and not breath:
                drums.add(snare(rng), at + jd, gain=human(rng, 0.55, 0.15))
            if s % 2 == 0 and not breath:            # rolling hats
                g = 0.075 if s % 4 == 0 else 0.045
                drums.add(hat(rng, open_=(s == 14)), at + jd,
                          gain=human(rng, g, 0.25))
            if s == 14 and b >= intro_b and b % 2 == 1 and not breath:
                for k in range(4):                   # 32nd flick into the bar
                    drums.add(hat(rng), at + int(k * step / 4),
                              gain=0.03 + 0.012 * k)
            if s == 0 and b >= intro_b and not breath:
                music.add(sub808(croot - 12, 2.4 * 60 / bpm), at,
                          gain=human(rng, 0.8, 0.08))
            if s == 10 and b >= intro_b and not breath:
                music.add(sub808(croot - 12 + (7 if rng.random() < 0.5 else 3),
                                 0.9 * 60 / bpm), at, gain=human(rng, 0.7, 0.1))
            if hook[b] and s in (0, 6, 12):          # brass enters orbit
                tones = [0, 3, 7, 12]
                chord = [croot + 12 + tones[(s // 6 + i) % 4] for i in range(3)]
                lead.add(stab(chord, 0.3), at + jit(rng, ms=4),
                         gain=human(rng, 0.5, 0.15))
            elif not hook[b] and s == 12 and b >= intro_b and rng.random() < 0.6:
                note = root + 24 + riff[(b * 3 + s) % len(riff)]
                lead.add(bell(note, 0.5), at, gain=human(rng, 0.16, 0.2))
        if hook[b] and b % 2 == 0:                   # cool guy call-answers
            vox.add(vox_chop(rng, root + 12 + riff[(b * 5) % len(riff)],
                             0.6 * 60 / bpm, vowel=("a", "o")),
                    base + 4 * step, gain=0.45)
            vox.add(vox_chop(rng, root + 12 + 7, 0.5 * 60 / bpm, vowel=("a",)),
                    base + 13 * step, gain=0.32)
        if build_open[b]:
            fx.add(riser(rng, 2 * bar_s), base, gain=0.6)
            events["risers"] += 1
        if build_last[b]:
            fx.add(snare_roll(rng, bar_s), base, gain=0.8)
            events["rolls"] += 1
        if b > 0 and hook[b] and not hook[b - 1]:
            fx.add(crash(rng), base, gain=0.45)
            events["crashes"] += 1

    lead.buf = chorus(lead.buf, mix=0.3)
    lead.buf = echo(lead.buf, 0.375 * 60 / bpm, gains=(0.3, 0.14))
    vox.buf = echo(vox.buf, 0.5 * 60 / bpm, gains=(0.22, 0.09))
    music.buf = sidechain(music.buf, kicks, SR, depth=0.5)
    lead.buf = sidechain(lead.buf, kicks, SR, depth=0.3, release=0.16)
    vox.buf = sidechain(vox.buf, kicks, SR, depth=0.3, release=0.16)
    out = master(drums.buf * 0.92 + music.buf + lead.buf + vox.buf * 0.8
                 + fx.buf)
    return out, {"genre": "orbit trap", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor",
                 "duration_s": total / SR, "events": events}


GENRES = {"drift_phonk": drift_phonk, "deep_pop": deep_pop,
          "dark_ambient": dark_ambient, "lofi": lofi,
          "baroque_waltz": baroque_waltz, "disco_house": disco_house,
          "skyline_anthem": skyline_anthem, "villain_pop": villain_pop,
          "orbit_trap": orbit_trap}



def compose(genre: str, rng: np.random.Generator, target_s: float):
    # 🛡 v14: wheel now carries ACE-only vibes (chart_pop / melodic_trap /
    # summer_rap) — if every vocal lane misses and the engine takes over, a
    # missing engine mapping must NOT crash the run. Nearest-mood fallback.
    _ALIASES = {"chart_pop": "disco_house", "melodic_trap": "drift_phonk",
                "summer_rap": "lofi"}
    eng = GENRES.get(genre) or GENRES[_ALIASES.get(genre, "deep_pop")]
    return eng(rng, target_s)


def arrange_arc(x, bpm, sr=SR):
    """Give the mix a SONG-shaped energy arc (in-place-free, returns new array).

    Autopsy of early renders showed a 10x intro build… then ~2.5 min of
    perfectly flat RMS — a loop, not an arc. Real phonk/lofi tracks breathe:
      0-10%    intro (engines already ramp this)
      10-45%   main groove, untouched
      45-62%   BREAKDOWN: dip to 58% + 'underwater' low-pass blend
      62-96%   finale, lifted +8%
      96-100%  guaranteed outro fade (early renders ended abruptly)
    """
    n = len(x)
    if n < sr * 30:                      # too short to break down — leave it
        return x
    t = np.linspace(0.0, 1.0, n, endpoint=False, dtype=np.float32)
    knots_t = [0.00, 0.10, 0.45, 0.50, 0.62, 0.68, 0.96, 1.00]
    knots_g = [1.00, 1.00, 1.00, 0.58, 0.58, 1.08, 1.05, 0.00]
    g = np.interp(t, knots_t, knots_g).astype(np.float32)

    # underwater version: one FFT, smooth low-pass taper 900→1800 Hz
    spec = np.fft.rfft(x)
    taper = np.clip((1800.0 - np.fft.rfftfreq(n, 1.0 / sr)) / 900.0, 0, 1)
    x_lp = np.fft.irfft(spec * taper, n).astype(np.float32)

    # blend into the filtered copy only while dipped
    a = np.clip((1.0 - g) / 0.42, 0, 1).astype(np.float32) * 0.75
    return (x * g * (1 - a) + x_lp * g * a).astype(np.float32)


def write_wav(path: Path, x, sr=SR):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path

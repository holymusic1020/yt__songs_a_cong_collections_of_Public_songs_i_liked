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

# ------------------------------------------------------------------- drums

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
        if at >= self.n:
            return
        end = min(self.n, at + len(sig))
        self.buf[at:end] += (sig[: end - at] * gain).astype(np.float32)


def master(bus, fade_s=3.0, sr=SR):
    x = np.tanh(bus * 1.15).astype(np.float32)
    peak = max(1e-6, float(np.max(np.abs(x))))
    x = x / peak * 0.92
    f = int(fade_s * sr)
    if len(x) > 2 * f:
        x[:f] *= np.linspace(0, 1, f, dtype=np.float32)
        x[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return x


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
    prog = [0, -4, -7, -5]
    melody = walk(rng, MINOR_PENT, bars * 8)

    drums, music, lead = Mix(total), Mix(total), Mix(total)
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 4 * 60 / bpm, swell=0.6),
                  base, gain=0.5)
        for s in range(16):
            at = base + s * step
            if b >= intro_b:
                if s in (0, 7, 11):
                    drums.add(kick(rng), at, gain=0.95)
                if s == 8:
                    drums.add(snare(rng), at, gain=0.55)
                if s in (0, 10):
                    music.add(sub808(croot - 12, 1.5 * 60 / bpm), at, gain=0.75)
            if s % 2 == 0 and b >= max(1, intro_b // 2):
                drums.add(hat(rng, open_=(s == 14)), at,
                          gain=0.17 if s % 4 == 0 else 0.11)
            if hook[b] and s % 2 == 0:
                note = root + 24 + melody[(b * 8 + s // 2) % len(melody)]
                lead.add(cowbell(rng, note=note), at, gain=0.26)
            elif not hook[b] and b >= intro_b and b % 2 == 0 and s % 4 == 2:
                arp = [0, 3, 7, 12]
                lead.add(pluck(croot + 12 + arp[(s // 4) % 4]), at, gain=0.15)

    lead.buf = echo(lead.buf, 0.75 * 60 / bpm)
    out = master(drums.buf * 0.9 + music.buf + lead.buf * 0.85)
    return out, {"genre": "drift phonk", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR}


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
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10)], 4 * 60 / bpm, swell=0.9),
                  base, gain=0.45)
        for s in range(16):
            at = base + s * step
            if b >= intro_b and s % 4 == 0:
                drums.add(lowpass(kick(rng)), at, gain=0.7)
            if s % 4 == 2:
                drums.add(hat(rng, open_=(s == 14)), at, gain=0.13)
            if b >= intro_b * 2 and s == 8:
                drums.add(snare(rng), at, gain=0.4)
            if s in (0, 10):
                music.add(sub808(croot - 12 + (7 if s == 10 else 0), 1.2 * 60 / bpm),
                          at, gain=0.7)
            if b >= intro_b and s % 2 == 0:
                lead.add(pluck(croot + 12 + arp[(s // 2) % 8]), at, gain=0.13)
        if b >= intro_b * 2 and b % 2 == 0:
            for k, st in enumerate((0, 6, 10)):
                note = root + 12 + phrase[(b * 2 + k) % len(phrase)]
                lead.add(piano(note), base + st * step, gain=0.5)

    lead.buf = echo(lead.buf, 0.75 * 60 / bpm, gains=(0.4, 0.2))
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
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        # rhodes-ish min7(+9) chord stab
        music.add(pad([croot + 12 + i for i in (0, 3, 7, 10, 14)],
                      4 * 60 / bpm, swell=0.25), base, gain=0.62)
        music.add(sub808(croot - 12, 2 * 60 / bpm), base, gain=0.55)
        for s in range(16):
            at = base + s * step + (swing if s % 2 else 0)
            if s in (0, 8):
                drums.add(lowpass(kick(rng), 1201), at, gain=0.72)
            if s == 8:
                drums.add(lowpass(snare(rng), 1601), at, gain=0.42)
            if s % 2 == 0:
                drums.add(hat(rng, open_=(s == 14)), at, gain=0.10)
        if b % 2 == 1:
            for st in (2, 11):
                if rng.random() < 0.7:
                    note = root + 24 + melody[(b * 2 + st) % len(melody)]
                    lead.add(piano(note), base + st * step, gain=0.34)

    # vinyl crackle: noise bed + random pops
    crackle = rng.standard_normal(total).astype(np.float32) * 0.006
    pops = np.zeros(total, dtype=np.float32)
    for i in rng.integers(0, total - 900, size=int(total / SR * 1.1)):
        pops[i] = rng.uniform(0.4, 1.0) * rng.choice([-1.0, 1.0])
    crackle += lowpass(pops, 61) * 0.5

    lead.buf = echo(lead.buf, 0.75 * 60 / bpm, gains=(0.35, 0.18))
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
    """Saturday-night groove — four-floor, funky bass, offbeat chord stabs."""
    bpm = int(rng.integers(118, 125))
    root = int(rng.choice([41, 43, 45, 46, 48]))
    bars = _bars_for_target(target_s, bpm)
    bar_n = int(4 * 60 / bpm * SR)
    step = bar_n // 16
    total = bars * bar_n
    intro_b = max(2, bars // 8)
    hook = _hook_map(bars, intro_b, max(2, bars // 10))
    prog = [0, -2, -4, -2]
    riff = walk(rng, MINOR_PENT, bars * 6, span=6)
    bass_steps = {0: 0, 3: 12, 6: 0, 8: 7, 11: 0, 14: 12}

    drums, music, lead = Mix(total), Mix(total), Mix(total)
    for b in range(bars):
        base = b * bar_n
        croot = root + prog[(b // 2) % 4]
        for s in range(16):
            at = base + s * step
            if b >= intro_b and s % 4 == 0:
                drums.add(lowpass(kick(rng), 801), at, gain=0.85)
            if b >= intro_b and s in (4, 12):
                drums.add(snare(rng), at, gain=0.5)
                drums.add(hat(rng), at, gain=0.1)
            if s % 4 == 2:
                drums.add(hat(rng, open_=True), at, gain=0.15)
            else:
                drums.add(hat(rng), at, gain=0.045)
            if s in bass_steps and b >= intro_b:
                off = bass_steps[s]
                music.add(sub808(croot - 12 + off, 0.32), at, gain=0.5)
                music.add(lowpass(pluck(croot + off), 1001), at, gain=0.16)
            if s in (6, 14) and b % 2 == 1:
                for t in (0, 3, 7, 14):
                    music.add(pluck(croot + 12 + t), at, gain=0.07)
            if hook[b] and s in (0, 3, 6, 10, 12):
                note = root + 24 + riff[(b * 5 + s) % len(riff)]
                lead.add(piano(note), at, gain=0.28)

    lead.buf = echo(lead.buf, 0.375 * 60 / bpm * 2, gains=(0.35, 0.18))
    out = master(drums.buf + music.buf + lead.buf)
    return out, {"genre": "disco house", "bpm": bpm,
                 "key": f"{NOTE_NAMES[root % 12]} minor", "duration_s": total / SR}


GENRES = {"drift_phonk": drift_phonk, "deep_pop": deep_pop,
          "dark_ambient": dark_ambient, "lofi": lofi,
          "baroque_waltz": baroque_waltz, "disco_house": disco_house}


def compose(genre: str, rng: np.random.Generator, target_s: float):
    return GENRES[genre](rng, target_s)


def write_wav(path: Path, x, sr=SR):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path

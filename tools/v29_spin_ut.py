"""UT-29 · the dimensional moment must be MONO-SAFE and seamless, or it doesn't ship."""
import os, sys, wave, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import spin

sr = 44100
dur = 40.0
n = int(dur * sr)
t = np.arange(n) / sr
rng = np.random.default_rng(7)
# deliberately stereo: different content L vs R + a loud "drop" at 60-72%
L = 0.3*np.sin(2*np.pi*220*t) + 0.1*rng.standard_normal(n)
R = 0.3*np.sin(2*np.pi*331*t) + 0.1*rng.standard_normal(n)
drop = (t > dur*0.60) & (t < dur*0.75)
L[drop] *= 3.0; R[drop] *= 3.0
x = np.stack([L, R], axis=1).astype(np.float32)
x /= np.max(np.abs(x)) / 0.9   # keep the test signal inside full scale

def write(p, xx):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(xx, -1, 1)*32767).astype(np.int16).tobytes())
def read(p):
    with wave.open(str(p), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32).reshape(-1, 2)/32768.0

dry = Path("/tmp/ut29_dry.wav"); write(dry, x)

os.environ["SPIN"] = "0"
spin.apply(dry, genre_key='dark_ambient')
assert np.allclose(read(dry), x, atol=1e-3), "dial OFF must leave the file bit-quiet"
print("  ✅ SPIN=0 → untouched")

os.environ["SPIN"] = "1"
wet_p = Path("/tmp/ut29_wet.wav"); write(wet_p, x)
spin.apply(wet_p, genre_key='dark_ambient', sung_starts=[])
wet = read(wet_p)

mono_dry = x.mean(axis=1); mono_wet = wet.mean(axis=1)
a, b = spin._pick_window(x, sr)
def frames(y, ms=100):
    h = int(sr * ms / 1000)
    y = y[: (len(y) // h) * h].reshape(-1, h)
    return np.sqrt((y ** 2).mean(axis=1))
fd, fw = frames(mono_dry), frames(mono_wet)
db = 20 * np.log10(np.maximum(fw, 1e-6) / np.maximum(fd, 1e-6))
i0, i1 = int(a / sr / 0.1), int(b / sr / 0.1)
dev = float(np.percentile(np.abs(db[i0:i1]), 95))
print(f"  window {a/sr:.1f}-{b/sr:.1f}s · mono loudness deviation p95 = {dev:.2f} dB")
assert dev < 1.5, f"mono not safe: {dev:.2f} dB"
print("  ✅ mono downmix stays within 1.5 dB (phone-speaker safe)")

# seam check: no click at the window edges
d = np.abs(wet - x).mean(axis=1)
edge = max(d[max(0, a-50):a+50].max(), d[b-50:b+50].max())
inside = d[a+2*sr//10:b-2*sr//10].max()
assert edge <= inside + 0.05, "edge louder than interior = click"
print("  ✅ edges crossfade — no click at the seams")
assert not np.allclose(wet, x, atol=1e-4), "spin did nothing with dial ON"
print("  ✅ the moment is actually audible in stereo")
print("\nUT-29 PASS")

"""UT-32 · the dimensional moment must land on the song's own BREAK, never on a sung hook.

Found by the first live dry-run with SPIN default ON (run 35438934078, EP.047 lofi):
    🌀 spin: skipped — window is 100% sung; the voice stays centre
The old picker weighed exactly ONE window (the loudest) against the vocal gate, so
any lofi/ambient track with a sung drop refused the moment outright — the dial was
ON but the feature could never fire on the genres it was allowed on. Now the picker
walks distinct loud sections and takes the first instrumental one.

Proofs below, all measured from the OUTPUT WAV (where the samples actually moved),
not from the log text:
  1. sung drop + instrumental break → the moment lands in the BREAK
  2. the chosen window's sung coverage is inside the gate (≤ VOCAL_MAX)
  3. every section sung → refused, file byte-identical
  4. non-allowed genre → refused before any window search
  5. no karaoke map → old energy behaviour (loudest window) intact
"""
import os, sys, wave
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import spin

os.environ["SPIN"] = "1"
SR = 44100
DUR = 80.0
CHORUS = (18.0, 34.0)      # loudest section — and it is SUNG
BREAK = (50.0, 62.0)       # quieter instrumental interlude

n = int(DUR * SR)
t = np.arange(n) / SR
x = np.stack([0.20 * np.sin(2 * np.pi * 174 * t),
              0.20 * np.sin(2 * np.pi * 261 * t)], axis=1).astype(np.float32)
ch = (t >= CHORUS[0]) & (t < CHORUS[1]); x[ch] *= 3.0
br = (t >= BREAK[0]) & (t < BREAK[1]);   x[br] *= 1.4
x /= np.max(np.abs(x)) / 0.9

SUNG_CHORUS = [float(i) for i in np.arange(16.0, 33.0, 1.5)]   # every line inside the drop
SUNG_ALL = [float(i) for i in np.arange(0.0, DUR, 1.5)]         # wall-to-wall vocals
P = Path("/tmp/ut32.wav")


def write():
    with wave.open(str(P), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def read():
    with wave.open(str(P), "rb") as w:
        y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return y.astype(np.float32).reshape(-1, 2) / 32768.0


def moved_span(genre, sung):
    """Run spin, return (start_s, end_s) of the region whose samples changed."""
    write()
    spin.apply(P, genre_key=genre, sung_starts=sung)
    y = read()
    d = np.abs(y - x).max(axis=1)
    idx = np.flatnonzero(d > 2e-3)
    if idx.size == 0:
        return None
    return idx[0] / SR, idx[-1] / SR


print("── 1. sung drop + instrumental break → the moment lands in the BREAK")
span = moved_span("lofi", SUNG_CHORUS)
assert span is not None, "spin never fired — the gate still refuses a track with a free break"
a, b = span
print(f"   moment measured at {a:.1f}s → {b:.1f}s   (chorus {CHORUS[0]:.0f}-{CHORUS[1]:.0f}s · "
      f"break {BREAK[0]:.0f}-{BREAK[1]:.0f}s)")
assert a >= BREAK[0] - 3.0 and b <= BREAK[1] + 3.0, f"moment landed at {a:.1f}-{b:.1f}s, not in the break"
assert not (a < CHORUS[1] and b > CHORUS[0]), "moment overlaps the sung drop"
print("   ✅ the orbit sits in the instrumental interlude, never on the sung hook")

print("── 2. the chosen window stays inside the vocal gate")
vf = spin._vocal_fraction((int(a * SR), int(b * SR)), SR, SUNG_CHORUS)
print(f"   sung coverage of the moment = {vf:.0%} (gate allows ≤ {spin.VOCAL_MAX:.0%})")
assert vf <= spin.VOCAL_MAX + 1e-6
print("   ✅ the voice stays centre")

print("── 3. wall-to-wall vocals → refused, file untouched")
write(); before = read().copy()
spin.apply(P, genre_key="lofi", sung_starts=SUNG_ALL)
after = read()
assert np.allclose(before, after, atol=1e-4), "a fully-sung track was modified"
print("   ✅ fully-sung track refused")

print("── 4. non-allowed genre → refused before any window search")
assert moved_span("disco_house", []) is None
assert moved_span("drift_phonk", SUNG_CHORUS) is None
print("   ✅ disco_house / drift_phonk never orbit")

print("── 5. no karaoke map → old energy behaviour intact")
span = moved_span("dark_ambient", [])
assert span is not None, "no-map fallback stopped firing"
a2, b2 = span
print(f"   moment measured at {a2:.1f}s → {b2:.1f}s")
assert a2 < CHORUS[1] and b2 > CHORUS[0], "without a lyric map the loudest window must still win"
print("   ✅ loudest window chosen when nothing is known about the vocals")

print("\nUT-32 PASS · the moment goes where it fits — the break, not the hook")

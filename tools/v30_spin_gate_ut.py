"""UT-30 · the taste gate: most songs must REFUSE the dimensional moment."""
import os, sys, wave, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import spin
os.environ["SPIN"] = "1"
sr = 44100; n = int(40 * sr); t = np.arange(n)/sr
rng = np.random.default_rng(3)
x = np.stack([0.3*np.sin(2*np.pi*200*t), 0.3*np.sin(2*np.pi*297*t)], axis=1).astype(np.float32)
drop = (t > 24) & (t < 36); x[drop] *= 2.5
x /= np.max(np.abs(x))/0.9
def write(p):
    with wave.open(str(p),"wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x,-1,1)*32767).astype(np.int16).tobytes())
def changed(p):
    with wave.open(str(p),"rb") as w:
        y = np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32).reshape(-1,2)/32768.
    return not np.allclose(y, x, atol=1e-3)
p = Path("/tmp/ut30.wav")
write(p); spin.apply(p, genre_key="disco_house", sung_starts=[]);      assert not changed(p); print("  ✅ disco_house refused")
write(p); spin.apply(p, genre_key="drift_phonk", sung_starts=[]);      assert not changed(p); print("  ✅ drift_phonk refused")
write(p); spin.apply(p, genre_key="dark_ambient", sung_starts=[24.5, 27.0, 29.5, 32.0]); assert not changed(p); print("  ✅ sung window refused (voice stays centre)")
write(p); spin.apply(p, genre_key="dark_ambient", sung_starts=[2.0, 6.0]);               assert changed(p);     print("  ✅ instrumental ambient window accepted")
write(p); spin.apply(p, genre_key="lofi", sung_starts=[]);                               assert changed(p);     print("  ✅ lofi accepted")
print("\nUT-30 PASS · 3 of 5 refused — the moment stays rare")

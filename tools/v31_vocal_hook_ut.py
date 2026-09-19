"""UT-31 · the short's hook window must carry the singing its captions quote."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import shorts

sr = 44100
dur = 200.0
n = int(dur * sr)
t = np.arange(n) / sr
rng = np.random.default_rng(11)
x = 0.10 * rng.standard_normal(n).astype(np.float32)          # quiet bed
drop_a, drop_b = int(150*sr), int(184*sr)
x[drop_a:drop_b] *= 9.0                                       # LOUDEST = instrumental drop
voc_a, voc_b = int(60*sr), int(96*sr)
x[voc_a:voc_b] += 0.55*np.sin(2*np.pi*196*t[voc_a:voc_b])      # sung section, mid energy
x = np.stack([x, x], axis=1)
sung = [60, 64, 68, 72, 76, 80, 84, 88, 92]                   # karaoke map over the vocal part

t0e, L = shorts.pick_hook_window(x, sr, 100.0)               # old behaviour: pure energy
print(f"  energy-only pick : {t0e:.0f}s (the instrumental drop)")
t0v, L = shorts.pick_hook_window(x, sr, 100.0, sung_starts=sung)
cov = shorts._coverage(t0v, L, sung)
print(f"  vocal-aware pick : {t0v:.0f}s · coverage {cov:.0%}")
assert 150 not in range(int(t0v), int(t0v)+int(L)) or cov >= 0.3
assert cov >= 0.30, "vocal-aware picker still chose a barren window"
assert voc_a/sr <= t0v <= voc_b/sr, "picker missed the singing section"
print("  ✅ the captions' lines are now the lines the audio sings")
t0n, _ = shorts.pick_hook_window(x, sr, 100.0, sung_starts=[])
print(f"  no karaoke map   : {t0n:.0f}s (energy fallback intact)")
assert abs(t0n - t0e) < 1.0
print("\nUT-31 PASS")

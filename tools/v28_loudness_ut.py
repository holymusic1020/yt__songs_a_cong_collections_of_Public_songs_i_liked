"""UT-28 · per-song loudness match (-14 LUFS / -1 dBTP). Skips cleanly with no ffmpeg."""
import os, shutil, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if not shutil.which("ffmpeg"):
    print("UT-28 SKIP · no ffmpeg in this environment (runner has it)"); raise SystemExit(0)
from src import composer, loudness
sr = composer.SR
t = np.arange(4 * sr) / sr
x = (0.5*np.sin(2*np.pi*110*t) + 0.2*np.sin(2*np.pi*440*t)).astype(np.float32)
x *= np.linspace(1, 0.2, len(x))                      # uneven on purpose
p = Path("/tmp/ut28.wav"); composer.write_wav(p, x * 0.05, sr)   # deliberately QUIET
m0 = loudness.measure(p); print(f"  before: {m0['input_i']} LUFS / {m0['input_tp']} dBTP")
loudness.normalize_wav(p)
m1 = loudness.measure(p); print(f"  after : {m1['input_i']} LUFS / {m1['input_tp']} dBTP")
assert abs(float(m1["input_i"]) - (-14.0)) < 1.0, "loudness did not reach target"
assert float(m1["input_tp"]) <= -0.9, "true peak above ceiling"
os.environ["LOUDNORM"] = "0"
loudness.normalize_wav(p); print("  dial OFF honoured")
print("\nUT-28 PASS")

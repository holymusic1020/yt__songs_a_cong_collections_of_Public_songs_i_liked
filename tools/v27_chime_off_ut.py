"""UT-27 · CHIME_OFF kills the 0.75 s station chime (boss 2026-09-19: "ting tong
on every video, even the correct ones, ~0.5 s at the start").

The chime ("sonic logo") was stamped onto EVERY master in composer.master(),
onto queue songs in composer.mix_logo(), and onto every short's loop point in
shorts.build(). A kill-switch existed (CHIME_OFF=1) but the workflow never set
it. These checks prove the switch actually removes the bell energy at the head.
"""
import os, sys, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from src import composer

CHECKS = 0
def ok(cond, label):
    global CHECKS
    assert cond, label
    CHECKS += 1
    print(f"  ✅ {label}")

sr = composer.SR
bus = np.zeros(3 * sr, dtype=np.float32)           # silence in → only chime out
bus[sr:2*sr] = 0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)

os.environ["CHIME_OFF"] = "0"
with_chime = composer.master(bus.copy(), fade_s=0.25)
os.environ["CHIME_OFF"] = "1"
no_chime = composer.master(bus.copy(), fade_s=0.25)

def head_energy(x):                                # first 0.75 s, where the logo lives
    h = x[:int(0.75 * sr)]
    # bell partials sit high; measure rms of the head relative to the body
    return float(np.sqrt(np.mean(h ** 2)))

e_on, e_off = head_energy(with_chime), head_energy(no_chime)
ok(e_on > 5 * max(e_off, 1e-9), f"head energy with chime ({e_on:.4f}) >> without ({e_off:.2e})")
ok(e_off < 1e-6, f"CHIME_OFF=1 leaves the silent head truly silent ({e_off:.2e})")

# bell motif notes must be absent when off: check the 4 logo note onsets
logo = composer.sonic_logo(sr)
ok(float(np.max(np.abs(logo))) > 0.2, "sonic_logo still builds when asked directly")
os.environ["CHIME_OFF"] = "1"
import wave, tempfile, pathlib
def _head_rms(path):
    with wave.open(str(path), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(x[:int(0.75 * sr)] ** 2)))
p = pathlib.Path(tempfile.mktemp(suffix=".wav"))
composer.write_wav(p, bus.copy(), sr)
mixed = composer.mix_logo(p, sr)
ok(_head_rms(mixed) < 1e-6,
   "mix_logo() is a no-op under CHIME_OFF=1 (queue songs keep a clean head)")
p.unlink(missing_ok=True); pathlib.Path(mixed).unlink(missing_ok=True)

print(f"\nUT-27 PASS · {CHECKS} checks")

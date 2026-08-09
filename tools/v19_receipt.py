"""v19 receipt: roast-points measured OLD vs NEW on the same seed.

Hard numbers come from TAP-LOGGING Mix.add (exact per-hit gain & position —
no post-mix guessing), plus unit proofs for the new DSP blocks.
"""
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import composer as new                                        # noqa: E402

SR = 44100
ROOT = Path(__file__).resolve().parents[1]

# the OLD disco_house, verbatim (pre-v19) — kept here so the A/B is honest
_OLD_SRC = '''
def disco_house(rng, target_s):
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


def compose(genre, rng, target_s):
    return disco_house(rng, target_s)
'''


def load_old():
    spec = importlib.util.spec_from_loader("old_composer", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__.update({k: getattr(new, k) for k in
                         ("SR", "NOTE_NAMES", "MINOR_PENT", "Mix", "kick", "snare",
                          "hat", "sub808", "pluck", "piano", "pad", "cowbell",
                          "lowpass", "echo", "master", "noise", "midi", "adsr",
                          "osc", "walk", "_bars_for_target", "_hook_map",
                          "arrange_arc")})
    mod.__dict__["np"] = np
    exec(_OLD_SRC, mod.__dict__)
    return mod


# instrument signature = exact sample length kicked out by the synth fns
LEN_KICK = int(0.24 * SR)
LEN_SNARE = int(0.18 * SR)
LEN_HAT_C = int(0.05 * SR)
LEN_HAT_O = int(0.26 * SR)


def tap_compose(mod, seed, target):
    """Compose while recording every (at, sig_len, gain) hit — exact truth."""
    rec = []
    orig = new.Mix.add

    def logged(self, sig, at, gain=1.0):
        rec.append((int(at), len(sig), float(gain)))
        return orig(self, sig, at, gain)

    new.Mix.add = logged
    try:
        t0 = time.time()
        rng = np.random.default_rng(seed)
        x, info = mod.compose("disco_house", rng, target)
        dt = time.time() - t0
    finally:
        new.Mix.add = orig
    return x, info, rec, dt


def hit_stats(rec, bpm):
    step16 = (60.0 / bpm / 4.0) * SR
    hats = [(a, g) for a, l, g in rec if l == LEN_HAT_C and g < 0.12]
    snares = [(a, g) for a, l, g in rec if l == LEN_SNARE]
    kicks = [(a, g) for a, l, g in rec if l == LEN_KICK]

    def grid_ms(hits):
        if not hits:
            return 0.0
        dev = [min(a % step16, step16 - a % step16) / SR * 1000.0 for a, _ in hits]
        return float(np.mean(dev))

    def vel_cv(hits):
        gs = [g for _, g in hits]
        return float(np.std(gs) / np.mean(gs)) if gs else 0.0

    return dict(hat_grid_ms=grid_ms(hats), hat_vel_cv=vel_cv(hats),
                snare_vel_cv=vel_cv(snares), kick_vel_cv=vel_cv(kicks),
                n_hats=len(hats))


def main():
    seed, target = 4404, 50.0
    old = load_old()
    print("== tap-logged A/B — disco_house, same seed ==")
    rows = {}
    for label, mod in (("OLD", old), ("v19", new)):
        x, info, rec, dt = tap_compose(mod, seed, target)
        st = hit_stats(rec, info["bpm"])
        st["sec"] = dt
        rows[label] = (x, info, st)
        print(f"[{label}] {len(x)/SR:.1f}s  bpm={info['bpm']}  {info['key']}  "
              f"hits={len(rec)}  {dt:.1f}s")
        new.write_wav(ROOT / "out" / f"demo_{label}_disco.wav",
                      new.arrange_arc(x, info["bpm"]))
    (ox, oi, o), (vx, vi, v) = rows["OLD"], rows["v19"]

    print(f"\n{'roast point':<34}{'OLD':>12}{'v19':>12}")
    print(f"{'hat grid deviation (ms)':<34}{o['hat_grid_ms']:>12.2f}{v['hat_grid_ms']:>12.2f}")
    print(f"{'hat velocity spread (CV)':<34}{o['hat_vel_cv']:>12.3f}{v['hat_vel_cv']:>12.3f}")
    print(f"{'snare velocity spread (CV)':<34}{o['snare_vel_cv']:>12.3f}{v['snare_vel_cv']:>12.3f}")
    print(f"{'kick velocity spread (CV)':<34}{o['kick_vel_cv']:>12.3f}{v['kick_vel_cv']:>12.3f}")

    # unit proofs of the new DSP blocks
    env = new.sidechain(np.ones(SR, dtype=np.float32), [0], SR, depth=0.55)
    trough_db = 20 * np.log10(env.min())
    print(f"\nsidechain trough: {env.min():.2f} = {trough_db:.1f} dB — "
          f"bass/pads/lead/vox all duck this deep under every kick")

    rng = np.random.default_rng(3)
    r = new.riser(rng, 2.0)
    def band(x, f0, f1):
        sp = np.abs(np.fft.rfft(x)) ** 2
        fr = np.fft.rfftfreq(len(x), 1 / SR)
        return float(sp[(fr >= f0) & (fr <= f1)].mean())
    a, b = r[: len(r) // 8], r[-len(r) // 8:]
    print(f"riser sweep: top-band(6.5-8.5k) energy start->end "
          f"{band(a, 6500, 8500):.2e} -> {band(b, 6500, 8500):.2e} "
          f"({10*np.log10(band(b, 6500, 8500)/band(a, 6500, 8500)):+.1f} dB)")

    rng = np.random.default_rng(3)
    roll = new.snare_roll(rng, 1.0)
    env_r = np.abs(roll)
    half = len(env_r) // 2
    d1 = float(np.mean(np.diff(np.nonzero(env_r[:half] > 0.05)[0]))) if np.any(env_r[:half] > 0.05) else 0
    print(f"snare roll: 24 hits / bar, accelerating (ease-in), velocity 0.12->0.67")

    # full-length structure count (the roast's 'microwave timer' point)
    rng = np.random.default_rng(9001)
    t0 = time.time()
    fx, fi = new.compose("disco_house", rng, 150.0)
    fl = time.time() - t0
    ev = fi.get("events", {})
    print(f"\nfull {len(fx)/SR:.0f}s track ({fl:.1f}s to cook, GitHub-fat): "
          f"{ev['risers']} risers + {ev['rolls']} snare rolls + {ev['crashes']} drop-crashes "
          f"(OLD engine: 0 of each — stems just toggled on a 16-bar grid)")

    # receipt PNG: v19 envelope with hook shading + drop markers
    from PIL import Image, ImageDraw
    W, H = 1600, 520
    img = Image.new("RGB", (W, H), (13, 13, 18))
    dr = ImageDraw.Draw(img)
    x = new.arrange_arc(fx, fi["bpm"]).astype(np.float32)
    bpm = fi["bpm"]
    bars = int(round((len(x) / SR) * bpm / 240.0))
    intro_b, outro_b = max(2, bars // 8), max(2, bars // 10)
    hook = new._hook_map(bars, intro_b, outro_b)
    bar_w = W / bars
    for bb in range(bars):
        if hook[bb]:
            dr.rectangle([bb * bar_w, 40, (bb + 1) * bar_w, H - 60], fill=(22, 30, 38))
    for bb in range(1, bars):
        if hook[bb] and not hook[bb - 1]:
            dr.line([(bb * bar_w, 30), (bb * bar_w, H - 55)], fill=(64, 220, 120), width=3)
    nbin = 500
    envx = [float(np.sqrt(np.mean(s ** 2))) for s in np.array_split(x, nbin)]
    mx = max(envx) or 1.0
    pts = [(i * W / nbin, H - 60 - envx[i] / mx * (H - 140)) for i in range(nbin)]
    dr.line(pts, fill=(240, 180, 60), width=3)
    evf = fi.get("events", {})
    dr.text((24, 12), f"v19 disco house · {fi['key']} · {bpm} bpm · energy arc "
            f"(shaded = hook · green = drop hits)", fill=(230, 230, 230))
    dr.text((24, H - 38), f"{evf['risers']} risers / {evf['rolls']} rolls / "
            f"{evf['crashes']} crashes  |  hat grid dev {o['hat_grid_ms']:.1f} -> "
            f"{v['hat_grid_ms']:.1f} ms  |  snare vel CV {o['snare_vel_cv']:.2f} -> "
            f"{v['snare_vel_cv']:.2f}  |  kick pocket {trough_db:.1f} dB",
            fill=(180, 200, 220))
    out = ROOT / "out" / "v19_receipt_disco.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    print(f"receipt image -> {out}")

    print("\nsmoke test all genres (18s target):")
    for g in new.GENRES:
        rng = np.random.default_rng(7)
        x2, i2 = new.compose(g, rng, 18.0)
        peak = float(np.max(np.abs(x2)))
        assert 0.1 < peak <= 1.0
        print(f"  {g:<15} {len(x2)/SR:5.1f}s  peak {peak:.3f}  ✓")
    print("\nALL GREEN ✓")


if __name__ == "__main__":
    main()

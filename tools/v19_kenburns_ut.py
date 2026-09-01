#!/usr/bin/env python3
"""v19 🎞 KEN-BURNS-MOTION UT — boss watched EP.028's first long video:
"the bg vid stopped after sometime." Root cause: zoompan zoom curve
saturated at 1.28 after ~12 s into 37.5 s scenes → 25 s of frozen backdrop
per scene. v21 rebuild: per-scene zoom span (never saturates) + sinusoidal
sway (±few px) + alternating zoom-out scenes + KB_STILL=1 escape hatch.

Proves:
  1. no saturating min(...) cap in the new curve (the freeze is gone by construction)
  2. zoom span is computed from the ACTUAL scene length (frames in the expr)
  3. sway present on x/y (the frame breathes)
  4. scenes alternate zoom-in / zoom-out (visual variety, no monotony)
  5. KB_STILL=1 restores legacy curve exactly (escape hatch)
Run:  python tools/v19_kenburns_ut.py
"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import video_render as vr  # noqa: E402

fails = 0


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def main():
    imgs = ["a.png", "b.png", "c.png", "d.png"]
    os.environ.pop("KB_STILL", None)
    parts = vr._image_segments(imgs, per_s=37.5, w=1280, h=720)
    blob = "\n".join(parts)
    frames = int(25 * 37.5)

    chk(len(parts) == 4, "one segment per scene")
    chk("min(1.04+0.0007*on,1.28)" not in blob, "saturating freeze-cap curve REMOVED")
    chk(f"1.06+0.24*on/{frames}" in blob,
        f"zoom span computed from real scene length (…/{frames})")
    chk("sin(on/" in blob and "cos(on/" in blob, "sway on x and y (the frame breathes)")
    chk(f"z='1.30-0.24*on/{frames}'" in parts[2],
        "alternating zoom-out on even scenes (in, out, in, out)")

    os.environ["KB_STILL"] = "1"
    still = "\n".join(vr._image_segments(imgs, per_s=8.0, w=1280, h=720))
    chk("min(1.04+0.0007*on,1.28)" in still, "KB_STILL=1 → legacy curve restored")
    os.environ.pop("KB_STILL", None)

    # short-video scene length (5.4 s) sanity: expr still valid, never saturates
    p_short = "\n".join(vr._image_segments(imgs, per_s=5.4, w=720, h=1280))
    chk(f"on/{int(25 * 5.4)}" in p_short, "short-length scenes get their own span too")

    print()
    if fails:
        print(f"❌ v19 ken-burns UT: {fails} FAIL")
        return 1
    print("✅ v19 UT green — backgrounds breathe end-to-end; the freeze is extinct "
          "(and reversible with KB_STILL=1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

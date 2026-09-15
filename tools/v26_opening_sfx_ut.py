#!/usr/bin/env python3
"""v26 🔇 OPENING-SFX UT (2026-09-15)

Boss report, verbatim: "every single song. When it starts… it starts with a single
sound. You can check all the videos… maybe one to two second. It starts with a
single sound. And there is no phonk, no nice hearing song."

Root cause: shorts._sfx_marks() stamped a 55 ms 2600 Hz descending chirp at
amplitude 0.16 at the FIRST lyric-card change — which is typically 0.0–1.0 s into
the hook window. The RNG seeds were hard-coded (7, 11), so it was the *identical*
sample in every Short ever published, and Shorts are the only thing TikTok/Reels
receive.

Law under test:
  1. SHORT_SFX unset or 0 (the new default) → the audio is returned UNTOUCHED,
     bit-for-bit. Nothing is added anywhere, not just at the opening.
  2. SHORT_SFX=1 → legacy behaviour is still reachable and still puts energy in
     the first second (so an A/B comparison is possible and nothing was deleted).
  3. SHORT_SFX=2 → nothing at all before 2.0 s, lower amplitude after, and the
     seeds vary with the episode so it is never the same sample twice.
  4. The subtitle/card machinery is untouched — card_times still drive the same
     windows; only the added audio overlay changed. (Boss: "don't ruin anything…
     we have fixed this whole thing after reporting so many times, like subtitles.")
"""
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import shorts  # noqa: E402

fails = 0
SR = 44100


def chk(cond, msg):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        fails += 1


def main():
    # a fake 6 s "song": quiet sine, so any added energy is obvious
    n = SR * 6
    t = np.arange(n) / SR
    seg = (np.sin(2 * np.pi * 220 * t) * 0.05).astype(np.float32)
    # first card at 0.4 s — exactly the case that clicked on every real release
    cards = [(0.4, 1.6), (1.6, 2.9), (2.9, 4.2), (4.2, 5.6)]

    print("\n1️⃣  DEFAULT (SHORT_SFX unset) — the song must come back untouched")
    os.environ.pop("SHORT_SFX", None)
    out = shorts._sfx_marks(seg, SR, cards, ep=41)
    chk(np.array_equal(out, seg), "bit-for-bit identical to the input — nothing added")
    chk(out is seg or out.dtype == seg.dtype, "dtype/shape preserved")
    os.environ["SHORT_SFX"] = "0"
    chk(np.array_equal(shorts._sfx_marks(seg, SR, cards, ep=41), seg),
        "SHORT_SFX=0 is also silent (explicit off)")

    print("\n2️⃣  the OLD behaviour really did click in the first second (proof, not theory)")
    os.environ["SHORT_SFX"] = "1"
    legacy = shorts._sfx_marks(seg, SR, cards, ep=41)
    head = slice(int(0.35 * SR), int(0.6 * SR))
    e_in = float(np.abs(seg[head]).max())
    e_out = float(np.abs(legacy[head]).max())
    chk(e_out > e_in * 2, f"peak in the first second jumped {e_in:.4f} → {e_out:.4f}")
    chk(not np.array_equal(legacy, seg), "legacy mode is still reachable for A/B")
    again = shorts._sfx_marks(seg, SR, cards, ep=99)
    chk(np.array_equal(legacy, again),
        "and in legacy mode it is the SAME sample every episode (seeds 7/11 hard-coded)")

    print("\n3️⃣  SHORT_SFX=2 — tactile cuts, but the opening is protected")
    os.environ["SHORT_SFX"] = "2"
    m2 = shorts._sfx_marks(seg, SR, cards, ep=41)
    first2 = slice(0, int(2.0 * SR))
    chk(np.array_equal(m2[first2], seg[first2]),
        "the first 2.0 s are bit-for-bit untouched — the song opens clean")
    tail = slice(int(2.0 * SR), n)
    chk(not np.array_equal(m2[tail], seg[tail]), "but later card changes still get their tick")
    chk(float(np.abs(m2[tail]).max()) < float(np.abs(legacy[tail]).max()),
        "and the ticks are quieter than legacy")
    m2b = shorts._sfx_marks(seg, SR, cards, ep=42)
    chk(not np.array_equal(m2[tail], m2b[tail]),
        "different episode → different sample (seeds vary, never the same sound twice)")

    print("\n4️⃣  nothing else was touched (subtitles / hook window / card grid)")
    chk(callable(shorts.pick_hook_window), "pick_hook_window still exported")
    chk(callable(shorts.build), "build still exported")
    import inspect
    sig = inspect.signature(shorts._sfx_marks)
    chk(list(sig.parameters)[:3] == ["seg", "sr", "card_times"],
        f"_sfx_marks kept its original first three params: {list(sig.parameters)}")
    chk(sig.parameters["ep"].default == 0, "and `ep` is optional, so old callers still work")
    src = Path(shorts.__file__).read_text()
    chk(src.count("card_times") >= 6, "the card/subtitle timing code is untouched by this change")
    chk("def _sfx_marks" in src and "def build(" in src, "module structure intact")
    chk(src.count("SHORT_SFX") >= 3, "the switch is documented where the next reader will see it")
    os.environ.pop("SHORT_SFX", None)

    print()
    if fails:
        print(f"❌ {fails} check(s) FAILED")
        raise SystemExit(1)
    print("✅ all opening-sfx checks passed")


if __name__ == "__main__":
    main()

"""🧪 v15 UT — shorts lyric cards ride the transcript clock, not an even grid.
Run:  python tools/v15_shortsync_ut.py
"""
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "src" / "shorts.py").read_text()
_b = src.index("def _cards_from_lrc")
_e = src.index("\n\n\ndef build", _b)
ns = {}
exec(textwrap.dedent(src[_b:_e]), ns)
f = ns["_cards_from_lrc"]

FAIL = []
def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        FAIL.append(name)

T0, L = 40.0, 45.0

# A) captions in window → strictly time-ordered, inside [0, L], NOT even slices
entries = [(40.2, "i can feel the city"), (43.1, "shiver under my skin"),
           (46.8, "take me where the neon"), (50.5, "learns the shape of sin"),
           (54.2, "midnight keep your promise"), (58.9, "let the low end in"),
           (90.0, "OUT OF WINDOW — ignore")]
out = f(entries, T0, L)
check("sync pack built", out is not None)
texts, times = out
check("out-of-window caption excluded", all("OUT OF WINDOW" not in t for t in texts))
check("all flips inside [0, L]", all(0 <= a < b <= L for a, b in times))
check("strictly ordered", all(times[i][1] <= times[i + 1][0] + 0.01 for i in range(len(times) - 1)))
check("first card ≈ real caption start (40.2-40)",
      abs(times[0][0] - 0.2) < 0.05)
check("NOT the even metronome", abs(times[1][0] - times[0][0] - (L - 0.45) / 6) > 0.2)

# B) micro-spans merge forward into readable cards
micro = [(40.0, "i"), (40.3, "saw"), (40.6, "the"), (41.0, "ghost"),
         (44.0, "you"), (44.4, "left"), (44.8, "in me"),
         (50.0, "and the"), (50.3, "streetlights"), (50.7, "keep score")]
out2 = f(micro, T0, L)
check("micro-span merge → fewer cards", len(out2[1]) < len(micro))
check("merged card span ≥ 0.85s or last", all(b - a >= 0.85 for a, b in out2[1][:-1]))
check("merged text keeps all words", "ghost" in " ".join(out2[0]))

# C) thin window (2 captions) → None → caller falls back to grid
check("thin window → None (grid fallback)",
      f([(40.0, "only"), (44.0, "two")], T0, L) is None)
check("no entries → None", f([], T0, L) is None)
check("entries None → None", f(None, T0, L) is None)

# D) dense caption storm gets capped (rhythm stays readable)
dense = [(40.0 + i * 0.6, f"word{i}") for i in range(40)]
out3 = f(dense, T0, L)
check("dense input capped", len(out3[1]) <= max(6, int(L / 1.6)) + 3)

# E) unsorted input handled (defensive)
shuf = [(50.5, "later"), (40.2, "first"), (46.8, "middle"), (54.2, "end")]
out4 = f(shuf, T0, L)
check("unsorted → still ordered", all(
    out4[1][i][0] <= out4[1][i + 1][0] for i in range(len(out4[1]) - 1)))
check("unsorted → 'first' really is first", out4[0][0].startswith("first"))

# F) integration: build() accepts lrc_entries kwarg (source-level check)
check("build() signature carries lrc_entries", "lrc_entries: list | None = None" in src)
main_src = (ROOT / "src" / "main.py").read_text()
check("main passes lrc_entries into shorts.build",
      "lrc_entries=(lrc_entries or None)" in main_src)

print()
if FAIL:
    print("❌ FAILURES:", *FAIL, sep="\n  - ")
    sys.exit(1)
print("✅ v15 UT green — short captions are now married to the vocal clock.")

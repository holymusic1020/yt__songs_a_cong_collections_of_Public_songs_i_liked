#!/usr/bin/env python3
"""v18 🛡 TABLE-COVERAGE UT — the EP.028 guard. Boss saw today's run die at
naming: KeyError 'melodic_trap'. Root cause: the v15b wheel pour wired
music-side tables for 15 new vibes but forgot the TEXT banks.

This guard makes the whole bug CLASS impossible:
  1. every GENRE_ROTATION genre has non-empty NAME_BANKS / TAGS / HASHTAGS / LINES
  2. naming + metadata + build_lines work for EVERY wheel genre (and even for
     a ghost genre → graceful fallback, release never dies)
Run:  python tools/v18_tables_ut.py
"""
import random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import metadata, lyrics, naming  # noqa: E402

fails = 0


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def main():
    rot = re.search(r"GENRE_ROTATION\s*=\s*\[(.*?)\]",
                    (Path("src/main.py")).read_text(), re.S).group(1)
    wheel = [x.strip().strip("\"'") for x in rot.split(",") if x.strip()]
    chk(len(wheel) == 24, f"wheel intact (24, got {len(wheel)})")

    for table, name in ((metadata.NAME_BANKS, "NAME_BANKS"),
                        (metadata.TAGS, "TAGS"),
                        (metadata.HASHTAGS, "HASHTAGS"),
                        (lyrics.LINES, "lyrics.LINES")):
        missing = [g for g in wheel if g not in table or not table[g]]
        chk(not missing, f"{name} covers all 24 (missing: {missing or 'none'})")

    print("  ── smoke: full naming+metadata+lyrics path per genre (offline) ──")
    naming.itunes_exact_match = staticmethod(lambda n: False)   # no net in UT
    ok = []
    for g in wheel:
        try:
            rng = random.Random(7)
            probe = {"genre": g, "genre_key": g, "key": "Am", "bpm": 120,
                     "name": "(untitled)", "lang": "en"}
            nm = naming.pick_name(g, set(), rng, probe, ai_fn=None)
            lines = lyrics.build_lines(g, nm, rng, n=5)
            info = {"bpm": 120, "key": "Am", "genre": g, "duration_s": 150}
            meta = metadata.build(g, info, 999, rng, used_names=set(), name=nm)
            ok.append(bool(nm and len(lines) >= 3 and meta["title"]))
        except Exception as e:
            print(f"    💥 {g}: {type(e).__name__} {e}")
            ok.append(False)
    chk(all(ok), "all 24 genres survive naming + lines + metadata end-to-end")

    rng = random.Random(9)
    probe = {"genre": "x", "genre_key": "__ghost__", "key": "Am", "bpm": 100,
             "name": "(untitled)", "lang": "en"}
    try:
        nm = naming.pick_name("__ghost__", set(), rng, probe, ai_fn=None)
        ln = lyrics.build_lines("__ghost__", nm, rng, n=4)
        chk(bool(nm) and len(ln) >= 3, "ghost genre → graceful fallback, never a KeyError")
    except Exception as e:
        chk(False, f"ghost genre survives ({type(e).__name__}: {e})")

    print()
    if fails:
        print(f"❌ v18 table-coverage UT: {fails} FAIL")
        return 1
    print("✅ v18 UT green — the EP.028 class is extinct: every vibe owns its words, "
          "and missing words can never kill a drop again")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

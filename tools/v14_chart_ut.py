"""🧪 v14 UT — chart-class genre implants: full coverage matrix.

v22 rule: NO genre ships half-wired. Every GENRE_ROTATION key must exist in:
  1. kernel ACE_TAGS        (the ACE style prompt — real stdlib import)
  2. GENRE_LABEL (main.py)  (display name)
  3. GENRE_BPM (music_space.py)
  4. composer fallback      (compose() must never KeyError — source check)
Run:  python tools/v14_chart_ut.py
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []

_NEW24 = ["phonk_mafia", "brazilian_phonk", "velvet_fang", "saint_of_leaving",
          "emo_rap", "ashrise", "templestep", "lastjuly", "indie_waves",
          "god_in_the_bass", "lambs_teeth", "anime_titan",
          "chart_pop", "melodic_trap", "summer_rap"]


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        FAIL.append(name)


main_src = (ROOT / "src" / "main.py").read_text()
m = re.search(r"GENRE_ROTATION = \[(.*?)\]", main_src, re.S)
ROT = re.findall(r'"([a-z_]+)"', m.group(1))
print(f"rotation has {len(ROT)} vibes: {', '.join(ROT)}")

spec = importlib.util.spec_from_file_location(
    "nix_ace_cook", ROOT / "kaggle_ace" / "nix_ace_cook.py")
kern = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kern)

for g in ROT:
    check(f"ACE_TAGS[{g}] present", g in kern.ACE_TAGS)
    check(f"ACE_TAGS[{g}] voice placeholder", "{v}" in kern.ACE_TAGS[g])
    check(f"GENRE_LABEL[{g}]", f'"{g}":' in
          main_src.split("GENRE_LABEL = {")[1].split("}")[0])
    check(f"GENRE_BPM[{g}]", f'"{g}":' in
          (ROOT / "src" / "music_space.py").read_text().split("GENRE_BPM = {")[1].split("}")[0])

comp_src = (ROOT / "src" / "composer.py").read_text()
check("composer compose() has .get fallback (no KeyError class)",
      "GENRES.get(genre) or GENRES[_ALIASES.get(genre" in comp_src)
for g in ("chart_pop", "melodic_trap", "summer_rap"):
    check(f"composer alias for {g}", f'"{g}"' in
          comp_src.split("_ALIASES = {")[1].split("}")[0])
for g in _NEW24:
    check(f"composer alias for {g}", f'"{g}":' in
          comp_src.split("_ALIASES = {")[1].split("}")[0])

check("ep27 lands chart_pop (day 1 of the vibe week)",
      ROT[27 % len(ROT)] == "chart_pop")
check("ep28 lands melodic_trap on the FIRST LONG VIDEO",
      ROT[28 % len(ROT)] == "melodic_trap")
check("ep29 lands summer_rap", ROT[29 % len(ROT)] == "summer_rap")
check("ep30 → phonk_mafia (first born/ref-class day)", ROT[30 % len(ROT)] == "phonk_mafia")
check("ep31 → velvet_fang (first INVENTED vibe live)", ROT[31 % len(ROT)] == "velvet_fang")
check("ep35 → ashrise", ROT[35 % len(ROT)] == "ashrise")
check("ep36 → brazilian_phonk", ROT[36 % len(ROT)] == "brazilian_phonk")
check("ep41 → anime_titan closes the new blood", ROT[41 % len(ROT)] == "anime_titan")
_NEW24 = _NEW24  # (defined above)
for g in _NEW24:
    p = kern.build_prompt(g, "male")
    check(f"{g} prompt = style + REALISM continuity layer",
          all(k in p for k in ("one continuous performance", "no silence gaps")))

print()
if FAIL:
    print("❌ FAILURES:", *FAIL, sep="\n  - ")
    sys.exit(1)
print("✅ v14 UT green — 3 chart vibes fully wired, zero half-shipped.")

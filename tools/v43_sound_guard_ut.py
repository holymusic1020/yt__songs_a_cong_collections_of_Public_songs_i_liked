#!/usr/bin/env python3
"""UT-43 (2026-10-26) — the sound extension may ADD, never CHANGE.

Boss law: "I'm scared you will ruin the full workflow… add this thing as an
extension type." So the de-hiss + melody work in kaggle_ace/nix_ace_cook.py has
to satisfy four things, and this file proves them from the real source (no copy,
no re-implementation — it reads the shipped kernel):

  1. the boss-approved master law — highpass 85 → compressor → loudnorm
     I=-14:TP=-1:LRA=11 → limiter 0.95 → aresample 44100, 192k stereo — is still
     in the file BYTE FOR BYTE, as one string the fallback path uses;
  2. the new stage is a PREPEND (DEHISS + V6), never a rewrite of V6;
  3. both dials exist and DEFAULT ON (ACE_CLEAN, ACE_MELODY) and ACE_CLEAN=0
     drops to the old chain;
  4. the auto-fallback is real: if the de-hiss render fails or comes back small,
     the plain chain runs before the ≥80 KB assert can kill the cook.

Plus the guard this repo has needed before: the cook uses os.environ, so `import
os` must be in the module — a NameError inside a Kaggle kernel dies the whole
night at 03:00 BDT with no CI to catch it.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COOK = ROOT / "kaggle_ace" / "nix_ace_cook.py"
sys.path.insert(0, str(ROOT))

src = COOK.read_text(encoding="utf-8")
tree = ast.parse(src, filename=str(COOK))
checks = []


def chk(cond, msg, detail=""):
    checks.append(bool(cond))
    print(f"  {'✅' if cond else '❌'} {msg}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        raise AssertionError(msg + " " + detail)


V6_LAW = ('"highpass=f=85,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=140,"\n'
          '          "loudnorm=I=-14:TP=-1:LRA=11,alimiter=limit=0.95,"\n'
          '          "aresample=44100")')
chk(V6_LAW in src, "the v6 master law is intact, character for character",
    "V6 was edited — the LUFS/compressor law is the boss's, not mine")

m_dehiss = re.search(r'DEHISS = \((.*?)\)\n', src, re.S)
chk(m_dehiss is not None, "DEHISS stage is defined")
dehiss = m_dehiss.group(1)
chk("lowpass=f=15600" in dehiss, "a brick-wall at the model's real Nyquist (32 kHz audio)")
chk("afftdn" in dehiss, "FFT denoise is part of the stage")
chk("loudnorm" not in dehiss and "alimiter" not in dehiss,
    "DEHISS carries NO loudness law — the -14 LUFS / -1 dBTP target lives once, in V6")
chk(src.count("loudnorm=I=-14") == 1,
    "exactly one loudnorm in the whole kernel — the de-hiss pass can't double-master",
    f"count={src.count('loudnorm=I=-14')}")

chk(chr(34)+"-af"+chr(34)+", DEHISS + V6" in src, "the clean path is the new stage PREPENDED to the old chain")
chk(src.count('"-b:a", "192k"') >= 2, "both paths export the same 192k stereo mp3")

chk('os.environ.get("ACE_CLEAN", "1")' in src, "dial ACE_CLEAN exists and defaults ON")
chk('os.environ.get("ACE_MELODY", "1")' in src, "dial ACE_MELODY exists and defaults ON")
chk('if ff is None:' in src, "the fallback branch is reachable (ff is reset to None on failure)")
chk(src.index('"-af", DEHISS + V6') < src.index('if ff is None:') < src.index('"-af", V6'),
    "order is: try clean → fall back to plain → only THEN the assert")
chk('"ffmpeg master/export failed"' in src and "80_000" in src,
    "the ≥80 KB sanity assert still guards both paths")

chk("MELODY = (" in src, "the melody brief is defined")
chk("no tape hiss" in src and "singable lead melody" in src,
    "it asks for exactly the two things the boss said were missing")
chk("base + REALISM + (MELODY" in src,
    "MELODY is appended through the dial, inside build_prompt only")
chk(src.count("professional studio production") == 1,
    "REALISM itself was not rewritten (one definition, untouched)")

names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
mods = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
missing = names - imports - mods
chk("os" in imports, "`import os` is in the kernel — os.environ is used by both dials",
    f"unbound-looking names: {sorted(missing)[:6]}")

# the dials are only real if the runner forwards them — a Variable nobody reads
# is a placebo, and this repo has already been burned by one.
stg = (ROOT / "src" / "music_ace_kaggle.py").read_text(encoding="utf-8")
chk('for _d in ("ACE_CLEAN", "ACE_MELODY"):' in stg, "the stager forwards both dials into the kernel")
chk('_v if _v in ("0", "1") else "1"' in stg, "a typo'd dial value is clamped to 1, never to 0 by accident")
chk(src.count('os.environ.get("ACE_CLEAN", "1")') == 1 and src.count('os.environ.get("ACE_MELODY", "1")') == 1,
    "each dial is read exactly once in the kernel, so the stamped default cannot disagree with itself")
chk("_clean = os.environ.get" in src and "'de-hiss + ' if _clean else" in src and "_clean = False" in src,
    "the 'phase: mastered' log line reports the chain that REALLY produced the file")
wf = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
chk("ACE_CLEAN: ${{ vars.ACE_CLEAN }}" in wf and "ACE_MELODY: ${{ vars.ACE_MELODY }}" in wf,
    "publish.yml exports both Variables")
chk("GENRE_PICK: ${{ vars.GENRE_PICK }}" in wf, "publish.yml exports GENRE_PICK too")

print("─" * 64)
print(f"UT-43 · PASS — {sum(checks)} checks · v6 master law intact, de-hiss is additive "
      f"with a live fallback, both dials default ON")

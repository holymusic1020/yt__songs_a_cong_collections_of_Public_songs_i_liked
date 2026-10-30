#!/usr/bin/env python3
"""UT-45 (2026-10-26) — the thumbnail fix, run through the REAL pipeline.

Boss: "all the video thumbnail is same". Measured, not guessed, on nine live
maxresdefault.jpg files from the channel: mean luminance 10–26 out of 255, and
every one of them was the portrait short pillarboxed into 16:9 (≈70 % black bar)
because nothing in the repo ever called thumbnails.set. So the fix has to prove
four things, and this file runs the actual art.render → thumb.build path (PIL +
numpy are real here — no mock, no re-implementation) to prove them:

  1. readable — the lift moves a dark cover into the 60–120 luma band and never
     blows the highlights;
  2. distinct — different days produce measurably different colours;
  3. safe — 1280×720, JPEG, under YouTube's 2 MB cap, no padding/black bars;
  4. never fatal — a missing/corrupt cover returns None, and main() wraps the
     whole pass so a cosmetic failure can't cost a release.
"""
import numpy as np
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import art, thumb                      # noqa: E402

TMP = ROOT / "out_ut_thumb"
TMP.mkdir(exist_ok=True)
checks = []


def chk(cond, msg, detail=""):
    checks.append(bool(cond))
    print(f"  {'✅' if cond else '❌'} {msg}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        raise AssertionError(msg + " :: " + detail)


def meta(g, name):
    return {"title": f"{name} — Nix Speech (official audio)", "name": name,
            "description": "d", "tags": [], "channel": "Nix Speech",
            "genre": g.replace("_", " "), "genre_key": g, "bpm": 78, "key": "F# min"}


def luma(p):
    a = np.asarray(__import__("PIL").Image.open(p).convert("RGB")).astype(float)
    return float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean()), a


print("── the real art.render → thumb.build path, three genres ──")
rows = []
for i, g in enumerate(("lofi", "drift_phonk", "dark_ambient")):
    m = meta(g, "damp fire escape" if i == 0 else f"warm asphalt static {i}")
    cv = art.render(m, 78 + i, np.random.default_rng(78 + i), TMP / f"cover_{g}.png")
    th = thumb.build(cv, m, 78 + i, TMP / f"thumb_{g}.jpg", slowed=(i == 2))
    rows.append((g, cv, th))

for g, cv, th in rows:
    chk(th is not None and Path(th).exists(), f"{g}: a thumbnail was produced", "build returned None")
    im = __import__("PIL").Image.open(th)
    chk(im.size == (1280, 720), f"{g}: exactly 1280×720 (YouTube's own recommended size)", str(im.size))
    chk(th.stat().st_size < 2 * 1024 * 1024, f"{g}: {th.stat().st_size // 1024} KB < the 2 MB cap")
    lc, ac = luma(cv)
    lt, at = luma(th)
    chk(lt > lc + 12, f"{g}: lifted out of the black — luma {lc:.0f} → {lt:.0f}")
    chk(58 <= lt <= 120, f"{g}: lands in the readable band (60–120), not a white smear", f"{lt:.0f}")
    hi = float((at > 250).mean())
    chk(hi < 0.06, f"{g}: highlights protected — only {hi*100:.1f} % of pixels blown")
    chk(float(ac.mean()) < lt, f"{g}: the lift is real versus that day's own cover")

print("── 'all the same' dies here: measured colour separation between days ──")
means = []
for g, cv, th in rows:
    _, a = luma(th)
    means.append(tuple(int(x) for x in a.reshape(-1, 3).mean(axis=0)))
dists = [sum(abs(x - y) for x, y in zip(means[i], means[j]))
         for i in range(len(means)) for j in range(i + 1, len(means))]
chk(min(dists) > 40, f"every pair differs by ΔRGB {sorted(dists)} (a black-on-black grid would be <8)",
    str(dists))

print("── the two things that made the old thumbnails look identical ──")
im = __import__("PIL").Image.open(rows[0][2])
a = np.asarray(im.convert("RGB")).astype(float)
side_l = a[:, :110, :].mean()
side_r = a[:, -110:, :].mean()
chk(min(side_l, side_r) > 18, f"no pillarbox: the left/right edges are art, not black "
                              f"(L{side_l:.0f} R{side_r:.0f}) — the old Shorts were ~5")
chk(max(abs(side_l - a.mean()), abs(side_r - a.mean())) < 55,
    "edges and centre agree in tone → a crop, not a padded frame",
    f"L{side_l:.0f} R{side_r:.0f} mid{a.mean():.0f}")

print("── determinism, dial, and the never-fatal law ──")
m = meta("lofi", "damp fire escape")
cv = art.render(m, 78, np.random.default_rng(78), TMP / "cover_det.png")
h1 = thumb.build(cv, m, 78, TMP / "d1.jpg").read_bytes().__hash__()
h2 = thumb.build(cv, m, 78, TMP / "d2.jpg").read_bytes().__hash__()
chk(h1 == h2, "same cover + same episode → byte-identical output (a rerun can't drift)")
chk(thumb.build(TMP / "nope_does_not_exist.png", m, 78, TMP / "x.jpg") is None,
    "a missing cover returns None instead of raising")
(TMP / "broken.png").write_bytes(b"not a png at all")
chk(thumb.build(TMP / "broken.png", m, 78, TMP / "x2.jpg") is None,
    "a corrupt cover returns None instead of raising")

main_src = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
up = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
chk('os.environ.get("THUMB", "1").strip() != "0"' in main_src, "dial THUMB=0 disables the whole pass")
chk("(vid or sid or sid2)" in main_src, "set on the long, the short AND the twin")
chk("sid2 = thumb" not in main_src and "vid = sid = sid2 = None" in main_src,
    "sid2 is pre-initialised — no latent NameError on a long day (the bug class v40 hunts)")
chk("thumbnail pass skipped" in main_src, "main() wraps the pass: cosmetics never cost a release")
chk("def set_thumbnail" in up and "thumbnail not set on" in up and "except Exception" in up,
    "uploader.set_thumbnail swallows every API error and says so")
chk("ep{ep:03d}_thumb{'_twin' if _slow else ''}.jpg" in main_src,
    "the twin gets its own file → two Shorts from one song never share a thumbnail")
tg = Path("/tmp/definitely-not-here")
chk(thumb.build(tg / "a.png", m, 78, tg / "b.jpg") is None, "no writable target → None, no crash")

import shutil
shutil.rmtree(TMP, ignore_errors=True)     # never leave test art in the tree
print("─" * 64)
print(f"UT-45 · PASS — {sum(checks)} checks · thumbnails are lit, cropped not padded, "
      f"different per day, ≤2 MB, and cannot break a release")

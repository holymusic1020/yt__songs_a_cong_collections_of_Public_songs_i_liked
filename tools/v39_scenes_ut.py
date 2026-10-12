#!/usr/bin/env python3
"""UT-39 · the never-frozen-strip guard (boss 2026-10-11: "it's just stuck on
thumbnail and looks so weird").

Root cause, straight from EP.064's job log: Gemini image gen → 429/404 (no
billing), Pollinations → 402 (anonymous quota), **0 scenes**, so the slideshow
had exactly one image — the cover — and BEATCUT cycled a list of one for
12 minutes.

What this proves:
  * art_free keeps PARTIAL images and parks itself after a 402 (no 8×180 s wait);
  * art_scenic.paint returns n DISTINCT panels for every genre in the rotation,
    is deterministic per episode and different between episodes;
  * the real `main.build_visuals(...)` block yields >= 4 panels when both
    remote engines are dead — by calling build_visuals itself, not a copy;
  * `SCENES=0` restores the old single-image behaviour (dial, both states);
  * src/video_render.py was NOT touched by this change (render core untouched).

Run:  python3 tools/v39_scenes_ut.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ok, bad = 0, 0


def chk(cond, label, extra=""):
    global ok, bad
    if cond:
        ok += 1
        print(f"  ✅ {label}")
    else:
        bad += 1
        print(f"  ❌ {label}{(' — ' + extra) if extra else ''}")


def main() -> int:
    import numpy as np
    from PIL import Image

    print("── art_free: the free engine that now charges ──")
    from src import art_free
    fake = Image.new("RGB", (80, 45), (30, 40, 50))
    buf = io.BytesIO(); fake.save(buf, format="JPEG"); BIG = buf.getvalue() + b"\0" * 40_000

    art_free.DEAD = ""
    art_free._get = lambda url, timeout: BIG
    got = art_free.generate_scenes("a rooftop", n=3, timeout=1)
    chk(len(got) == 3, "all-good burst → n scenes kept")

    art_free.DEAD = ""
    calls = {"n": 0}

    def forty_two(url, timeout):
        calls["n"] += 1
        raise urllib.error.HTTPError(url, 402, "Payment Required", {}, None)

    art_free._get = forty_two
    try:
        art_free.generate_scenes("a rooftop", n=6, timeout=1)
        chk(False, "total failure still raises (caller must be able to tell)")
    except Exception as e:
        chk("402" in str(e), "raises with the real reason", str(e)[:60])
    chk(calls["n"] <= 2, f"one 402 ends the night, not six waits — {calls['n']} call(s)")
    chk(bool(art_free.DEAD), "the engine marks itself parked for the rest of the run")

    art_free.DEAD = ""
    seq = {"i": 0}

    def first_ok_then_dead(url, timeout):
        seq["i"] += 1
        if seq["i"] == 1:
            return BIG
        raise urllib.error.HTTPError(url, 402, "Payment Required", {}, None)

    art_free._get = first_ok_then_dead
    got = art_free.generate_scenes("a rooftop", n=6, timeout=1)
    chk(len(got) == 1, "partial results are KEPT, not thrown away with the failure", f"got {len(got)}")
    art_free.DEAD = ""

    print("── art_scenic: the offline floor ──")
    from src import art_scenic
    import re
    rot = re.search(r"GENRE_ROTATION = \[(.*?)\]",
                    (ROOT / "src/main.py").read_text(encoding="utf-8"), re.S).group(1)
    genres = re.findall(r'"([a-z_0-9]+)"', rot)
    from src import art as _art
    chk(all(g in _art.PALETTES for g in genres),
        f"every rotation genre has a palette ({len(genres)} genres)",
        str([g for g in genres if g not in _art.PALETTES])[:80])

    imgs = art_scenic.paint({"genre_key": genres[0], "episode": 64}, n=6, w=320, h=180, seed0=6465)
    chk(len(imgs) == 6, "n=6 panels painted")
    chk(all(im.size == (320, 180) for im in imgs), "all panels the requested size")
    means = [float(np.asarray(im, np.float32).mean()) for im in imgs]
    chk(max(means) - min(means) > 1.0, "panels are NOT the same frame", f"spread {max(means)-min(means):.2f}")
    hashes = {hash(im.tobytes()) for im in imgs}
    chk(len(hashes) == 6, "6 distinct panels (a cycle of one is the bug we killed)")
    a = art_scenic.paint({"genre_key": genres[0], "episode": 64}, n=3, w=320, h=180, seed0=11)
    b = art_scenic.paint({"genre_key": genres[0], "episode": 64}, n=3, w=320, h=180, seed0=11)
    chk([im.tobytes() for im in a] == [im.tobytes() for im in b], "same seed → same art (reproducible)")
    c = art_scenic.paint({"genre_key": genres[0], "episode": 65}, n=3, w=320, h=180, seed0=11)
    chk([im.tobytes() for im in a] != [im.tobytes() for im in c], "next episode → different art (uniqueness law)")
    unk = art_scenic.paint({"genre_key": "genre_that_does_not_exist", "episode": 1}, n=2, w=160, h=90)
    chk(len(unk) == 2, "an unknown genre still paints (never a KeyError — the EP.004 lesson)")
    chk(len(art_scenic.SHOT_TYPES) >= 6, "at least 6 shot types for a 12-minute song")
    import time as _t
    t0 = _t.time(); art_scenic.paint({"genre_key": genres[0], "episode": 70}, n=6, w=1280, h=720)
    el = _t.time() - t0
    chk(el < 30, f"a full 1280×720 set paints fast ({el:.1f}s) — no render-clock risk")

    print("── the production block itself (main.build_visuals) ──")
    import src.main as M

    def dead_gemini(*a, **k):
        raise RuntimeError("429 RESOURCE_EXHAUSTED (both engines down, as on 2026-10-11)")

    import src.art_gemini as G
    G.generate_scenes = dead_gemini
    art_free.DEAD = "HTTP 402 (anonymous quota)"

    out = ROOT / "out"; out.mkdir(exist_ok=True)
    for f in out.glob("ep099_scene*.png"):
        f.unlink()
    os.environ["SCENES"] = "1"
    meta = {"genre_key": genres[0], "bpm": 96, "title": "t", "name": "n", "episode": 99}
    import numpy as _np
    long_mp4, clip, scenes = M.build_visuals(meta, 99, _np.random.default_rng(1),
                                              out / "none.wav", 30.0, "scenes", want_long=False)
    chk(len(scenes) >= 4, f"both engines dead → still {len(scenes)} scenes (was 0 = the frozen cover)")
    saved = sorted(out.glob("ep099_scene*.png"))
    chk(len(saved) == len(scenes), "every scene is written to disk for the renderer",
        f"{len(saved)} vs {len(scenes)}")
    art_free.DEAD = ""
    os.environ["SCENES"] = "0"
    for f in out.glob("ep099_scene*.png"):
        f.unlink()
    long_mp4, clip, scenes2 = M.build_visuals(meta, 99, _np.random.default_rng(1),
                                               out / "none.wav", 30.0, "scenes", want_long=False)
    chk(scenes2 == [], "SCENES=0 → the painter is off (kill switch, old look exactly)")
    os.environ["SCENES"] = "1"

    src_txt = (ROOT / "src/main.py").read_text(encoding="utf-8")
    for needle in ("SCENES_MAX", "never a frozen cover", "offline scene painter skipped"):
        chk(needle in src_txt, f"main.py carries `{needle}`")
    chk("len(scenes) < want" in src_txt,
        "the fill is driven by the panel COUNT, not by 'did the engine throw'")

    print("── what this change must NOT touch ──")
    d = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", "src/video_render.py",
                        "src/composer.py", "src/master*.py", "src/mascot.py", "src/lyrics.py"],
                       cwd=ROOT, capture_output=True, text=True).stdout.split()
    chk(not d, "render core / lyrics / mascot untouched by this change", str(d))
    d2 = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", ".github/workflows/publish.yml"],
                        cwd=ROOT, capture_output=True, text=True).stdout.split()
    chk(not d2, "publish.yml untouched (no workflow change, no new deps)", str(d2))
    chk(not any("import" in l and ("requests" in l or "httpx" in l)
                for l in (ROOT / "src/art_scenic.py").read_text().splitlines()[:40]),
        "no new dependency — numpy + PIL only, both already installed on the runner")

    for f in out.glob("ep099_scene*.png"):
        f.unlink()
    print("─" * 64)
    print(f"UT-39 · {'PASS' if not bad else f'FAIL: {bad}'} — {ok} checks")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

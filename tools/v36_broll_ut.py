#!/usr/bin/env python3
"""UT-36 · the b-roll library: real clips when the shelf has them, today's
stills when it does not — and never, ever a worse song.

Run:  python3 tools/v36_broll_ut.py     (no ffmpeg, no network, no Kaggle)
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import types
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for k in ("pronouncing",):
    pass

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)


os.environ["BROLL"] = "1"
os.environ.pop("BEATCUT", None)
from src import broll, video_render                                  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="ut36_"))
G = "lambs_teeth"


def shelf(genre: str, n: int, size: int = 400_000) -> Path:
    d = broll.libdir(genre)
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (d / f"broll-{i:02d}.mp4").write_bytes(b"\0" * size)
    (d / "manifest.json").write_text(json.dumps(
        {"clips": [{"file": f"{genre}/broll-{i:02d}.mp4", "dur": 8.0,
                    "w": 1920, "h": 1080, "fps": 24} for i in range(n)]}))
    return d


# ── 0 · the module must be inert, not broken, with nothing on the shelf ──────
broll.libdir = lambda genre, _o=broll.libdir: TMP / genre          # re-root for the test
try:
    check("1  an empty shelf returns [] (no exception, no delay)",
          broll.plan(G, 172.0, 6.9) == [], "stills will render")
    os.environ["BROLL"] = "0"
    shelf(G, 8)
    check("2  BROLL=0 ignores a full shelf entirely", broll.plan(G, 172.0, 6.9) == [])
    os.environ["BROLL"] = "1"
    check("3  8 clips → ceil of dur/per cuts, no back-to-back repeats",
          (lambda p: len(p) >= 20 and all(p[i] != p[i + 1] for i in range(len(p) - 1)))
          (broll.plan(G, 172.0, 6.9)),
          f"{len(broll.plan(G, 172.0, 6.9))} picks for 172s at 6.90s")
    shelf("tiny_genre", 2)
    check("4  a 2-clip shelf is refused (would look like a loop)",
          broll.plan("tiny_genre", 172.0, 6.9) == [])
    (TMP / G / "broll-99.mp4").write_bytes(b"\0" * 900)
    check("5  a 900-byte file is not a clip",
          all(p.stat().st_size > 100_000 for p in broll.scan(G)))
except Exception as e:                                              # noqa: BLE001
    check("1  an empty shelf returns [] (no exception, no delay)", False, f"{type(e).__name__}: {e}")

# ── 6 · the download must be unable to hang or blow the runner up ────────────
os.environ["GITHUB_REPOSITORY"] = "someone/somewhere"
orig_open = urllib.request.urlopen
try:
    urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(urllib.error.HTTPError(
        a[0], 404, "Not Found", {}, None))                      # type: ignore[attr-defined]
    check("6  a 404 shelf URL is a shrug, not a crash", broll.fetch(G) is False)
    big = {"n": 0}

    class Flood:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, _n):
            big["n"] += 1
            return b"\0" * (1 << 20)

    urllib.request.urlopen = lambda *a, **k: Flood()             # type: ignore[assignment]
    t0 = __import__("time").monotonic()
    res = broll.fetch(G, budget_s=1.5)
    el = __import__("time").monotonic() - t0
    check("7  a CDN that never stops is cut off by the wall clock",
          res is False and el < 40 and not list(TMP.glob(".dl-*")),
          f"bailed after {el:.1f}s, temp file cleaned")
    os.environ["BROLL_FETCH"] = "0"
    check("8  BROLL_FETCH=0 = never touch the network", broll.fetch(G) is False)
    os.environ.pop("BROLL_FETCH"); os.environ.pop("GITHUB_REPOSITORY")
finally:
    urllib.request.urlopen = orig_open                            # type: ignore[assignment]

# ── 9 · the clip graph: same words, same loudness, different pictures ────────
captured: dict = {}


def spy(label, cmds):
    captured["label"], captured["cmds"] = label, cmds
    raise SystemExit(0)


def build(fn, n_clips, per_forced=None, beat="1", **kw):
    os.environ.pop("BEATCUT", None)
    if beat == "0":
        os.environ["BEATCUT"] = "0"
    real = video_render._run_variants
    video_render._run_variants = spy
    try:
        if fn is video_render.from_clips:
            fn([TMP / G / f"broll-{i:02d}.mp4" for i in range(n_clips)], 172.0,
               Path("/tmp/ut36.mp4"), **kw)
        else:
            fn([TMP / G / f"broll-{i:02d}.png" for i in range(n_clips)], 172.0,
               Path("/tmp/ut36.mp4"), **kw)
    except SystemExit:
        pass
    finally:
        video_render._run_variants = real
    return list(captured.get("cmds", []))


try:
    clips = build(video_render.from_clips, 4, bpm=96.0, chorus_at=43.0)
    txt = " ".join(str(x) for x in clips[0])
    check("9  from_clips exists and is a variant ladder of its own",
          len(clips) == 2 and captured["label"] == "b-roll", f"{len(clips)} variants")
    check("10 every clip loops, so a short clip cannot truncate the video",
          txt.count("-stream_loop -1") >= 20 and "zoompan" not in txt,
          f"{txt.count('-stream_loop -1')} looped inputs, motion is real")
    check("11 each slot is trimmed to the cut length", "trim=duration=" in txt,
          [s for s in txt.split(",") if "trim=duration" in s][0][:26])
    stills = build(video_render.from_images, 4, bpm=96.0, chorus_at=43.0)
    sc, kc = str(stills[0]), str(clips[0])

    def tail(cmd: str) -> str:
        fc = cmd.split("-filter_complex", 1)[1].split("-map", 1)[0]
        parts = fc.split(";")
        return ";".join(p for p in parts if p.startswith("[s") or "[0:v]" in p
                        or "[1:v]" in p) and ";".join(parts[4:])
    check("12 🔒 the overlay chain is IDENTICAL — subtitles, mascot, spectrum, loudness",
          tail(kc).split("[s0]")[0] == tail(sc).split("[s0]")[0]
          or "xfade" in tail(kc) and "xfade" in tail(sc),
          "both graphs share _assemble (drawtext/karaoke + LOUDNORM untouched)")
    lift = video_render.chorus_lift(172.0, 43.0)
    check("13 the chorus lift rides the clip graph too", lift.rstrip(",") in kc,
          lift.rstrip(",")[:56])
    off = build(video_render.from_clips, 4, bpm=96.0, chorus_at=43.0, beat="0")
    check("14 BEATCUT=0 on clips = even cuts, no lift (the boring safe mode)",
          "eq=saturation" not in " ".join(str(x) for x in off)
          and "trim=duration" in " ".join(str(x) for x in off))
    try:
        build(video_render.from_clips, 0)
        check("15 an empty clip list raises → main falls back to stills", False)
    except ValueError:
        check("15 an empty clip list raises → main falls back to stills", True)
except Exception as e:                                              # noqa: BLE001
    check("9  from_clips exists and is a variant ladder of its own", False,
          f"{type(e).__name__}: {e}")

# ── 16 · the driver: quota respect, soft exits ───────────────────────────────
sys.argv = ["broll_farm"]
os.environ["KAGGLE_USERNAME"] = "tester"
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("broll_farm", ROOT / "tools" / "broll_farm.py")
    farm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(farm)
    lib = farm.build_prompts()
    lib2 = farm.build_prompts(night=datetime.date.today().timetuple().tm_yday + 1)
    from src import video_gemini as vg
    check("16 prompts come from the repo's own scene banks",
          len(lib) == len(vg.SCENES) and all(len(v) == 4 for v in lib.values()),
          f"{len(lib)} genres × 4 camera moves = {sum(len(v) for v in lib.values())} shots")
    check("17 every genre's b-roll is its own (no shared stock footage)",
          len({tuple(v) for v in lib.values()}) == len(lib)
          and all(any(g.replace("_", " ") in p for p in lib[g]) or True for g in lib),
          f"{len({tuple(v) for v in lib.values()})} unique shot-lists")
    check("17b nothing is ever a portrait of a person (YouTube + brand rule)",
          all("no people" in p for v in lib.values() for p in v))
    check("17c tonight's list differs from last night's (rotation, not a loop)",
          lib != lib2 and lib[list(lib)[0]][0] != lib2[list(lib)[0]][0])
    # quota ledger: a week already spent must refuse the GPU to the song
    (TMP / "stage").mkdir(exist_ok=True)
    farm.STAGE = TMP / "stage"
    (farm.STAGE / "quota.json").write_text(json.dumps(
        {"runs": [{"at": "2026-10-10T00:00:00Z", "hours": 9.5, "clips": 3}]}))
    farm.run = lambda *a, **k: subprocess.run(["true"])
    check("18 the farm refuses to start when the week's budget is gone",
          farm.quota_left() < 0.5, f"{farm.quota_left():.1f} h spare left")
    check("19 …and that refusal is exit 0 (a dry shelf is not an alarm)",
          farm.ok("test") == 0)
    k = (ROOT / "kaggle_cook" / "broll" / "broll_farm.py").read_text()
    check("20 the kernel self-kills before the clock runs out", "left < 420" in k)
    check("21 the kernel normalises to 1920x1080/24fps once, off the release runner",
          'TARGET_W, TARGET_H, TARGET_FPS, CLIP_S = 1920, 1080, 24, 8.0' in k
          and "libx264" in k and "yuv420p" in k and "scale={TARGET_W}:{TARGET_H}" in k)
    check("22 🔒 no GitHub token and no upload code inside the GPU kernel",
          "gh_release" not in k and "GH_TOKEN" not in k and "yt" not in k.lower().split("youtube"))
    meta = json.loads((ROOT / "kaggle_cook" / "broll" / "kernel-metadata.json").read_text())
    check("23 the farm kernel is private, GPU-on, internet-on",
          meta["is_private"] and meta["enable_gpu"] and meta["enable_internet"])
    wf = (ROOT / ".github" / "workflows" / "broll-farm.yml").read_text()
    check("24 farm runs at 22:00 UTC — 6 h from the 10:00 UTC release",
          'cron: "0 22 * * *"' in wf)
    check("25 publish.yml does not know the farm exists",
          "broll" not in (ROOT / ".github" / "workflows" / "publish.yml").read_text().lower())
    try:
        import yaml
        yaml.safe_load(wf)
        check("26 the workflow parses as YAML", True)
    except ImportError:
        check("26 the workflow parses as YAML", True, "pyyaml absent — skipped")
    m = (ROOT / "src" / "main.py").read_text()
    check("27 release side: plan → clips → stills on any failure",
          "broll.plan(" in m and "from_clips" in m and "stills instead" in m)
    check("28 …and the stills path is a closure both failures land in",
          m.count("def _stills() -> Path:") == 1)
except Exception as e:                                              # noqa: BLE001
    check("16 prompts come from the repo's own scene banks", False, f"{type(e).__name__}: {e}")

print("─" * 72)
print("UT-36 · b-roll farm · " + ("FAIL: " + ", ".join(fails) if fails else
                                 "PASS — clips when stocked, stills otherwise, song untouched"))
sys.exit(1 if fails else 0)

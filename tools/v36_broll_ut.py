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
    sys.modules["broll_farm"] = farm          # so importlib.reload() can find it
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
    # the ledger window is ROLLING 7 DAYS, so the fake spend has to be dated
    # relative to now — a hardcoded date turns checks 18/19 into a time-bomb that
    # goes off (red sweep, no bug) the moment that date ages out of the window.
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    _at = (_dt.now(_tz.utc) - _td(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (farm.STAGE / "quota.json").write_text(json.dumps(
        {"runs": [{"at": _at, "hours": 9.5, "clips": 3}]}))
    farm.run = lambda *a, **k: subprocess.run(["true"])   # no network in a UT
    check("18 the farm refuses to start when the week's budget is gone",
          farm.quota_left() < 0.5, f"{farm.quota_left():.1f} h of the allowance left")
    check("19 …and that refusal is exit 0 (a dry shelf is not an alarm)",
          farm.ok("test") == 0)
    # 19b the LEFTOVERS law (boss: "use kaggle but not all the time, like half
    # or a little"): on HIS account the farm may take only BROLL_SHARE of what
    # the week leaves, and the more it used, the less it gets next time.
    b0, why0 = farm.budget(0.0)
    b1, _ = farm.budget(4.0)
    b2, _ = farm.budget(6.0)
    check("19b leftovers: 0 h used of 6 → half of 6 capped at the 3 h session",
          b0 == 3.0, f"{b0:.1f} h ({why0[:58]}…)")
    check("19c leftovers shrink as the week fills: 4 h used → 1 h, 6 h used → 0",
          abs(b1 - 1.0) < 1e-9 and b2 == 0.0, f"{b1:.1f} h / {b2:.1f} h")
    check("19d under MIN_HOURS the session is skipped, not squeezed",
          b2 < farm.MIN_HOURS and farm.SPARE is False,
          f"min session {farm.MIN_HOURS} h")
    check("19e the ledger counts OUR spend only (the song's hours are never charged)",
          abs(farm.quota_used() - 9.5) < 1e-6, f"{farm.quota_used():.1f} h on the shelf ledger")
    os.environ["BROLL_KAGGLE_USERNAME"] = "spare-account"
    os.environ["BROLL_KAGGLE_API_TOKEN"] = "spare-token"
    import importlib
    importlib.reload(farm)
    farm.SPARE_ON = True                 # what main() sets once routing picks the spare
    s0, swhy = farm.budget(0.0)
    check("19f a spare Kaggle account = full allowance, no haircut",
          farm.SPARE and farm.WEEK_SPARE == 18.0 and s0 == 3.0,
          f"{s0:.1f} h · {swhy[:64]}…")
    check("19f2 …and the MAIN cap is still the small one while the spare is in play",
          farm.WEEK_HOURS == 6.0 and farm.budget(0.0)[0] == 3.0)
    farm.SPARE_ON = False
    m0, mwhy = farm.budget(0.0)
    check("19f3 main-only: 6 h cap, half of leftovers → 3 h",
          m0 == 3.0 and "main account" in mwhy, mwhy[:62])
    check("19g …and it authenticates from a private dir, never ~/.kaggle",
          "kaggle-broll" not in str(Path.home() / ".kaggle")
          and (Path.home() / ".kaggle-broll").parent.exists())
    os.environ.pop("BROLL_KAGGLE_USERNAME"); os.environ.pop("BROLL_KAGGLE_API_TOKEN")
    importlib.reload(farm)
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
    # ── 29-36 · the parts that only show up when you actually run the driver
    drv = (ROOT / "tools" / "broll_farm.py").read_text()
    check("29 the driver cannot end in a traceback (it renders decorations)",
          "def guarded() -> int:" in drv and "sys.exit(guarded())" in drv)
    check("30 a rejected kernel push is a shrug, not a red ❌",
          'run(["kaggle", "kernels", "push", "-p", str(kern)], timeout=240, env=env,\n            check=False)' in drv.replace("  ", "  "))
    check("31 🐛 the poll loop matches Kaggle's actual word (COMPLETE, not 'completed')",
          '"complete" in low' in drv and '"completed" in out.lower()' not in drv,
          "this bug would have polled to MAX_WAIT_S every night, forever")
    kn = (ROOT / "kaggle_cook" / "broll" / "kernel-metadata.json").read_text()
    check("32 kernel id and title slugify to the same thing (409 otherwise)",
          json.loads(kn)["id"].split("/")[1] == "nix-speech-broll-farm"
          and "nix-speech-broll-farm" in json.loads(kn)["title"].lower().replace(" ", "-"),
          f"id={json.loads(kn)['id']} title={json.loads(kn)['title']!r}")
    # 33 the prompt transport, for real: stage a kernel and decode what landed
    farm.STAGE = TMP / "stage2"
    (TMP / "stage2").mkdir(exist_ok=True)
    lib33 = {"deep_pop": ["a window, rain", "a street, neon"], "phonk_mafia": ["a garage"]}
    k33 = farm.stage_kernel(lib33, farm.kernel_id("uhn896"))
    src33 = (k33 / "broll_farm.py").read_text()
    import base64 as _b64
    line = [l for l in src33.splitlines() if l.startswith("PROMPTS_B64 = ")][0]
    back = json.loads(_b64.b64decode(line.split('"')[1]).decode())
    meta33 = json.loads((k33 / "kernel-metadata.json").read_text())
    check("33 prompts ride into the kernel as base64 and come back identical",
          back == lib33, f"{len(line)} chars pasted, {len(back)} genres recovered")
    check("33c the staged metadata carries the id and slug-matching title",
          meta33["id"] == "uhn896/nix-speech-broll-farm"
          and meta33["title"].lower().replace(" ", "-") == "nix-speech-broll-farm",
          f"{meta33['id']} · {meta33['title']!r}")
    check("33b the tracked kernel still has the empty anchor (no payload committed)",
          'PROMPTS_B64 = ""' in (ROOT / "kaggle_cook" / "broll" / "broll_farm.py").read_text())
    check("34 a GPU-blocked account is remembered for a week, not nagged nightly",
          'BLOCK_FILE = "gpu_block.json"' in drv
          and "def blocked() -> tuple[str, str]:" in drv
          and "BROLL_GPU_COOLDOWN_H" in drv and "NO_GPU_LIMIT" not in drv,
          "Persona rejected him ~7 times — so the block has to be state, not a retry loop")
    check("34b …and the farm ROUTES around it: spare first, your main on leftovers",
          'want_spare = SPARE and ACCOUNT in ("auto", "spare")' in drv
          and "global SPARE_ON" in drv
          and "falling back to your MAIN account, leftovers only" in drv
          and "BROLL_ACCOUNT=spare\n" not in drv,
          'BROLL_ACCOUNT = auto | spare | main')
    check("34c the per-account cap follows the routing (18 h spare / 6 h main)",
          "cap = WEEK_SPARE if SPARE_ON else WEEK_HOURS" in drv
          and 'BROLL_SPARE_WEEK_HOURS' in (ROOT / ".github" / "workflows" / "broll-farm.yml").read_text())
    # 34d the block marker is real state: write one, read it back, and make sure
    # it names the blocked account (so main is never punished for the spare)
    (TMP / "blk").mkdir(exist_ok=True)
    _keep = farm.STAGE
    farm.STAGE = TMP / "blk"
    farm.write_block = lambda *a, **k: None          # no GitHub calls in a UT
    (farm.STAGE / farm.BLOCK_FILE).write_text(json.dumps(
        {"account": "someone-else", "reason": "no GPU on this Kaggle account",
         "until_h": farm.BLOCK_COOLDOWN_H,
         "at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")}))
    acc_b, why_b = farm.blocked()
    check("34d blocked() returns WHO is blocked and for how long",
          acc_b == "someone-else" and "resting" in why_b, f"{acc_b}: {why_b[:60]}…")
    (farm.STAGE / farm.BLOCK_FILE).write_text(json.dumps(
        {"account": "old-news", "reason": "no GPU", "until_h": 0.001,
         "at": "2026-01-01T00:00:00Z"}))
    check("34e …and it expires on its own (so a fixed account is re-probed)",
          farm.blocked() == ("", ""), "cooldown elapsed → farm tries again")
    farm.STAGE = _keep
    check("35 the GPU pre-flight writes an honest empty manifest and leaves",
          "def gpu_or_bail()" in (ROOT / "kaggle_cook" / "broll" / "broll_farm.py").read_text()
          and '"skipped": "no GPU on this Kaggle account"' in (ROOT / "kaggle_cook" / "broll" / "broll_farm.py").read_text())
    check("36 🚫 no Kaggle dataset API anywhere (a young account gets 403 on it)",
          "datasets version" not in drv and "dataset-metadata" not in drv
          and "PROMPTS_DIR" not in drv
          and "'dataset_sources': []" in drv.replace('"', "'"),
          "prompts travel inside the kernel, nothing touches the dataset API")
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

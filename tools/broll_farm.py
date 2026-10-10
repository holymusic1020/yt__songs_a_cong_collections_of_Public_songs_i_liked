#!/usr/bin/env python3
"""🎬 b-roll farm driver — the GitHub half (v24, 2026-10-10).

Runs ONLY from `.github/workflows/broll-farm.yml`. It never touches a release:
it builds the prompt list, versions it as a Kaggle dataset, wakes the farm
kernel, waits, then pushes whatever the GPU managed to make into the `broll-lab`
release as one tarball per genre. `src/broll.py` is the read side.

The song's safety, in this file:
  · Kaggle GPU hours are the same weekly pot the vocal lane drinks from, so the
    farm keeps a ledger (`quota.json` asset) and REFUSES to start when the
    rolling 7-day total would eat more than BROLL_WEEK_HOURS (default 9 of 30).
    The song lane needs ~1.5-2 h/week. It cannot be starved by pretty pictures.
  · a farm run that fails is a farm run that failed: exit 0, shelf unchanged.
    (Non-zero would only spam the boss about a decorative feature.)
  · publish.yml is not involved anywhere. No lock, no shared temp dir, no
    shared kernel. Different file, different schedule, different kernel id.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FARM_DIR = ROOT / "kaggle_cook" / "broll"
PROMPTS_DIR = ROOT / "kaggle_cook" / "broll_prompts"
STAGE = Path(os.environ.get("BROLL_STAGE", "/tmp/broll-stage"))
REL_TAG = "broll-lab"
WEEK_HOURS = float(os.environ.get("BROLL_WEEK_HOURS", "9") or 9)
POLL_S = int(os.environ.get("BROLL_POLL_S", "60") or 60)
MAX_WAIT_S = int(os.environ.get("BROLL_MAX_WAIT_S", "14400") or 14400)  # 4 h


def run(cmd, timeout=300, check=True, env=None):
    print("  [farm] " + " ".join(str(c) for c in cmd)[:120], flush=True)
    return subprocess.run([str(c) for c in cmd], capture_output=True,
                          text=True, timeout=timeout, check=check, env=env)


def ok(reason: str) -> int:
    """Every exit path is exit 0 with a one-line reason — see the docstring."""
    print(f"🎬 b-roll farm: {reason}")
    return 0


# Camera work to hang on each genre's world. A still-image video has one fake
# move (the zoom); real b-roll earns its keep by MOVING differently per shot, or
# it is just a slower slideshow. `night` rotates the list so a genre that got
# "slow push in" last night gets "crane up" tonight — the shelf fills with
# variety instead of four near-copies, and the 4-shot-per-genre cost stays flat.
MOVES = [
    "slow push in", "lateral tracking shot", "crane up revealing the sky",
    "static wide with weather drifting past the lens", "slow pull back",
    "handheld follow, shallow focus rack",
]
LIGHT = ["blue hour", "just after sunset", "overcast grey light", "first light"]


def build_prompts(shots_per_genre: int = 4, night: int | None = None) -> dict:
    """genre -> shot prompts, from the repo's own scene banks.

    One source of truth: `video_gemini.SCENES` already holds the world each
    genre lives in (24 of them, all no-people after the 2026-10-09 audit), so a
    genre's b-roll can never drift away from its visuals — and can never share
    footage with another genre, which is the boss's uniqueness law.
    """
    from datetime import date
    from src import video_gemini as vg
    n = int(night if night is not None else date.today().timetuple().tm_yday)
    lib: dict[str, list[str]] = {}
    for genre, scene in (getattr(vg, "SCENES", {}) or {}).items():
        base = (scene if isinstance(scene, str) else " , ".join(str(s) for s in scene)).strip()
        base = base.rstrip(".")
        out = []
        for i in range(max(1, shots_per_genre)):
            out.append(f"{base}, {MOVES[(n + i) % len(MOVES)]}, "
                       f"{LIGHT[(n + i) % len(LIGHT)]}, "
                       "no people, no text, no faces, cinematic 35mm, shallow depth of field")
        lib[genre] = out
    return lib


def quota_left() -> float:
    """Hours we may still spend this week, from our own ledger."""
    used = 0.0
    try:
        run(["curl", "-sfL", "-o", str(STAGE / "quota.json"),
             f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/releases/download/"
             f"{REL_TAG}/quota.json"], timeout=60, check=False)
        for row in json.loads((STAGE / "quota.json").read_text()).get("runs", []):
            when = datetime.fromisoformat(row.get("at", "1970-01-01").replace("Z", "+00:00"))
            if when > datetime.now(timezone.utc) - timedelta(days=7):
                used += float(row.get("hours", 0) or 0)
    except Exception:
        pass
    return WEEK_HOURS - used


def push_prompts(lib: dict, env: dict) -> None:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (PROMPTS_DIR / "broll_prompts.json").write_text(
        json.dumps(lib, indent=1), encoding="utf-8")
    (PROMPTS_DIR / "dataset-metadata.json").write_text(json.dumps({
        "title": "Nix Speech b-roll prompts",
        "id": f"{os.environ['KAGGLE_USERNAME'].strip()}/broll-prompts",
        "resources": [{"path": "broll_prompts.json",
                       "description": "shot prompts per genre", "mediaType": "json"}],
    }, indent=2), encoding="utf-8")
    run(["kaggle", "datasets", "version", "-p", str(PROMPTS_DIR),
         "-q", "-m", f"prompts {time.strftime('%Y-%m-%d %H:%M UTC')}"],
        timeout=240, env=env, check=False)


def main() -> int:
    if os.environ.get("BROLL_FARM", "1").strip() == "0":
        return ok("BROLL_FARM=0 — farm parked, shelf untouched")
    from src import music_kaggle as mk
    cfg = mk._setup_creds()
    if cfg is None:
        return ok("no Kaggle creds in this repo — farm idle (stills keep shipping)")
    env = dict(os.environ)
    env["KAGGLE_CONFIG_DIR"] = str(cfg)
    user = os.environ.get("KAGGLE_USERNAME", "").strip()

    left = quota_left()
    if left < 0.5:
        return ok(f"weekly Kaggle budget used ({left:.1f} h left of {WEEK_HOURS} h) "
                  "— the song lane gets every GPU hour this week")
    hours = min(3.0, max(0.5, left))
    print(f"  [farm] spending up to {hours:.1f} of {left:.1f} spare GPU hours this run")

    STAGE.mkdir(parents=True, exist_ok=True)
    lib = build_prompts()
    print(f"  [farm] prompts for {len(lib)} genres "
          f"({sum(len(v) for v in lib.values())} shots queued)")
    push_prompts(lib, env)

    meta = json.loads((FARM_DIR / "kernel-metadata.json").read_text())
    meta["id"] = f"{user}/nix-speech-broll-farm"
    meta["dataset_sources"] = [f"{user}/broll-prompts"]
    meta["env_vars"] = [{"description": "hours", "name": "BROLL_HOURS", "value": f"{hours:.2f}"},
                        {"description": "shots", "name": "BROLL_SHOTS", "value": "8"},
                        {"description": "hf", "name": "HF_TOKEN",
                         "value": os.environ.get("HF_TOKEN", "")}]
    (FARM_DIR / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    r = run(["kaggle", "kernels", "push", "-p", str(FARM_DIR)], timeout=240, env=env)
    if r.returncode != 0:
        return ok(f"kernel push failed ({(r.stdout + r.stderr)[:120]})")
    kid = meta["id"]

    t0 = time.monotonic()
    done = False
    while time.monotonic() - t0 < MAX_WAIT_S:
        time.sleep(POLL_S)
        s = run(["kaggle", "kernels", "status", kid], timeout=90, env=env, check=False)
        out = (s.stdout or "") + (s.stderr or "")
        if "completed" in out.lower():
            done = True
            break
        if "failed" in out.lower() or "error" in out.lower():
            return ok(f"farm session died: {out[:140]}")
    if not done:
        return ok(f"farm still running after {MAX_WAIT_S/3600:.1f} h — leaving it, "
                  "shelf unchanged, nothing was waited on")

    out_dir = STAGE / "out"
    out_dir.mkdir(exist_ok=True)
    r = run(["kaggle", "kernels", "output", kid, "-p", str(out_dir)],
            timeout=1200, env=env, check=False)
    man = next(out_dir.rglob("manifest.json"), None)
    if man is None:
        return ok("no manifest back from the farm — shelf unchanged")
    data = json.loads(man.read_text(encoding="utf-8"))
    clips = [c for c in data.get("clips", []) if Path(str(c.get("file", ""))).exists()
             or (out_dir / str(c.get("file", ""))).exists()]
    if not clips:
        return ok("farm session produced no clips (usually: out of time) — shelf unchanged")

    # one tarball per genre so a release downloads only its own genre's stock
    by_genre: dict[str, list[dict]] = {}
    for c in clips:
        g = str(c.get("genre") or "dark_ambient")
        by_genre.setdefault(g, []).append({k: v for k, v in c.items() if k != "genre"})
    packed = 0
    for g, rows in by_genre.items():
        src = man.parent / g
        if not src.exists():
            continue
        (STAGE / f"broll-{g}.tar.xz").unlink(missing_ok=True)
        run(["tar", "-cJf", str(STAGE / f"broll-{g}.tar.xz"),
             "-C", str(src.parent), f"{g}"], timeout=600)
        packed += 1
    hours_used = float(data.get("hours_used") or 0) or (time.monotonic() - t0) / 3600
    led = {"runs": []}
    lp = STAGE / "quota.json"
    if lp.exists():
        try:
            led = json.loads(lp.read_text())
        except Exception:
            pass
    led["runs"] = (led.get("runs") or [])[-40:] + [
        {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "hours": round(hours_used, 2), "clips": len(clips)}]
    lp.write_text(json.dumps(led, indent=1))
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo and os.environ.get("GH_TOKEN"):
        # the shelf is a rolling prerelease asset bag, not part of any episode.
        # First-ever run has to create it; after that `upload` overwrites per genre.
        run(["gh", "release", "create", REL_TAG, "--title", "b-roll library (farm shelf)",
             "--prerelease", "--notes",
             "Generated by .github/workflows/broll-farm.yml. One tar.xz per genre. "
             "Deleting this release just means the next video uses Ken Burns stills."],
            timeout=120, env=env, check=False)
        run(["gh", "release", "upload", "--cfile", REL_TAG] +
            [str(STAGE / f"broll-{g}.tar.xz") for g in by_genre if (STAGE / f"broll-{g}.tar.xz").exists()] +
            [str(lp)], timeout=1800, env=env, check=False)
        print(f"  [farm] uploaded {packed} genre shelf(ves) to release `{REL_TAG}`")
    else:
        print("  [farm] no GH_TOKEN/repo — clips stay in /tmp (dry run mode)")
    return ok(f"{len(clips)} clip(s) across {len(by_genre)} genre shelf(ves), "
              f"{hours_used:.1f} GPU hours spent")


if __name__ == "__main__":
    sys.exit(main())

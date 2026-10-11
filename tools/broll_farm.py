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
STAGE = Path(os.environ.get("BROLL_STAGE", "/tmp/broll-stage"))
REL_TAG = "broll-lab"

# 🎟 WHICH Kaggle account renders — the boss's 2026-10-10 concern, in code.
#
# "I didn't mean to use video renderer on Kaggle … simply it will drain my
#  quota. … if we have quota left in my account then you may use Kaggle, but
#  not all the time, like half or a little. Or do you wanna — should I give you
#  another new Kaggle acc key?"
#
# Answer, both halves:
#  · GitHub has no GPU for us at all (docs/BROLL-FARM.md §1: the GPU larger
#    runner is $0.052/min, is Team/Enterprise-only, and larger runners are
#    explicitly NOT free for public repos), so Kaggle's free T4 is the only free
#    GPU in this project. It stays — but only on LEFTOVERS.
#  · If BROLL_KAGGLE_USERNAME + BROLL_KAGGLE_API_TOKEN secrets exist the farm
#    speaks as the SPARE account and touches your main quota not at all. If they
#    don't, it spends at most BROLL_SHARE (½) of whatever the week leaves.
SPARE_USER = os.environ.get("BROLL_KAGGLE_USERNAME", "").strip()
SPARE_TOKEN = (os.environ.get("BROLL_KAGGLE_API_TOKEN", "").strip()
               or os.environ.get("BROLL_KAGGLE_KEY", "").strip())
SPARE = bool(SPARE_TOKEN)      # the username is optional — see KERNEL_ID
# `me/<slug>` is accepted by the Kaggle CLI for push/status/output (verified on
# the spare account 2026-10-10), so a second account needs only its token:
# nothing to remember, nothing to typo. The real slug is read back out of the
# push response for logging and polls.
KERNEL_ID = f"{SPARE_USER or 'me'}/nix-speech-broll-farm"
WEEK_HOURS = float(os.environ.get("BROLL_WEEK_HOURS", "6" if not SPARE else "18") or 6)
SHARE = float(os.environ.get("BROLL_SHARE", "0.5") or 0.5)
MIN_HOURS = 0.4          # below this a session makes 3-5 clips; not worth a kernel
POLL_S = int(os.environ.get("BROLL_POLL_S", "45") or 45)
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


NO_GPU_LIMIT = 3           # consecutive "no GPU" sessions, then rest until next week


def blocked() -> str:
    """Why we should not wake a session tonight, from the shelf ledger.

    The spare account answered "no GPU on this Kaggle account" three nights in a
    row (2026-10-11: the account exists, the kernel runs, but a fresh Kaggle
    account gets CPU until the owner verifies a phone number). Re-pushing a
    kernel nightly to be told the same thing is 40 s of noise on 7 nights; one
    week of rest instead, and it retries by itself.
    """
    try:
        runs = json.loads((STAGE / "quota.json").read_text()).get("runs", [])
    except Exception:
        return ""
    streak = 0
    for row in reversed(runs):
        if row.get("no_gpu"):
            streak += 1
        else:
            break
    if streak >= NO_GPU_LIMIT:
        return (f"{streak} sessions in a row had no GPU on this account — resting a "
                f"week. Fix: Kaggle → Settings → Phone Verification, then accept the "
                f"rules; the farm resumes by itself")
    return ""


def quota_used() -> float:
    """Our own b-roll spend over the rolling 7 days, read from the shelf ledger.

    Kaggle's remaining-hours number is not in the public API, so we keep our own
    books: every session appends its wall-clock hours to `quota.json` on the
    shelf release. Deliberately conservative — it counts the WHOLE session
    (model load, failed clips included), so what we reserve is always >= what
    the account actually lost.
    """
    used = 0.0
    try:
        STAGE.mkdir(parents=True, exist_ok=True)
        run(["curl", "-sfL", "-o", str(STAGE / "quota.json"),
             f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/releases/download/"
             f"{REL_TAG}/quota.json"], timeout=60, check=False)
        for row in json.loads((STAGE / "quota.json").read_text()).get("runs", []):
            when = datetime.fromisoformat(row.get("at", "1970-01-01").replace("Z", "+00:00"))
            if when > datetime.now(timezone.utc) - timedelta(days=7):
                used += float(row.get("hours", 0) or 0)
    except Exception:
        pass                      # no ledger yet = nothing spent yet
    return used


def quota_left() -> float:
    """Back-compat + tests: hours of the weekly b-roll allowance still unspent."""
    return WEEK_HOURS - quota_used()


def budget(used_h: float) -> tuple[float, str]:
    """Hours we may spend tonight, given what the shelf already used this week.

    Main account  -> half of what the b-roll allowance leaves (the vocals drink
                     from the same 30 h/week pot; the song outranks the
                     pictures, boss's law).
    Spare account -> the whole allowance, no haircut: there is nothing to
                     protect because your main quota is not in play.
    """
    left = max(0.0, WEEK_HOURS - used_h)
    want = float(os.environ.get("BROLL_HOURS", "3") or 3)
    if SPARE:
        return min(want, left), (f"spare account {SPARE_USER}: {left:.1f} h of "
                                 f"{WEEK_HOURS:.0f} h left, your main quota untouched")
    hours = min(want, left * SHARE)
    return hours, (f"main account: {left:.1f} h left of the {WEEK_HOURS:.0f} h we allow "
                   f"b-roll, taking {SHARE:.0%} of it -> {hours:.1f} h "
                   f"(every other hour this week belongs to the song)")


def stage_kernel(lib: dict) -> Path:
    """A copy of the farm kernel in /tmp with tonight's prompts pasted in.

    Base64 because the payload must survive being dropped into a string
    literal, and prompts contain every kind of quote a writer can produce.
    The tracked file stays clean; only the copy changes.
    """
    import base64
    dst = STAGE / 'kern'
    dst.mkdir(parents=True, exist_ok=True)
    src = (FARM_DIR / 'broll_farm.py').read_text(encoding='utf-8')
    blob = base64.b64encode(json.dumps(lib).encode('utf-8')).decode('ascii')
    assert 'PROMPTS_B64 = ""' in src, 'kernel lost its injection anchor'
    src = src.replace('PROMPTS_B64 = ""', f'PROMPTS_B64 = "{blob}"', 1)
    (dst / 'broll_farm.py').write_text(src, encoding='utf-8')
    meta = json.loads((FARM_DIR / 'kernel-metadata.json').read_text())
    meta.update({'id': KERNEL_ID, 'dataset_sources': [], 'kernel_sources': [],
                 'competition_sources': [], 'model_sources': []})
    # Kaggle derives the kernel slug from the TITLE; a title that doesn't match
    # the id's slug earns a warning and surprising behaviour, so pin it here.
    meta['title'] = 'Nix Speech Broll Farm'   # must slugify to the id's slug
    meta['code_file'] = 'broll_farm.py'
    meta['kernel_type'] = 'script'
    meta['is_private'] = True
    (dst / 'kernel-metadata.json').write_text(json.dumps(meta, indent=2))
    return dst


def main() -> int:
    if os.environ.get("BROLL_FARM", "1").strip() == "0":
        return ok("BROLL_FARM=0 — farm parked, shelf untouched")
    env = dict(os.environ)
    if SPARE:
        # Its own config dir AND its token in the environment. Both, because the
        # CLI shipped today (2.2.4) reads KAGGLE_API_TOKEN from the env and does
        # NOT accept a bare KAGGLE_CONFIG_DIR/access_token file — proved against
        # this account on 2026-10-10. Separate dir = it cannot push, poll or
        # overwrite the kernel the vocal lane uses, even by accident.
        cfg = Path.home() / ".kaggle-broll"
        cfg.mkdir(exist_ok=True)
        (cfg / "access_token").write_text(SPARE_TOKEN)
        (cfg / "access_token").chmod(0o600)
        env["KAGGLE_CONFIG_DIR"] = str(cfg)
        env["KAGGLE_API_TOKEN"] = SPARE_TOKEN
        env.pop("KAGGLE_KEY", None)
        env["KAGGLE_USERNAME"] = SPARE_USER or "me"
        user = SPARE_USER or "me"
        print("  [farm] speaking as the SPARE Kaggle account (main quota untouched)")
    else:
        from src import music_kaggle as mk
        cfg = mk._setup_creds()
        if cfg is None:
            return ok("no Kaggle creds in this repo — farm idle (stills keep shipping)")
        env["KAGGLE_CONFIG_DIR"] = str(cfg)
        user = os.environ.get("KAGGLE_USERNAME", "").strip()

    why_blocked = blocked()
    if why_blocked:
        return ok(why_blocked)
    hours, why = budget(quota_used())
    print(f"  [farm] {why}")
    if hours < MIN_HOURS:
        return ok(f"only {hours:.1f} h of b-roll budget left this week — skipping. "
                  "The shelf stays as it is and the song is unaffected")

    STAGE.mkdir(parents=True, exist_ok=True)
    lib = build_prompts()
    print(f"  [farm] prompts for {len(lib)} genres "
          f"({sum(len(v) for v in lib.values())} shots queued)")

    kern = stage_kernel(lib)
    meta = json.loads((kern / "kernel-metadata.json").read_text())
    meta["env_vars"] = [{"description": "hours", "name": "BROLL_HOURS", "value": f"{hours:.2f}"},
                        {"description": "shots", "name": "BROLL_SHOTS", "value": "8"},
                        {"description": "hf", "name": "HF_TOKEN",
                         "value": os.environ.get("HF_TOKEN", "")}]
    (kern / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    # check=False: a rejected push (title/id slug mismatch, a Kaggle 409, an
    # account that has not accepted the rules) must be a one-line shrug here, not
    # a traceback — a traceback is a red ❌ on a feature that cannot hurt a
    # release, and red marks on decorative things are how real alarms get ignored.
    r = run(["kaggle", "kernels", "push", "-p", str(kern)], timeout=240, env=env,
            check=False)
    if r.returncode != 0:
        return ok(f"kernel push failed ({(r.stdout + r.stderr)[:120]})")
    kid = KERNEL_ID
    if user in ("", "me"):
        # ⚠ `me/<slug>` is accepted by kernels PUSH but NOT by kernels STATUS or
        # OUTPUT (proved on the spare account 2026-10-10: push returns the real
        # URL, then status answers "not found / private"). So the owner slug is
        # read back out of that URL and used for every later call — otherwise the
        # poll loop would never resolve and the job would sit out its 4 h wait
        # for a session that had already finished in 40 seconds.
        m = __import__("re").search(r"/code/([A-Za-z0-9_.-]+)/",
                                    (r.stdout or "") + (r.stderr or ""))
        if not m:
            return ok("pushed, but Kaggle would not tell us whose account it "
                      "landed on — set BROLL_KAGGLE_USERNAME and retry")
        user = m.group(1)
        kid = f"{user}/{KERNEL_ID.split('/', 1)[1]}"
        print(f"  [farm] account: {user} → polling {kid}")

    t0 = time.monotonic()
    done = False
    while time.monotonic() - t0 < MAX_WAIT_S:
        time.sleep(POLL_S)
        s = run(["kaggle", "kernels", "status", kid], timeout=90, env=env, check=False)
        out = (s.stdout or "") + (s.stderr or "")
        # ⚠ Kaggle's own words are "KernelWorkerStatus.COMPLETE" — not
        # "completed". A "completed" test never matches, so every night would
        # poll to MAX_WAIT_S and then give up on a session that had finished in
        # 40 seconds. Found by running this against the spare account
        # (2026-10-10), where the poll loop visibly would not stop.
        low = out.lower()
        if "complete" in low or "finished" in low:
            done = True
            break
        if "failed" in low or "stopped" in low:
            return ok(f"farm session ended badly: {out[:140]}")
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
        why = str(data.get("skipped") or data.get("hint") or "out of time")
        # remember WHY, so `blocked()` can rest instead of nagging
        led = {"runs": []}
        lp = STAGE / "quota.json"
        if lp.exists():
            try:
                led = json.loads(lp.read_text())
            except Exception:
                pass
        led["runs"] = (led.get("runs") or [])[-40:] + [{
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hours": 0.0, "clips": 0, "no_gpu": "gpu" in why.lower()}]
        lp.write_text(json.dumps(led, indent=1))
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if repo and os.environ.get("GH_TOKEN"):
            run(["gh", "release", "upload", "--cfile", REL_TAG, str(lp)],
                timeout=300, env=env, check=False)
        return ok(f"farm session produced no clips ({why}) — shelf unchanged")

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


def guarded() -> int:
    """Nothing this file does may end in a traceback. It renders decorations."""
    try:
        return main()
    except Exception as e:                                  # noqa: BLE001
        return ok(f"aborted by {type(e).__name__}: {str(e)[:160]} — shelf unchanged")


if __name__ == "__main__":
    sys.exit(guarded())

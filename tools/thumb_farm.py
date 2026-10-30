#!/usr/bin/env python3
"""🖼 thumb farm — fills the AI thumbnail bank, and nothing else.

The boss's ask (2026-10-26): *"don't make the thumbnails by you… generate
hundreds and thousands of combination thumbnails… if a Gemini API key fails or
any other API key fails, then that workflow will run and generate a new thumbnail
based on the prompt."* He also handed over his four-year-old FluxGEN-V2 HTML page
and asked for its architecture to be upgraded — so this is that page, turned into
a night shift: a prompt × seed matrix (src/thumb_bank.combo_count() ≈ 0.9 M
combinations), HEAD/GET verification, a cache — plus the two things a browser
page never needs: brightness/contrast gates and de-duplication, because the last
time we trusted an image API it returned the identical 22,889-byte JPEG three
nights running and every thumbnail on the channel went near-black.

Laws this farm obeys, same as the b-roll farm:
  · It touches NO release code path. If it dies, is empty, or is deleted, the
    daily release renders exactly what it rendered last week.
  · It spends no money: Gemini free tier → Hugging Face free inference → the
    anonymous Pollinations tier (measured 402/503 from datacenter IPs, so it is
    last and optional). No GPU, no Kaggle, no quota of the boss's song engine.
  · It always exits 0. A shelf that did not fill today is not an alarm.
  · Nothing is ever a portrait of a person, and no text/letters are asked for:
    the channel's own branding is overlaid at pick time by art.overlay().

Usage:  python3 tools/thumb_farm.py [--n 24] [--genres lofi,deep_pop] [--dry]
Dials (repo Variables): THUMB_FARM=0 park it · THUMB_FARM_N per night ·
THUMB_BANK_TARGET shelf size · THUMB_SHELF tag name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import thumb_bank as TB          # noqa: E402  (the same code the release uses)

STAGE = Path(os.environ.get("THUMB_STAGE", "/tmp/thumb-stage"))
TAG = TB.SHELF_TAG
INDEX = TB.INDEX_FILE
NIGHTS = "nights.json"


PACE = {"hf-space": 25.0,                    # the shared demo rate-limits per visitor
        "pollinations": 16.0,                 # its own docs: anonymous = 1 request / 15 s
        "gemini": 3.0, "huggingface": 4.0, "cloudflare": 1.5,
        "cpu": 1.5}


def _i(name: str, default: int) -> int:
    """An env/Variable that is EMPTY must not crash the farm.

    This is not paranoia: a `workflow_dispatch` input that the boss leaves blank
    arrives as "" — and the first real run of this file (2026-10-30, run
    41066066865) died on exactly that, `int("")`, with the log line
    "⚠ thumb farm crashed: invalid literal for int() with base 10: ''". The
    crash handler did its job (exit 0, release unaffected), but a farm that
    cannot start from a blank box is a farm that never fills the shelf.
    """
    v = (os.environ.get(name) or "").strip()
    return int(v) if v.lstrip("-").isdigit() else default


def run(cmd, timeout=300, check=False):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:                                # gh missing, network out
        class R:
            returncode, stdout, stderr = 1, "", str(e)
        return R()


def ok(reason: str) -> int:
    print(f"\n  🖼 thumb farm: {reason}", flush=True)
    return 0


def load_shelf() -> dict:
    """The current index, from the cache dir or the release. Never raises."""
    STAGE.mkdir(parents=True, exist_ok=True)
    loc = STAGE / INDEX
    r = run(["curl", "-sfL", "-o", str(loc), TB.shelf_url(INDEX)], timeout=90)
    if r.returncode == 0 and loc.exists():
        try:
            d = json.loads(loc.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("images", [])
                d.setdefault("nights", [])
                return d
        except Exception:
            pass
    return {"images": [], "nights": [], "tag": TAG}


def cursor_of(shelf: dict) -> int:
    """Where in the matrix the next night starts. A cursor (not a fresh 0) is what
    turns 24 images/night into real coverage of ~0.9 M combinations."""
    return int(shelf.get("cursor", len(shelf.get("images", [])) * 977))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=_i("THUMB_FARM_N", 24))
    ap.add_argument("--target", type=int, default=_i("THUMB_BANK_TARGET", 900))
    ap.add_argument("--genres", default=os.environ.get("THUMB_GENRES", ""))
    ap.add_argument("--sleep", type=float, default=float(_i("THUMB_SLEEP_S", 2)))
    ap.add_argument("--budget-s", type=int, default=_i("THUMB_BUDGET_S", 1500))
    ap.add_argument("--dry", action="store_true", help="build prompts, call no API, upload nothing")
    ap.add_argument("--cpu-only", action="store_true",
                    help="no network at all: SD 1.5 on this machine's cores (thumb-cpu.yml)")
    args = ap.parse_args()

    if os.environ.get("THUMB_FARM", "1").strip() == "0":
        return ok("parked by THUMB_FARM=0 — the shelf is untouched tonight")
    if os.environ.get("GITHUB_ACTIONS") and not os.environ.get("GH_TOKEN"):
        return ok("no GH_TOKEN on this runner — nowhere to put the shelf")

    shelf = load_shelf()
    have = len(shelf["images"])
    if have >= args.target:
        return ok(f"shelf already holds {have} images (target {args.target}) — nothing to do")

    if args.cpu_only:
        # The boss's third backup: "if both of those first two get failed then the
        # third backup will start its work… I don't care about how long". So the API
        # engines are switched OFF for this run rather than merely deprioritised — a
        # CPU night must not quietly burn a day's quota on its way past.
        for k in ("THUMB_GEMINI", "THUMB_CF", "THUMB_HF", "THUMB_SPACE", "THUMB_POLLINATIONS"):
            os.environ[k] = "0"
        os.environ["THUMB_CPU"] = "1"
        print("  \U0001f422 cpu-only night: no keys, no quota, nothing to expire")

    gpool = [g.strip() for g in (args.genres or "").split(",") if g.strip()] or list(TB.GENRE_MOOD)
    cur = cursor_of(shelf)
    known_sha = {r.get("sha") for r in shelf["images"]}
    near = [int(r.get("dhash", 0)) for r in shelf["images"][-400:] if r.get("dhash")]

    out = STAGE / "new"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"🖼 thumb farm · shelf {have}/{args.target} · cursor {cur} · "
          f"{args.n} slots · genres {len(gpool)} · combos {TB.combo_count():,}", flush=True)
    t0 = time.time()
    made = rejected = 0
    for i in range(args.n):
        if time.time() - t0 > args.budget_s:
            print(f"  ⏱ budget of {args.budget_s}s spent — stopping with {made} new")
            break
        idx = (cur + i * 61) % TB.combo_count()
        genre = gpool[(cur + i) % len(gpool)]
        ch, prompt = TB.build_prompt(idx, genre)
        seed = (cur + i * 101) % 2_000_000
        if args.dry:
            print(f"  [{i:02d}] idx={idx} seed={seed} {genre}: {prompt[:96]}…")
            made += 1
            continue
        data, engine, why = TB.generate(prompt, seed, near=near)
        if data is None:
            rejected += 1
            print(f"  [{i:02d}] ✗ {why[:420]}")
            if "429" in (why or "") and os.environ.get("THUMB_GEMINI", "1").strip() != "0":
                # A free-tier quota is a wall for the DAY, not a retry-with.
                # Tonight's log: 429 RESOURCE_EXHAUSTED on both image models on
                # the boss's only key. Stop paying for the same answer 24 times.
                os.environ["THUMB_GEMINI"] = "0"
                print("  ⏭ Gemini parked for the rest of the night (429 quota) — "
                      "the other engines keep the lane open")
            if made == 0 and i >= 1 and ("402" in (why or "") or "503" in (why or "")):
                # every engine said no AND nothing landed yet — a night of that is
                # a night over, not a loop of timeouts on a wall (the EP.064
                # lesson, same as art_free). Once images ARE banked, keep walking.
                print("  ⏸ every engine is refusing this IP tonight and the shelf is "
                      "still empty — stopping early")
                break
            time.sleep(max(0.5, args.sleep))
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha in known_sha:
            rejected += 1
            print(f"  [{i:02d}] ✗ byte-identical to a shelf image — skipped")
            continue
        im, why2 = TB.usable(data, near=near)
        if im is None:
            rejected += 1
            print(f"  [{i:02d}] ✗ {why2}")
            continue
        luma, spread, dh = TB.stats(im)
        name = f"{sha[:24]}.jpg"
        (out / name).write_bytes(data)
        known_sha.add(sha)
        near.append(dh)
        shelf["images"].append({"file": name, "sha": sha[:32], "seed": seed, "idx": idx,
                                "genre": genre, "engine": engine, "luma": luma,
                                "spread": spread, "dhash": dh, "combo": ch,
                                "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        made += 1
        print(f"  [{i:02d}] ✓ {engine:26s} luma {luma:5.1f} spread {spread:4.1f} · {name}")
        # be polite to free tiers — and the shared FLUX demo Space is the most
        # polite of all: it rate-limits per visitor within a couple of seconds,
        # so a fast night there costs the whole night (measured 2026-10-30)
        time.sleep(max(0.5, args.sleep, PACE.get((engine or "").split("/")[0], 0.0)))

    if not made:
        return ok(f"nothing new (rejected {rejected}) — the release keeps using the "
                  f"shelf it has ({have} images) or its own cover")

    shelf["cursor"] = (cur + args.n * 61) % TB.combo_count()
    shelf["nights"] = (shelf.get("nights", []) + [{
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "added": made,
        "rejected": rejected, "total": len(shelf["images"]),
        "engines": sorted({r.get("engine", "?") for r in shelf["images"][-made:]})}])[-90:]
    (STAGE / INDEX).write_text(json.dumps(shelf, indent=1, ensure_ascii=False))

    if args.dry:
        return ok(f"dry run — {made} prompts built, no API calls, no upload")

    files = [STAGE / INDEX] + sorted(out.glob("*.jpg"))
    r = run(["gh", "release", "create", TAG, "--title", "🖼 thumb bank (decorative, never fatal)",
             "--prerelease", "--target", (os.environ.get("GIT_BRANCH") or "main").strip() or "main",
             "--notes", "AI-generated thumbnail shelf. The release lane reads index.json "
             "and picks one; if this whole release disappears, releases still publish."],
            timeout=90)
    if r.returncode != 0 and "already exists" not in (r.stderr or "").lower():
        print(f"  (release create: {(r.stderr or r.stdout or '')[:160]})")
    # `--cfile` is not a gh flag. Night 4 (run 41070851775) banked three good
    # images and then every single upload answered "unknown flag: --cfile",
    # leaving release `thumb-lab` at zero assets — and the same flag in
    # broll_farm is why `broll-lab` has never existed. `gh release upload` takes
    # paths positionally; `--clobber` because index.json is rewritten nightly.
    rr = run(["gh", "release", "upload", TAG, "--clobber"] + [str(x) for x in files], timeout=900)
    if rr.returncode != 0:
        print("  ⚠ upload failed (" + ((rr.stderr or rr.stdout or "").strip())[:180] +
              ") — the shelf keeps what it had; releases are unaffected")
    else:
        print(f"  ⬆ {len(files)} file(s) on release `{TAG}`")
    return ok(f"+{made} new, {rejected} rejected → shelf now {len(shelf['images'])} images "
              f"on `{TAG}` · {int(time.time() - t0)}s")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:                                  # a shelf is never an alarm
        print(f"  ⚠ thumb farm crashed: {str(e)[:160]} — release unaffected")
        raise SystemExit(0)

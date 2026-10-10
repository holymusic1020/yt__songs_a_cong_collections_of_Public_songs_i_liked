"""🎬 The b-roll library — read side of the offline render farm (v24).

WHY THIS FILE EXISTS
The boss asked (2026-10-10): "why not we set a very powerful local vid renderer…
if it takes 1h for a 5 sec vid, then in 24*3 h we get 24*3*5 sec of video… and
no need to worry about shorts, they're just short versions of the long vid.
BUTTT main goal is song… run it on Kaggle or smtg, think really hard so it
doesn't affect my song even an inch."

So this is a *library*, not a step in the render:

  · a separate job (tools/kaggle_broll.py, workflow broll-farm.yml) spends the
    Kaggle GPU hours at night and drops finished, pre-normalised clips into a
    GitHub release asset (`broll-lab`). The release pipeline NEVER generates.
  · the release pipeline only *reads* what is already there.

THE CONTRACT THAT KEEPS THE SONG SAFE (boss's rule, in code):
  1. every public function returns [] instead of raising — a missing/corrupt/
     half-downloaded library is a shrug, not a failed release;
  2. the download has a byte cap AND a wall-clock budget, so a slow CDN can't
     stretch the run;
  3. nothing here touches audio, loudness, subtitle timing or upload — it hands
     `video_render.from_clips` a list of files and that is the whole surface;
  4. `BROLL=0` (repo Variable) turns the feature off completely: today's Ken
     Burns stills, exactly as shipped EP.001→EP.063.

Clip layout:  <repo>/assets/broll/<genre>/broll-<id>.mp4  +  manifest.json
The farm encodes 1920x1080 / 24 fps / h264 / yuv420p and 8 s per clip, so the
release side just trims — no scaling surprises on the runner.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL_TAG = "broll-lab"
MIN_BYTES = 150_000          # a real 8 s 1080p clip is megabytes; anything less is junk
POOL_MIN = 3                 # below this it would just be the same shot on repeat


def enabled() -> bool:
    """`BROLL=0` → never look at the library at all. Default ON: with an empty
    library this whole module is inert, so 'on' costs nothing until the farm
    actually produces clips."""
    return os.environ.get("BROLL", "1").strip() != "0"


def libdir(genre: str) -> Path:
    g = "".join(ch for ch in (genre or "dark_ambient").lower() if ch.isalnum() or ch == "_")
    return ROOT / "assets" / "broll" / (g or "dark_ambient")


def _read_manifest(d: Path) -> list[dict]:
    m = d / "manifest.json"
    if not m.exists():
        return []
    try:
        data = json.loads(m.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [c for c in data.get("clips", []) if isinstance(c, dict)]


def scan(genre: str) -> list[Path]:
    """Verified clips on disk, in farm order. Anything doubtful is dropped here."""
    d = libdir(genre)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("broll-*.mp4")):
        try:
            if p.stat().st_size < MIN_BYTES:
                continue
        except OSError:
            continue
        out.append(p)
    return out


def probe(p: Path) -> dict:
    """Duration/res via ffprobe when the runner has it — logging and floor
    checks only. Never required: `-stream_loop -1` on the input makes a short
    clip harmless, so a missing ffprobe cannot block a release."""
    if shutil.which("ffmpeg") is None:
        return {}
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "0", "-show_entries",
             "format=duration:stream=width,height,r_frame_rate", "-of", "json", str(p)],
            capture_output=True, text=True, timeout=20)
        j = json.loads(r.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        fps = st.get("r_frame_rate") or "0/1"
        num, _, den = fps.partition("/")
        return {"dur": float(j.get("format", {}).get("duration") or 0),
                "w": int(st.get("width") or 0), "h": int(st.get("height") or 0),
                "fps": (float(num) / float(den or 1)) if den else 0.0}
    except Exception:
        return {}


def fetch(genre: str, budget_s: float = 90.0) -> bool:
    """Pull tonight's archive from the farm's release. Hard caps: bytes AND
    seconds. Returns True if the library got bigger."""
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not repo or "/" not in repo or os.environ.get("BROLL_FETCH", "1").strip() == "0":
        return False
    max_mb = float(os.environ.get("BROLL_MAX_MB", "220") or 220)
    url = f"https://github.com/{repo}/releases/download/{REL_TAG}/broll-{genre}.tar.xz"
    d = libdir(genre)
    tmp = ROOT / "assets" / "broll" / f".dl-{genre}.tar.xz"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    before = len(scan(genre))
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "yt-auto/20"})
        with urllib.request.urlopen(req, timeout=25) as r, open(tmp, "wb") as f:
            got = 0
            while True:
                if time.monotonic() - t0 > budget_s or got > max_mb * 1e6:
                    print(f"  (b-roll: download budget hit at {got/1e6:.0f} MB — "
                          f"keeping the stills, no harm done)")
                    return False
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
        extracted = 0
        with tarfile.open(tmp, "r:xz") as tf:          # no path traversal, no exec
            safe = [m for m in tf.getmembers()
                    if m.isfile() and Path(m.name).name.startswith("broll-")
                    and (m.name.endswith(".mp4") or m.name.endswith(".json"))]
            d.mkdir(parents=True, exist_ok=True)
            for m in safe:
                m.name = f"{d.name}/{Path(m.name).name}"
                try:                       # `filter=` needs 3.12 / the 3.11.4 security
                    tf.extract(m, d.parent, filter="data")     # backport; on an older
                    extracted += 1                              # patch fall back by hand
                except TypeError:
                    member = tf.extractfile(m)
                    if member is None:
                        continue
                    dest = d.parent / m.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(member.read())
                    extracted += 1
        return extracted > 0 or len(scan(genre)) > before
    except Exception as e:
        print(f"  (b-roll: nothing to fetch for {genre}: {type(e).__name__})")
        return False
    finally:
        tmp.unlink(missing_ok=True)


def plan(genre: str, dur: float, per_s: float) -> list[Path]:
    """The files to cut, or [] — [] means 'render exactly like yesterday'.
    Never raises: an input library must not be able to sink a release."""
    try:
        if not enabled():
            return []
        clips = scan(genre)
        if not clips and fetch(genre):
            clips = scan(genre)
        if len(clips) < POOL_MIN:
            if clips:
                print(f"  (b-roll: only {len(clips)} usable clip(s) for {genre} "
                      f"— below the {POOL_MIN} that stops it looking like a loop)")
            return []
        want = max(4, int(round((dur or 0) / max(per_s, 0.5))))
        out: list[Path] = []
        while len(out) < want:                      # cycle, but re-seed the order
            for c in clips:                         # so a repeat never lands back-to-back
                if len(out) >= want:
                    break
                if out and c == out[-1]:
                    continue
                out.append(c)
            if len(clips) == 1:
                break
        picks = out[:want]
        bad = [p for p in picks if not p.exists() or p.stat().st_size < MIN_BYTES]
        if bad:
            return []
        return picks
    except Exception as e:                          # noqa: BLE001 — by contract
        print(f"  (b-roll: skipped, staying on stills: {type(e).__name__}: {e})")
        return []


def describe(picks: list[Path]) -> str:
    """One honest line for the log + the receipt."""
    if not picks:
        return "stills (Ken Burns)"
    try:
        durs = [probe(p).get("dur") or 0 for p in picks]
        held = sum(d for d in durs if d > 0) or len(picks) * 8
        return f"{len(picks)} generated clips · {held/60:.1f} min of footage in the library"
    except Exception:
        return f"{len(picks)} generated clips"

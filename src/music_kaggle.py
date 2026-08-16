"""🎵 KAGGLE VOCAL LANE — free T4/P100 GPU (no credit card) via the Kaggle API.

The lane that FINALLY solves vocals for $0 without a card:
  1. GitHub (this lane) triggers a private Kaggle notebook via `kaggle kernels
     push` — the notebook runs DiffRhythm (Apache-2.0) on Kaggle's FREE GPU
     (30h/week, no card) and cooks a FULL song WITH SUNG VOCALS.
  2. We poll `kaggle kernels status` until it completes (~5-10 min).
  3. We download the output via `kaggle kernels output` → mp3 + lrc + lyrics
     land in `incoming/` → the NEXT run publishes the vocal song.

No card, no GPU of our own, no quota shared with strangers — Kaggle's quota
is per-account (30h/week) and resets weekly.

Needs Kaggle API creds (free, no card — kaggle.com → Settings → API → Create
New Token) in GitHub Secrets:
  KAGGLE_USERNAME, KAGGLE_KEY
Optional: GEMINI_API_KEY secret inside the KAGGLE notebook (Add-ons →
Secrets) so lyrics are fresh per song; else the notebook's bank lyrics.

Kill-switch: KAGGLE_OFF=1. Any failure → None → next lane / engine.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

KERNEL_ID = os.environ.get("KAGGLE_KERNEL_ID", "nixspeech/nix-speech-vocal-cook")
NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "kaggle_cook"
POLL_S = int(os.environ.get("KAGGLE_POLL_S", "15") or "15")
MAX_WAIT_S = int(os.environ.get("KAGGLE_MAX_WAIT_S", "1200") or "1200")  # 20 min


def _run(cmd: list[str], timeout: int = 120, check: bool = True):
    print(f"  [kaggle] {' '.join(str(c) for c in cmd)[:120]}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, check=check)


def _available() -> bool:
    if os.environ.get("KAGGLE_OFF", "") == "1":
        return False
    if not (os.environ.get("KAGGLE_USERNAME", "") or "").strip():
        return False
    if not (os.environ.get("KAGGLE_KEY", "") or "").strip():
        return False
    if not shutil.which("kaggle"):
        try:
            _run(["pip", "install", "--quiet", "kaggle"], timeout=300)
        except Exception:
            return False
    return shutil.which("kaggle") is not None


def generate(genre_key: str, seconds: float, out_path: Path,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None) -> Path | None:
    """Trigger a Kaggle GPU vocal cook, poll, download. None = next lane."""
    if not _available():
        print("  (kaggle lane skipped: no KAGGLE creds or KAGGLE_OFF=1)")
        return None
    kaggle = shutil.which("kaggle")

    # write creds for the CLI (ephemeral, like HF_TOKEN handling)
    cfg = Path.home() / ".kaggle"
    cfg.mkdir(exist_ok=True)
    (cfg / "kaggle.json").write_text(
        '{"username":"%s","key":"%s"}' % (
            os.environ["KAGGLE_USERNAME"].strip(),
            os.environ["KAGGLE_KEY"].strip()))
    (cfg / "kaggle.json").chmod(0o600)

    try:
        # 1) push the notebook (this also starts it)
        print("  🎵 kaggle: pushing vocal cook to free GPU…", flush=True)
        r = _run([kaggle, "kernels", "push", "-p", str(NOTEBOOK_DIR)],
                 timeout=180, check=False)
        if r.returncode != 0:
            print(f"  ⚠ kaggle push failed: {r.stderr[-300:]} — next lane")
            return None

        # 2) poll until complete
        t0 = time.time()
        while time.time() - t0 < MAX_WAIT_S:
            time.sleep(POLL_S)
            r = _run([kaggle, "kernels", "status", KERNEL_ID],
                     timeout=60, check=False)
            out = (r.stdout or "") + (r.stderr or "")
            if "complete" in out.lower():
                break
            if "error" in out.lower() or "failed" in out.lower():
                print(f"  ⚠ kaggle kernel errored: {out[-200:]} — next lane")
                return None
            print(f"  [kaggle] cooking… {int(time.time()-t0)}s", flush=True)
        else:
            print("  ⚠ kaggle timed out — next lane")
            return None

        # 3) download output
        out_dir = out_path.parent / "kaggle_out"
        out_dir.mkdir(exist_ok=True)
        _run([kaggle, "kernels", "output", KERNEL_ID, "-p", str(out_dir)],
             timeout=180, check=False)
        mp3s = sorted(out_dir.glob("next_song--*.mp3"))
        if not mp3s:
            print("  ⚠ kaggle output has no next_song mp3 — next lane")
            return None
        src = mp3s[0]
        import shutil as _s
        _s.copy(src, out_path)
        if out_path.stat().st_size < 80_000:
            print(f"  ⚠ kaggle mp3 suspiciously small — next lane")
            return None
        # sidecars
        stem = src.stem
        for suf, dest in ((".lrc.txt", lrc_out), (".lyrics.txt", None)):
            side = src.with_name(stem + suf)
            if dest is not None and side.exists():
                dest.write_bytes(side.read_bytes())
        mode = f"{lang} vocals 🎤" if lyrics else "instrumental"
        print(f"  🎁 kaggle-GPU cooked {genre_key} ({mode}, "
              f"{out_path.stat().st_size//1024} KB)")
        return out_path
    except Exception as e:
        print(f"  ⚠ kaggle lane failed: {type(e).__name__}: {str(e)[:140]}")
        return None

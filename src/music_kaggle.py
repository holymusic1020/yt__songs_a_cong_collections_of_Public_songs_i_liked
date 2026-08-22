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

v23.7.1 fixes:
  · kernel-metadata.json is built DYNAMICALLY with the real KAGGLE_USERNAME
    (the hardcoded 'nixspeech/...' id made `kaggle kernels push` fail with
    an auth/validation error for any other account).
  · push failures now print BOTH stdout and stderr (the 'empty error' was
    the CLI writing the reason to stdout).
  · KAGGLE_CONFIG_DIR is set so the CLI always finds kaggle.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

KERNEL_SLUG = os.environ.get("KAGGLE_KERNEL_SLUG", "nix-speech-vocal-cook")
NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "kaggle_cook"
POLL_S = int(os.environ.get("KAGGLE_POLL_S", "15") or "15")
MAX_WAIT_S = int(os.environ.get("KAGGLE_MAX_WAIT_S", "1500") or "1500")  # 25 min
# DiffRhythm on a T4 takes ~10-15 min; the OUTPUT download can also be slow
# (kaggle kernels output pulls the whole /kaggle/working) — 600s so it never
# times out mid-download (the 2026-08-20 runs cooked 10-13 min then the
# 180s output timeout threw and we re-pushed a fresh kernel, wasting quota).
OUTPUT_TIMEOUT_S = int(os.environ.get("KAGGLE_OUTPUT_TIMEOUT_S", "600") or "600")
OUTPUT_TRIES = int(os.environ.get("KAGGLE_OUTPUT_TRIES", "3") or "3")


def _run(cmd: list[str], timeout: int = 120, check: bool = True):
    print(f"  [kaggle] {' '.join(str(c) for c in cmd)[:120]}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, check=check)


def _setup_creds() -> Path | None:
    """Write Kaggle creds + return the config dir. None = skip.

    2026 auth reality: Kaggle moved to an API-TOKEN model.
      · KAGGLE_API_TOKEN (new)     → ~/.kaggle/access_token  (settings → API)
      · KAGGLE_USERNAME+KAGGLE_KEY (legacy) → ~/.kaggle/kaggle.json
    Both are accepted; we write whichever secrets are present.
    """
    if os.environ.get("KAGGLE_OFF", "") == "1":
        return None
    user = os.environ.get("KAGGLE_USERNAME", "").strip()
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    key = os.environ.get("KAGGLE_KEY", "").strip()
    if not user or not (token or key):
        print("  (kaggle skipped: need KAGGLE_USERNAME + (KAGGLE_API_TOKEN "
              "or KAGGLE_KEY))")
        return None
    if not shutil.which("kaggle"):
        try:
            _run(["pip", "install", "--quiet", "kaggle"], timeout=300)
        except Exception:
            return None
        if not shutil.which("kaggle"):
            return None
    cfg = Path.home() / ".kaggle"
    cfg.mkdir(exist_ok=True)
    if token:
        (cfg / "access_token").write_text(token)
        (cfg / "access_token").chmod(0o600)
        print("  [kaggle] using API-token auth (access_token)", flush=True)
    else:
        (cfg / "kaggle.json").write_text(
            json.dumps({"username": user, "key": key}))
        (cfg / "kaggle.json").chmod(0o600)
        print("  [kaggle] using legacy kaggle.json auth", flush=True)
    return cfg


def _push(notebook_dir: Path, cfg: Path) -> tuple[int, str]:
    """Push (create/update) the notebook. Returns (returncode, output)."""
    # dynamic metadata: real username → valid Kaggle kernel id
    user = os.environ.get("KAGGLE_USERNAME", "").strip()
    meta = notebook_dir / "kernel-metadata.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        m["id"] = f"{user}/{KERNEL_SLUG}"
        meta.write_text(json.dumps(m, indent=2))
    env = dict(os.environ)
    env["KAGGLE_CONFIG_DIR"] = str(cfg)
    r = subprocess.run(
        [shutil.which("kaggle"), "kernels", "push", "-p", str(notebook_dir)],
        capture_output=True, text=True, timeout=180, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def generate(genre_key: str, seconds: float, out_path: Path,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None) -> Path | None:
    """Trigger a Kaggle GPU vocal cook, poll, download. None = next lane."""
    cfg = _setup_creds()
    if cfg is None:
        print("  (kaggle lane skipped: no KAGGLE creds or KAGGLE_OFF=1)")
        return None
    kaggle = shutil.which("kaggle")

    # 1) push the notebook (this also starts it)
    print("  🎵 kaggle: pushing vocal cook to free GPU…", flush=True)
    rc, out = _push(NOTEBOOK_DIR, cfg)
    if rc != 0:
        print(f"  ⚠ kaggle push failed (rc={rc}): {out[-400:]} — next lane")
        return None
    print(f"  [kaggle] push ok: {out.strip()[-200:]}", flush=True)

    # 2) poll until complete
    kernel_id = f"{os.environ.get('KAGGLE_USERNAME','').strip()}/{KERNEL_SLUG}"
    t0 = time.time()
    while time.time() - t0 < MAX_WAIT_S:
        time.sleep(POLL_S)
        r = _run([kaggle, "kernels", "status", kernel_id], timeout=60,
                 check=False)
        out = (r.stdout or "") + (r.stderr or "")
        low = out.lower()
        if "complete" in low:
            break
        if "error" in low or "failed" in low:
            print(f"  ⚠ kaggle kernel errored: {out[-300:]} — next lane")
            return None
        print(f"  [kaggle] cooking… {int(time.time()-t0)}s", flush=True)
    else:
        print("  ⚠ kaggle timed out — next lane")
        return None

    # 3) download output — the kernel is DONE; retry the download itself
    #    (never re-push — that would re-cook from scratch and burn quota)
    out_dir = out_path.parent / "kaggle_out"
    out_dir.mkdir(exist_ok=True)
    dl_ok = False
    for dl_try in range(1, OUTPUT_TRIES + 1):
        try:
            _run([kaggle, "kernels", "output", kernel_id, "-p", str(out_dir)],
                 timeout=OUTPUT_TIMEOUT_S, check=False)
            dl_ok = True
            break
        except Exception as e:
            print(f"  [kaggle] output dl try {dl_try}/{OUTPUT_TRIES} timed out "
                  f"({str(e)[:80]}) — retrying download…", flush=True)
            time.sleep(10)
    if not dl_ok:
        print("  ⚠ kaggle output download failed after retries — next lane")
        return None
    # the notebook writes error.txt on failure (never crashes the kernel) —
    # surface the REAL reason instead of "KernelWorkerStatus.ERROR"
    errs = list(out_dir.rglob("error.txt"))
    if errs:
        why = errs[0].read_text(encoding="utf-8", errors="replace")[-500:]
        print(f"  ⚠ kaggle notebook reported: {why.strip()} — next lane")
        return None
    mp3s = sorted(out_dir.glob("next_song--*.mp3"))
    if not mp3s:
        print("  ⚠ kaggle output has no next_song mp3 — next lane")
        return None
    src = mp3s[0]
    shutil.copy(src, out_path)
    if out_path.stat().st_size < 80_000:
        print(f"  ⚠ kaggle mp3 suspiciously small — next lane")
        return None
    # sidecars
    stem = src.stem
    side = src.with_name(stem + ".lrc.txt")
    if lrc_out is not None and side.exists():
        lrc_out.write_bytes(side.read_bytes())
    mode = f"{lang} vocals 🎤" if lyrics else "instrumental"
    print(f"  🎁 kaggle-GPU cooked {genre_key} ({mode}, "
          f"{out_path.stat().st_size//1024} KB)")
    return out_path

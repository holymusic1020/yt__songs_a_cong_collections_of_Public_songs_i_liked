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
MAX_WAIT_S = int(os.environ.get("KAGGLE_MAX_WAIT_S", "3600") or "3600")  # 60 min: 56-step + 285s cooks run longer but cleaner
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
    # 📝 FRESH-LYRICS INJECTION (2026-08-26): main.py writes brand-new lyrics
    # every episode, but the notebook always sang its built-in 8-line bank —
    # every song sounded the same ("still sucks" traced here). Render today's
    # words into a temp copy of the script before pushing. 8-line cap keeps the
    # notebook's lrc timing valid; en-only (DiffRhythm G2P is en/zh).
    nb_dir = NOTEBOOK_DIR
    staging = None
    alen = "285" if (seconds or 0) >= 200 else "95"   # full-length model on video days
    if lyrics and lyrics.strip() and (lang or "en") == "en":
        import tempfile
        lines = [ln.strip(" -\u2013\u2014\u2022") for ln in lyrics.splitlines() if ln.strip()]
        lines = [ln for ln in lines if not ln.lower().startswith(
            ("verse", "chorus", "hook", "bridge", "intro", "outro", "title", "["))]
        if len(lines) >= 4:
            lines = lines[:8]
            staging = Path(tempfile.mkdtemp(prefix="kaggle_nb_"))
            for _f in NOTEBOOK_DIR.iterdir():
                if _f.is_file():
                    shutil.copy(_f, staging / _f.name)
            _script = staging / "nix_speech_cook.py"
            _txt = _script.read_text(encoding="utf-8")
            _a = _txt.index("LYRIC_LINES = [")
            _b = _txt.index("]", _a) + 1
            _rendered = "LYRIC_LINES = [\n" + "".join(
                f"    {json.dumps(ln)},\n" for ln in lines) + "]"
            _script.write_text(_txt[:_a] + _rendered + _txt[_b:], encoding="utf-8")
            nb_dir = staging
            print(f"  \U0001f4dd fresh lyrics injected ({len(lines)} lines — not the bank)", flush=True)
    if staging is None and alen == "285":
        import tempfile
        staging = Path(tempfile.mkdtemp(prefix="kaggle_nb_"))
        for _f in NOTEBOOK_DIR.iterdir():
            if _f.is_file():
                shutil.copy(_f, staging / _f.name)
    if staging is not None:
        _script = staging / "nix_speech_cook.py"
        _txt = _script.read_text(encoding="utf-8")
        if alen == "285":
            _txt = _txt.replace('"--audio-length", "95",',
                                '"--audio-length", "285",\n        "--chunked",', 1)
            _script.write_text(_txt, encoding="utf-8")
        nb_dir = staging
        print(f"  [kaggle] staged notebook (len={alen}" + (", full model + chunked" if alen == "285" else "") + ")", flush=True)
    rc, out = _push(nb_dir, cfg)
    if staging:
        shutil.rmtree(staging, ignore_errors=True)
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
    # 3b) SUCCESS FIRST: a real cooked mp3 is what matters. Kaggle kernels
    #     sometimes also carry a stale/leftover error.txt (e.g. a harmless
    #     onnxruntime provider warning that got captured) — if the mp3 is
    #     there and big, we take the song and IGNORE the error file.
    #     (2026-08-22: the notebook cooked lofi 2.1MB + SUCCESS.txt yet the
    #      error-first check threw away the finished song.)
    mp3s = sorted(out_dir.glob("next_song--*.mp3"))
    if mp3s:
        src = mp3s[0]
        if src.stat().st_size >= 80_000:
            shutil.copy(src, out_path)
            stem = src.stem
            side = src.with_name(stem + ".lrc.txt")
            if lrc_out is not None and side.exists():
                lrc_out.write_bytes(side.read_bytes())
            mode = f"{lang} vocals 🎤" if lyrics else "instrumental"
            print(f"  🎁 kaggle-GPU cooked {genre_key} ({mode}, "
                  f"{out_path.stat().st_size // 1024} KB)")
            return out_path
    # only now: no good mp3 → surface the notebook's reported error
    errs = list(out_dir.rglob("error.txt"))
    if errs:
        why = errs[0].read_text(encoding="utf-8", errors="replace")[-500:]
        print(f"  ⚠ kaggle notebook reported: {why.strip()} — next lane")
        return None
    print("  ⚠ kaggle output has no usable song — next lane")
    return None

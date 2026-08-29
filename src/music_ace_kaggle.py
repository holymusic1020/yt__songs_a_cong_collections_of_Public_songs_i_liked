"""🎤 ACE-Step OFFLINE KAGGLE LANE — your own free GPU, no HF quota, $0.

The boss rejected every cloud singer (Suno: broke; Lyria: paywall; HF ACE
spaces: ZeroGPU quota dead for this account; DiffRhythm: ears said no ×4).
This lane runs the OPEN-SOURCE ACE-Step v1 (3.5B, Apache-2.0) directly on
your OWN Kaggle GPU (30 free h/wk, no card):

  1. push kaggle_ace/ via `kaggle kernels push` (fresh lyrics stamped in)
  2. the notebook pip-installs ACE-Step, downloads ACE-Step-v1-3.5B from HF
     (public weights), generates up to 240s WITH SUNG VOCALS (fp16 on T4,
     cpu_offload fallback), masters with ffmpeg
  3. we poll, download `next_song--*.mp3` + sidecars → song on deck

Same creds & infra as the DiffRhythm kaggle lane (KAGGLE_USERNAME +
KAGGLE_API_TOKEN / KAGGLE_KEY). Kill-switch: KAGGLE_OFF=1 or ACE_KAGGLE_OFF=1.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

KERNEL_SLUG = os.environ.get("ACE_KAGGLE_KERNEL_SLUG", "nix-ace-cook")
NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "kaggle_ace"
POLL_S = int(os.environ.get("KAGGLE_POLL_S", "15") or "15")
MAX_WAIT_S = int(os.environ.get("ACE_KAGGLE_MAX_WAIT_S", "5400") or "5400")  # 90min: first cooks pull 7GB weights
OUTPUT_TIMEOUT_S = int(os.environ.get("KAGGLE_OUTPUT_TIMEOUT_S", "600") or "600")
OUTPUT_TRIES = int(os.environ.get("KAGGLE_OUTPUT_TRIES", "3") or "3")


def _run(cmd: list[str], timeout: int = 120, check: bool = True):
    print(f"  [ace-kaggle] {' '.join(str(c) for c in cmd)[:110]}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, check=check)


def _setup_creds() -> Path | None:
    if os.environ.get("KAGGLE_OFF", "") == "1" or os.environ.get("ACE_KAGGLE_OFF", "") == "1":
        return None
    user = os.environ.get("KAGGLE_USERNAME", "").strip()
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    key = os.environ.get("KAGGLE_KEY", "").strip()
    if not user or not (token or key):
        print("  (ace-kaggle skipped: no KAGGLE creds)")
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
    else:
        (cfg / "kaggle.json").write_text(json.dumps({"username": user, "key": key}))
        (cfg / "kaggle.json").chmod(0o600)
    return cfg


def _push(notebook_dir: Path, cfg: Path) -> tuple[int, str]:
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


def _stage(lyrics: str | None, seconds: float, genre_key: str) -> Path:
    """Stamp today's lyrics/duration/genre into a temp copy of the notebook."""
    import tempfile
    staging = Path(tempfile.mkdtemp(prefix="ace_nb_"))
    for f in NOTEBOOK_DIR.iterdir():
        if f.is_file():
            shutil.copy(f, staging / f.name)
    script = staging / "nix_ace_cook.py"
    txt = script.read_text(encoding="utf-8")
    # 1) lyrics (fresh Gemini words every video day)
    if lyrics and lyrics.strip():
        lines = [ln.strip(" –—•") for ln in lyrics.splitlines() if ln.strip()]
        lines = [ln for ln in lines if not ln.lower().startswith(
            ("verse", "chorus", "hook", "bridge", "intro", "outro", "title", "["))]
        if len(lines) >= 4:
            lines = lines[:8]
            a = txt.index("LYRIC_LINES = [")
            b = txt.index("]", a) + 1
            txt = txt[:a] + "LYRIC_LINES = [\n" + "".join(
                f"    {json.dumps(ln)},\n" for ln in lines) + "]" + txt[b:]
            print(f"  📝 fresh lyrics stamped into ACE cook ({len(lines)} lines)", flush=True)
    # 2) duration — the open model sings up to 4 min: full songs on video days
    dur = int(max(90, min(240, round(seconds or 150))))
    txt = txt.replace("AUDIO_DURATION_S = 150", f"AUDIO_DURATION_S = {dur}", 1)
    # 3) genre + daily seed
    txt = txt.replace('GENRE_KEY = "deep_pop"', f'GENRE_KEY = {json.dumps(genre_key)}', 1)
    from datetime import datetime, timezone
    txt = txt.replace("SEED = 20260826",
                      f"SEED = {datetime.now(timezone.utc).toordinal()}", 1)
    # 4) v6 (2026-08-29): per-attempt run token (staleness autopsy) + TG
    #    live-beacon creds. Stamped into the PRIVATE kernel only, never printed.
    import re as _re
    import uuid as _uuid
    run_token = (f"ace-{datetime.now(timezone.utc).strftime('%y%m%d%H%M')}"
                 f"-{_uuid.uuid4().hex[:5]}")
    if 'RUN_TOKEN = "boot"' in txt:
        txt = txt.replace('RUN_TOKEN = "boot"',
                          f'RUN_TOKEN = {json.dumps(run_token)}', 1)
        print(f"  [ace-kaggle] run token: {run_token}", flush=True)
    else:
        print("  ⚠ ace-kaggle: RUN_TOKEN anchor missing — autopsy OFF", flush=True)
    _tg_t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    _tg_c = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if (_re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{30,60}", _tg_t)
            and _re.fullmatch(r"-?[0-9]+", _tg_c)):
        txt = txt.replace('TG_TOKEN = ""', f'TG_TOKEN = {json.dumps(_tg_t)}', 1)
        txt = txt.replace('TG_CHAT = ""', f'TG_CHAT = {json.dumps(_tg_c)}', 1)
        print("  [ace-kaggle] TG live-beacons wired into kernel (silent until the audio lands)", flush=True)
    else:
        print("  (ace-kaggle: TG creds absent/odd — kernel beacons off)", flush=True)
    script.write_text(txt, encoding="utf-8")
    print(f"  [ace-kaggle] staged (dur={dur}s, genre={genre_key})", flush=True)
    return staging, run_token


def generate(genre_key: str, seconds: float, out_path: Path,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None) -> Path | None:
    """Push → poll → download an ACE-Step song from your Kaggle GPU."""
    cfg = _setup_creds()
    if cfg is None:
        return None
    kaggle = shutil.which("kaggle")
    staging = None
    try:
        staging, run_token = _stage(lyrics if (lang or "en") == "en" else None,
                                    seconds, genre_key)
        print("  🎤 ace-offline: ACE-Step v1 cooking on YOUR Kaggle GPU "
              "(no HF quota, $0)…", flush=True)
        # 🧟 zombie rescue: a previous run may have left this kernel RUNNING
        # (2026-08-26: the 7GB-weight first cook outlived a 60-min leash, then
        # the retry push died on 409 Conflict). A live kernel blocks pushes —
        # try to delete it first (best effort; fresh lyrics need a fresh cook).
        _uid = os.environ.get('KAGGLE_USERNAME', '').strip()
        _st = _run([kaggle, "kernels", "status", f"{_uid}/{KERNEL_SLUG}"],
                   timeout=60, check=False)
        if "running" in ((_st.stdout or "") + (_st.stderr or "")).lower():
            print("  [ace-kaggle] stale kernel still RUNNING — deleting it…", flush=True)
            _run([kaggle, "kernels", "delete", f"{_uid}/{KERNEL_SLUG}", "-y"],
                 timeout=120, check=False)
            time.sleep(8)
        rc, out = _push(staging, cfg)
        if rc != 0:
            # 409 after a failed delete → the old kernel is already cooking
            # the same words; don't die, just keep polling it instead.
            if "conflict" in out.lower() or "409" in out:
                print("  [ace-kaggle] push conflicted — kernel already live; "
                      "polling it instead", flush=True)
            else:
                print(f"  ⚠ ace-kaggle push failed (rc={rc}): {out[-400:]} — next lane",
                      flush=True)
                return None
        else:
            print(f"  [ace-kaggle] push ok: {out.strip()[-160:]}", flush=True)

        kernel_id = f"{os.environ.get('KAGGLE_USERNAME', '').strip()}/{KERNEL_SLUG}"
        t0 = time.time()
        while time.time() - t0 < MAX_WAIT_S:
            time.sleep(POLL_S)
            r = _run([kaggle, "kernels", "status", kernel_id], timeout=60, check=False)
            low = ((r.stdout or "") + (r.stderr or "")).lower()
            if "complete" in low:
                break
            if "error" in low or "failed" in low:
                print(f"  ⚠ ace kernel errored: {low[-260:]} — next lane", flush=True)
                return None
            print(f"  [ace-kaggle] cooking… {int(time.time()-t0)}s", flush=True)
        else:
            print("  ⚠ ace kernel timed out — next lane", flush=True)
            return None

        out_dir = out_path.parent / "ace_kaggle_out"
        shutil.rmtree(out_dir, ignore_errors=True)   # v6: no carryover ghosts
        out_dir.mkdir(exist_ok=True)
        dl_ok = False
        for dl_try in range(1, OUTPUT_TRIES + 1):
            try:
                _r = _run([kaggle, "kernels", "output", kernel_id, "-p", str(out_dir)],
                          timeout=OUTPUT_TIMEOUT_S, check=False)
                if any(out_dir.iterdir()):
                    dl_ok = True
                    break
                print(f"  [ace-kaggle] dl {dl_try}/{OUTPUT_TRIES} came back EMPTY "
                      f"({((_r.stdout or '') + (_r.stderr or '')).strip()[-120:]}) — retrying…",
                      flush=True)
                time.sleep(10)
            except Exception as e:
                print(f"  [ace-kaggle] dl {dl_try}/{OUTPUT_TRIES} failed "
                      f"({str(e)[:70]}) — retrying…", flush=True)
                time.sleep(10)
        if not dl_ok:
            print("  ⚠ ace-kaggle download failed — next lane", flush=True)
            return None

        # 🔦 v5 (2026-08-29): stop flying blind — print the full download
        # inventory + any text files' content, ALWAYS.
        _inv = sorted(out_dir.rglob("*"), key=lambda p: p.stat().st_size)
        print(f"  [ace-kaggle] 📦 output inventory ({len(_inv)} files):", flush=True)
        for _f in _inv:
            if _f.is_file():
                print(f"    · {_f.name} ({_f.stat().st_size} B)", flush=True)
        for _name in ("log.txt", "out.json", "error.txt", "SUCCESS.txt"):
            _candidates = sorted(out_dir.rglob(_name))
            if _candidates:
                _body = _candidates[0].read_text(encoding="utf-8", errors="replace")[:2000]
                print(f"  [ace-kaggle] 📜 {_name}:\n{_body}", flush=True)
        mp3s = sorted(out_dir.glob("next_song--*.mp3"))
        if mp3s and mp3s[0].stat().st_size >= 80_000:
            src = mp3s[0]
            shutil.copy(src, out_path)
            side = src.with_name(src.stem + ".lrc.txt")
            if lrc_out is not None and side.exists():
                lrc_out.write_bytes(side.read_bytes())
            mode = f"{lang} vocals 🎤" if lyrics else "instrumental"
            print(f"  🎁 ACE-OFFLINE cooked {genre_key} ({mode}, "
                  f"{out_path.stat().st_size // 1024} KB)", flush=True)
            return out_path
        # 🧭 v6 staleness autopsy (2026-08-29): v13/v14 "completed" kernels each
        # handed back the SAME OLD bundle (identical SUCCESS.txt + hf_cache
        # blobs, zero fresh files) = the fresh run died before persistence
        # (SIGKILL class; Kaggle then serves the last persisted version).
        suc = sorted(out_dir.rglob("SUCCESS.txt"))
        sval = suc[0].read_text(encoding="utf-8", errors="replace") if suc else ""
        if f"RUN_TOKEN={run_token}" in sval:
            print("  ⚠ v6 RIDDLE: fresh SUCCESS but no mp3 in bundle — "
                  "output file drop; audio went out-of-band via TG instead", flush=True)
        elif suc:
            _bad = (sval.splitlines()[0][:60] if sval.strip() else "?")
            print(f"  ⚠ v6 STALE BUNDLE — its token «{_bad}» ≠ "
                  f"«RUN_TOKEN={run_token}»: attempt died pre-persistence "
                  "(SIGKILL class); TG beacons hold the true last phase — next lane",
                  flush=True)
            return None
        else:
            print("  ⚠ v6 EMPTY/OUTPUTLESS — zero persistence (death before any "
                  "SUCCESS); TG beacons hold the true last phase — next lane", flush=True)
            return None
        errs = list(out_dir.rglob("error.txt"))
        if errs:
            why = errs[0].read_text(encoding="utf-8", errors="replace")[-1500:]
            print(f"  ⚠ ace kernel reported: {why.strip()} — next lane", flush=True)
        else:
            print("  ⚠ ace-kaggle output has no usable song — next lane", flush=True)
        return None
    finally:
        if staging:
            shutil.rmtree(staging, ignore_errors=True)

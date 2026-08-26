# ⚡ NIX SPEECH VOCAL COOKER — runs on KAGGLE free T4/P100 GPU (no card)
# v3: NEVER crashes the kernel. Every failure is caught, written to
# error.txt, and the script exits 0 — so GitHub's `kaggle kernels output`
# downloads error.txt and prints the REAL reason in the run log.
# (A KernelWorkerStatus.ERROR gives us nothing — this fixes that.)
#
# DiffRhythm usage (correct): clone repo + run infer/infer.py CLI.

import datetime
import os
import subprocess
import sys
import traceback
from pathlib import Path

WORK = Path("/kaggle/working")
GENRES = ["drift_phonk", "deep_pop", "dark_ambient", "lofi", "baroque_waltz",
          "disco_house", "skyline_anthem", "villain_pop", "orbit_trap"]

STYLE = {
    # 2026-08-26 QUALITY FIX: every descriptor that ASKED for noise is gone
    # (was: "tape hiss", "vinyl crackle", "rain on window", "distant thunder",
    #  "vintage ballroom tape" → the model OBEYED and made 1920s-radio mud).
    # Every style now explicitly demands a clean modern mix + clear vocals.
    "drift_phonk": "drift phonk, dark memphis phonk, punchy clean 808 bass, phonk cowbell melody, night drive mood, clean modern studio mix, clear vocals, hi-fi, polished",
    "deep_pop": "melancholic alt pop, deep pulsing synth bass, airy detuned pads, slow burn build, emotional, clean modern studio production, clear vocals front and center, hi-fi",
    "dark_ambient": "dark cinematic ambient, slow evolving clean textures, deep sub drone, spacious modern mix, pristine, clear ethereal vocals, hi-fi, no noise",
    "lofi": "mellow chillhop, warm clean rhodes chords, soft boom bap drums, smooth mellow groove, clean modern studio mix, crisp vocals, hi-fi, no vinyl noise",
    "baroque_waltz": "playful modern baroque pop waltz, bright harpsichord and clean string quartet, polished studio production, clear vocals, hi-fi",
    "disco_house": "french house disco, funky filtered bassline, four on the floor, lush modern string stabs, feel-good, clean polished club mix, clear vocals, hi-fi",
    "skyline_anthem": "anthemic folk-edm, progressive house festival lift, big clean piano stabs, euphoric, polished stadium mix, strong clear vocals, hi-fi",
    "villain_pop": "dark cinematic pop, villain aesthetic, music-box bells, punchy clean 808 sub, menacing elegance, polished modern mix, clear confident vocals, hi-fi",
    "orbit_trap": "melodic trap, confident rap-sung bounce, crisp rolling hi-hats, clean sliding 808 bass, spacey polished pads, modern studio mix, clear vocals, hi-fi",
}

LYRIC_LINES = [
    "midnight city lights below",
    "we ride the neon flow",
    "the signal never dies tonight",
    "we're glowing, burning bright",
    "headlights cut the rain",
    "we're chasing every lane",
    "the station hums a quiet song",
    "and we keep driving on",
]


def fail(msg: str) -> None:
    """Record the failure so GitHub can read it, then exit 0."""
    print("❌ " + msg, flush=True)
    (WORK / "error.txt").write_text(msg + "\n", encoding="utf-8")
    sys.exit(0)


def pick_genre() -> str:
    day = (datetime.datetime.now(datetime.timezone.utc) -
           datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)).days
    return GENRES[day % len(GENRES)]


def build_lrc() -> str:
    lines = []
    t = 30.0
    for txt in LYRIC_LINES:
        mm, ss = int(t // 60), int(t % 60)
        lines.append(f"[{mm:02d}:{ss:02d}]{txt}")
        t += 8.0
    return "\n".join(lines)


def main():
    genre = pick_genre()
    print(f"🎹 genre: {genre}", flush=True)

    print("📦 cloning DiffRhythm…", flush=True)
    r = os.system("rm -rf DiffRhythm && git clone --depth 1 "
                  "https://github.com/ASLP-lab/DiffRhythm.git "
                  "> /tmp/clone.log 2>&1")
    if r != 0 or not Path("DiffRhythm/infer/infer.py").exists():
        log = Path("/tmp/clone.log").read_text()[-800:] if Path("/tmp/clone.log").exists() else ""
        # clear guidance: github.com unresolvable = Internet is OFF in the
        # notebook settings (Kaggle toggles it per-notebook)
        if "Could not resolve host" in log or "Name or service not known" in log:
            fail("INTERNET IS OFF in this Kaggle notebook — open it on "
                 "kaggle.com, click the ⚙️ Settings, set Internet: ON, "
                 "Save, then re-run. (clone log: " + log.strip()[-200:] + ")")
        fail(f"DiffRhythm clone failed (rc={r}): {log}")

    print("📦 installing DiffRhythm deps…", flush=True)
    # espeak-ng is REQUIRED by phonemizer for DiffRhythm's vocal G2P
    # (2026-08-19 run died at EspeakBackend — binary was missing)
    os.system("apt-get update -qq > /tmp/apt_update.log 2>&1 && apt-get install -y -qq espeak-ng espeak-ng-data libespeak-ng1 > /tmp/espeak.log 2>&1")
    if not os.system("which espeak-ng") == 0:
        tail = (Path("/tmp/espeak.log").read_text()[-400:]
                if Path("/tmp/espeak.log").exists() else "")
        fail(f"espeak-ng install failed: {tail}")
    print("✅ espeak-ng installed (vocals G2P ready)", flush=True)
    r = os.system("pip -q install -r DiffRhythm/requirements.txt "
                  "> /tmp/pip.log 2>&1")
    if r != 0:
        # fallback: Kaggle ships its own torch — skip torch pins if the
        # exact-pinned set conflicts, keep the rest (einops, librosa, etc.)
        print("⚠ full requirements failed — retrying without torch pins…",
              flush=True)
        os.system("grep -vE '^(torch|torchaudio)' "
                  "DiffRhythm/requirements.txt > /tmp/req_notorch.txt")
        r = os.system("pip -q install -r /tmp/req_notorch.txt "
                      "> /tmp/pip2.log 2>&1")
        if r != 0:
            log = (Path("/tmp/pip2.log").read_text()[-800:]
                   if Path("/tmp/pip2.log").exists() else "")
            fail(f"pip install failed (both ways): {log}")
    os.system("pip -q install mutagen")

    # write LRC
    lrc = build_lrc()
    lrc_path = WORK / "song.lrc"
    lrc_path.write_text(lrc, encoding="utf-8")
    print(f"✍️ lyrics: {len(LYRIC_LINES)} lines", flush=True)

    style = STYLE.get(genre, "pop")
    out_dir = WORK / "out"
    out_dir.mkdir(exist_ok=True)
    # run from the DiffRhythm ROOT so `model`, `g2p`, `infer_utils` all
    # resolve (running from /kaggle/working gave "No module named 'model'")
    dr_root = Path("DiffRhythm").resolve()
    cmd = [
        sys.executable, "infer/infer.py",
        "--lrc-path", str(lrc_path),
        "--ref-prompt", style,
        "--audio-length", "95",
        "--output-dir", str(out_dir),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{dr_root}:{dr_root / 'infer'}"
    print(f"🎤 cooking {genre} WITH VOCALS on GPU…", flush=True)
    try:
        p = subprocess.run(cmd, cwd=str(dr_root), env=env,
                           capture_output=True, text=True, timeout=1200)
    except subprocess.TimeoutExpired:
        fail("DiffRhythm inference timed out after 20 min")
    if p.returncode != 0:
        tail = ((p.stdout or "") + (p.stderr or ""))[-1500:]
        fail(f"DiffRhythm inference failed (rc={p.returncode}): {tail}")

    wavs = list(out_dir.glob("*.wav")) + list(out_dir.glob("*.mp3"))
    if not wavs:
        fail(f"no output audio in {out_dir}")
    wav = wavs[0]
    print(f"🎵 output: {wav.name} ({wav.stat().st_size//1024} KB)", flush=True)

    # 🎚 MASTERING (2026-08-26): kill the "old radio" — FFT denoise, rumble
    # high-pass, mud-cut @180Hz, vocal presence @3.5kHz, glue compression,
    # limiter, then streaming loudness (loudnorm). Fall back to raw on error.
    mastered = out_dir / "mastered.wav"
    AFILT = ("highpass=f=70,"
             "afftdn=nr=14:nf=-24,"
             "equalizer=f=180:t=q:w=1:g=-2,"
             "equalizer=f=3500:t=q:w=2:g=3.5,"
             "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
             "alimiter=limit=0.93,"
             "loudnorm=I=-14:TP=-1.5:LRA=11")
    r = os.system(f'ffmpeg -y -v error -i "{wav}" -af "{AFILT}" '
                  f'-ar 44100 "{mastered}" > /tmp/ffm.log 2>&1')
    if r == 0 and mastered.exists() and mastered.stat().st_size > 80000:
        wav = mastered
        print("🎚 mastered: denoise + rumble-cut + presence + loudnorm ✔", flush=True)
    else:
        tail = Path("/tmp/ffm.log").read_text()[-200:] if Path("/tmp/ffm.log").exists() else ""
        print(f"⚠ mastering skipped ({tail}) — raw used", flush=True)

    stem = f"next_song--{genre}--en"
    mp3 = WORK / f"{stem}.mp3"
    r = os.system(f'ffmpeg -y -v error -i "{wav}" '
                  f'-codec:a libmp3lame -qscale:a 2 "{mp3}" '
                  f'> /tmp/ff.log 2>&1')
    if r != 0 or not mp3.exists() or mp3.stat().st_size < 80000:
        log = Path("/tmp/ff.log").read_text()[-400:] if Path("/tmp/ff.log").exists() else ""
        fail(f"ffmpeg convert failed (rc={r}): {log}")

    (WORK / f"{stem}.lyrics.txt").write_text("\n".join(LYRIC_LINES), encoding="utf-8")
    (WORK / f"{stem}.lrc.txt").write_text(lrc, encoding="utf-8")
    # success marker
    (WORK / "SUCCESS.txt").write_text(f"cooked {genre} via DiffRhythm\n", encoding="utf-8")
    print(f"✅ DONE: {mp3.name} ({mp3.stat().st_size//1024} KB) — vocals 🎤", flush=True)
    for f in WORK.glob("next_song*"):
        print("  ", f.name, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        fail("uncaught: " + traceback.format_exc()[-1500:])

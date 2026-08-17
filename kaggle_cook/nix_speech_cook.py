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
    "drift_phonk": "drift phonk, dark memphis phonk, distorted 808 bass, phonk cowbell melody, night drive, ominous",
    "deep_pop": "melancholic alt pop, deep pulsing synth bass, airy detuned pads, slow burn build, emotional",
    "dark_ambient": "dark ambient drone, slow evolving textures, distant thunder, tape hiss, unsettling calm",
    "lofi": "lofi hip hop, dusty vinyl crackle, warm rhodes chords, soft boom bap drums, rain on the window",
    "baroque_waltz": "playful baroque waltz, harpsichord and string quartet, vintage ballroom tape, whimsical",
    "disco_house": "french house disco, funky filtered bassline, four on the floor, lush string stabs, feel-good",
    "skyline_anthem": "anthemic folk-edm, progressive house festival lift, big piano stabs, euphoric",
    "villain_pop": "dark cinematic pop, villain aesthetic, music-box bells, heavy 808 sub, menacing elegance",
    "orbit_trap": "melodic trap, confident rap-sung bounce, rolling hi-hats, sliding 808 bass, spacey pads",
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
        fail(f"DiffRhythm clone failed (rc={r}): {log}")

    print("📦 installing DiffRhythm deps…", flush=True)
    r = os.system("pip -q install -r DiffRhythm/requirements.txt "
                  "> /tmp/pip.log 2>&1")
    if r != 0:
        log = Path("/tmp/pip.log").read_text()[-800:] if Path("/tmp/pip.log").exists() else ""
        fail(f"pip install failed (rc={r}): {log}")
    os.system("pip -q install mutagen")

    # write LRC
    lrc = build_lrc()
    lrc_path = WORK / "song.lrc"
    lrc_path.write_text(lrc, encoding="utf-8")
    print(f"✍️ lyrics: {len(LYRIC_LINES)} lines", flush=True)

    style = STYLE.get(genre, "pop")
    out_dir = WORK / "out"
    out_dir.mkdir(exist_ok=True)
    cmd = [
        "python", str(Path("DiffRhythm/infer/infer.py").resolve()),
        "--lrc-path", str(lrc_path),
        "--ref-prompt", style,
        "--audio-length", "95",
        "--output-dir", str(out_dir),
    ]
    print(f"🎤 cooking {genre} WITH VOCALS on GPU…", flush=True)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        fail("DiffRhythm inference timed out after 15 min")
    if p.returncode != 0:
        tail = ((p.stdout or "") + (p.stderr or ""))[-1200:]
        fail(f"DiffRhythm inference failed (rc={p.returncode}): {tail}")

    wavs = list(out_dir.glob("*.wav")) + list(out_dir.glob("*.mp3"))
    if not wavs:
        fail(f"no output audio in {out_dir}")
    wav = wavs[0]
    print(f"🎵 output: {wav.name} ({wav.stat().st_size//1024} KB)", flush=True)

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

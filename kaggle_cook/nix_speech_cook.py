# ⚡ NIX SPEECH VOCAL COOKER — runs on KAGGLE free T4/P100 GPU (no card)
# Installed by the GitHub workflow via `kaggle kernels push` when the queue
# is empty. Uses DiffRhythm (Apache-2.0) the CORRECT way: clone the repo +
# run infer/infer.py CLI (NOT the pip package — that was the kernel error).
# Outputs next_song--<genre>--en.mp3 + .lrc.txt + .lyrics.txt to
# /kaggle/working for GitHub to download.

import datetime
import os
import random
import subprocess
import sys
from pathlib import Path

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
LYRIC_TAGS = ["[verse]", "[chorus]", "[verse]", "[chorus]", "[bridge]", "[chorus]", "[outro]"]


def pick_genre() -> str:
    day = (datetime.datetime.now(datetime.timezone.utc) -
           datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)).days
    return GENRES[day % len(GENRES)]


def build_lrc(genre: str, dur: int = 95) -> str:
    """Build an LRC file with timestamps — DiffRhythm needs LRC format.
    Plain [mm:ss] + lyric text (no inline [verse] tags — the LRC parser
    chokes on them)."""
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

    # 1) clone DiffRhythm
    print("📦 cloning DiffRhythm…", flush=True)
    os.system("rm -rf DiffRhythm && git clone --depth 1 "
              "https://github.com/ASLP-lab/DiffRhythm.git")
    if not Path("DiffRhythm/infer/infer.py").exists():
        print("❌ clone failed", flush=True)
        sys.exit(1)

    # 2) install deps (Kaggle has torch preinstalled; DiffRhythm needs the rest)
    print("📦 installing DiffRhythm deps…", flush=True)
    os.system("pip -q install -r DiffRhythm/requirements.txt")
    os.system("pip -q install mutagen")

    # 3) write LRC lyrics
    lrc = build_lrc(genre)
    lrc_path = Path("/kaggle/working/song.lrc")
    lrc_path.write_text(lrc, encoding="utf-8")
    print(f"✍️ lyrics: {len(LYRIC_LINES)} lines → {lrc_path}", flush=True)

    # 4) run inference (95s is the min supported length)
    style = STYLE.get(genre, "pop")
    cmd = [
        "python", "DiffRhythm/infer/infer.py",
        "--lrc-path", str(lrc_path),
        "--ref-prompt", style,
        "--audio-length", "95",
        "--output-dir", "/kaggle/working/out",
    ]
    print(f"🎤 cooking {genre} WITH VOCALS on GPU…\n{' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd="/kaggle/working", capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ inference failed:", flush=True)
        print((r.stdout or "")[-2000:], flush=True)
        print((r.stderr or "")[-2000:], flush=True)
        sys.exit(1)
    print("✅ inference ok", flush=True)

    # 5) find output wav
    out_dir = Path("/kaggle/working/out")
    wavs = list(out_dir.glob("*.wav")) + list(out_dir.glob("*.mp3"))
    if not wavs:
        print("❌ no output audio found in", out_dir, flush=True)
        sys.exit(1)
    wav = wavs[0]
    print(f"🎵 output: {wav} ({wav.stat().st_size//1024} KB)", flush=True)

    # 6) convert + save as next_song
    stem = f"next_song--{genre}--en"
    mp3 = Path("/kaggle/working") / f"{stem}.mp3"
    os.system(f'ffmpeg -y -v error -i "{wav}" -codec:a libmp3lame -qscale:a 2 "{mp3}"')
    if not mp3.exists() or mp3.stat().st_size < 80000:
        print("❌ mp3 conversion failed", flush=True)
        sys.exit(1)
    # sidecars
    (Path("/kaggle/working") / f"{stem}.lyrics.txt").write_text(
        "\n".join(LYRIC_LINES), encoding="utf-8")
    (Path("/kaggle/working") / f"{stem}.lrc.txt").write_text(lrc, encoding="utf-8")
    print(f"✅ DONE: {mp3} ({mp3.stat().st_size//1024} KB) — vocals 🎤", flush=True)
    print("FILES:", flush=True)
    for f in Path("/kaggle/working").glob("next_song*"):
        print(" ", f.name, flush=True)


if __name__ == "__main__":
    main()

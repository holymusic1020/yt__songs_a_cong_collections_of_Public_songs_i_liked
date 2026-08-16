# ⚡ NIX SPEECH VOCAL COOKER — runs on KAGGLE free T4/P100 GPU (no card)
# Installed by the GitHub workflow via `kaggle kernels push` when the queue
# is empty. Self-contained: picks the genre by date (same wheel as main.py),
# writes lyrics (Gemini secret if present, else the built-in bank), cooks a
# FULL song WITH SUNG VOCALS using DiffRhythm (Apache-2.0), and saves
# next_song--<genre>--en.mp3 + .lrc.txt + .lyrics.txt to /kaggle/working
# for GitHub to download via `kaggle kernels output`.

import os
import random
from datetime import datetime, timezone
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

LYRIC_BANK = (
    "[verse]\nmidnight city lights below\nwe ride the neon flow\n"
    "[chorus]\nnix speech in the night\nwe're glowing, burning bright\n"
    "[verse]\nheadlights cut the rain\nwe're chasing every lane\n"
    "[chorus]\nnix speech in the night\nwe're glowing, burning bright\n"
    "[outro]\nglow until the morning light"
)


def pick_genre() -> str:
    # same wheel as main.py: EP count from date (2026-08-01 = start)
    day = (datetime.now(timezone.utc) - datetime(2026, 8, 1, tzinfo=timezone.utc)).days
    return GENRES[day % len(GENRES)]


def write_lyrics(genre: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        try:
            from google import genai
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=(
                    f"Write tagged lyrics ([verse]/[chorus]/[bridge]/[outro]) for a "
                    f"{genre} song, 60-90 words, night-city imagery, original, no famous "
                    f"phrases. Return ONLY the tagged lyrics."
                ))
            if resp.text and len(resp.text) > 40:
                return resp.text.strip()
        except Exception:
            pass
    return LYRIC_BANK


def main():
    genre = pick_genre()
    print(f"🎹 genre: {genre}", flush=True)
    lyrics = write_lyrics(genre)
    print("✍️ lyrics ready", flush=True)

    print("📦 installing DiffRhythm…", flush=True)
    os.system("pip -q install git+https://github.com/ASLP-lab/DiffRhythm.git")
    os.system("pip -q install demucs")

    from diffrhythm import DiffRhythm
    print("🎼 loading model…", flush=True)
    model = DiffRhythm()
    model.load_model("ASLP/DiffRhythm-base")   # ~8GB VRAM → T4/P100 fits

    seconds = 150  # 2:30 song
    print(f"🎤 cooking {seconds}s {genre} WITH VOCALS on GPU…", flush=True)
    model.inference(
        lyrics=lyrics,
        style=STYLE.get(genre, "pop"),
        duration=seconds,
        seed=random.randint(0, 2**31),
        chunked=False,
    )
    # DiffRhythm saves to /kaggle/working/song.wav by default
    wav = Path("/kaggle/working/song.wav")
    if not wav.exists():
        cands = list(Path("/kaggle/working").glob("*.wav"))
        if not cands:
            raise RuntimeError("no output wav produced")
        wav = cands[0]

    stem = f"next_song--{genre}--en"
    mp3 = Path("/kaggle/working") / f"{stem}.mp3"
    os.system(f'ffmpeg -y -v error -i "{wav}" -codec:a libmp3lame -qscale:a 2 "{mp3}"')
    (Path("/kaggle/working") / f"{stem}.lyrics.txt").write_text(lyrics, encoding="utf-8")
    # rough evenly-timed LRC so the karaoke video has words
    lines = [l for l in lyrics.splitlines() if l.strip() and not l.strip().startswith("[")]
    step = seconds / max(1, len(lines))
    lrc = "\n".join(f"[{int(i*step//60)}:{int(i*step%60):02d}] {l}"
                    for i, l in enumerate(lines))
    (Path("/kaggle/working") / f"{stem}.lrc.txt").write_text(lrc, encoding="utf-8")
    print(f"✅ DONE: {mp3} ({mp3.stat().st_size//1024} KB) — vocals 🎤", flush=True)


if __name__ == "__main__":
    main()

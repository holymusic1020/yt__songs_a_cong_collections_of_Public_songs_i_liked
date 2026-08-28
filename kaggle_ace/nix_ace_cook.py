"""🎤 NIX × ACE-Step OFFLINE vocal cook — Kaggle free T4, $0, NO quota.

NOT the HF space (whose ZeroGPU quota is dead for this account) — the
open-source ACE-Step v1 (3.5B, Apache-2.0) running directly on your own
Kaggle GPU. The GitHub lane (src/music_ace_kaggle.py) stamps LYRIC_LINES,
AUDIO_DURATION_S, GENRE_KEY and SEED into a temp copy of this script before
pushing — every cook = fresh Gemini words.

Contract with the GitHub lane:
  · success → /kaggle/working/next_song--<stem>.mp3 (>= 80 KB, SUNG) +
              next_song--<stem>.lrc.txt
  · failure → /kaggle/working/error.txt, non-zero exit
"""
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import date
from pathlib import Path

WORK = Path("/kaggle/working")

# ── stamped by the GitHub lane (do not edit by hand) ──────────────────────
SEED = 20260826
AUDIO_DURATION_S = 150
GENRE_KEY = "deep_pop"
LYRIC_LINES = [
    "midnight glow on the empty street, echoes pull me in",
    "every shadow keeps a secret underneath my skin",
    "slowly drifting where the quiet frequencies begin",
    "hold the static till it feel like something we can win",
    "take me under, where the low light never ends",
    "all the borders blur between the signal and the noise",
    "take me under, let the current shape the bends",
    "we rise above it with the calmest kind of voice",
]
# ──────────────────────────────────────────────────────────────────────────

ACE_TAGS = {
    "drift_phonk":  "phonk, moody night-drive atmosphere, drifting synths, punchy drift bass, "
                    "clear {v} vocals, 120 bpm, modern production",
    "deep_pop":     "emotional deep pop, warm analog pads, deep sub bass, clean intimate {v} vocals, "
                    "100 bpm, melancholic, modern mix",
    "dark_ambient": "cinematic ambient-pop ballad, ethereal pads, soft piano, airy close {v} vocals, "
                    "72 bpm, intimate, spacious mix",
    "lofi":         "lo-fi pop, warm tape texture, mellow keys, dusty drums, soft {v} vocals, "
                    "80 bpm, chill, cozy mix",
    "baroque_waltz": "baroque waltz pop, harpsichord, strings ensemble, elegant {v} vocals, "
                    "3/4 time, romantic",
    "disco_house":  "funky disco house, groovy bassline, four-on-the-floor drums, soulful {v} vocals, "
                    "118 bpm, uplifting, glossy mix",
    "skyline_anthem": "anthemic pop, big cinematic synths, soaring chorus, powerful {v} vocals, "
                    "128 bpm, euphoric, stadium mix",
    "villain_pop":  "dark pop, moody sub bass, cinematic tension, sultry {v} vocals, "
                    "90 bpm, dramatic, punchy mix",
    "orbit_trap":   "melodic space trap, dreamy synths, hard 808s, smooth {v} vocals, "
                    "140 bpm, futuristic, clean mix",
}


def sh(cmd, timeout=1800):
    print("  $ " + " ".join(str(c) for c in cmd)[:150], flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print((r.stdout or "")[-600:], flush=True)
        print((r.stderr or "")[-900:], flush=True)
    return r


def build_lyrics(lines):
    lines = [l.strip() for l in lines if l.strip()]
    if len(lines) >= 4:
        half = max(2, len(lines) // 2)
        verse, chorus = lines[:half], lines[half:]
        return "[verse]\n" + "\n".join(verse) + "\n\n[chorus]\n" + "\n".join(chorus)
    if lines:
        return "[verse]\n" + "\n".join(lines)
    return ""  # instrumental


def main():
    t0 = time.time()
    print("=== NIX × ACE-Step OFFLINE (your Kaggle GPU · $0 · no HF quota) ===", flush=True)

    # 1) install — SURGICAL (v2, 2026-08-26): --no-deps for the package itself,
    # then only the runtime deps. requirements.txt pulls gradio + UNPINNED
    # torch/vision/audio → pip used to REINSTALL torch (multi-GB, >60-min
    # hang: the first cook outlived its leash). Cut it. Kaggle already has
    # torch/vision/audio/tokenizers/numpy — do not touch.
    sh(["pip", "install", "-q", "--no-deps",
        "git+https://github.com/ace-step/ACE-Step.git"], timeout=900)
    sh(["pip", "install", "-q",
        "diffusers>=0.33.0", "transformers==4.50.0", "accelerate==1.6.0",
        "librosa", "soundfile", "loguru", "pypinyin", "py3langid",
        "hangul-romanize", "num2words", "spacy==3.8.4", "cutlet",
        "fugashi[unidic-lite]", "opencc-python-reimplemented",
        "click", "datasets", "tqdm"], timeout=1200)

    # T4 has NO bf16 — force fp16 (≈7 GB weights) via the pipeline's env hook
    os.environ["ACE_PIPELINE_DTYPE"] = "float16"
    os.environ.setdefault("HF_HOME", "/kaggle/working/hf_cache")

    import torch
    assert torch.cuda.is_available(), "no GPU on this kernel (enable_gpu: true?)"
    print(f"torch {torch.__version__} · gpu: {torch.cuda.get_device_name(0)}", flush=True)
    from acestep.pipeline_ace_step import ACEStepPipeline

    voice = ["female", "male"][date.today().toordinal() % 2]
    prompt = ACE_TAGS.get(GENRE_KEY, ACE_TAGS["deep_pop"]).format(v=voice)
    lyrics_txt = build_lyrics(LYRIC_LINES)
    dur = float(max(60, min(240, int(AUDIO_DURATION_S))))
    print(f"🎶 genre={GENRE_KEY} · voice={voice} · dur={dur:.0f}s · seed={SEED}", flush=True)
    print(f"   tags: {prompt}", flush=True)

    out_dir = WORK / "ace_raw"
    out_dir.mkdir(exist_ok=True)

    def gen(offload: bool):
        pipe = ACEStepPipeline(
            checkpoint_dir="/kaggle/working/ace_ckpt",
            device_id=0, dtype="bfloat16",          # env hook upgrades to fp16
            torch_compile=False, cpu_offload=offload, quantized=False,
            overlapped_decode=False)
        return pipe(format="wav", audio_duration=dur, prompt=prompt,
                    lyrics=lyrics_txt, infer_step=60, guidance_scale=15.0,
                    manual_seeds=[SEED], save_path=str(out_dir))

    # v3 autopsy (2026-08-28): kernels v3/v4 died silently at 10/20 min —
    # classic 16GB OOM paths (init + gen). Start with cpu_offload=True:
    # slower (models shuttle CPU<->GPU) but it CANNOT OOM-kill the cook.
    # If offload-free fits this kernel dies... no — offload first, always.
    print("📊 gpu mem at start:", end=" ", flush=True)
    try:
        print(f"{torch.cuda.memory_allocated()/1e9:.1f}G", flush=True)
    except Exception:
        print("n/a", flush=True)
    import gc
    gen(offload=True)

    wavs = sorted(out_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
    if not wavs:
        wavs = sorted(WORK.rglob("*.wav"), key=lambda p: p.stat().st_mtime)
    assert wavs, "ACE-Step produced no wav"
    raw = wavs[-1]
    print(f"🎼 raw generation: {raw.name} ({raw.stat().st_size//1024} KB)", flush=True)

    # 2) master + export (vocal-forward chain, 44.1k mp3 192k — radio loud)
    stem = f"next_song--ace_{GENRE_KEY}_{SEED}"
    mp3 = WORK / f"{stem}.mp3"
    ff = sh(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
             "-af", ("highpass=f=85,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=140,"
                     "loudnorm=I=-14:TP=-1:LRA=11,alimiter=limit=0.95,"
                     "aresample=44100"),
             "-ac", "2", "-b:a", "192k", str(mp3)], timeout=600)
    assert ff.returncode == 0 and mp3.exists() and mp3.stat().st_size >= 80_000, \
        "ffmpeg master/export failed"
    print(f"🔥 mastered {mp3.name} ({mp3.stat().st_size//1024} KB)", flush=True)

    # 3) sidecars: rough lrc (even split) + lyrics + result json
    if lyrics_txt:
        sung = [l for l in lyrics_txt.splitlines() if l.strip() and not l.startswith("[")]
        step = dur / max(1, len(sung) + 1)
        lrc = "\n".join(
            f"[{int((i+1)*step//60):02d}:{int((i+1)*step%60):05.2f}] {l}"
            for i, l in enumerate(sung))
        (WORK / f"{stem}.lrc.txt").write_text(lrc + "\n", encoding="utf-8")
        (WORK / f"{stem}.lyrics.txt").write_text(lyrics_txt + "\n", encoding="utf-8")
    (WORK / "SUCCESS.txt").write_text(
        f"ace-offline ok · {dur:.0f}s · {GENRE_KEY} · {voice} · {mp3.stat().st_size}\n")
    (WORK / "out.json").write_text(json.dumps({
        "ok": True, "lane": "ace-kaggle", "duration_s": dur, "genre": GENRE_KEY,
        "voice": voice, "bytes": mp3.stat().st_size}))
    print(f"✅ ACE-OFFLINE COOKED in {int(time.time()-t0)}s — sending it home 🚀", flush=True)


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    try:
        main()
    except SystemExit:
        (WORK / "log.txt").write_text("systemexit during main\n")
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        (WORK / "error.txt").write_text(tb[-2500:])   # lane downloads & prints this
    # NOTE (v3): do NOT re-raise — a raised kernel = status error = the lane
    # never fetches the output and the traceback dies unseen. Exit 0 so the
    # output (error.txt on failure, mp3 on success) always comes home.

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
RUN_TOKEN = "boot"
TG_TOKEN = ""
TG_CHAT = ""
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


_TG_KEYS = ("START", "uninstall done", "install done", "curated deps done",
            "smoke probe", "imported", "gen()", "wav found", "mastered",
            "COOKED", "FATAL", "systemexit", "tg audio")


def _tg(text):
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        import urllib.request
        import urllib.parse
        _d = urllib.parse.urlencode({
            "chat_id": TG_CHAT, "text": text,
            "disable_notification": True}).encode()
        urllib.request.urlopen(urllib.request.Request(
            "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage",
            data=_d), timeout=8).read()
    except Exception:
        pass


def _tg_file(path, caption):
    if not (TG_TOKEN and TG_CHAT):
        return
    for method, field in (("sendAudio", "audio"), ("sendDocument", "document")):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-m", "280",
                 "https://api.telegram.org/bot" + TG_TOKEN + "/" + method,
                 "-F", "chat_id=" + TG_CHAT,
                 "-F", field + "=@" + str(path),
                 "-F", "caption=" + caption],
                capture_output=True, text=True, timeout=300)
            if '"ok":true' in (r.stdout or ""):
                mark("phase: tg audio sent via " + method)
                return
        except Exception:
            pass
    mark("phase: tg audio send FAILED")


def mark(msg):
    print(msg, flush=True)
    try:
        WORK.mkdir(parents=True, exist_ok=True)
        with open(WORK / "log.txt", "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass
    if any(k in msg for k in _TG_KEYS):
        _tg("🎤 ace v6 " + RUN_TOKEN + " · " + msg[:160])


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
    mark("=== ACE NOTEBOOK v6 START (tg live + run token) ===")
    print("=== NIX × ACE-Step OFFLINE (your Kaggle GPU · $0 · no HF quota) ===", flush=True)

    # 🔩 TORCH SWAP (v4, 2026-08-29 — ROOT CAUSE of kernels v3-v6 dying):
    # Kaggle's current base-image torch DROPPED sm_75 (Turing): first CUDA op
    # in umt5's embed_tokens → "no kernel image is available for execution".
    # DiffRhythm sings on the SAME T4 because its requirements pin
    # torchaudio 2.6.0 → torch 2.6.0 (PyPI cu124 build has sm_75). Mirror the
    # stack that is PROVEN working on this iron — swap BEFORE anything imports.
    mark("phase: torch uninstall"); sh(["pip", "uninstall", "-y", "-q", "torch", "torchvision", "torchaudio"], timeout=600); mark("phase: torch uninstall done")
    sh(["pip", "install", "-q", "torch==2.6.0", "torchvision==0.21.0",
        "torchaudio==2.6.0"], timeout=1800); mark("phase: torch 2.6.0 install done")

    # 1) install — SURGICAL (v2, 2026-08-26): --no-deps for the package itself,
    # then only the runtime deps. requirements.txt pulls gradio + UNPINNED
    # torch/vision/audio → pip used to REINSTALL torch (multi-GB, >60-min
    # hang: the first cook outlived its leash). Cut it. Kaggle already has
    # torch/vision/audio/tokenizers/numpy — do not touch.
    mark("phase: ace git install"); sh(["pip", "install", "-q", "--no-deps",
        "git+https://github.com/ace-step/ACE-Step.git"], timeout=900); mark("phase: ace git install done")
    sh(["pip", "install", "-q",
        "diffusers>=0.33.0", "transformers==4.50.0", "accelerate==1.6.0",
        "librosa", "soundfile", "loguru", "pypinyin", "py3langid",
        "hangul-romanize", "num2words", "spacy==3.8.4", "cutlet",
        "fugashi[unidic-lite]", "opencc-python-reimplemented",
        "click", "datasets", "tqdm"], timeout=1200); mark("phase: curated deps done")

    # T4 has NO bf16 — force fp16 (≈7 GB weights) via the pipeline's env hook
    os.environ["ACE_PIPELINE_DTYPE"] = "float16"
    os.environ.setdefault("HF_HOME", "/kaggle/working/hf_cache")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    mark("phase: importing torch")
    import torch
    assert torch.cuda.is_available(), "no GPU on this kernel (enable_gpu: true?)"
    si = (f"python {sys.version.split()[0]}\ntorch {torch.__version__} (cuda {torch.version.cuda})\n"
          f"gpu: {torch.cuda.get_device_name(0)} capability {torch.cuda.get_device_capability(0)}\n")
    (WORK / "log.txt").write_text(si)   # corpse's birth certificate — comes home in the download
    print(si, flush=True)
    # 🔥 ARCH SMOKE TEST (v4): one CUDA op RIGHT NOW — a dead-arch env must
    # die HERE in seconds, not 20 minutes deep in a text encoder's embedding.
    probe = torch.randn(64, device="cuda")
    _ = (probe * probe).sum().item(); del probe
    torch.cuda.synchronize()
    mark("phase: CUDA smoke probe PASSED")
    print("✔ CUDA arch smoke test passed", flush=True)
    mark("phase: importing ACEStepPipeline")
    from acestep.pipeline_ace_step import ACEStepPipeline
    mark("phase: ACEStepPipeline imported")

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
    mark("phase: building pipeline (weights dl inside)")
    print("📊 gpu mem at start:", end=" ", flush=True)
    try:
        print(f"{torch.cuda.memory_allocated()/1e9:.1f}G", flush=True)
    except Exception:
        print("n/a", flush=True)
    import gc
    try:
        _gf, _gt = torch.cuda.mem_get_info()
        _ma = next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable"))
        mark(f"phase: pre-gen mem · gpu {_gf/1e9:.1f}/{_gt/1e9:.1f}G · {_ma.strip()}")
    except Exception:
        pass
    mark("phase: gen() start")
    gen(offload=True)
    mark("phase: gen() returned")

    wavs = sorted(out_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
    if not wavs:
        wavs = sorted(WORK.rglob("*.wav"), key=lambda p: p.stat().st_mtime)
    assert wavs, "ACE-Step produced no wav"
    raw = wavs[-1]
    mark(f"phase: wav found {raw.name}")
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
    mark(f"phase: mastered {mp3.name}")
    print(f"🔥 mastered {mp3.name} ({mp3.stat().st_size//1024} KB)", flush=True)
    _tg_file(mp3, f"🎤 ACE-OFFLINE v6 {RUN_TOKEN} · {dur:.0f}s {GENRE_KEY} · {voice} vocals · EARS PLEASE 👂")

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
        f"RUN_TOKEN={RUN_TOKEN}\n"
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
        mark("systemexit during main")
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            (WORK / "error.txt").write_text(tb[-2500:])   # lane downloads & prints this
        except Exception:
            pass
        mark("FATAL: " + (tb.strip().splitlines()[-1] if tb.strip() else "?")[:180])
    # NOTE (v3): do NOT re-raise — a raised kernel = status error = the lane
    # never fetches the output and the traceback dies unseen. Exit 0 so the
    # output (error.txt on failure, mp3 on success) always comes home.

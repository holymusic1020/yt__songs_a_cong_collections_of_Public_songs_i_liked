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
import shutil
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
    # 🎯 v14 chart-class implants (boss 2026-08-30: Espresso / Astronaut In The
    # Ocean / Sommernacht TYPE — not copies — "make this vibe"). Delayed until
    # free-first squeeze: radio-ready gloss descriptors steer ACE's average take.
    "chart_pop":    "glossy chart pop, funky plucky guitars, tight disco-pop drums, "
                    "bright confident {v} vocals, 105 bpm, polished radio-ready mix, "
                    "unstoppable earworm chorus",
    "melodic_trap": "melodic rap anthem, icy atmospheric pads, booming 808 bass, "
                    "crisp trap hats, catchy sung-rap {v} vocals, 150 bpm, "
                    "radio-ready hip-hop mix, anthemic chant hook",
    "summer_rap":   "summer melodic rap, warm afrobeat guitar groove, sunny bouncy "
                    "percussion, laid-back sing-rap {v} vocals, 98 bpm, feel-good "
                    "golden-hour mix, big sing-along chorus",
}


_TG_KEYS = ("START", "uninstall done", "install done", "curated deps done",
            "smoke probe", "imported", "gen()", "wav found", "mastered",
            "COOKED", "FATAL", "systemexit", "tg audio", "lrc aligned",
            "whisper", "even split", "karaoke", "realism")


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
    """TG the file to the boss AND return {message_id, file_id, method}.

    v12 (2026-08-30): the Kaggle kernels-output API keeps DROPPING the mp3
    out of the bundle (boss got a demo with NO song — all lanes fell to the
    instrumental engine). The TG copy always lands, so the lane now pulls
    the song straight from Telegram using the file_id we persist in
    tg_ids.json (a tiny text file — the bundle never drops those).
    """
    if not (TG_TOKEN and TG_CHAT):
        return None
    for method, field in (("sendAudio", "audio"), ("sendDocument", "document")):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-m", "280",
                 "https://api.telegram.org/bot" + TG_TOKEN + "/" + method,
                 "-F", "chat_id=" + TG_CHAT,
                 "-F", field + "=@" + str(path),
                 "-F", "caption=" + caption],
                capture_output=True, text=True, timeout=300)
            try:
                _ok = bool(json.loads(r.stdout or "{}").get("ok"))
            except Exception:
                _ok = '"ok":true' in (r.stdout or "")
            if _ok:
                mark("phase: tg audio sent via " + method)
                try:
                    res = json.loads(r.stdout or "{}").get("result", {}) or {}
                    return {"message_id": res.get("message_id", 0),
                            "file_id": (res.get(field) or {}).get("file_id", ""),
                            "method": method}
                except Exception:
                    return {"message_id": 0, "file_id": "", "method": method}
        except Exception:
            pass
    mark("phase: tg audio send FAILED")
    return None


def mark(msg):
    print(msg, flush=True)
    try:
        WORK.mkdir(parents=True, exist_ok=True)
        with open(WORK / "log.txt", "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass
    if any(k in msg for k in _TG_KEYS):
        _tg("🎤 ace v12 " + RUN_TOKEN + " · " + msg[:160])


def sh(cmd, timeout=1800):
    print("  $ " + " ".join(str(c) for c in cmd)[:150], flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print((r.stdout or "")[-600:], flush=True)
        print((r.stderr or "")[-900:], flush=True)
    return r


def build_lyrics(lines):
    """v9 (boss 2026-08-29): "vocals have no feeling — no stops, unfinished".
    Root cause: 8 flat lines over 150s = ~15-18s per line stretched forever.
    Now: short punctuated lines in real sections, hook repeats twice — ACE
    breathes at punctuation and section tags. Text-side only; zero timbre.
    v13 (boss 2026-08-30, "unmatching stops… give some life"): real song ARC —
    with a 10+ line sheet ACE now gets verse/chorus/verse/chorus/BRIDGE/chorus
    so sections MOVE forward instead of stalling/restarting mid-song."""
    lines = [l.strip() for l in lines if l.strip()]
    if not lines:
        return ""  # instrumental
    lines = [l if l[-1:] in ",.!?—–" else l + "," for l in lines]
    n = len(lines)
    if n >= 8:
        hook = [h.rstrip(",.") + ("," if i == 0 else ".") for i, h in enumerate(lines[-2:])]
        body = lines[:-2]
        if len(body) >= 10:
            # full arc: v1 · chorus · v2 · chorus · bridge · final chorus
            third = len(body) // 3
            v1, v2, br = body[:third], body[third:2 * third], body[2 * third:]
            return ("\n".join(["[verse]", *v1, "[chorus]", *hook,
                               "[verse]", *v2, "[chorus]", *hook,
                               "[bridge]", *br, "[chorus]", *hook]))
        half = max(2, len(body) // 2)
        v1, v2 = body[:half], body[half:]
        return ("\n".join(["[verse]", *v1, "[chorus]", *hook,
                           "[verse]", *v2, "[chorus]", *hook]))
    if n >= 4:
        half = max(2, n // 2)
        verse, chorus = lines[:half], lines[half:]
        return "[verse]\n" + "\n".join(verse) + "\n\n[chorus]\n" + "\n".join(chorus)
    return "[verse]\n" + "\n".join(lines)


# 🎚 v13 realism suffix (boss 2026-08-30: "doesn't feel real… unmatching
# stops… full attraction, give some life"). Appended to EVERY genre's tags:
# continuity + human phrasing + movement, so ACE delivers one living take,
# not stitched fragments — phonk, lofi, anthem, waltz, all of them.
REALISM = (", one continuous performance, seamless transitions, no stops, "
           "no silence gaps, natural human vocal phrasing, realistic breathing, "
           "vocal ad-libs, dynamic arrangement, professional studio production")


def build_prompt(genre_key, voice):
    base = ACE_TAGS.get(genre_key, ACE_TAGS["deep_pop"]).format(v=voice)
    return base + REALISM


def main():
    t0 = time.time()
    mark("=== ACE NOTEBOOK v11 START (goat chain + breathing lyrics + TRANSCRIPT karaoke) ===")
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
    prompt = build_prompt(GENRE_KEY, voice)
    mark("phase: v13 realism tags + bridge arc · one living take")
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
                    lyrics=lyrics_txt, infer_step=80, guidance_scale=15.0,
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
    # 🔙 v8 (2026-08-29, boss ears): enchant made the voice MORE robotic —
    # experiment OVER. Exact boss-approved v6 chain returns, untouched.
    ff = sh(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
             "-af", ("highpass=f=85,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=140,"
                     "loudnorm=I=-14:TP=-1:LRA=11,alimiter=limit=0.95,"
                     "aresample=44100"),
             "-ac", "2", "-b:a", "192k", str(mp3)], timeout=600)
    assert ff.returncode == 0 and mp3.exists() and mp3.stat().st_size >= 80_000, \
        "ffmpeg master/export failed"
    mark(f"phase: mastered (plain v6 chain) {mp3.name}")
    print(f"🔥 mastered {mp3.name} ({mp3.stat().st_size//1024} KB)", flush=True)
    tg_mp3 = None
    tg_lrc = None
    tg_mp3 = _tg_file(mp3, f"🎤 ACE-OFFLINE v13 {RUN_TOKEN} · {dur:.0f}s {GENRE_KEY} · {voice} · realism chain: bridge arc + living-take tags 🔥 · karaoke=what-you-HEAR 🎯 · EARS PLEASE 👂")

    # 3) sidecars: rough lrc (even split) + lyrics + result json
    if lyrics_txt:
        sung = [l for l in lyrics_txt.splitlines() if l.strip() and not l.startswith("[")]
        lrc = None
        # 🎤⏱ v11 (2026-08-29, boss: "its not even saying anything related to
        # the sub"): the sheet was the wrong source — ACE sings its OWN phrasing.
        # From now on the karaoke IS the audio: transcribe the master, chunk the
        # WORD-LEVEL transcript into captions. Screen can never disagree with ears.
        try:
            mark("phase: karaoke from the AUDIO ITSELF (whisper small.en)")
            sh(["pip", "install", "-q", "-U", "openai-whisper"], timeout=900)
            import whisper
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            wm = whisper.load_model("small.en")
            res = wm.transcribe(str(mp3), language="en", fp16=True,
                                temperature=0, condition_on_previous_text=False,
                                word_timestamps=True)
            words = []
            for x in res["segments"]:
                for w in x.get("words", []):
                    wt = w["word"].strip()
                    if wt:
                        words.append((float(w["start"]), float(w["end"]), wt))
            caps, cur, cur_start = [], [], None
            for ws_, we_, wt_ in words:
                if not cur:
                    cur_start = ws_
                    cur = [(ws_, we_, wt_)]
                    continue
                gap = ws_ - cur[-1][1]
                span = we_ - cur_start
                last = cur[-1][2].rstrip()
                if len(cur) >= 7 or (len(cur) >= 4 and (
                        gap >= 0.6 or span >= 3.5
                        or last.endswith((".", "!", "?")))):
                    caps.append((cur_start, cur[-1][1],
                                 " ".join(w for _, _, w in cur)))
                    cur_start, cur = ws_, [(ws_, we_, wt_)]
                else:
                    cur.append((ws_, we_, wt_))
            if cur:
                caps.append((cur_start, cur[-1][1],
                             " ".join(w for _, _, w in cur)))
            nw = sum(len(c[2].split()) for c in caps)
            if len(caps) >= 8 and nw >= 40:
                lines_out = []
                for s0, _e0, txt in caps:
                    txt = txt.strip()
                    if txt:
                        txt = txt[0].upper() + txt[1:]
                    lines_out.append((max(0.0, s0 - 0.05), txt))
                lrc = "\n".join(f"[{int(ts//60):02d}:{ts%60:05.2f}] {txt}"
                                for ts, txt in lines_out) + "\n"
                mark(f"phase: karaoke = TRANSCRIPT small.en · {len(lines_out)} captions · {nw} words")
            else:
                mark(f"phase: transcript too thin ({len(caps)} caps/{nw} words) — even split stands")
        except Exception as e:
            mark(f"phase: whisper align failed ({type(e).__name__}) — even split stands")
        if lrc is None:
            step = dur / max(1, len(sung) + 1)
            lrc = "\n".join(
                f"[{int((i+1)*step//60):02d}:{int((i+1)*step%60):05.2f}] {l}"
                for i, l in enumerate(sung))
        (WORK / f"{stem}.lrc.txt").write_text(lrc, encoding="utf-8")
        (WORK / f"{stem}.lyrics.txt").write_text(lyrics_txt + "\n", encoding="utf-8")
        tg_lrc = _tg_file(WORK / f"{stem}.lrc.txt",
                          f"🎤⏱ karaoke map {RUN_TOKEN} — captions transcribed FROM the audio (screen can never disagree)")
    # 🛟 v12 (2026-08-30, boss demo had NO vocals at all): persist the TG
    # file_ids so the lane can pull the song from Telegram even when Kaggle's
    # output API drops the mp3 from the bundle.
    (WORK / "tg_ids.json").write_text(json.dumps(
        {"run_token": RUN_TOKEN, "mp3": tg_mp3 or {}, "lrc": tg_lrc or {}}))
    # 🧹 v12: slim /kaggle/working — 1.6GB of model-cache junk crowds the song
    # out of the output bundle. Checkpoints are dead weight after gen().
    for _dead in ("hf_cache", "ace_ckpt", "ace_out", "checkpoints"):
        try:
            shutil.rmtree(WORK / _dead, ignore_errors=True)
        except Exception:
            pass
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

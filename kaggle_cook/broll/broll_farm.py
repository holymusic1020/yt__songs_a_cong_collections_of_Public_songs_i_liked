"""🎬 b-roll farm — the GPU half. Runs ONLY as its own Kaggle kernel.

Why a farm and not a live render (boss, 2026-10-10): a real video model costs
minutes per 5 seconds. The release must not wait minutes for anything — the
song is the goal — so generation happens on its own schedule, hours ahead of
the next upload, and the release just reads the shelf.

MODEL CHOICE, and the honesty that goes with it:
  · Wan2.1-T2V-1.3B (Apache-2.0 → monetisable on YouTube) is the workhorse.
    ~832x480, 81 frames @16fps ≈ 5 s, and on a Kaggle T4 that is roughly
    3-6 min per clip. Upscaled to 1920x1080 with lanczos, it reads as soft
    cinematic movement BEHIND text — exactly what our frames are: a background.
  · The 14B / HunyuanVideo class is NOT here on purpose. At ~25-60 min per
    5 s it would eat the account's whole weekly GPU quota that the SONG lane
    needs, and boss was explicit: it must not touch the song "even an inch".
  · `BROLL_MODEL` can point at a bigger Wan tag if the quota math ever changes.

SELF-CLOCKED AND SELF-STOPPING: it never runs past BROLL_HOURS (default 3 h)
and stops early if the shelf is full. Kaggle's free tier is 30 h/week; the
music lane uses about 1.5-2 h of that. At 3 h/night we take <= 21 h, leaving
the song lane its full budget with a night skipped whenever it looks tight.
"""
import json
import os
import subprocess
import time
from pathlib import Path

HOURS = float(os.environ.get("BROLL_HOURS", "3") or 3)
SHOTS_PER_GENRE = int(os.environ.get("BROLL_SHOTS", "8") or 8)
MODEL = os.environ.get("BROLL_MODEL", "Wan-AI/Wan2.1-T2V-1.3B-Diffusers")
OUT = Path("/kaggle/working/broll")
MANIFEST = OUT / "manifest.json"
FRAMES, W, H, FPS = 81, 832, 480, 16
TARGET_W, TARGET_H, TARGET_FPS, CLIP_S = 1920, 1080, 24, 8.0


def log(msg):
    print(f"[broll-farm] {msg}", flush=True)


def prompts():
    """genre -> list of shot descriptions, from the repo's own scene banks.

    `broll_prompts.json` is committed by GitHub (tools/broll_farm.py writes it
    from video_gemini.SCENES, so a shot always matches what that genre's video
    is about). If it is missing, the kernel exits quietly and the shelf simply
    does not grow — the release is unaffected either way.
    """
    for cand in ("/kaggle/input/broll-prompts/broll_prompts.json",
                 "/kaggle/working/broll_prompts.json"):
        p = Path(cand)
        if p.exists():
            return json.loads(p.read_text())
    return {}


def main():
    t0 = time.monotonic()
    lib = prompts()
    if not lib:
        log("no broll_prompts.json in the session — nothing to render, exiting")
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({"clips": [], "skipped": "no prompts"}))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    import torch                                  # noqa: E402
    from diffusers import AutoencoderKLWan, WanPipeline   # noqa: E402
    from diffusers.schedulers.scheduling_unipc_multistep import (
        UniMultistepScheduler as UniPCMultistepScheduler)   # noqa: E402
    from transformers import UMT5EncoderModel        # noqa: E402

    log(f"loading {MODEL} on {'cuda' if torch.cuda.is_available() else 'cpu'}")
    vae = AutoencoderKLWan.from_pretrained(MODEL, subfolder="vae", torch_dtype=torch.float16)
    pipe = WanPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=torch.float16)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=5.0)
    if torch.cuda.is_available():
        pipe.enable_model_cpu_offload()            # 16 GB T4 headroom, not a crash
    clip_s = time.monotonic() - t0
    log(f"model up in {clip_s/60:.1f} min")

    made, plan = [], []
    for genre, shots in lib.items():
        for i, shot in enumerate(shots[:SHOTS_PER_GENRE]):
            plan.append((genre, i, shot))
    log(f"{len(plan)} shots queued, {HOURS} h of clock to spend")

    for genre, i, shot in plan:
        left = HOURS * 3600 - (time.monotonic() - t0)
        if left < 420:                             # a clip costs ~4 min; leave a margin
            log(f"out of time after {len(made)} clip(s) — stopping clean, shelf is valid")
            break
        gdir = OUT / genre
        gdir.mkdir(parents=True, exist_ok=True)
        dst = gdir / f"broll-{i:02d}.mp4"
        if dst.exists() and dst.stat().st_size > 150_000:
            made.append({"genre": genre, "file": f"{genre}/{dst.name}", "prompt": shot,
                         "reused": True})
            continue
        raw = gdir / f"raw-{i:02d}.mp4"
        t1 = time.monotonic()
        try:
            vid = pipe(prompt=shot, negative_prompt=(
                "text, captions, watermark, logo, faces close up, deformed hands, "
                "cartoon, low contrast, flicker, jitter"),
                height=H, width=W, num_frames=FRAMES, guidance_scale=6.0,
                num_inference_steps=20).frames[0]
            from diffusers.utils import export_to_video   # noqa: E402
            export_to_video(vid, str(raw), fps=FPS)
            # Normalise ONCE, here, so the release runner spends no CPU on it:
            # 1080p / 24 fps / h264 yuv420p / closed GOP, silent.
            subprocess.run([
                "ffmpeg", "-y", "-i", str(raw),
                "-vf", f"scale={TARGET_W}:{TARGET_H}:flags=lanczos,"
                       f"crop={TARGET_W}:{TARGET_H},fps={TARGET_FPS},setsar=1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-g", "48", "-an",
                "-t", f"{CLIP_S}", str(dst)], check=True, capture_output=True)
            raw.unlink(missing_ok=True)
            made.append({"genre": genre, "file": f"{genre}/{dst.name}", "prompt": shot,
                         "dur": CLIP_S, "w": TARGET_W, "h": TARGET_H, "fps": TARGET_FPS,
                         "bytes": dst.stat().st_size})
            el = time.monotonic() - t1
            log(f"✅ {genre}/{dst.name} in {el/60:.1f} min "
                f"({len(made)} done, {left/3600:.1f} h left)")
        except Exception as e:                                        # noqa: BLE001
            log(f"⚠ {genre}/{i} failed ({type(e).__name__}: {e}) — skipped, not fatal")
            raw.unlink(missing_ok=True)

    MANIFEST.write_text(json.dumps({
        "clips": made,
        "model": MODEL,
        "hours_used": round((time.monotonic() - t0) / 3600, 2),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))
    # the whole /kaggle/working dir comes back with `kaggle kernels output`
    log(f"DONE: {len(made)} clip(s), {(time.monotonic()-t0)/60:.0f} min wall clock")


main()

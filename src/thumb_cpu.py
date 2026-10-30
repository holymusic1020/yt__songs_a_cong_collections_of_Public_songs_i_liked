"""CPU-only image generation inside the workflow — the boss's third backup.

Why this file exists, in his words (2026-10-30): *"it will be their 3rd backup if
both of those first two get failed then the third backup will start its work… I
don't care about how long 'cause it's just one image, one frame… we can run this
thing on our CPU, even if it's a really heavy model… we can at least spend 10
hours for 1 thumbnail on workflow."*

The arithmetic that shapes the design (all of it checked today, don't re-derive):

  · A **public** repo's standard GitHub-hosted Linux runner is free with **no
    minute cap**, and gets 4 vCPU / 16 GB (the 2-core / 7 GB figures are the
    private-repo SKU). So "spend hours on CPU" costs ₹0 here and only here.
  · A single job is killed at **6 h (360 min)**. That is the real ceiling, so
    "10 hours for one frame" means either one 300-minute job that banks many
    frames, or a chain. This file does the first: many frames, one job, and the
    farm's own budget guard stops it before the ceiling (never at it).
  · The model has to fit 14 GB of disk and download without a login. That rules
    out FLUX.1-schnell's fp32 diffusers repo (30 GB+) and every **gated**
    Stability repo (SD 3.5, SDXL-Turbo accept-a-licence) — a gated repo 401s in
    CI and a 401 in a cosmetic lane is exactly the noise we are not building.
    What fits: `stable-diffusion-v1-5/stable-diffusion-v1-5` — SD 1.5, ~4 GB
    fp32, **not gated**, CreativeML OpenRAIL-M (commercial use allowed, with the
    usual use-policy line), native 512². Same family the whole open ecosystem
    ships, and the cover-art lane's licence posture does not change: our own
    branding and relight go on top afterwards.
  · 4 vCPU float32, 768×448, 20 steps ≈ **3-8 minutes an image** (measured in CI
    by the run this file ships with, not guessed from a GPU blog), so one Sunday
    night is ~20-40 frames. The bank target is 900, so CPU is the slow lane that
    still fills the shelf with nothing else switched on — which is the point.

`generate(prompt, seed)` speaks the same contract as every other engine in
`src/thumb_bank.py` — `(bytes | None, label)`, never an exception — so it can be
appended to the ladder and removed from it with one Variable. Without torch the
module still imports and refuses in one line; that is what keeps `src/main.py`
safe on a runner that has no reason to install 200 MB of ML for a thumbnail.
"""
from __future__ import annotations

import io
import os
import time

MODEL_DEFAULT = "stable-diffusion-v1-5/stable-diffusion-v1-5"      # ungated mirror of the RunwayML repo
NEGATIVE = ("text, words, letters, typography, watermark, signature, logo, "
            "frame, border, people, faces, extra limbs, deformed, lowres, jpeg artifacts, "
            "oversaturated, cartoon, 3d render")
_W, _H = 768, 448                                                   # 16:9-ish, ~1.3× a 512² bucket
_pipe = None                                                        # built once per job
_why = ""


def _num(name: str, default: int) -> int:
    """Empty env/Variable → the default. A `workflow_dispatch` input left blank
    arrives as "" and `int("")` once killed the whole farm (2026-10-30)."""
    v = (os.environ.get(name) or "").strip()
    return int(v) if v.lstrip("-").isdigit() else default


def enabled() -> bool:
    return os.environ.get("THUMB_CPU", "0").strip() == "1"


def pipeline():
    """Load once, on the CPU, in float32, with the memory savers on.

    Returns (pipe, None) or (None, why) — the caller turns `why` into a log line.
    """
    global _pipe, _why
    if _pipe is not None:
        return _pipe, None
    if _why and os.environ.get("THUMB_CPU_RETRY") != "1":
        return None, _why
    try:
        import torch                                    # noqa: F401
        from diffusers import StableDiffusionPipeline
    except Exception as e:
        _why = f"torch/diffusers not installed ({str(e)[:70]})"
        return None, _why
    model = (os.environ.get("THUMB_CPU_MODEL") or MODEL_DEFAULT).strip() or MODEL_DEFAULT
    torch = __import__("torch")
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 2)))
    try:
        os.environ.setdefault("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        pipe = StableDiffusionPipeline.from_pretrained(
            model, torch_dtype=torch.float32, safety_checker=None, requires_safety_checker=False)
        pipe = pipe.to("cpu")
        for meth in ("enable_attention_slicing", "enable_vae_slicing", "enable_vae_tiling"):
            try:
                getattr(pipe, meth)()
            except Exception:
                pass                                    # version-dependent savers
        _pipe = pipe
        print(f"  🐢 cpu engine up · {model} · {torch.get_num_threads()} threads · "
              f"{_W}×{_H} · {_num('THUMB_CPU_STEPS', 20)} steps", flush=True)
        return pipe, None
    except Exception as e:
        _why = f"model load failed ({type(e).__name__}: {str(e)[:140]})"
        return None, _why


def generate(meta_prompt: str, seed: int):
    """(bytes | None, label). The contract `thumb_bank.generate()` expects.

    Deliberately no retries and no cleverness: one image, one attempt, and the
    farm paces itself. A CPU job's worst enemy is a crash that burns 40 minutes
    of CI, so everything unexpected becomes a refusal string.
    """
    if not enabled():
        return None, "cpu engine off (THUMB_CPU=1 to wake it)"
    try:
        pipe, why = pipeline()
        if pipe is None:
            return None, why
        import torch
        from src import thumb_bank as TB

        steps = max(4, _num("THUMB_CPU_STEPS", 20))
        guidance = float(_num("THUMB_CPU_GUIDANCE", 75)) / 10.0
        w = _num("THUMB_CPU_W", _W)
        h = _num("THUMB_CPU_H", _H)
        t0 = time.time()
        print(f"  🐢 generating · seed {seed} · {w}×{h} · {steps} steps", flush=True)
        img = pipe(
            prompt=("cinematic still photograph, " + meta_prompt +
                    ", 16:9 widescreen, strong single light source, deep but readable "
                    "shadows, high dynamic range, professional music-release cover art"),
            negative_prompt=NEGATIVE,
            height=h, width=w, num_inference_steps=steps, guidance_scale=guidance,
            generator=torch.Generator("cpu").manual_seed(int(seed) % (2 ** 31)),
        ).images[0]
        buf = io.BytesIO()
        img.save(buf, "PNG")                            # lossless into the shared fit step
        data = TB._fit_frame(buf.getvalue())            # crop 16:9 + upscale + unsharp + JPEG
        im, note = TB.usable(data)
        if im is None:
            print(f"  🐢 rejected by the gate → {note[:90]}", flush=True)
            return None, f"cpu: gate rejected it ({note[:90]})"
        print(f"  🐢 done in {time.time() - t0:.0f}s · {len(data):,}B · "
              f"luma {TB.stats(im)[0]:.0f}", flush=True)
        return data, f"cpu/{os.environ.get('THUMB_CPU_MODEL') or MODEL_DEFAULT.split('/')[-1]}"
    except Exception as e:
        msg = f"cpu engine failed ({type(e).__name__}: {str(e)[:160]})"
        _why = msg
        print(f"  ⚠ {msg}", flush=True)
        return None, msg


def selftest() -> int:
    """`python3 -m src.thumb_cpu` on any machine: proves the contract, not the model."""
    print(f"enabled={enabled()} torch={'yes' if _has_torch() else 'no'} model={MODEL_DEFAULT}")
    data, label = generate("a lonely road under a wide dusk sky, no text", 7)
    print("generate →", (f"{len(data):,} bytes" if data else "None"), "·", label[:120])
    return 0


def _has_torch() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


if __name__ == "__main__":
    os.environ.setdefault("THUMB_CPU", "1")
    raise SystemExit(selftest())

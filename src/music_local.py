"""🎹 MUSICGEN LOCAL — Meta's open music model on the runner's OWN CPU.

Why this lane exists: every cloud lane has a gate (suno wallet / Lyria
billing / ACE-Step HF quota). THIS ONE HAS NONE — it runs entirely on the
GitHub runner's CPU: no API key, no GPU, no quota, no monthly cost.
It makes instrumentals only (MusicGen doesn't sing), but it is the
RELIABLE lane: the channel can NEVER miss a release again.

Speed on the runner (4 vCPU): a ~2-min instrumental takes ~5-20 min —
fits easily in the 6h job window; songs are only needed every 2-3 days.

torch + transformers are installed LAZILY (CPU wheels only) so the main
requirements stay untouched and the lane is self-contained. Any failure →
return None → next lane / engine takes over. A lane can NEVER kill a run.

Env dials:
  MUSICGEN_OFF=1     skip entirely
  MUSICGEN_MODEL     facebook/musicgen-small (default) / -medium / -large
  MUSICGEN_STEPS     guidance steps (default 16)
"""
from __future__ import annotations

import os
import subprocess
import sys
import wave
from pathlib import Path

DEFAULT_MODEL = os.environ.get("MUSICGEN_MODEL", "facebook/musicgen-small")


def _ensure_deps(timeout: int = 900) -> bool:
    """Install torch (CPU wheel) + transformers once, lazily."""
    import shutil
    if not shutil.which("pip") and not sys.executable:
        return False
    print("  📦 musicgen-local: installing torch (CPU) + transformers…")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--index-url", "https://download.pytorch.org/whl/cpu",
             "--extra-index-url", "https://pypi.org/simple",
             "torch", "transformers<5"],
            timeout=timeout, check=True)
        return True
    except Exception as e:
        print(f"  ⚠ musicgen-local: dep install failed ({e}) — engine takes over")
        return False


def _prompt_for(genre_key: str) -> str:
    from src.music_space import PROMPTS, GENRE_BPM
    base = PROMPTS.get(genre_key, "moody, atmospheric").format(
        bpm=GENRE_BPM.get(genre_key, 100))
    return f"{base}, instrumental, high quality, clean mix"


def generate(genre_key: str, seconds: float, out_path: Path,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None) -> Path | None:
    """Cook one instrumental on the runner's CPU. None = next lane/engine."""
    if os.environ.get("MUSICGEN_OFF", "") == "1":
        print("  (musicgen-local skipped: MUSICGEN_OFF=1)")
        return None
    try:
        import numpy as np
    except Exception:
        return None
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
    except Exception:
        if not _ensure_deps():
            return None
        try:
            import torch
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
        except Exception as e:
            print(f"  ⚠ musicgen-local: deps unavailable ({e}) — engine takes over")
            return None

    model_name = os.environ.get("MUSICGEN_MODEL", DEFAULT_MODEL)
    try:
        steps = max(4, int(os.environ.get("MUSICGEN_STEPS", "16") or "16"))
    except ValueError:
        steps = 16
    prompt = _prompt_for(genre_key)

    try:
        print(f"  🎹 MusicGen-local (CPU) cooking {seconds:.0f}s "
              f"'{genre_key}' ({model_name.split('/')[-1]})…")
        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
        torch.set_grad_enabled(False)
        proc = AutoProcessor.from_pretrained(model_name)
        model = MusicgenForConditionalGeneration.from_pretrained(
            model_name, low_cpu_mem_usage=True)
        model.eval()
        inputs = proc(text=[prompt], padding=True, return_tensors="pt")
        max_tokens = int(max(30, min(float(seconds), 240)) * 50)  # 50 frames/s
        audio = model.generate(
            **inputs, do_sample=True, guidance_scale=3.0,
            max_new_tokens=max_tokens, num_beams=1)
        arr = audio[0, 0].numpy()
        sr = 32000
        peak = float(np.abs(arr).max()) or 1.0
        pcm = (arr / peak * 0.9 * 32767).astype(np.int16)

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        if out_path.stat().st_size < 80_000:
            raise RuntimeError(f"suspiciously small ({out_path.stat().st_size} B)")
        print(f"  🎁 musicgen-local cooked {seconds:.0f}s '{genre_key}' "
              f"(instrumental, {out_path.stat().st_size // 1024} KB)")
        return out_path
    except Exception as e:
        print(f"  ⚠ musicgen-local failed: {type(e).__name__}: "
              f"{str(e)[:130]} — next lane")
        return None

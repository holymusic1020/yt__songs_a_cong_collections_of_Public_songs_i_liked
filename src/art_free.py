"""Free, NO-KEY scene painter — middle fallback between Gemini and procedural.

Uses the public Pollinations image API (no signup, no token, $0). Prompts come
from the same scene templates as art_gemini: environments only, no people, no
faces — the classic AI tells stay banned. Any failure → caller drops to the
procedural cover, so this can never break a run.
"""
from __future__ import annotations

import io
import time
import urllib.parse
import urllib.request

from PIL import Image

SHOT_TYPES = [
    "wide establishing shot",
    "close-up detail, shallow depth of field",
    "low angle, dramatic perspective",
    "aerial high angle view",
]
STYLE_TAIL = (", 1990s retro anime film still, cinematic film grain, moody "
              "lighting, muted nostalgic palette, no people, no faces, no "
              "text, no watermark, no logo")


def _fetch_one(prompt: str, w: int, h: int, seed: int, timeout: int) -> Image.Image:
    url = ("https://image.pollinations.ai/prompt/"
           + urllib.parse.quote(prompt + STYLE_TAIL)
           + f"?width={w}&height={h}&nologo=true&seed={seed}&model=flux")
    last = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "yt-auto/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 20_000:
                raise RuntimeError(f"suspiciously tiny image ({len(data)} bytes)")
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:
            last = e
            time.sleep(4)
    raise RuntimeError(f"pollinations failed twice: {last}")


def generate_scenes(scene_text: str, n: int = 4, w: int = 1408, h: int = 768,
                    seed0: int = 0, timeout: int = 180) -> list[Image.Image]:
    """Paint n matching scenes (different shot types) for the slideshow."""
    imgs = []
    for i in range(n):
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        imgs.append(_fetch_one(f"{scene_text}, {shot}", w, h, seed0 + 101 * i, timeout))
        time.sleep(2)                      # politeness — it's a free service
    return imgs

"""Free, NO-KEY scene painter — middle fallback between Gemini and the offline
painter in art_scenic.py.

History of the "free engine": Pollinations' public image endpoint was truly
open, and this module leaned on it hard. As of the 2026-10-11 EP.064 run it
answers `402 Payment Required` for everything past roughly one image per IP
burst (measured from this repo: first request HTTP 200 + a real 768×432 JPEG,
the next four requests 402 — any size, any `model`, `nologo` set or not). That
is fine — it is still the cheapest real-art source we have — but it changed two
things here:

  * **partial results are kept**. The old code raised on the first failure, so
    one 402 threw away the one image it had already paid for, and the whole
    episode fell back to a single static cover — which is exactly the "stuck on
    thumbnail" look the boss complained about.
  * **the service is marked dead for the rest of the run** after the first 402,
    so a night does not spend 8 × 180 s waiting on a wall.

Callers: `main.build_visuals` (scene strip) and the cover fallback. Both treat
an empty result as "engine down" and move on to art_scenic.
"""
from __future__ import annotations

import io
import time
import urllib.error
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

#: set once Pollinations refuses the burst, so one run never waits on it twice
DEAD: str = ""


def _get(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "yt-auto/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _fetch_one(prompt: str, w: int, h: int, seed: int, timeout: int) -> Image.Image:
    """One image. `flux` first (best free model), plain default second — the
    anonymous tier sometimes serves turbo while rejecting flux."""
    global DEAD
    if DEAD:
        raise RuntimeError(f"free engine parked for this run ({DEAD})")
    q = urllib.parse.quote(prompt + STYLE_TAIL)
    last = None
    for attempt, tail in enumerate(("", "&model=turbo")):
        url = (f"https://image.pollinations.ai/prompt/{q}"
               f"?width={w}&height={h}&nologo=true&seed={seed}{tail}")
        try:
            data = _get(url, timeout)
            if len(data) < 20_000:
                raise RuntimeError(f"suspiciously tiny image ({len(data)} bytes)")
            return Image.open(io.BytesIO(data)).convert("RGB")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (402, 401, 429):        # paywalled / rate-limited: stop asking
                DEAD = f"HTTP {e.code} (anonymous quota)"
                raise RuntimeError(f"pollinations parked: {DEAD}") from e
        except Exception as e:                    # network / decode — retry once, then give up
            last = e
            if attempt == 0:
                time.sleep(3)
    raise RuntimeError(f"pollinations failed twice: {last}")


def generate_scenes(scene_text: str, n: int = 4, w: int = 1408, h: int = 768,
                    seed0: int = 0, timeout: int = 60) -> list[Image.Image]:
    """Up to n scenes, different shot types — whatever the free tier gives us
    before it says no. Raises only if it returned NOTHING, so callers can tell
    "some" from "none" and the caller always keeps a floor to fall through to."""
    imgs: list[Image.Image] = []
    err = ""
    for i in range(n):
        if DEAD:
            break
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        try:
            imgs.append(_fetch_one(f"{scene_text}, {shot}", w, h, seed0 + 101 * i, timeout))
        except Exception as e:
            err = str(e)
            break
        time.sleep(2)                             # politeness — it's a free service
    if not imgs:
        raise RuntimeError(err or "pollinations returned nothing")
    return imgs

"""Free, offline, NEVER-EMPTY scene painter (v24, boss 2026-10-11: "it's just
stuck on thumbnail and looks so weird").

What actually happened on EP.064 (measured in the run log, not guessed):

    ⚠ cover gen failed (gemini…429 RESOURCE_EXHAUSTED … 404 models/gemini-*-flash-image) — fallback scene cover
    🖼  painting 4 matching scenes with Gemini…   ⚠ gemini scenes failed (only 0 scenes generated)
    🖼  painting 4 scenes with the free engine…  ⚠ free-engine scenes failed (pollinations 402) — static cover it is

So the slideshow got **one** image: the branded cover. BEATCUT then dutifully
cycled a list of one → every "cut" showed the same picture → 12 minutes of
thumbnail. Both remote painters are paywalled now: Gemini's image models need
billing, and Pollinations answers `402 Payment Required` for everything past
its one free image per burst (verified: 200 on the first request, 402 on the
next four, any size, any model).

This module is the floor that cannot run out: real compositions drawn with
numpy — skyline layers, rain, bokeh, light shafts, an aerial grid — in the
song's own palette, one per shot type, deterministic per episode seed. No text
(karaoke owns the type layer), no people, no faces, no watermark. It is *not*
trying to beat Gemini; it is trying to never be a still frame again.

Wired in as the LAST fill in src/main.py, after both remote engines, so nothing
here can slow a night where Gemini works.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

# palettes live in art.py so the cover and the scenes stay one visual family
from src.art import PALETTES

SHOT_TYPES = [
    "wide establishing",       # skyline + sky
    "close-up, bokeh",         # shallow depth of field
    "low angle",               # converging towers, strong top glow
    "aerial",                  # city from above, light roads
    "corridor",                # vanishing point between two walls
    "water",                   # horizon + reflection
]


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed & 0x7FFFFFFF)


def _sky(w: int, h: int, pal: dict, sun_y: float, sun_x: float, glow_s: float) -> np.ndarray:
    top = np.array(pal["top"], np.float32)
    bot = np.array(pal["bottom"], np.float32)
    t = np.linspace(0, 1, h, np.float32)[:, None, None]
    img = top * (1 - t) + bot * t
    img = np.repeat(img, w, axis=1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w * sun_x) / (w * glow_s)) ** 2 + ((yy - h * sun_y) / (h * glow_s * 0.7)) ** 2)
    glow = np.clip(1 - r, 0, 1) ** 2.2
    return img + glow[..., None] * np.array(pal["glow"], np.float32) * 0.55


def _rain(a: np.ndarray, rng, n: int = 900) -> np.ndarray:
    h, w = a.shape[:2]
    for _ in range(n):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        ln = int(rng.integers(12, 46))
        sl = ln * rng.uniform(0.15, 0.45)
        pts = [(int(x + sl * i / max(ln, 1)), min(h - 1, y + i)) for i in range(0, ln, 2)]
        for px, py in pts:
            a[py, max(0, min(w - 1, px))] = np.clip(
                a[py, max(0, min(w - 1, px))] * 1.22 + 26, 0, 255)
    return a


def _skyline(a: np.ndarray, rng, w: int, h: int, base_y: int, max_h: int,
             col: np.ndarray, lit: float = 0.0) -> None:
    x = 0
    base_y = min(h - 1, int(base_y))
    while x < w - 4:
        bw = int(rng.integers(int(w * 0.02), int(w * 0.075)))
        bh = int(max_h * rng.uniform(0.32, 1.0))
        y0 = max(0, base_y - bh)
        xl, xr = int(x), min(w, x + bw)
        a[y0:base_y, xl:xr] = col
        if lit > 0 and bh > max_h * 0.45 and xr - xl >= 8:    # a few lit windows
            y_hi = max(y0 + 1, min(h - 1, base_y) - 4)
            for _ in range(int(bh * bw * 0.0006 * lit)):
                wx = int(rng.integers(xl + 2, xr - 4))
                wy = int(rng.integers(min(y0 + 2, y_hi), max(y0 + 3, y_hi - 2)))
                ww = int(rng.integers(2, 4)); hh = int(rng.integers(2, 4))
                a[wy:wy + hh, wx:min(w, wx + ww)] = np.clip(
                    col + np.array([185, 150, 80]) * lit, 0, 255)
        if rng.random() < 0.25:                              # antenna
            ax = min(w - 1, xl + (xr - xl) // 2)
            a[max(0, y0 - int(rng.integers(6, 26))):y0, ax] = col
        x += (xr - xl) + int(rng.integers(1, 5))


def _bokeh(a: np.ndarray, rng, w: int, h: int, glow: np.ndarray) -> None:
    for _ in range(26):
        cx, cy = int(rng.integers(0, w)), int(rng.integers(0, h))
        r = int(rng.integers(int(h * 0.02), int(h * 0.11)))
        yy, xx = np.mgrid[max(0, cy - r):min(h, cy + r), max(0, cx - r):min(w, cx + r)].astype(np.float32)
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
        ring = np.clip(1 - np.abs(d - 0.72) * 3.4, 0, 1)
        a[int(yy.min()):int(yy.max()) + 1, int(xx.min()):int(xx.max()) + 1] += \
            (ring * glow * 0.4)[..., None]


def _grid_floor(a: np.ndarray, w: int, h: int, glow: np.ndarray, horizon: int) -> None:
    for k in range(-14, 15, 1):
        x0 = w // 2 + k * (w // 14)
        pts = [(int(np.clip(w // 2 + (x0 - w // 2) * (i / 22.0), -w, 2 * w)) ,
                int(horizon + (h - horizon) * (i / 22.0) ** 1.8)) for i in range(23)]
        for px, py in pts:
            if 0 <= py < h and 0 <= px < w:
                a[py, px] = np.clip(a[py, px] + glow * 0.30, 0, 255)
    for i in range(1, 10):
        y = int(horizon + (h - horizon) * (i / 10.0) ** 1.9)
        if 0 <= y < h:
            a[y, :] = np.clip(a[y, :] + glow * 0.16, 0, 255)


def _shaft(a: np.ndarray, rng, w: int, h: int, glow: np.ndarray) -> None:
    for _ in range(3):
        x0 = int(rng.integers(0, w))
        tilt = int(rng.integers(-w // 6, w // 6))
        wid = int(rng.integers(w // 40, w // 14))
        for i in range(h):
            t = i / max(h - 1, 1)
            c = int(np.clip(x0 + tilt * t, 0, w - 1))
            a[i, max(0, c - wid):min(w, c + wid)] = np.clip(
                a[i, max(0, c - wid):min(w, c + wid)] + glow * 0.10 * (1 - t), 0, 255)


def _grain(a: np.ndarray, rng, sd: float = 6.0) -> np.ndarray:
    h, w = a.shape[:2]
    a = a + rng.normal(0, sd, (h, w, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vig = np.clip(1.12 - 0.42 * ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2) * 2.2, 0, 1)
    return a * vig[..., None]


def _panel(shot: int, w: int, h: int, pal: dict, rng) -> Image.Image:
    glowc = np.array(pal["glow"], np.float32)
    a = np.zeros((h, w, 3), np.float32)

    if shot == 0:                                     # wide establishing
        a = _sky(w, h, pal, 0.36, rng.uniform(0.28, 0.72), 0.55)
        horizon = int(h * rng.uniform(0.62, 0.72))
        _skyline(a, rng, w, h, int(horizon + h * 0.06), int(h * 0.30),
                 np.array(pal["top"], np.float32) * 0.55, lit=0.5)
        _skyline(a, rng, w, h, horizon, int(h * 0.42),
                 np.array(pal["top"], np.float32) * 0.28, lit=0.9)
        a = _rain(a, rng, 700)
    elif shot == 1:                                    # close-up bokeh
        a = _sky(w, h, pal, 0.5, 0.5, 0.95)
        _bokeh(a, rng, w, h, glowc)
        a = np.array(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(1.6)), np.float32)
    elif shot == 2:                                    # low angle
        a = _sky(w, h, pal, 0.14, rng.uniform(0.3, 0.7), 0.75)
        for side in (0, 1):
            for k in range(6):
                bw = int(w * rng.uniform(0.05, 0.11))
                x0 = int(rng.integers(0, w * 0.55)) if side == 0 else int(w * 0.45 + rng.integers(0, w * 0.55))
                top_y = int(h * rng.uniform(0.02, 0.30))
                a[top_y:h, x0:min(w, x0 + bw)] = np.array(pal["top"], np.float32) * (0.22 + 0.05 * k)
        _shaft(a, rng, w, h, glowc)
    elif shot == 3:                                    # aerial: a city at night from above
        a = _sky(w, h, pal, 0.95, 0.5, 1.3) * 0.5
        rows = 13
        for k in range(rows):                              # rooftops get bigger nearer the bottom
            t0, t1 = k / rows, (k + 1) / rows
            y0, y1 = int(h * t0 ** 1.35), int(h * t1 ** 1.35)
            if y1 - y0 < 3:
                y1 = y0 + 3
            bw = max(4, int(w * 0.012 * (1 + 2.2 * t0)))
            x = int(rng.integers(-bw, 0))
            while x < w - 2:
                bx = min(w, x + bw + int(rng.integers(0, max(2, bw // 3))))
                yy0, yy1 = y0 + 1, max(y0 + 2, y1 - 1)
                lit = rng.random()
                if lit > 0.62:                               # a lit roof / open floor
                    a[yy0:yy1, x:bx] = np.array(pal["top"], np.float32) * 0.42 + glowc * (
                        0.10 + 0.30 * rng.random())
                elif lit > 0.2:                              # dark block with a few windows
                    a[yy0:yy1, x:bx] = np.array(pal["top"], np.float32) * 0.30
                    for _ in range(int((bx - x) * 0.05)):
                        a[rng.integers(yy0, max(yy0 + 1, yy1 - 1)),
                          int(rng.integers(x + 1, max(x + 2, bx - 1)))] = glowc * 0.85 + 40
                else:
                    a[yy0:yy1, x:bx] = np.array(pal["top"], np.float32) * 0.22
                x = bx + max(1, int(w * 0.004 * (1 + 2 * t0)))   # the street
            a[max(0, y1 - 1):min(h, y1), :] = np.clip(a[max(0, y1 - 1):min(h, y1), :] + glowc * 0.16, 0, 255)
        _shaft(a, rng, w, h, glowc)
        a = np.array(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
                     .rotate(float(rng.uniform(-6, 6)), resample=Image.BICUBIC,
                             fillcolor=tuple(int(v) for v in pal["top"])), np.float32)
    elif shot == 4:                                    # corridor
        a = _sky(w, h, pal, 0.5, 0.5, 0.8)
        for t in range(0, 26):
            k = t / 25.0
            ww = int(w * (0.5 - 0.46 * k))
            hh = int(h * (0.5 - 0.46 * k))
            cx, cy = w // 2, h // 2
            for (x, y) in ((cx - ww, cy - hh), (cx + ww, cy + hh)):
                if 0 <= y < h and 0 <= x < w:
                    a[y, x] = glowc * 0.5
            a[np.clip(cy - hh, 0, h - 1), np.clip(cx - ww, 0, w - 1):np.clip(cx + ww, 0, w - 1)] = \
                np.array(pal["top"], np.float32) * 0.4
            a[np.clip(cy + hh, 0, h - 1), np.clip(cx - ww, 0, w - 1):np.clip(cx + ww, 0, w - 1)] = \
                np.array(pal["top"], np.float32) * 0.4
        _shaft(a, rng, w, h, glowc)
    else:                                              # water + reflection
        a = _sky(w, h, pal, 0.3, rng.uniform(0.3, 0.7), 0.6)
        horizon = int(h * rng.uniform(0.48, 0.58))
        need = h - horizon
        if need > 1:
            band = np.array(Image.fromarray(np.clip(a[:horizon], 0, 255).astype(np.uint8))[::-1]
                            .resize((w, need), Image.BILINEAR), np.float32)
            a[horizon:] = a[horizon:] * 0.45 + band * 0.55
            for y in range(horizon, h, 3):               # ripple smear
                a[y, :] *= float(rng.uniform(0.86, 1.12))
    a = _grain(a, rng)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGB")


def paint(meta: dict, n: int = 6, w: int = 1408, h: int = 768,
          seed0: int = 0) -> list[Image.Image]:
    """n distinct backdrop panels for one episode. Never raises on an unknown
    genre (same lesson as art.render's PALETTES.get guard — a missing key must
    never kill the nightly)."""
    pal = PALETTES.get(str(meta.get("genre_key") or ""), PALETTES["dark_ambient"])
    ep = int(meta.get("episode") or meta.get("ep") or 0)
    out = []
    for i in range(max(1, int(n))):
        for try_i, shot in enumerate((i % len(SHOT_TYPES), 0)):
            rng = _rng(hash((ep, i, seed0, try_i)) & 0x7FFFFFFF)   # fresh draw per attempt
            # first try the shot type, then the wide establishing one — a bad
            # draw must cost a panel, never the slideshow (a decoration that
            # eats a release is a bug, not a trade-off).
            try:
                out.append(_panel(shot, w, h, pal, rng))
                break
            except Exception as e:
                if shot == 0:
                    print(f"  🖼  scenic panel {i} skipped ({type(e).__name__}: {e})")
    return out

"""Cover-art system.

Two layers:
  1. Base scene — Gemini image gen (art_gemini.py) OR procedural fallback.
  2. Branding overlay — our typography, grain, vignette, frame. Always ours,
     so every thumbnail in the series stays visually locked to the channel.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1280, 720

PALETTES = {
    "drift_phonk":  {"top": (10, 8, 18),   "bottom": (58, 12, 40),  "glow": (255, 65, 108)},
    "deep_pop":     {"top": (6, 10, 24),   "bottom": (16, 42, 84),  "glow": (90, 160, 255)},
    "dark_ambient": {"top": (4, 8, 10),    "bottom": (10, 34, 30),  "glow": (70, 200, 160)},
    "lofi":         {"top": (20, 12, 8),   "bottom": (62, 40, 26),  "glow": (255, 170, 90)},
    "baroque_waltz": {"top": (18, 10, 6),  "bottom": (80, 52, 14),  "glow": (255, 190, 80)},
    "disco_house":  {"top": (12, 6, 20),   "bottom": (70, 18, 90),  "glow": (255, 90, 220)},
}

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size):
    for p in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _grain_vignette(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    arr += rng.normal(0, 7, (H, W, 1)).astype(np.float32)
    vig = np.clip(1.15 - 0.5 * ((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2.2, 0, 1)
    arr *= vig[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _scrim() -> Image.Image:
    """Soft dark bands so the text stays readable on any base image."""
    yy = np.linspace(0, 1, H, dtype=np.float32)
    center = np.exp(-((yy - 0.5) / 0.16) ** 2)
    bottom = np.clip((yy - 0.84) / 0.16, 0, 1)
    top = np.clip((0.12 - yy) / 0.12, 0, 1)
    alpha = np.clip(75 * center + 95 * bottom + 65 * top, 0, 160).astype(np.uint8)
    scrim = np.zeros((H, W, 4), dtype=np.uint8)
    scrim[:, :, 3] = np.repeat(alpha[:, None], W, axis=1)
    return Image.fromarray(scrim, "RGBA")


def _draw_branding(img: Image.Image, meta: dict, ep: int) -> None:
    d = ImageDraw.Draw(img)
    f_small, f_title, f_meta = _font(26), _font(72), _font(30)

    d.rectangle([28, 28, W - 28, H - 28], outline=(255, 255, 255), width=2)
    d.text((54, 50), meta["channel"].upper(), font=f_small, fill=(230, 230, 235))

    chip = "OFFICIAL AUDIO"
    f_chip = _font(22)
    cw = d.textlength(chip, font=f_chip)
    d.rounded_rectangle([W - 54 - cw - 30, 42, W - 54, 88], radius=21,
                        fill=(245, 245, 248))
    d.text((W - 54 - cw - 15, 48), chip, font=f_chip, fill=(16, 16, 20))

    lines = textwrap.wrap(meta["name"].upper(), width=18)
    y = H // 2 - (len(lines) * 84) // 2
    for line in lines:
        w_line = d.textlength(line, font=f_title)
        d.text(((W - w_line) / 2, y), line, font=f_title, fill=(245, 245, 248))
        y += 84

    footer = (f"EP.{ep:03d}  ·  {meta['genre'].upper()}  ·  {meta['bpm']} BPM  ·  "
              f"{meta['key'].upper()}")
    d.text((54, H - 76), footer, font=f_meta, fill=(200, 200, 210))


def _save(img: Image.Image, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


# ------------------------------------------------------------- base scenes

def _procedural_base(pal: dict, rng: np.random.Generator) -> Image.Image:
    top = np.array(pal["top"], dtype=np.float32)
    bot = np.array(pal["bottom"], dtype=np.float32)
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img = top[None, None, :] * (1 - t) + bot[None, None, :] * t
    img = np.repeat(img, W, axis=1)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * rng.uniform(0.35, 0.65), H * rng.uniform(0.3, 0.55)
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (W * 0.5)
    glow = np.clip(1 - r, 0, 1) ** 2.4
    img += glow[:, :, None] * np.array(pal["glow"], dtype=np.float32)[None, None, :] * 0.45
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


# ------------------------------------------------------------- public API

def overlay(meta: dict, ep: int, rng: np.random.Generator,
            base: Image.Image, out_path: Path) -> Path:
    """Take any base scene (e.g. from Gemini), brand it, save it."""
    img = ImageOps.fit(base.convert("RGB"), (W, H), Image.LANCZOS)
    img = _grain_vignette(img, rng)
    img = Image.alpha_composite(img.convert("RGBA"), _scrim()).convert("RGB")
    _draw_branding(img, meta, ep)
    return _save(img, out_path)


def render(meta: dict, ep: int, rng: np.random.Generator, out_path: Path) -> Path:
    """Fully procedural cover — the never-fails fallback."""
    img = _procedural_base(PALETTES[meta["genre_key"]], rng)
    img = _grain_vignette(img, rng)
    _draw_branding(img, meta, ep)
    return _save(img, out_path)


def chip_png(out_path: Path, text: str = "OFFICIAL AUDIO") -> Path:
    """Transparent 'OFFICIAL AUDIO' pill for video overlays."""
    font = _font(26)
    probe = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(probe)
    w = int(d.textlength(text, font=font))
    img = Image.new("RGBA", (w + 44, 62), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, w + 42, 60], radius=29, fill=(245, 245, 248, 235))
    d.text((22, 14), text, font=font, fill=(16, 16, 20, 255))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path

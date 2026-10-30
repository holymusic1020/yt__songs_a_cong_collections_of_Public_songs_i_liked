"""Feed-lit thumbnails, built from the release cover (boss 2026-10-26).

Why this exists: we never set a thumbnail, so YouTube grabbed a frame. For a
Short that frame is the portrait image pillarboxed into 16:9 — about 70 % black
bar — and our covers are deliberately moody (grain + vignette + scrim), so nine
days in a row looked like nine near-black rectangles. Measured on the live
channel: mean luminance of the published thumbnails was 10–26 out of 255.

The rule this module follows: re-light, never redesign. Same artwork, same
brand frame, same title — lifted to a mean that reads on a phone, sharpened so
it survives 320 px, and given an accent keyline pulled from that day's own
palette so the grid shows nine different colours instead of nine blacks. The
twin short gets a chip so two Shorts from one song never look duplicated.

Cosmetics by law: nothing in here may cost a release. `build()` returns None on
any problem and main() treats the whole thumbnail pass as best-effort.
Kill switch: repo Variable THUMB=0 (no thumbnail is built or uploaded).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

SIZE = (1280, 720)
TARGET_LUMA = 76.0          # mean luma that reads in a feed without looking washed
MAX_LUMA = 118.0            # never brighter than this — brand is moody, not white
MAX_BYTES = 2 * 1024 * 1024     # YouTube's hard limit for thumbnails
GAMMA_CAP = 3.0             # most aggressive lift allowed


def _luma(arr: np.ndarray) -> np.ndarray:
    return 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]


def relight(img: Image.Image) -> tuple[Image.Image, float, float]:
    """Soft-curve lift toward TARGET_LUMA with the highlights pinned in place.

    Returns (image, luma_before, luma_after)."""
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    before = float(_luma(a).mean() * 255.0)
    k = max(1.0, min(GAMMA_CAP, TARGET_LUMA / max(before, 6.0)))
    if before >= MAX_LUMA:                      # a bright day stays bright — no double-lift
        k = 1.0
    if k <= 1.02:
        return img.convert("RGB"), before, before
    y = a ** (1.0 / k)
    guard = np.clip((a - 0.80) / 0.20, 0.0, 1.0)     # keep window-lights lit, not blown
    y = y * (1.0 - guard) + a * guard
    out = Image.fromarray(np.clip(y * 255.0, 0, 255).astype(np.uint8), "RGB")
    after = float(_luma(np.asarray(out).astype(np.float32) / 255.0).mean() * 255.0)
    return out, before, after


def _accent(img: Image.Image) -> tuple[int, int, int]:
    """The day's own brightest saturated cluster → the keyline colour. This is
    where 'every thumbnail looks the same' actually dies: the frame hue changes
    per release because it is measured from that release's art."""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    lum = _luma(a.astype(np.float32))
    mx = a.max(axis=2).astype(np.int32)
    mn = a.min(axis=2).astype(np.int32)
    sat = mx - mn
    score = (sat * 2 + lum * 0.35) * (lum > 40)          # ignore the black corners
    idx = int(np.argmax(score))
    r, g, b = (int(v) for v in a.reshape(-1, 3)[idx])
    m = max(r, g, b) or 1
    boost = max(1.0, 235.0 / m)                          # push it to a readable accent
    return tuple(min(255, int(c * boost)) for c in (r, g, b))


def brand(img: Image.Image, meta: dict, ep: int, accent, *, slowed: bool) -> Image.Image:
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    for i, w in enumerate((6, 2)):                       # double keyline, brand-consistent
        d.rectangle([i * 5 + 8, i * 5 + 8, W - (i * 5 + 9), H - (i * 5 + 9)],
                    outline=accent + (235 - 90 * i,), width=w)   # 4-tuple: RGBA
    if slowed:
        from src import art
        txt = "SLOWED  +  REVERB"
        f = art._font(30)
        cw = d.textlength(txt, font=f)
        # lifted clear of the EP · GENRE · BPM · KEY strip art.py draws at H-76,
        # so the two never crowd each other at 320 px (they did at H-96).
        d.rounded_rectangle([W - 56 - cw - 34, H - 152, W - 40, H - 100], radius=26,
                            fill=(16, 16, 20, 215))
        d.text((W - 56 - cw - 17, H - 140), txt, font=f, fill=(245, 245, 248))
    return img


def build(cover_path, meta: dict, ep: int, out_path, *, slowed: bool = False) -> Path | None:
    """1280×720 JPEG thumbnail from that episode's cover. None = skip, never raise."""
    try:
        src = Path(cover_path)
        if not src.exists() or src.stat().st_size < 1_000:
            print(f"  🖼 thumbnail skipped — no cover to light ({src.name})")
            return None
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        if im.size != SIZE:                               # crop, never pad: no black bars
            w, h = im.size
            want = SIZE[0] / SIZE[1]
            if w / h > want:
                nw = int(h * want)
                im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
            else:
                nh = int(w / want)
                im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
            im = im.resize(SIZE, Image.LANCZOS)
        im, before, after = relight(im)
        im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=105, threshold=3))
        im = ImageEnhance.Contrast(im).enhance(1.06)
        im = ImageEnhance.Color(im).enhance(1.16)
        im = brand(im, meta, ep, _accent(im), slowed=slowed)
        q = 88
        im.save(out_path, "JPEG", quality=q, optimize=True)
        if out_path.stat().st_size > MAX_BYTES:
            im.save(out_path, "JPEG", quality=72, optimize=True)
        print(f"  🖼 thumbnail: mean luma {before:.0f} → {after:.0f} · "
              f"{out_path.name} {out_path.stat().st_size // 1024} KB")
        return out_path
    except Exception as e:                                 # cosmetics never break a release
        print(f"  (thumbnail build skipped: {str(e)[:120]})")
        return None


def dials() -> dict:
    """What the run will do — kept as a function so the UT can read the truth."""
    return {"THUMB": os.environ.get("THUMB", "1").strip() != "0"}


def pick(meta: dict, ep: int, rng, cover, out_dir):
    """(art_path, source, note) — ONE frame chosen per release, exactly as real
    labels do: the long and its Shorts share the day's cover art, the twin gets a
    chip on top of it. Cheaper and calmer than generating three images, and it is
    the DAYS that were all-black, not the videos within a day.

    He was explicit: *don't make the thumbnails by you*. So the pixels come from an
    AI model — the pre-generated bank shelf first (that is what makes a dead-API
    night still look fresh), live generation second (Gemini → Hugging Face →
    Pollinations). Re-lighting the episode's own cover is the LAST step, only so a
    release never ships the old black bar. Nothing here can raise.

    Branding stays ours: an AI frame gets art.overlay() (channel · title ·
    EP · genre · BPM · KEY) laid over it, then relight() pulls it back out of the
    scrim's darkness. Dials: THUMB=0 everything off · THUMB_AI=0 no live
    generation · THUMB_BANK=0 no shelf · THUMB_RELIGHT=0 no cover fallback ·
    THUMB_BRAND=0 no overlay.
    """
    out_dir = Path(out_dir)
    if os.environ.get("THUMB", "1").strip() == "0":
        return None, "off", "THUMB=0"
    base, src, note = None, "", ""
    if os.environ.get("THUMB_AI", "1").strip() != "0":
        try:
            from src import thumb_bank
            base, src, note = thumb_bank.acquire(meta, ep, out_dir / "thumbcache", rng)
            if base is not None and os.environ.get("THUMB_BRAND", "1").strip() != "0":
                try:
                    from PIL import Image
                    from src import art
                    branded = art.overlay(meta, ep, rng, Image.open(base),
                                          out_dir / f"ep{ep:03d}_thumbbase.png")
                    if branded and Path(branded).exists():
                        base = Path(branded)
                except Exception as e:
                    print(f"  (thumb branding skipped: {str(e)[:80]} — using the raw AI frame)")
        except Exception as e:
            base, src, note = None, "", f"bank/live failed: {str(e)[:90]}"
    if base is None:
        if os.environ.get("THUMB_RELIGHT", "1").strip() == "0":
            print(f"  🖼 no AI frame and THUMB_RELIGHT=0 → no custom thumbnail ({note})")
            return None, "off", note
        base, src = cover, (note or "") and f"cover-relight ({note})" or "cover-relight"
    return base, src, note

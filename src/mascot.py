"""NYX the signal-cat 😼📡 — the channel's mascot, drawn from a pixel grid.

One spec, two frames (eyes open / blink), byte-identical every run forever.
The blink rides a seamless 2-beat loop video so NYX blinks ON the kick of
whatever song plays beneath (Lofi-Girl lesson: a recurring character IS the
moat — ours costs $0 because it's code).

Also home of the broadcast HUD skin: scanline/bracket overlay PNG.
Pure PIL + ffmpeg. No assets, no keys, no network.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

FPS = 25
SCALE = 8                       # 22x15 grid → 176x120 px sprite
GRID_W = 22

# palette — night-signal cyan on moonlit-navy fur, riser-blue outline
# (near-black outlines vanish on dark scenes; NYX must read on ANY frame)
_PX = {
    ".": None,
    "K": (52, 68, 108, 255),    # outline
    "F": (38, 52, 84, 255),     # fur
    "V": (34, 211, 238, 235),   # visor glow
    "E": (224, 254, 255, 255),  # eye core
    "W": (240, 246, 255, 255),  # fang / pad spark
    "S": (0, 0, 0, 90),         # ground shadow
}

# The pixel-grid spec — THE cat, frozen in code. Identical in every video,
# every episode, forever. Pointy ear tips (r0-2), visor band (r5-7) with
# the cyan signal eyes, fang chisels, paws. Blink = middle row closes.
_OPEN = [
    "..K................K..",
    ".KFK..............KFK.",
    ".KFFK............KFFK.",
    ".KFFKKKKKKKKKKKKKKFFK.",
    ".KFFFFFFFFFFFFFFFFFFK.",
    ".KFFVVVVVVVVVVVVVVFFK.",
    ".KFFVVEEEVVVVEEEVVFFK.",
    ".KFFVVVVVVVVVVVVVVFFK.",
    "KFFWFFFFFFFFFFFFFFWFFK",
    ".KFFFFFFFFFFFFFFFFFFK.",
    "KFFFFFFFFFFFFFFFFFFFFK",
    "KFFFFKFFFFFFFFFFKFFFFK",
    "KFWWFKFFFFFFFFFFKFWWFK",
    ".KKKKKKKKKKKKKKKKKKKK.",
    "..SSSSSSSSSSSSSSSSSS..",
]
# blink = the middle visor row closes (eyes -> glow bar)
_BLINK_ROW = ".KFFVVVVVVVVVVVVVVFFK."

_CYAN = (34, 211, 238)


def _render(blink: bool) -> bytes:
    """Grid → PNG bytes. Deterministic: same input, same bytes, forever."""
    rows = list(_OPEN)
    if blink:
        rows[6] = _BLINK_ROW
    assert all(len(r) == GRID_W for r in rows), "pixel spec drifted"
    img = Image.new("RGBA", (GRID_W, len(rows)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = _PX[ch]
            if c:
                d.point((x, y), fill=c)
    img = img.resize((GRID_W * SCALE, len(rows) * SCALE), Image.NEAREST)
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def sprites(out_dir: Path) -> tuple[Path, Path]:
    """(open, blink) sprite PNGs on disk, cached. Byte-stable across runs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    open_p, blink_p = out_dir / "nyx_open.png", out_dir / "nyx_blink.png"
    if not open_p.exists():
        open_p.write_bytes(_render(blink=False))
    if not blink_p.exists():
        blink_p.write_bytes(_render(blink=True))
    return open_p, blink_p


def blink_webm(out_path: Path, beat_s: float, out_dir: Path | None = None):
    """Seamless 2-beat alpha loop: NYX blinks ON the downbeat (the kick).

    Stream-looped under the video, the blink re-lands on beat 1 of every
    2-beat cycle — the cat groves with the track, whatever the bpm.
    Returns the webm Path, or None (never crash a release over the cat).
    """
    if not shutil.which("ffmpeg"):
        print("  (NYX: no ffmpeg — cat stays home)")
        return None
    try:
        out_dir = out_dir or out_path.parent
        open_p, blink_p = sprites(out_dir)
        n = max(12, round(2 * beat_s * FPS))          # one 2-beat cycle
        n_blink = max(2, round(0.13 * FPS))           # 130 ms blink on beat 1
        frames_dir = out_dir / "nyx_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            Image.open(blink_p if i < n_blink else open_p).save(
                frames_dir / f"f{i:03d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
             "-i", str(frames_dir / "f%03d.png"),
             "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
             "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
             str(out_path)], check=True, capture_output=True)
        for f in frames_dir.glob("*.png"):
            f.unlink()
        frames_dir.rmdir()
        return out_path if out_path.exists() and out_path.stat().st_size > 400 else None
    except Exception as e:
        print(f"  (NYX: blink loop failed — {e})")
        return None


def hud_png(w: int, h: int, out_path: Path) -> Path:
    """Broadcast HUD overlay: scanlines + corner brackets + ON AIR tag.

    One static full-frame RGBA PNG — cheap to overlay, instantly makes the
    frame look like a TRANSMISSION instead of a slideshow. Deterministic.
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(0, h, 4):                                 # scanlines
        d.line([(0, y), (w, y)], fill=(0, 0, 0, 22))
    a = _CYAN + (215,)
    m, arm, t = max(18, w // 50), max(38, w // 24), 3        # corner brackets
    for cx, sx in ((m, 1), (w - m, -1)):
        for cy, sy in ((m, 1), (h - m, -1)):
            d.line([(cx, cy), (cx + sx * arm, cy)], fill=a, width=t)
            d.line([(cx, cy), (cx, cy + sy * arm)], fill=a, width=t)
    try:                                                     # ON AIR tag
        from src import art as art_mod
        f = art_mod._font(max(16, h // 44))
    except Exception:
        f = ImageDraw.Draw(img).font
    tag = "NIX SPEECH ◉ ON AIR"
    tw = d.textlength(tag, font=f)
    d.text(((w - tw) / 2, m + 10), tag, font=f, fill=_CYAN + (150,))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path

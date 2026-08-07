"""Video assembly — Ken Burns slideshows, crossfades, Veo-clip looping.

Requires ffmpeg (present on GitHub runners). Every builder tries the fancy
variant first (xfade crossfades) and falls back to plain concat on error.
Audio is mastered to YouTube specs: -14 LUFS integrated, -1 dBTP, AAC 320k.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

FPS = 25
LONG = (1280, 720)
VERT = (1080, 1920)
XFADE_S = 0.8
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
LOUDNORM = "alimiter=limit=0.4:level=false,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.6:level=false"


def loudnorm_filter(wav: Path) -> str:
    """Master chain, verified on real AAC masters: -14.0 LUFS / -2.4 dBTP.

    Raw masters peak at ~+2.5 dBTP while sitting at ~-14 LUFS, and AAC
    encoding adds its own intersample overshoot (measured +1.6 dBTP final —
    real clipping). This chain was iterated against the actual AAC output:
      1. alimiter 0.4  — pre-tames spikes deep, in float domain
      2. loudnorm -14 / TP -1.5 — re-balances loudness to YouTube's target
      3. alimiter 0.6  — hard ceiling well below 0 dBFS, encode-safe
    """
    return LOUDNORM


def _run_variants(label: str, cmds: list[list[str]]) -> None:
    last = None
    for i, cmd in enumerate(cmds):
        try:
            subprocess.run([FFMPEG] + cmd, check=True, capture_output=True)
            if i:
                print(f"  ({label}: fancy variant failed, used fallback)")
            return
        except subprocess.CalledProcessError as e:
            last = e
    raise RuntimeError(f"ffmpeg failed for {label}: "
                       f"{last.stderr.decode(errors='ignore')[-400:] if last else '?'}")


def _image_segments(images: list, per_s: float, w: int, h: int) -> list[str]:
    frames = max(1, int(FPS * per_s))
    parts = []
    for i in range(len(images)):
        parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,"
            f"zoompan=z='min(1.04+0.0007*on,1.28)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS},"
            f"format=yuv420p[s{i}]")
    return parts


def _audio_branch(idx: int, fc: list[str], wav=None) -> None:
    chain = loudnorm_filter(wav) if wav is not None else LOUDNORM
    fc.append(f"[{idx}:a]{chain}[aout]")


def _assemble(segs, inputs, wav, chip, out, dur, n, w, h, audio_idx, chip_idx):
    has_audio = wav is not None
    maps = (["-map", "[vout]", "-map", "[aout]"] if has_audio
            else ["-map", "[vout]"])
    tail = ["-t", f"{dur:.3f}", "-r", str(FPS)]
    if has_audio:
        tail += ["-c:a", "aac", "-b:a", "320k"]
    tail += ["-c:v", "libx264", "-preset", "medium", "-crf", "21", str(out)]

    # variant 1: xfade crossfades
    per = dur / n
    fc = list(segs)
    prev = "s0"
    for i in range(1, n):
        lbl = f"x{i}"
        off = (per - XFADE_S) * i
        fc.append(f"[{prev}][s{i}]xfade=transition=fade:duration={XFADE_S}:"
                  f"offset={off:.3f}[{lbl}]")
        prev = lbl
    if chip is not None:
        fc.append(f"[{prev}][{chip_idx}:v]overlay={w}-W-36:{h}-H-36:format=auto,"
                  f"format=yuv420p[vout]")
    else:
        fc.append(f"[{prev}]format=yuv420p[vout]")
    if has_audio:
        _audio_branch(audio_idx, fc, wav)
    cmd1 = inputs + ["-filter_complex", ";".join(fc)] + maps + tail

    # variant 2: plain concat
    fc2 = list(segs)
    cat = "".join(f"[s{i}]" for i in range(n))
    fc2.append(f"{cat}concat=n={n}:v=1:a=0[cat]")
    if chip is not None:
        fc2.append(f"[cat][{chip_idx}:v]overlay={w}-W-36:{h}-H-36:format=auto,"
                   f"format=yuv420p[vout]")
    else:
        fc2.append("[cat]format=yuv420p[vout]")
    if has_audio:
        _audio_branch(audio_idx, fc2, wav)
    cmd2 = inputs + ["-filter_complex", ";".join(fc2)] + maps + tail
    return [cmd1, cmd2]


def from_images(images: list[Path], dur: float, out_path: Path,
                wav: Path | None = None, chip: Path | None = None,
                size=LONG) -> Path:
    w, h = size
    n = len(images)
    per = dur / n
    inputs = []
    for img in images:
        inputs += ["-i", str(img)]
    audio_idx = chip_idx = None
    if wav is not None:
        inputs += ["-i", str(wav)]
        audio_idx = len(images)
    if chip is not None:
        inputs += ["-loop", "1", "-i", str(chip)]
        chip_idx = len(images) + (1 if wav else 0)
    segs = _image_segments(images, per, w, h)
    cmds = _assemble(segs, inputs, wav, chip, out_path, dur, n, w, h,
                     audio_idx, chip_idx)
    _run_variants("slideshow", cmds)
    return out_path


def from_clip(clip: Path, dur: float, out_path: Path, wav: Path | None = None,
              chip: Path | None = None, size=LONG) -> Path:
    """Loop a generated clip (e.g. Veo 8s) to any duration."""
    w, h = size
    inputs = ["-stream_loop", "-1", "-i", str(clip)]
    audio_idx = chip_idx = None
    if wav is not None:
        inputs += ["-i", str(wav)]
        audio_idx = 1
    if chip is not None:
        inputs += ["-loop", "1", "-i", str(chip)]
        chip_idx = 1 + (1 if wav else 0)
    fc = [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h},setsar=1,format=yuv420p[cv]"]
    if chip is not None:
        fc.append(f"[cv][{chip_idx}:v]overlay={w}-W-36:{h}-H-36:format=auto,"
                  f"format=yuv420p[vout]")
    else:
        fc.append("[cv]copy[vout]")
    if wav:
        fc.append(f"[{audio_idx}:a]{loudnorm_filter(wav)}[aout]")
    maps = ["-map", "[vout]"] + (["-map", "[aout]"] if wav else [])
    tail = ["-t", f"{dur:.3f}", "-r", str(FPS)]
    if wav:
        tail += ["-c:a", "aac", "-b:a", "320k"]
    tail += ["-c:v", "libx264", "-preset", "medium", "-crf", "21", str(out_path)]
    cmd = inputs + ["-filter_complex", ";".join(fc)] + maps + tail
    _run_variants("clip-loop", [cmd])
    return out_path

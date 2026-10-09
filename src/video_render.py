"""Video assembly — Ken Burns slideshows, crossfades, Veo-clip looping.

Requires ffmpeg (present on GitHub runners). Every builder tries the fancy
variant first (xfade crossfades) and falls back to plain concat on error.
Audio is mastered to YouTube specs: -14 LUFS integrated, -1 dBTP, AAC 320k.

v23 THE UNIVERSE UPDATE 🌌 — every long video now ships as a TRANSMISSION:
  · NYX the signal-cat (mascot webm loop, blinks on the beat)  [MASCOT_OFF=1 kills]
  · broadcast HUD skin (scanlines + corner brackets overlay)   [SPECTRUM_OFF=1 kills]
  · live showfreqs spectrum strip along the bottom             [SPECTRUM_OFF=1 kills]
All three are pure overlays — if any input is absent the video still renders.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

FPS = 25
LONG = (1280, 720)
VERT = (1080, 1920)
XFADE_S = 0.8
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
LOUDNORM = "alimiter=limit=0.4:level=false,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.6:level=false,treble=g=-3:f=6000"  # 2026-09-04 anti-hash law: -3dB@6k+ — boss-report EP.030 brick gave 2-sec headaches (LRA 1.3 + hash 13dB-down); level was lawful, SPECTRUM wasn't


def _env_off(name: str) -> bool:
    return os.environ.get(name, "") == "1"


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


# karaoke overlay (v18) — the words land ON the beat they are sung 🎤
LYRIC_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _lyric_font() -> str | None:
    return next((p for p in LYRIC_FONTS if Path(p).exists()), None)


def _dt_esc(t: str) -> str:
    return (t.replace("\\", "\\\\").replace(":", "\\:")
             .replace("'", "’").replace("%", "\\%"))


_HAS_DRAW = {}


def _drawtext_ok() -> bool:
    """Some ffmpegs (static builds) ship without drawtext/freetype — detect
    once, degrade to plain video, never crash a release over karaoke."""
    if "ok" not in _HAS_DRAW:
        try:
            out = subprocess.run([FFMPEG, "-hide_banner", "-filters"],
                                 capture_output=True, text=True, timeout=20)
            _HAS_DRAW["ok"] = "drawtext" in out.stdout
        except Exception:
            _HAS_DRAW["ok"] = False
        if not _HAS_DRAW["ok"]:
            print("  ⚠ ffmpeg lacks drawtext — karaoke overlay skipped "
                  "(CI's runner ffmpeg has it; static builds don't)")
    return _HAS_DRAW["ok"]


def lyric_chain(entries, w: int, h: int, dur: float) -> str:
    """drawtext chain of timed sung lines → '' when unavailable."""
    font = _lyric_font()
    if not font or not entries or not _drawtext_ok():
        return ""
    size = max(30, int(h * 0.045))
    y = int(h * 0.76)                      # lower-third, above the chip zone
    parts = []
    for i, (t0, txt) in enumerate(entries):
        t1 = entries[i + 1][0] if i + 1 < len(entries) else dur
        if t1 - t0 < 0.5:
            continue
        parts.append(
            f"drawtext=fontfile='{font}':text='{_dt_esc(txt)}':fontsize={size}:"
            f"fontcolor=white:borderw=3:bordercolor=black@0.9:"
            f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:y={y}:enable='between(t,{t0:.2f},{t1:.2f})'")
    return ",".join(parts)


def credit_chain(w: int, h: int, secs: float = 4.5) -> str:
    """'by Nix Speech' opening credit — the first screen finally names the
    chef. Burns in for the first ~4.5 s, top-center; drawtext-gated like
    karaoke so a drawtext-less ffmpeg simply skips it, never crashes."""
    font = _lyric_font()
    if not font or not _drawtext_ok():
        return ""
    size = max(22, int(h * 0.030))
    return (f"drawtext=fontfile='{font}':"
            f"text='{_dt_esc('by Nix Speech')}':fontsize={size}:"
            f"fontcolor=white@0.92:borderw=2:bordercolor=black@0.85:"
            f"x=(w-text_w)/2:y={int(h * 0.10)}:enable='between(t,0,{secs:.2f})'")


# ---------------------------------------------------------------- universe
# v23 broadcast dressing, applied over ANY base (xfade slideshow, concat
# fallback or looped clip): chip → spectrum strip → NYX → HUD → karaoke.
# Every piece optional, every piece env-killable, order is signal-safe.


def _decorate(fc: list[str], cur: str, w: int, h: int, dur: float, *,
              chip_idx=None, masc_idx=None, hud_idx=None, spec_label=None,
              lyrics=None) -> None:
    """Append the transmission stack to fc; consumes [cur], emits [vout]."""
    n = [0]

    def step(graph: str) -> None:
        nonlocal cur
        n[0] += 1
        nxt = f"d{n[0]}"
        fc.append(graph.replace("[SRC]", f"[{cur}]").replace("[OUT]", f"[{nxt}]"))
        cur = nxt

    if chip_idx is not None:
        step(f"[SRC][{chip_idx}:v]overlay={w}-W-36:{h}-H-36:format=auto[OUT]")

    if spec_label is not None and not _env_off("SPECTRUM_OFF"):
        sh = max(64, int(h * 0.11))
        fc.append(f"[{spec_label}]showfreqs=s={w}x{sh}:mode=bar:fscale=log:"
                  f"ascale=sqrt:win_func=hann:colors=0x39e6ff|0x7d5cff,"
                  f"format=rgba,colorchannelmixer=aa=0.72[spc]")
        step(f"[SRC][spc]overlay=0:{h - sh}:format=auto[OUT]")

    if masc_idx is not None and not _env_off("MASCOT_OFF"):
        sw = max(120, round(w * 0.14))
        sh_m = int(round(sw * 120 / 176 / 2) * 2)   # sprite is 176x120
        fc.append(f"[{masc_idx}:v]format=rgba,scale={sw}:{sh_m}[mc]")
        step(f"[SRC][mc]overlay=30:{h - 30 - sh_m}:format=auto[OUT]")

    if hud_idx is not None and not _env_off("SPECTRUM_OFF"):
        step(f"[SRC][{hud_idx}:v]overlay=0:0:format=auto[OUT]")

    lyr = lyric_chain(lyrics, w, h, dur)
    signoff = _signoff_chain(w, h, dur)
    parts = [c for c in (credit_chain(w, h), lyr, signoff) if c]
    full = ",".join(parts)
    fc.append(f"[{cur}]{full},format=yuv420p[vout]" if full
              else f"[{cur}]format=yuv420p[vout]")


def _signoff_chain(w: int, h: int, dur: float) -> str:
    """End-beat sign-off — last 3.5 s of every transmission: channel name +
    the promise. Free subscriber CTA, zero clicks. Kill-switch: SIGNOFF_OFF=1.
    """
    if _env_off("SIGNOFF_OFF") or dur < 12 or h > w:
        return ""                     # long-form landscape only — a sign-off
                                      # at a short's loop point kills the loop
    font = _lyric_font()
    if not font or not _drawtext_ok():
        return ""
    size = max(20, int(h * 0.032))
    t0 = max(0.0, dur - 3.5)
    txt = _dt_esc("— Nix Speech · new drops daily —")
    return (f"drawtext=fontfile='{font}':text='{txt}':fontsize={size}:"
            f"fontcolor=white@0.9:borderw=2:bordercolor=black@0.8:"
            f"x=(w-text_w)/2:y={int(h * 0.44)}:"
            f"enable='between(t,{t0:.2f},{dur:.2f})'")


# ─────────────────────────🥁 v23.7 BEATCUT — cuts on the grid, cut ON the chorus
# Boss, 2026-10-09: "the video editing is really so much s***". He was right in a
# measurable way: four scene images over a 172-second song = ONE 43-second slab
# with a single crossfade in it, and nothing in the frame cared where the chorus
# began. Opt-in until a live dry run has proved the graph (BEATCUT=1).
def bar_s(bpm: float, beats: int = 8) -> float:
    """Seconds in `beats` quarter notes (2 bars of 4/4 by default)."""
    try:
        b = float(bpm)
    except (TypeError, ValueError):
        return 0.0
    if b <= 0:
        return 0.0
    return max(0.5, 60.0 / b * max(1, int(beats)))


def beat_plan(dur: float, bpm: float, chorus_at: float | None = None,
              xfade: float | None = None) -> float:
    """Segment length: a whole number of bars, and — when we know where the
    chorus starts — a CUT that lands exactly on it.

    The trick is the period between cuts: `p = per - xfade` is what the xfade
    graph actually advances by, so we solve p = chorus_at / k for the integer k
    closest to the target bar length. No guesswork in the filter graph, just
    arithmetic, and it degrades to the bar grid when chorus_at is unknown.
    """
    xf = XFADE_S if xfade is None else float(xfade)
    target = bar_s(bpm) or 4.0
    target = min(12.0, max(2.5, target))              # never a slideshow, never a seizure
    if chorus_at and chorus_at > target and dur > chorus_at + target:
        k = max(1, int(round(chorus_at / target)))
        p = chorus_at / k
        if 1.6 <= p <= 14.0:
            return p + xf
    p = target
    if dur and dur < p * 2:                            # short film: one cut at most
        p = max(1.2, dur / 2 - xf)
    return p + xf


def beat_layout(images: list, dur: float, per: float) -> list:
    """Cycle the scene set so the whole song is cut on the grid (n = dur/period).

    Same four Gemini images — they are just no longer left to sit still for
    40 seconds at a time. Order is preserved and never repeats twice in a row.
    """
    if not images or per <= 0:
        return list(images)
    n = max(len(images), int(dur / max(0.5, per - XFADE_S)) + 1)
    out = []
    for i in range(n):
        if len(images) > 1 and i and out[i - 1] == images[i % len(images)]:
            out.append(images[(i + 1) % len(images)])   # no double frame
        else:
            out.append(images[i % len(images)])
    return out


def chorus_lift(dur: float, chorus_at: float | None) -> str:
    """The colour/energy lift over the chorus window (empty string = off).

    `eq` supports timeline editing, so `enable='between(t,…)’` is legal and the
    graph is IDENTICAL outside that window — worst case the effect does nothing,
    it can never break the render.
    """
    if not chorus_at or chorus_at <= 0 or chorus_at >= dur - 2:
        return ""
    a, b = float(chorus_at), max(float(chorus_at) + 1.2, dur - 3.5)
    return (f"eq=saturation=1.18:brightness=0.012:"
            f"enable='between(t,{a:.2f},{b:.2f})',")



def _image_segments(images: list, per_s: float, w: int, h: int) -> list[str]:
    frames = max(1, int(FPS * per_s))
    parts = []
    for i in range(len(images)):
        # v21 🎞 boss heard the bg "stop after sometime" (EP.028 first long):
        # the old zoom 1.04+0.0007*on SATURATED at 1.28 after ~12 s into a
        # 37.5 s scene → frozen backdrop for ~25 s of every scene. New curve
        # spans the WHOLE scene (1.06→~1.30 computed per scene length) and a
        # slow sinusoidal sway keeps the frame breathing — background never
        # holds still again. Kill-switch: KB_STILL=1 restores the frozen look.
        # 🥁 BEATCUT: a 5-second cut needs a much shallower move than a
        # 40-second one, or the frame lurches. Travel scales with the shot.
        depth = min(0.24, max(0.06, 0.022 * float(per_s)))
        if os.environ.get("KB_STILL", "") == "1":
            zoom = "min(1.04+0.0007*on,1.28)"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"
        else:
            slope = f"1.06+{depth:g}*on/{frames}"
            zoom = slope
            sway = f"sin(on/{max(FPS * 6, 90)})*9"           # ±9 px, ~6 s breath
            sway2 = f"cos(on/{max(FPS * 7, 120)})*7"         # out-of-phase drift
            x = f"iw/2-(iw/zoom/2)+{sway}"
            y = f"ih/2-(ih/zoom/2)+{sway2}"
        parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,"
            f"zoompan=z='{zoom}':x='{x}':"
            f"y='{y}':d={frames}:s={w}x{h}:fps={FPS},"
            f"format=yuv420p[s{i}]")
        if i and not (i % 2):                                  # alternate zoom-out
            parts[-1] = parts[-1].replace(
                f"z='{zoom}'", f"z='{1.06 + depth:.2f}-{depth:g}*on/{frames}'", 1)
    return parts


def _audio_branch(idx: int, fc: list[str], want_spec: bool) -> str | None:
    """[aout] master chain; returns the 'as' label for the spectrum tap."""
    if want_spec:
        fc.append(f"[{idx}:a]asplit=2[am][as]")
        fc.append(f"[am]{LOUDNORM}[aout]")
        return "as"
    fc.append(f"[{idx}:a]{LOUDNORM}[aout]")
    return None


def _assemble(segs, inputs, wav, chip, out, dur, n, w, h, audio_idx, chip_idx,
              lyrics=None, masc_idx=None, hud_idx=None, chorus_at=None):
    has_audio = wav is not None
    want_spec = has_audio and not _env_off("SPECTRUM_OFF")
    maps = (["-map", "[vout]", "-map", "[aout]"] if has_audio
            else ["-map", "[vout]"])
    tail = ["-t", f"{dur:.3f}", "-r", str(FPS)]
    if has_audio:
        tail += ["-c:a", "aac", "-b:a", "320k"] + ["-ar", "48000", "-ac", "2"]  # 2026-09-04 social law: 48k stereo
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
    spec = _audio_branch(audio_idx, fc, want_spec) if has_audio else None
    if os.environ.get("BEATCUT", "").strip() == "1":
        lift = chorus_lift(dur, chorus_at) if chorus_at is not None else ""
        if lift:
            fc.append(f"[{prev}]{lift}format=yuv420p[lp]")
            prev = "lp"
    _decorate(fc, prev, w, h, dur, chip_idx=chip_idx, masc_idx=masc_idx,
              hud_idx=hud_idx, spec_label=spec, lyrics=lyrics)
    cmd1 = ["-y"] + inputs + ["-filter_complex", ";".join(fc)] + maps + tail

    # variant 2: plain concat
    fc2 = list(segs)
    cat = "".join(f"[s{i}]" for i in range(n))
    fc2.append(f"{cat}concat=n={n}:v=1:a=0[cat]")
    spec2 = _audio_branch(audio_idx, fc2, want_spec) if has_audio else None
    _decorate(fc2, "cat", w, h, dur, chip_idx=chip_idx, masc_idx=masc_idx,
              hud_idx=hud_idx, spec_label=spec2, lyrics=lyrics)
    cmd2 = ["-y"] + inputs + ["-filter_complex", ";".join(fc2)] + maps + tail
    return [cmd1, cmd2]


def from_images(images: list[Path], dur: float, out_path: Path,
                wav: Path | None = None, chip: Path | None = None,
                size=LONG, lyrics=None, mascot: Path | None = None,
                hud: Path | None = None, bpm: float | None = None,
                chorus_at: float | None = None) -> Path:
    w, h = size
    # 🥁 BEATCUT=1 (default OFF — needs one live dry run to prove the graph):
    # cut on the bar grid, put a cut exactly on the chorus, and cycle the scene
    # set instead of leaving one image on screen for 40 seconds.
    beat = os.environ.get("BEATCUT", "").strip() == "1"
    per = dur / max(1, len(images))
    if beat and images:
        per = beat_plan(dur, bpm or 0.0, chorus_at)
        images = beat_layout(images, dur, per)
        if chorus_at:
            images = images  # (the lift itself is applied on the assembled label)
    n = len(images)
    inputs = []
    for img in images:
        inputs += ["-i", str(img)]
    idx = len(images)
    audio_idx = chip_idx = masc_idx = hud_idx = None
    if wav is not None:
        inputs += ["-i", str(wav)]
        audio_idx = idx
        idx += 1
    if chip is not None:
        inputs += ["-loop", "1", "-i", str(chip)]
        chip_idx = idx
        idx += 1
    if mascot is not None:
        inputs += ["-stream_loop", "-1", "-i", str(mascot)]
        masc_idx = idx
        idx += 1
    if hud is not None:
        inputs += ["-loop", "1", "-i", str(hud)]
        hud_idx = idx
        idx += 1
    segs = _image_segments(images, per, w, h)
    cmds = _assemble(segs, inputs, wav, chip, out_path, dur, n, w, h,
                     audio_idx, chip_idx, lyrics=lyrics,
                     masc_idx=masc_idx, hud_idx=hud_idx, chorus_at=chorus_at)
    _run_variants("slideshow", cmds)
    return out_path


def from_clip(clip: Path, dur: float, out_path: Path, wav: Path | None = None,
              chip: Path | None = None, size=LONG, lyrics=None,
              mascot: Path | None = None, hud: Path | None = None) -> Path:
    """Loop a generated clip (e.g. Veo 8s) to any duration."""
    w, h = size
    inputs = ["-stream_loop", "-1", "-i", str(clip)]
    idx = 1
    audio_idx = chip_idx = masc_idx = hud_idx = None
    if wav is not None:
        inputs += ["-i", str(wav)]
        audio_idx = idx
        idx += 1
    if chip is not None:
        inputs += ["-loop", "1", "-i", str(chip)]
        chip_idx = idx
        idx += 1
    if mascot is not None:
        inputs += ["-stream_loop", "-1", "-i", str(mascot)]
        masc_idx = idx
        idx += 1
    if hud is not None:
        inputs += ["-loop", "1", "-i", str(hud)]
        hud_idx = idx
        idx += 1
    want_spec = wav is not None and not _env_off("SPECTRUM_OFF")
    fc = [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h},setsar=1,format=yuv420p[cv]"]
    spec = _audio_branch(audio_idx, fc, want_spec) if wav else None
    _decorate(fc, "cv", w, h, dur, chip_idx=chip_idx, masc_idx=masc_idx,
              hud_idx=hud_idx, spec_label=spec, lyrics=lyrics)
    maps = ["-map", "[vout]"] + (["-map", "[aout]"] if wav else [])
    tail = ["-t", f"{dur:.3f}", "-r", str(FPS)]
    if wav:
        tail += ["-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2"] + ["-ar", "48000", "-ac", "2"]  # 2026-09-04 social law: 48k stereo
    tail += ["-c:v", "libx264", "-preset", "medium", "-crf", "21", str(out_path)]
    cmd = ["-y"] + inputs + ["-filter_complex", ";".join(fc)] + maps + tail
    _run_variants("clip-loop", [cmd])
    return out_path

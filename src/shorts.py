"""Shorts engine — vertical lyric shorts cut from the track's catchiest window.

Psychology implemented from research:
  - HOOK placement: picks the highest-energy bar-snapped 24-34s window
    (the section brains would replay anyway), not a random slice.
  - LOOP cut: start/end snap to bar boundaries → end flows into start.
  - SOUND-OFF SAFE: every card readable without audio.
  - ONE IDEA: lyric cards + artwork + OFFICIAL chip. Nothing else.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from src import art as art_mod
from src import lyrics

SW, SH = 1080, 1920


# ------------------------------------------------------------------ audio

def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def pick_hook_window(x: np.ndarray, sr: int, bpm: float) -> tuple[float, float]:
    """Highest-energy contiguous window, snapped to bar boundaries."""
    try:                                # queue songs may ship '~' — never die
        bpm = float(bpm)
    except (TypeError, ValueError):
        bpm = 110.0
    dur = len(x) / sr
    bar = 4 * 60.0 / bpm
    target = min(34.0, max(18.0, dur * 0.45))
    n_bars = max(4, int(target // bar))
    L = n_bars * bar
    if dur <= L + 2:
        return 0.0, min(dur, L)

    frame = int(sr * 0.25)
    n = len(x) // frame
    e = np.array([
        float(np.sqrt(np.mean(x[i * frame:(i + 1) * frame] ** 2) + 1e-12))
        for i in range(n)
    ])
    w = max(1, int(L / 0.25))
    cs = np.concatenate([[0.0], np.cumsum(e)])
    sums = cs[w:] - cs[:-w]
    t0 = float(np.argmax(sums)) * 0.25
    t0 = round(t0 / bar) * bar                       # bar snap (loop cut)
    t0 = float(max(0.0, min(t0, dur - L - 0.5)))
    return t0, L


def _slice_with_fades(x: np.ndarray, sr: int, t0: float, L: float) -> np.ndarray:
    seg = x[int(t0 * sr): int((t0 + L) * sr)].copy()
    f = int(0.18 * sr)
    if len(seg) > 2 * f:
        seg[:f] *= np.linspace(0, 1, f, dtype=np.float32)
        seg[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    peak = max(1e-6, float(np.max(np.abs(seg))))
    return seg / peak * 0.95


def _chunk_lines(lines: list[str], L: float) -> list[str]:
    """Shatter lyric lines into quick cards of ~2 s (Gemini cut-rhythm rule:
    a visual change every 1.5-2.5 s).  One long static card per line was the
    'lame' feeling — this keeps eyes chasing."""
    target = max(5, int(L // 2.1))
    words = [ln.split() for ln in lines]
    total = max(1, sum(len(w) for w in words))
    chunks: list[str] = []
    for ws in words:
        k = max(1, min(4, round(len(ws) / total * target)))
        per = -(-len(ws) // k)                       # ceil-split, near equal
        for i in range(0, len(ws), per):
            chunks.append(" ".join(ws[i:i + per]))
    return chunks


def _sfx_marks(seg: np.ndarray, sr: int, card_times: list) -> np.ndarray:
    """Percussive ticks at every card change + small riser into the final
    card's bait. The eye changes, the ear confirms it — tactile weight."""
    out = seg.copy()
    n_tick = int(0.055 * sr)
    t = np.arange(n_tick) / sr
    chirp = np.sin(2 * np.pi * (2600 - 26000 * t) * t).astype(np.float32)
    tick = chirp * np.exp(-t * 60) * 0.16
    click = (np.random.default_rng(7).standard_normal(n_tick)
             * np.exp(-t * 220) * 0.07).astype(np.float32)
    for i, (a, b) in enumerate(card_times):
        if a <= 0.05:
            continue
        s = int(a * sr)
        if s + n_tick < len(out):
            sig = tick if i < len(card_times) - 1 else click
            out[s:s + n_tick] += sig.astype(np.float32)
    # riser rising into the LAST card start
    a_last = card_times[-1][0]
    n_r = int(0.9 * sr)
    s = max(0, int(a_last * sr) - n_r)
    n_r = min(n_r, len(out) - s)
    if n_r > sr // 4:
        tr = np.arange(n_r) / n_r
        noise = np.random.default_rng(11).standard_normal(n_r)
        noise = np.convolve(noise, np.ones(25) / 25, mode="same")
        out[s:s + n_r] += (noise * tr ** 2 * 0.05).astype(np.float32)
    return out


# ------------------------------------------------------------------ visuals

def _base_image(cover: Path, meta: dict, ep: int, out: Path) -> Path:
    bg = ImageOps.fit(Image.open(cover).convert("RGB"), (SW, SH), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(22))
    arr = np.asarray(bg).astype(np.float32) * 0.42
    bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # artwork square, centered upper-third
    sq = ImageOps.fit(Image.open(cover).convert("RGB"), (840, 840), Image.LANCZOS)
    framed = ImageOps.expand(sq, border=6, fill=(245, 245, 248))
    bg.paste(framed, ((SW - framed.width) // 2, int(SH * 0.16)))

    d = ImageDraw.Draw(bg)
    f_small = art_mod._font(30)
    d.text((54, 52), meta["channel"].upper(), font=f_small, fill=(235, 235, 240))

    import os as _os
    # 😼 NYX rides the shorts too — static sprite on the left rail, clear of
    # the artwork, caption zone and button rail. Channel name is at y=52,
    # artwork starts at SH*0.16 — NYX perches in the gap. MASCOT_OFF=1 skips.
    if _os.environ.get("MASCOT_OFF", "") != "1":
        try:
            from src import mascot as _mx
            nyx_p, _ = _mx.sprites(out.parent)
            nyx = Image.open(nyx_p).convert("RGBA")
            bg.paste(nyx, (54, int(SH * 0.16) - nyx.height - 14), nyx)
        except Exception as e:
            print(f"  (NYX short stamp skipped: {e})")
    chip = "OFFICIAL AUDIO"
    f_chip = art_mod._font(26)
    cw = d.textlength(chip, font=f_chip)
    d.rounded_rectangle([SW - 54 - cw - 34, 40, SW - 54, 96], radius=26,
                        fill=(245, 245, 248))
    d.text((SW - 54 - cw - 17, 51), chip, font=f_chip, fill=(16, 16, 20))
    # (footer removed: the bottom ~200 px of a Short is YouTube's own UI —
    #  anything drawn there gets buried and looks amateur)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, quality=92)
    return out


def _lyric_card(line: str, out: Path, credit: bool = False,
                cta: bool = False) -> Path:
    card = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    f = art_mod._font(72)
    import textwrap
    lines = textwrap.wrap(line, width=13)          # respect the right rail
    y = int(SH * 0.64) - (len(lines) * 88) // 2    # clear of bottom UI zone
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((SW - w) / 2, y), ln, font=f, fill=(250, 250, 252, 255),
               stroke_width=3, stroke_fill=(0, 0, 0, 200))
        y += 88
    if credit:                                     # first screen names the chef
        fc = art_mod._font(30)
        tag = "by NIX SPEECH · official audio"
        tw = d.textlength(tag, font=fc)
        d.text(((SW - tw) / 2, y + 42), tag, font=fc,
               fill=(235, 235, 240, 235), stroke_width=2,
               stroke_fill=(0, 0, 0, 180))
    if cta:                                        # end card: sound-page CTA
        ft = art_mod._font(28)
        tag = "use this sound 🎧 · @nixspeech"
        tw = d.textlength(tag, font=ft)
        d.text(((SW - tw) / 2, y + 118), tag, font=ft,
               fill=(120, 230, 255, 235), stroke_width=2,
               stroke_fill=(0, 0, 0, 180))
    card.save(out)
    return out


# ------------------------------------------------------------------ ffmpeg

def render_video(pack: dict, out_path: Path) -> Path | None:
    ff = shutil.which("ffmpeg")
    if not ff:
        print("  ffmpeg not found — short assets ready (CI assembles the mp4)")
        return None
    L = pack["duration_s"]
    base_video = pack.get("base_video")
    if base_video:
        inputs = [ff, "-y", "-i", str(base_video), "-i", str(pack["wav"])]
        start = ["[0:v]format=rgba[bg]"]
    else:
        inputs = [ff, "-y", "-loop", "1", "-i", str(pack["base"]), "-i", str(pack["wav"])]
        start = ["[0:v]format=rgba,zoompan=z='min(1.0+0.00055*on,1.14)':d=1:"
                 f"s={SW}x{SH}:fps=25[bg]"]
    for c in pack["cards"]:
        inputs += ["-i", str(c)]

    fc = start
    prev = "bg"
    for i, (a, b) in enumerate(pack["card_times"]):
        lbl = f"v{i}"
        fc.append(f"[{prev}][{i + 2}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'"
                  f"[{lbl}]")
        prev = lbl
    fc.append(f"[{prev}]format=yuv420p[vout]")
    fc.append(f"[1:a]alimiter=limit=0.4:level=false,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.6:level=false[aout]")

    cmd = inputs + ["-filter_complex", ";".join(fc),
                    "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-c:a", "aac", "-b:a", "320k",
                    "-t", f"{L:.3f}", "-r", "25", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


# ------------------------------------------------------------------ build

def _cards_from_lrc(entries, t0, L):
    """🎤⏱ v15 (boss 2026-08-30: 'sub and vocal isnt matching at same time').

    The old card grid was an EVEN METRONOME — L/len(cards) slices flipping
    like a clock while the singer breathes freely. That's the dead
    sheet-timing class sneaking back in through the shorts back door.
    When the whisper transcript map exists, cards ARE the transcript's own
    captions inside the hook window — they flip when the VOICE flips.
    Returns (texts, card_times) or None (caller falls back to the grid)."""
    win = sorted(((ts, txt.strip()) for ts, txt in (entries or [])
                  if txt and txt.strip() and t0 - 0.25 <= ts <= t0 + L - 0.4),
                 key=lambda e: e[0])
    if len(win) < 3:
        return None
    a = [max(0.0, ts - t0) for ts, _ in win]
    texts = [t for _, t in win]
    cards = []
    i = 0
    while i < len(a):
        span = (a[i + 1] - a[i]) if i + 1 < len(a) else min(2.0, max(0.4, L - a[i]))
        txt = texts[i]
        j = i
        while span < 0.85 and j + 1 < len(a):   # unreadably fast flip → merge fwd
            j += 1
            txt = txt + " " + texts[j]
            span = (a[j + 1] - a[i]) if j + 1 < len(a) else min(2.0, max(0.4, L - a[i]))
        cards.append((a[i], min(a[i] + max(span, 0.4), L), txt))
        i = j + 1
    if len(cards) < 3:
        return None
    cap = max(6, int(L / 1.6))                  # keep the rhythm readable
    while len(cards) > cap:
        m = [(cards[k], cards[k + 1]) for k in range(0, len(cards) - 1, 2)]
        if len(cards) % 2:
            m.append(cards[-1])
        cards = [(x[0], y[1], x[2] + " " + y[2]) for x, y in m]
    return [c[2] for c in cards], [(c[0], c[1]) for c in cards]


def build(wav_path: Path, cover_path: Path, meta: dict, info: dict,
          ep: int, rng, rng_py, out_dir: Path,
          lines_override: list[str] | None = None,
          lrc_entries: list | None = None) -> dict:
    x, sr = read_wav(wav_path), 44100
    t0, L = pick_hook_window(x, sr, info["bpm"])
    seg = _slice_with_fades(x, sr, t0, L)
    if os.environ.get("CHIME_OFF", "") != "1":       # 🔔 loop point = station
        try:                                       #    chime — brand the loop
            from src.composer import sonic_logo
            lg = sonic_logo(sr)
            m = min(len(lg), len(seg))
            seg[:m] = np.clip(seg[:m] + lg * 0.55, -0.99, 0.99)
        except Exception as e:
            print(f"  (short chime skipped: {e})")

    card_times = None
    if lrc_entries:                              # 🎤⏱ v15: transcript clock
        _sy = _cards_from_lrc(lrc_entries, t0, L)
        if _sy:
            lines, card_times = _sy
            print(f"  🎤⏱ short cards ride the TRANSCRIPT clock "
                  f"({len(lines)} flips — screen moves when the voice moves)")
    if card_times is None:                       # legacy grid (no transcript)
        if lines_override:
            lines = lines_override[:max(4, int(L // 5.2))]
        else:
            lines = lyrics.build_lines(meta["genre_key"], meta["name"], rng_py,
                                       n=max(4, int(L // 5.2)))
        if rng_py.random() < 0.6:                # comment-bait closer card
            lines = list(lines) + [rng_py.choice(lyrics.BAITS)]
        lines = _chunk_lines(lines, L)           # ~2 s quick-cuts, not 5 s slabs
    n_real = len(lines)
    cards = [_lyric_card(ln, out_dir / f"ep{ep:03d}_card{i}.png",
                         credit=(i == 0), cta=(i == n_real - 1))
             for i, ln in enumerate(lines)]
    # 🔁 DESIGNED LOOP (v23): the first card repeats as the LAST frame — end
    # melts into start, retention can spike past 100% (the algo's favorite).
    # Pixel-exact echo of card 0; the 'use this sound' CTA rides the real
    # final card just before it. Kill-switch: LOOP_OFF=1.
    # (v15: only on the legacy grid — synced cards already end at L.)
    base = _base_image(cover_path, meta, ep, out_dir / f"ep{ep:03d}_short_base.jpg")

    if card_times is None:
        if os.environ.get("LOOP_OFF", "") != "1" and len(cards) >= 3:
            cards.append(cards[0])
        per = (L - 0.45) / len(cards)            # beat of air before the loop
        card_times = [(i * per, (i + 1) * per) for i in range(len(cards))]

    seg = _sfx_marks(seg, sr, card_times)         # ticks + riser = tactile cuts
    from src.composer import write_wav
    short_wav = write_wav(out_dir / f"ep{ep:03d}_short.wav", seg)

    # composite preview for QA (base + first card)
    prev = Image.alpha_composite(Image.open(base).convert("RGBA"),
                                 Image.open(cards[0])).convert("RGB")
    prev.save(out_dir / f"ep{ep:03d}_short_preview.jpg", quality=88)

    pack = {"wav": short_wav, "base": base, "cards": cards,
            "card_times": card_times, "duration_s": L, "hook_t0": t0,
            "hook_line": lines[0]}
    (out_dir / f"ep{ep:03d}_short_pack.json").write_text(
        json.dumps({k: (str(v) if isinstance(v, Path) else
                        [str(c) for c in v] if k == "cards" else v)
                    for k, v in pack.items()}, indent=2))
    return pack


# ------------------------------------------------------------------ twins

def slowed_twin_pack(pack: dict, out_dir: Path, ep: int,
                     speed: float = 0.84) -> dict:
    """💤 slowed + reverb TWIN of our own master (dial: SLOWED_EVERY in
    main). The whole 'slowed & reverb' lane uploads OTHER people's masters —
    copyright roulette. We slow OUR OWN composition: 100% safe, same
    dreamy payoff. Pure-numpy asetrate + aecho twin (no ffmpeg needed here),
    night-blue room tint, same lyric cards re-timed to the slower clock."""
    from src.composer import write_wav
    seg = read_wav(pack["wav"])
    sr = 44100
    n2 = max(1024, int(len(seg) / speed))          # asetrate: stretch + pitch
    x2 = np.interp(np.linspace(0, len(seg) - 1, n2),
                   np.arange(len(seg)), seg).astype(np.float32)
    for d, a in ((0.23, 0.32), (0.41, 0.18)):      # aecho voices
        k = int(d * sr)
        x2[k:] += x2[:-k] * a
    x2 = x2 / max(1e-6, float(np.max(np.abs(x2)))) * 0.95
    wav2 = write_wav(out_dir / f"ep{ep:03d}_slowed.wav", x2)

    base_src = Image.open(pack["base"]).convert("RGB")   # same room, night side
    tint = Image.new("RGB", base_src.size, (18, 28, 64))
    base2 = Image.blend(base_src, tint, 0.28)
    base2_p = out_dir / f"ep{ep:03d}_slowed_base.jpg"
    base2.save(base2_p, quality=92)

    sc = 1.0 / speed
    twin = dict(pack)
    twin.update({"wav": wav2, "base": base2_p, "base_video": None,
                 "card_times": [(a * sc, b * sc)
                                for a, b in pack["card_times"]],
                 "duration_s": pack["duration_s"] * sc})
    return twin

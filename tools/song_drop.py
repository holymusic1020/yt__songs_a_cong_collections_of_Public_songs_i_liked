#!/usr/bin/env python3
"""🐐 BOSS-SONG DROP — boss's OWN track end-to-end (2026-09-02, directive:
"ihv made a song, can u edit and post it too? match the vibe… make it as
coolest goated as u can"). One command takes the boss's mp3 → GOAT-grade
long video + 60s 9:16 short + FB reel + TG preview, via house render DNA
(v21 breathing scenes, spectrum, loudness grade) and house upload law
(ai-disclosure env, quota-safe retries, caption ≤245 on fb).

MODES
  proof   → render both vids, send previews to boss Telegram, exit. NO upload,
            NO fb. (boss ears rule the drop)
  publish → render + upload long+short to YT (public immediately — boss said
            "friday", no smart-scheduler fog) + FB reel + TG receipt.
  schedule-driven publishes arm only when today == BOSS_DROP_DATE and var
  BOSSDROP_ARMED=1 (self-cleaning: other Fridays no-op).

CONFIG (inputs for manual runs / repo Vars for the Friday cron):
  AUDIO_URL   = public http(s) url to the song file (release-asset bridge;
                boss's rstream.io = untobin end-to-end encrypted → re-bridge
                via GH release asset, handled outside this script)
  TITLE, ARTIST   = exact strings ("its on its name. by me Nix Speech")
  CUT_S           = short start-seconds ("auto"/empty/0 = first punchy minute)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import video_render as vr            # house render DNA
from src import multi_post                    # fb lane (caption-cap 245 inside)

OUT = Path("out/song_drop")
OUT.mkdir(parents=True, exist_ok=True)

AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")
LONG = (1280, 720)
SHORT = (720, 1280)
NEON = [(255, 47, 129), (110, 64, 255), (0, 229, 199), (255, 184, 66), (47, 129, 255)]


# ───────────────────────────── helpers ─────────────────────────────

def parse_cut(raw: str) -> int:
    raw = (raw or "").strip().lower()
    if raw in ("", "auto", "0"):
        return 0
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2})", raw)
    if not m:
        return 0
    if m.group(1):
        return int(m.group(1)) * 60 + int(m.group(2))
    return int(m.group(2))


def fb_caption(title: str, artist: str, yt_link: str | None) -> str:
    cap = f"{title} — {artist} 🐐"
    if yt_link:
        cap += f"\n📺 on youtube: {yt_link}"
    cap += "\n#newmusic #vibes #nyxspeech #bossdrop"
    return cap[:245]


def yt_meta(title: str, artist: str, desc_lines: list[str]) -> dict:
    desc = "\n".join([
        f"{title} — {artist}",
        *desc_lines,
        "",
        "👁‍🗨 nix speech · boss's own drop · #bossdrop",
        "",
        "#newmusic #originalmusic #vibes #nyxspeech",
    ])
    return {"title": f"{title} — {artist}",
            "description": desc,
            "tags": [t for t in {title.lower(), artist.lower(), "nyx speech", "new music",
                                 "original song", "vibes", "boss drop"} if t][:15]}


def scenes(title: str, artist: str, *, size, stem: str, count: int = 5) -> list[Path]:
    """GOAT-grade procedural art: neon-grade backgrounds, vignette, hero title
    on scene 0, subtle NYX stamp on the rest. v21 Ken-Burns breathes them live."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
    w, h = size
    imgs = []
    for i in range(count):
        im = Image.new("RGB", (w, h), (10, 10, 18))
        grad = Image.new("RGB", (w, h))
        g = grad.load()
        c1 = NEON[i % len(NEON)]
        c2 = NEON[(i + 2) % len(NEON)]
        for y in range(h):
            t = y / h
            row = tuple(int(c1[k] * (1 - t) + c2[k] * t) for k in range(3))
            for x in range(w):
                xr = abs(x - w / 2) / w
                g[x, y] = tuple(max(0, min(255, int(v * (0.25 + 0.75 * (1 - xr))))) for v in row)
        im = Image.blend(im, grad, 0.82)
        im = ImageEnhance.Contrast(im).enhance(1.12)
        # neon blob centerpiece
        blob = Image.new("RGB", (w, h), (0, 0, 0))
        bd = ImageDraw.Draw(blob)
        bw = int(min(w, h) * 0.55)
        bd.ellipse([(w - bw) // 2, (h - bw) // 2, (w + bw) // 2, (h + bw) // 2],
                   fill=c2 if size == LONG else c1)
        blob = blob.filter(ImageFilter.GaussianBlur(bw // 5))
        im = Image.blend(im, Image.composite(blob, im, blob.convert("L")), 0.35)
        d = ImageDraw.Draw(im)
        try:
            f_big = ImageFont.truetype("DejaVuSans-Bold.ttf", int(min(w, h) * 0.09))
            f_small = ImageFont.truetype("DejaVuSans.ttf", int(min(w, h) * 0.032))
        except Exception:
            f_big = ImageFont.load_default(); f_small = ImageFont.load_default()
        txt = title if i == 0 else f"NIX SPEECH ★ {artist}".upper()
        fnt = f_big if i == 0 else f_small
        bb = d.textbbox((0, 0), txt, font=fnt)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = 10
        pos = ((w - tw) // 2, int(h * 0.42) if i == 0 else (h - th - pad * 3))
        d.rectangle([pos[0] - pad, pos[1] - pad, pos[0] + tw + pad, pos[1] + th + pad],
                    fill=(0, 0, 0))
        d.text(pos, txt, font=fnt, fill=(245, 245, 250))
        p = OUT / f"{stem}_scene{i}.png"; im.save(p); imgs.append(p)
    return imgs


def fetch_audio(url: str) -> Path:
    for ext in AUDIO_EXTS:
        target = OUT / ("song" + ext)
        if target.exists():
            target.unlink()
    name = url.split("?")[0].rsplit("/", 1)[-1] or "song"
    if not name.lower().endswith(AUDIO_EXTS):
        name = "song.mp3"
    target = OUT / name
    print(f"  📥 audio bridge: {url[:90]}…")
    req = urllib.request.Request(url, headers={"User-Agent": "nix-song-drop/1.0"})
    data = urllib.request.urlopen(req, timeout=300).read()
    target.write_bytes(data)
    print(f"  ✅ {len(data) / 1e6:.1f} MB → {target}")
    return target


def sh(cmd: list[str]) -> None:
    print("  $ " + " ".join(cmd[:6]) + (" …" if len(cmd) > 6 else ""))
    subprocess.run(cmd, check=True)


def grade_wav(src: Path, *, cut_s: int = 0, cap_s: float | None = None) -> Path:
    out = OUT / ("song_short_grade.wav" if cap_s else "song_grade.wav")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if cut_s:
        cmd += ["-ss", str(cut_s)]
    if cap_s:
        cmd += ["-t", str(cap_s)]
    cmd += ["-af", "loudnorm=I=-14:TP=-1.0:LRA=11", "-ar", "48000", "-c:a", "pcm_s16le", str(out)]
    sh(cmd); return out


def dur_s(f: Path) -> float:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", str(f)])
    return float(out)


# ───────────────────────────── the drop ─────────────────────────────

def render_set(title: str, artist: str, wav: Path, cut_s: int):
    dur = dur_s(wav)
    print(f"  ⏱ song length {dur:.1f}s")
    long_imgs = scenes(title, artist, size=LONG, stem="long")
    short_imgs = scenes(title, artist, size=SHORT, stem="short")
    long_mp4 = OUT / "boss_long.mp4"
    print("  🎬 long render (1280×720)…")
    vr.from_images(long_imgs, dur, long_mp4, wav=wav, size=LONG)
    swav = grade_wav(wav, cut_s=cut_s, cap_s=min(60.0, dur))
    short_mp4 = OUT / "boss_short.mp4"
    print(f"  📱 short render (720×1280 · 60s cut @{cut}s)…")
    vr.from_images(short_imgs, min(60.0, dur), short_mp4, wav=swav, size=SHORT)
    return long_mp4, short_mp4, dur


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIOS", "proof")
    url = os.environ.get("BOSSDROP_URL", "").strip()
    title = os.environ.get("BOSSDROP_TITLE", "").strip()
    artist = os.environ.get("BOSSDROP_ARTIST", "Nix Speech").strip()
    cut_s = parse_cut(os.environ.get("BOSSDROP_CUT_S", ""))
    if not url or not title:
        print("  🛑 need BOSSDROP_URL + BOSSDROP_TITLE (input or repo Var)"); return 1

    state_p = Path("state/boss_drops.json")
    done = json.loads(state_p.read_text()) if state_p.exists() else {}
    if mode == "publish" and title in done:
        print(f"  ♻️ '{title}' already dropped {done[title]} — refusing a double publish")
        return 0

    song = fetch_audio(url)
    wav = grade_wav(song)
    long_mp4, short_mp4, dur = render_set(title, artist, wav, cut_s)
    cap_fb = fb_caption(title, artist, None)
    meta = yt_meta(title, artist, ["🐐 a Nix Speech original — boss's own track",
                                   "🔽 the 60s cut lives under Shorts",
                                   "🧬 rendered by the nyx house engine"])

    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if mode == "proof":
        from src import notify
        print("  👁 PROOF mode — previews to boss's telegram, nothing public anywhere")
        notify.send_telegram(tok, cid,
            f"👁 BOSS-DROP PROOF · '{title}' — {artist} ({dur:.0f}s)\n"
            f"long: {long_mp4.stat().st_size // 1_000_000} MB · short: 60s cut @{cut_s}s\n"
            f"friday slot armed only when var BOSSDROP_ARMED=1 + BOSS_DROP_DATE=2026-09-04\n"
            f"rule check → say 'go goat' to arm; say cut points/name fixes anytime", dry=False)
        notify.send_telegram_video(tok, cid, str(short_mp4), "📱 boss-drop short (proof)")
        notify.send_telegram_video(tok, cid, str(long_mp4), "🎬 boss-drop full (proof)")
        print("  ✅ proof previews sent")
        return 0

    # ── publish ──
    from src import uploader
    print("  🚀 publishing long…")
    vid_l = uploader.upload(long_mp4, meta)                      # public now
    print(f"  ✅ long: https://youtu.be/{vid_l}")
    meta_short = {"title": f"{title} — {artist} (official audio short)",
                  "description": (f"{title} — {artist}\n📺 full track: https://youtu.be/{vid_l}\n"
                                  f"#nyxspeech #newmusic #vibes #shorts"),
                  "tags": meta["tags"]}
    print("  🚀 publishing short…")
    vid_s = uploader.upload(short_mp4, meta_short)
    print(f"  ✅ short: https://youtu.be/{vid_s}")
    cap_fb = fb_caption(title, artist, f"https://youtu.be/{vid_l}")
    fb = multi_post.fb_reel(short_mp4, cap_fb)
    print(f"  🌐 fb: {fb}")
    done[title] = {"date": "2026-09-04", "yt_long": vid_l, "yt_short": vid_s,
                   "fb": fb}
    state_p.write_text(json.dumps(done, indent=2))
    from src import notify
    notify.send_telegram(tok, cid,
        f"🐐 BOSS-DROP LIVE · '{title}' — {artist}\n"
        f"🎬 long: https://youtu.be/{vid_l}\n"
        f"📱 short: https://youtu.be/{vid_s}\n"
        f"🟦 fb reel: {fb.get('fb', fb)}\n"
        f"engine resumes normal daily drops tomorrow 🫡", dry=False)
    print("  🏁 boss drop complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

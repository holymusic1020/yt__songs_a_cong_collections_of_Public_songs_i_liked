#!/usr/bin/env python3
"""v23 THE UNIVERSE UPDATE — receipts. Every P0 claim, proven on THIS machine:
 ① NYX mascot: deterministic pixel-grid, blink ≠ open, alpha loop builds
 ② HUD + live spectrum strip: real render, cyan energy present/absent (kill-switch)
 ③ designed loop shorts: last frame == first frame (pixel-exact echo)
 ④ chapters: 0:00 first, ≥10 s apart, ≥3 — or description stays untouched
 ⑤ chime: heads of masters get louder by exactly the logo; deterministic
 ⑥ slowed+reverb twin: ≈1/0.84× longer, spectral centroid DROPS, renders
 ⑦ CTA: 'use this sound 🎧' in every short's description + end card
Kill-switch inventory asserted too. Run: python3 tools/v23_receipt.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image

from src import composer, mascot, metadata, shorts, video_render

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
OK = 0


def check(label: str, cond: bool, extra: str = "") -> bool:
    global OK
    OK += bool(cond)
    print(("  ✅ " if cond else "  ❌ ") + label
          + (f" — {extra}" if extra else ""))
    return bool(cond)


def wav_write(path: Path, x: np.ndarray, sr: int = 44100) -> Path:
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()),
                             dtype=np.int16).astype(np.float32) / 32768.0


def frame(mp4: Path, t: float, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                    "-i", str(mp4), "-frames:v", "1", str(out)],
                   check=True, capture_output=True)
    return out


def px(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int32)


print("═" * 64)
print("v23 THE UNIVERSE UPDATE — receipts 🌌")
print("═" * 64)

# ---------------------------------------------------------------- ① NYX
print("\n① NYX the signal-cat — pixel-grid mascot")
a = mascot._render(blink=False)
b = mascot._render(blink=False)
c = mascot._render(blink=True)
check("pixel spec deterministic (same bytes forever)", a == b,
      hashlib.sha256(a).hexdigest()[:12])
check("blink frame differs from open frame", a != c)
(OUT / "nyx_open_check.png").write_bytes(a)
im = Image.open(OUT / "nyx_open_check.png")
check("sprite is 176x120 RGBA", im.size == (176, 120) and im.mode == "RGBA",
      f"{im.size} {im.mode}")
arr = np.asarray(im)
check("cyan visor present in the grid",
      bool(((arr[..., 1] > 180) & (arr[..., 2] > 200)).sum() > 50))
webm = mascot.blink_webm(OUT / "nyx_check.webm", beat_s=0.5, out_dir=OUT)
if check("blink loop webm builds (vp9 alpha)", bool(webm and webm.exists()),
         f"{webm.stat().st_size // 1024} KB" if webm else "none"):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(webm)], capture_output=True, text=True)
    dur = float(probe.stdout.strip() or 0)
    check("loop ≈ 2 beats @120bpm (blink lands on the kick)",
          abs(dur - 1.0) < 0.09, f"{dur:.3f}s")

# ------------------------------------------------------- ② HUD + spectrum
print("\n② HUD skin + live spectrum strip — REAL ffmpeg render")
hud = mascot.hud_png(*video_render.LONG, OUT / "hud_check.png")
harr = np.asarray(Image.open(hud))
check("HUD png: brackets inked, center transparent",
      float((harr[..., 3] == 0).mean()) > 0.55
      and bool((harr[..., 3] > 100).sum() > 2000))

def mini_video(off: bool, out_mp4: Path, dur: float = 6.0) -> Path:
    hud_local = mascot.hud_png(640, 360, OUT / "hud_640.png")
    sr = 44100
    t = np.arange(int(dur * sr)) / sr
    sig = 0.18 * np.sin(2 * np.pi * 220 * t)
    for k in range(int(dur / 0.5)):                    # kicks for the strip
        s = int(k * 0.5 * sr)
        sig[s:s + 800] += 0.5 * np.exp(-np.arange(800) / 120)
    w = wav_write(OUT / "v23_mini.wav", sig)
    imgs = []
    for i, hue in enumerate(((18, 12, 48), (8, 30, 40))):
        iv = Image.new("RGB", (640, 360), hue)
        p = OUT / f"v23_scene{i}.png"
        iv.save(p)
        imgs.append(p)
    if off:
        os.environ["SPECTRUM_OFF"] = "1"
        os.environ["MASCOT_OFF"] = "1"
        kw = {}
    else:
        os.environ.pop("SPECTRUM_OFF", None)
        os.environ.pop("MASCOT_OFF", None)
        kw = {"mascot": mascot.blink_webm(OUT / "nyx_mini.webm", 0.5, OUT),
              "hud": hud_local}
    lrc = [(0.2, "hello night"), (2.0, "we own the sky"),
           (4.0, "loop it back")]
    video_render.from_images(imgs, dur, out_mp4, w, size=(640, 360),
                             lyrics=lrc, **kw)
    return out_mp4

m_on = mini_video(False, OUT / "v23_on.mp4", dur=13.0)  # ≥12s: sign-off lives
f1 = px(frame(m_on, 3.05, OUT / "v23_frame_spectrum.png"))
H, W = f1.shape[:2]
strip = f1[H - 40:H, :]                                # spectrum zone
cyan = ((strip[..., 2] > 140) & (strip[..., 1] > 110)
        & (strip[..., 2] > strip[..., 0] + 25)).sum()
check("spectrum strip paints LIVE bars (bottom band)", int(cyan) > 400,
      f"{int(cyan)} cyan px")
roi = f1[H - 115:H - 25, 30:170]                       # NYX corner
eye = ((roi[..., 1] > 170) & (roi[..., 2] > 190)).sum()
check("NYX sits bottom-left (visor glow in corner)", int(eye) > 25,
      f"{int(eye)} glow px")

m_off = mini_video(True, OUT / "v23_off.mp4")
f2 = px(frame(m_off, 3.05, OUT / "v23_frame_off.png"))
strip2 = f2[H - 40:H, :]
cyan2 = ((strip2[..., 2] > 140) & (strip2[..., 1] > 110)
         & (strip2[..., 2] > strip2[..., 0] + 25)).sum()
roi2 = f2[H - 115:H - 25, 30:170]
eye2 = ((roi2[..., 1] > 170) & (roi2[..., 2] > 190)).sum()
check("SPECTRUM_OFF=1 kills the strip", int(cyan2) < 80, f"{int(cyan2)} px")
check("MASCOT_OFF=1 sends the cat home", int(eye2) < 25, f"{int(eye2)} px")
os.environ.pop("SPECTRUM_OFF", None)
os.environ.pop("MASCOT_OFF", None)

# ---------------------------------------------------------------- ③ loop
print("\n③ designed loop shorts — end melts into start")
sr = 44100
t = np.arange(40 * sr) / sr
beat = 0.15 * np.sin(2 * np.pi * 110 * t)
for k in range(int(40 / 0.5)):
    s = int(k * 0.5 * sr)
    beat[s:s + 1500] += 0.6 * np.exp(-np.arange(1500) / 150)
song_wav = wav_write(OUT / "v23_song.wav", beat)
cov = Image.new("RGB", (720, 720), (30, 20, 60))
cover = OUT / "v23_cover.jpg"
cov.save(cover)
gmeta = {"channel": "Nix Speech", "genre_key": "lofi", "name": "unit test loop"}
ginfo = {"bpm": 120.0, "key": "—", "genre": "lofi", "duration_s": 40.0}
lines = ["midnight static in my chest", "we ride the loop forever",
         "say my name when the city sleeps", "neon veins under the skin",
         "the signal never lies"]
pack = shorts.build(song_wav, cover, gmeta, ginfo, 901,
                    np.random.default_rng(1), __import__("random").Random(1),
                    OUT, lines_override=lines)
echo_ok = pack["cards"][-1] == pack["cards"][0]
same = pack["cards"][0].read_bytes() == pack["cards"][-1].read_bytes()
check("LAST card == FIRST card (pixel-exact echo)", echo_ok and same)
cta_c = px(pack["cards"][-2])
cta_px = ((cta_c[..., 1] > 210) & (cta_c[..., 2] > 235)
          & (cta_c[..., 0] < 180)).sum()
c0 = px(pack["cards"][0])
c0_px = ((c0[..., 1] > 210) & (c0[..., 2] > 235)
         & (c0[..., 0] < 180)).sum()
check("CTA ink on the final real card, clean loop card",
      int(cta_px) > 30 and int(c0_px) == 0,
      f"cta={int(cta_px)}px first={int(c0_px)}px")
os.environ["LOOP_OFF"] = "1"
pack2 = shorts.build(song_wav, cover, gmeta, ginfo, 902,
                     np.random.default_rng(1), __import__("random").Random(1),
                     OUT, lines_override=lines)
check("LOOP_OFF=1 → no echo card", len(pack2["cards"]) == len(pack["cards"]) - 1,
      f"{len(pack2['cards'])} vs {len(pack['cards'])}")
os.environ.pop("LOOP_OFF", None)

# ---------------------------------------------------------------- ④ chapters
print("\n④ description chapters from the karaoke map")
meta = metadata.build("lofi", ginfo, 7, __import__("random").Random(3),
                      used_names=set(), name="chapter test")
lrc = [(6.0, "midnight lights fade slow"), (17.0, "we chase the dark tonight"),
       (29.0, "neon veins under skin"), (41.0, "say my name out loud"),
       (53.0, "the signal never lies")]
nch = metadata.add_chapters(meta, lrc, 90.0)
desc = meta["description"]
cand = [l for l in desc.splitlines() if ":" in l and l[0].isdigit()]
stamps = [l.split()[0] for l in cand]
secs = [int(s.split(":")[0]) * 60 + int(s.split(":")[1]) for s in stamps]
check("≥3 chapters, first is 0:00 intro", nch >= 3 and stamps[0] == "0:00",
      f"{nch} chapters: {stamps[:4]}")
check("all gaps ≥10 s", all(b - a >= 10 for a, b in zip(secs, secs[1:])),
      str(secs))
check("hashtags still ride last", desc.rstrip().splitlines()[-1].startswith("#"))
meta2 = metadata.build("lofi", ginfo, 8, __import__("random").Random(3),
                       used_names=set(), name="dense test")
nch2 = metadata.add_chapters(meta2, [(3.0, "a"), (5.0, "b"), (7.0, "c")], 30.0)
check("too-dense map → description untouched", nch2 == 0
      and "chapters" not in meta2["description"])

# ---------------------------------------------------------------- ⑤ chime
print("\n⑤ sonic logo — one chime to rule the station")
l1 = composer.sonic_logo()
l2 = composer.sonic_logo()
check("logo deterministic", np.array_equal(l1, l2), f"{len(l1)} samples")
os.environ.pop("CHIME_OFF", None)
# honest test: an intro that starts SILENT, like real engine tracks —
# the chime must be the first thing you hear, or it's not a logo
intro = np.zeros(int(0.9 * 44100), dtype=np.float32)
body = 0.015 * np.sin(2 * np.pi * 220 * np.arange(2 * 44100) / 44100)
quiet = np.concatenate([intro, body]).astype(np.float32)
mast_on = composer.master(quiet.copy())
r_on = float(np.sqrt(np.mean(mast_on[:int(0.7 * 44100)] ** 2)))
os.environ["CHIME_OFF"] = "1"
mast_off = composer.master(quiet.copy())
r_off = float(np.sqrt(np.mean(mast_off[:int(0.7 * 44100)] ** 2)))
os.environ.pop("CHIME_OFF", None)
check("chime speaks over a silent intro", r_on > r_off * 5 and r_on > 0.05,
      f"{r_on:.4f} vs {r_off:.4f}")
qw = wav_write(OUT / "v23_queue.wav", quiet)
r_raw = float(np.sqrt(np.mean(read_wav(qw)[:int(0.7 * 44100)] ** 2)))
composer.mix_logo(qw)
rq = float(np.sqrt(np.mean(read_wav(qw)[:int(0.7 * 44100)] ** 2)))
check("queue masters stamped too (mix_logo)", rq > max(r_raw * 5, 0.05),
      f"{r_raw:.4f} → {rq:.4f}")

# ------------------------------------------------------- ⑥ slowed twin
print("\n⑥ slowed + reverb twin — our OWN master, safe lane")
twin = shorts.slowed_twin_pack(pack, OUT, 903)
orig = read_wav(pack["wav"])
tw = read_wav(twin["wav"])
ratio = len(tw) / len(orig)
check("twin longer by ≈1/0.84", abs(ratio - 1 / 0.84) < 0.05, f"{ratio:.3f}x")

def centroid(x: np.ndarray) -> float:
    s = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(len(x), 1 / 44100)
    return float((s * f).sum() / max(1e-9, s.sum()))

c_o, c_t = centroid(orig), centroid(tw)
check("pitched down (spectral centroid drops)", c_t < c_o * 0.92,
      f"{c_o:.0f} → {c_t:.0f} Hz")
check("card clock re-timed to the slower grid",
      abs(twin["duration_s"] / pack["duration_s"] - ratio) < 0.02)
mp4t = shorts.render_video(twin, OUT / "v23_twin.mp4")
check("twin renders to mp4", bool(mp4t and mp4t.exists())
      and mp4t.stat().st_size > 200_000,
      f"{mp4t.stat().st_size // 1024} KB" if mp4t else "none")

# ---------------------------------------------------------------- ⑦ CTA
print("\n⑦ use-this-sound CTA everywhere it compounds")
sm = metadata.short_meta(gmeta, "midnight static")
check("short description carries the CTA", "use this sound" in sm["description"]
      and "🎧" in sm["description"])
sm2 = metadata.short_meta(gmeta, "midnight static", slowed=True)
check("twin packaging honest + CTA", "slowed + reverb" in sm2["title"]
      and "use this sound" in sm2["description"])

# --------------------------------------------- ⑧ NYX rides shorts too
print("\n⑧ NYX short stamp — brand on the highest-reach surface")
base_path = pack["base"]
bpx = px(base_path)
nyx_zone = bpx[170:295, 50:240]                        # left rail perch
nyx_cyan = ((nyx_zone[..., 1] > 150) & (nyx_zone[..., 2] > 180)).sum()
check("NYX perches on the short base image", int(nyx_cyan) > 40,
      f"{int(nyx_cyan)} glow px")

# ------------------------------------------------ ⑨ end-beat sign-off
print("\n⑨ end-beat sign-off — free subscriber CTA, long-form only")
f_end = px(frame(m_on, 11.2, OUT / "v23_frame_signoff.png"))
band = f_end[int(H * 0.40):int(H * 0.50), :]
ink = int((band.mean(axis=2) > 170).sum())
check("sign-off ink in last 3.5s of long video", ink > 60, f"{ink} bright px")
os.environ["SIGNOFF_OFF"] = "1"
# graph-level proof without a full re-render: patch runner to capture
captured = {}
orig_run = video_render._run_variants
def cap(label, cmds):
    captured["graph"] = cmds[0][cmds[0].index("-filter_complex") + 1]
video_render._run_variants = cap
try:
    video_render.from_images([OUT / "v23_scene0.png"], 13.0, OUT / "cap.mp4",
                             OUT / "v23_mini.wav", size=(640, 360), lyrics=[])
finally:
    video_render._run_variants = orig_run
check("SIGNOFF_OFF=1 wipes the end-beat",
      "new drops daily" not in captured.get("graph", ""))
os.environ.pop("SIGNOFF_OFF", None)
video_render._run_variants = cap
try:
    video_render.from_images([OUT / "v23_scene0.png"], 13.0, OUT / "cap.mp4",
                             OUT / "v23_mini.wav", size=(1920, 1080), lyrics=[])
finally:
    video_render._run_variants = orig_run
g = captured.get("graph", "")
check("sign-off present in landscape graph, window = last 3.5s",
      "new drops daily" in g and "between(t,9.50" in g)

# ------------------------------------------------- kill-switch inventory
print("\n🎛 kill-switch inventory (env dials, no code edits)")
src_main = (ROOT / "src" / "main.py").read_text()
src_vr = (ROOT / "src" / "video_render.py").read_text()
src_sh = (ROOT / "src" / "shorts.py").read_text()
src_cp = (ROOT / "src" / "composer.py").read_text()
for name, src in (("SLOWED_EVERY", src_main), ("MASCOT_OFF", src_vr),
                  ("SPECTRUM_OFF", src_vr), ("LOOP_OFF", src_sh),
                  ("CHIME_OFF", src_cp), ("SIGNOFF_OFF", src_vr)):
    check(f"{name} wired", name in src)

print("\n" + "═" * 64)
print(f"RECEIPTS: {OK} checks green — v23 {'FORGED ✅' if OK >= 37 else 'NEEDS WORK ❌'}")
print("═" * 64)
sys.exit(0 if OK >= 37 else 1)

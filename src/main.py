"""yt-auto: daily machine.

CADENCE (your spec):
  · SHORT  → every run (cron fires daily)
  · VIDEO  → every 3rd EP (EP.001, EP.004, EP.007…) or --video to force

  · short  → scheduled now+1–3h (random, seconds)
  · video  → scheduled now+0–5h on video days (<15 min → immediate)

copy (Gemini text) → hooks/lines   [fallback: banks]
cover art → scenes/clip visuals    [fallback: procedural]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from src import art, composer, lyrics, metadata, state

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
GENRE_ROTATION = ["deep_pop", "drift_phonk", "skyline_anthem",
                  "baroque_waltz", "villain_pop", "disco_house",
                  "dark_ambient", "orbit_trap", "lofi"]

VIDEO_WINDOW_S = (3600, 5 * 3600)      # boss 2026-08-30: vid drops 1–5h out, random seconds
SHORT_WINDOW_S = (3600, int(3.5 * 3600))  # boss 2026-08-30: shorts drop 1–3.5h out, random seconds
IMMEDIATE_UNDER_S = 900
VIDEO_EVERY = 3          # long-form cadence: every Nth episode


def _twin_today(video_today: bool, ep: int, slowed_every: int,
                two_a_day: bool) -> bool:
    """Boss cadence (2026-08-30): video day = ONE short only (long vid takes
    the slot); off-day = 2 shorts (main + slowed+reverb twin). The twin IS
    the second short — same song, slowed/remixed (a legit separate format,
    never a same-audio double). Legacy SLOWED_EVERY still fires on off-days."""
    if video_today:
        return False
    return two_a_day or (slowed_every > 0 and ep % slowed_every == 0)


def _last_video_dt(st: dict) -> datetime | None:
    """When was the last REAL video (full/video, not a short) uploaded?
    Reads state.history; a short-only day (kind 'short') does NOT count.
    Returns a UTC datetime or None if no video has ever gone up."""
    best = None
    for h in st.get("history", []) or []:
        if h.get("kind") == "short":        # shorts don't advance the video clock
            continue
        # prefer the video's actual publish time; fall back to the run time
        raw = h.get("publish_at") or h.get("at")
        if not raw or raw == "immediate":
            raw = h.get("at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if best is None or dt > best:
            best = dt
    return best


def _keep_alive_hours() -> float:
    try:
        v = float((os.environ.get("KEEP_ALIVE_HOURS", "15") or "15").strip())
        return max(0.0, v)
    except ValueError:
        return 15.0


def _pick_lang(ep: int) -> str:
    """🌍 World Tour (v17): every Nth COOKED song is a foreign-language drop.

    Dials (repo Actions SECRETS/vars — no code edits needed):
      WORLD_TOUR_EVERY  default 5  ('0' → international OFF, all-English)
      WORLD_LANGS       default 'pt-BR,es,fr,tr' — rotation order
    Brazilian phonk first: PT-vocal phonk is the genre's hottest lane rn.
    """
    try:
        every = int((os.environ.get("WORLD_TOUR_EVERY", "5") or "0").strip())
    except ValueError:
        every = 5
    if every <= 0 or ep % every:
        return "en"
    langs = [l.strip() for l in os.environ.get(
        "WORLD_LANGS", "pt-BR,es,fr,tr").split(",")
        if l.strip() in lyrics.LANGS and l.strip() != "en"]
    if not langs:
        return "en"
    return langs[(ep // every - 1) % len(langs)]



def _retime_lrc_to_vocals(audio, entries: list, dur: float) -> list:
    """🎤⏱ Snap a naive karaoke map (kernel even-split) onto REAL sung phrases.

    STFT the 44.1k mono wav; a frame counts as SUNG when loud enough and its
    mid-band (300–3400 Hz, where voices live) dominates vs the instrumental
    bed (bed ratio measured on the quiet half). Loud masters are dense, so we
    walk a 3-rung ladder (strict → relaxed) and take the first that finds a
    usable phrase map; if NONE does, the original map goes back unchanged —
    a good karaoke is never made worse. Always prints a one-line diagnostic
    so runs can't silently no-op. Boss 2026-08-29: "subtitle and vocal isn't
    matching the time".
    """
    if len(entries) < 2:
        return entries
    try:
        import wave as _wv
        with _wv.open(str(audio), "rb") as wf:
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        if sr < 8000 or not raw:
            return entries
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        win, hop = int(sr * 0.05), int(sr * 0.025)           # 50 ms / 25 ms
        nfr = (len(pcm) - win) // hop
        if nfr < 12:
            return entries
        shp = (nfr, win)
        std = (pcm.strides[0] * hop, pcm.strides[0])
        seg = np.lib.stride_tricks.as_strided(
            pcm, shape=shp, strides=std, writeable=False)
        spec = np.abs(np.fft.rfft(seg * np.hanning(win)[None, :], axis=1))
        fr = np.fft.rfftfreq(win, 1.0 / sr)
        vox = spec[:, (fr >= 300) & (fr <= 3400)].sum(axis=1)
        tot = spec[:, (fr >= 60) & (fr <= 8000)].sum(axis=1) + 1e-9
        energy = (seg.astype(np.float64) ** 2).sum(axis=1)
        ratio = vox / tot
        quiet = energy <= np.percentile(energy, 45)
        if quiet.sum() < nfr * 0.1:
            quiet = energy <= np.percentile(energy, 60)
        bed_ref = float(np.median(ratio[quiet])) if quiet.any() else float(
            np.percentile(ratio, 50))
        times = np.arange(nfr) * (hop / sr)

        best = None
        for scale, vq, eq in ((1.6, 60, 55), (1.35, 55, 50), (1.15, 50, 45)):
            sung = ((ratio > bed_ref * scale)
                    & (vox > np.percentile(vox, vq))
                    & (energy > np.percentile(energy, eq)))
            onsets, last = [], -10.0
            prev = False
            for i in range(nfr):
                if sung[i] and not prev and times[i] - last >= 0.5:
                    onsets.append(float(times[i]))
                    last = times[i]
                prev = bool(sung[i])
            ends = [times[i] for i in range(nfr) if sung[i]]
            if not ends:
                continue
            v0, v1 = onsets[0], float(ends[-1])
            if len(onsets) >= max(3, len(entries) // 2) and                     v1 - v0 >= len(entries) * 1.2 and v1 > v0:
                best = (scale, v0, v1, onsets)
                break
        if best is None:
            print(f"  🎤⏱ sub-sync: no reliable phrase map (bed_ref {bed_ref:.2f}, "
                  f"ladder exhausted) — keeping kernel timing", flush=True)
            return entries
        scale, v0, v1, onsets = best
        weights = [max(1, len(txt.split())) for _, txt in entries]
        total_w = sum(weights)
        span = v1 - v0
        out, cursor = [], max(0.0, v0)
        for (_t, txt), w in zip(entries, weights):
            cand = [o for o in onsets if abs(o - cursor) <= 0.9]
            st_ = min(cand, key=lambda o: abs(o - cursor)) if cand else cursor
            out.append((round(st_, 2), txt))
            cursor = cursor + span * (w / total_w)
        fixed, last_t = [], -1.0
        for st_, txt in out:                    # strict monotonic guard
            if st_ <= last_t:
                st_ = round(last_t + 0.4, 2)
            fixed.append((st_, txt))
            last_t = st_
        print(f"  🎤⏱ sub-sync: {len(onsets)} phrase onsets · voice window "
              f"{v0:.1f}–{v1:.1f}s of {dur:.0f}s · bed_ref {bed_ref:.2f} · "
              f"ladder ×{scale} — subs snapped", flush=True)
        return fixed
    except Exception as e:
        print(f"  🎤⏱ sub-sync skipped ({type(e).__name__}: {e})", flush=True)
        return entries


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_visuals(meta, ep, rng, wav, dur, mode, want_long=True,
                  sung_lines=None, lrc_entries=None):
    scenes, clip, long_mp4 = [], None, None
    have_ff = shutil.which("ffmpeg")

    if mode in ("auto", "clip"):
        try:
            from src import video_gemini
            print("  🎬 asking Veo for a cinematic clip…")
            clip = video_gemini.generate_clip(meta, OUT / f"ep{ep:03d}_veo.mp4")
        except Exception as e:
            print(f"  ⚠ Veo unavailable ({e}) — trying image scenes")

    if clip is None and mode in ("auto", "clip", "scenes"):
        variant = None
        try:                       # v18: scene meaning pulled from the SONG
            from src import copy_ai as _cai
            variant = _cai.scene_prompt(meta, sung_lines)
            print(f"  🧠 meaningful scene from the song itself: '{variant[:70]}…'")
        except Exception:
            variant = None
        try:
            from src import art_gemini
            if variant is None:
                variant = rng.choice(art_gemini.SCENE_VARIANTS.get(meta["genre_key"]) or art_gemini.SCENE_VARIANTS["drift_phonk"])
            print("  🖼  painting 4 matching scenes with Gemini…")
            print(f"     style: {variant[:72]}…")
            scenes = art_gemini.generate_scenes(meta, n=4, scene_text=variant)
            meta["style_variant"] = variant
        except Exception as e:
            print(f"  ⚠ gemini scenes failed ({e})")
            # free, keyless middle fallback — real anime scenes for $0
            try:
                from src import art_free
                if variant is None:
                    variant = "empty neon city street in night rain"
                print("  🖼  painting 4 scenes with the free engine…")
                scenes = art_free.generate_scenes(variant, n=4, seed0=ep * 101)
                meta["style_variant"] = variant + " (free engine)"
            except Exception as e2:
                print(f"  ⚠ free-engine scenes failed ({e2}) — static cover it is")
        if scenes:
            for i, im in enumerate(scenes):
                im.save(OUT / f"ep{ep:03d}_scene{i}.png")

    if have_ff and want_long:
        from src import video_render
        chip = art.chip_png(OUT / "chip.png")
        # 🌌 v23 UNIVERSE: NYX blinks on the kick · HUD skin · live spectrum strip
        mascot = hud = None
        try:
            from src import mascot as _mx
            beat = 60.0 / float(meta.get("bpm") or 120)
            w_l, h_l = video_render.LONG
            if os.environ.get("MASCOT_OFF", "") != "1":
                mascot = _mx.blink_webm(OUT / f"ep{ep:03d}_nyx.webm", beat)
                if mascot:
                    print("  😼 NYX the signal-cat is on deck (blinks on the kick)")
            if os.environ.get("SPECTRUM_OFF", "") != "1":
                hud = _mx.hud_png(w_l, h_l, OUT / "hud_overlay.png")
                print("  📡 HUD skin on: scanlines + live spectrum strip")
        except Exception as e:
            print(f"  (universe dressing skipped: {e})")
        if lrc_entries:
            print(f"  🎤⏱ burning {len(lrc_entries)} synced lyric lines "
                  f"into the video (karaoke!)")
        if clip:
            print("  🎞  looping clip to song length…")
            long_mp4 = video_render.from_clip(clip, dur, OUT / f"ep{ep:03d}.mp4",
                                              wav=wav, chip=chip,
                                              lyrics=lrc_entries,
                                              mascot=mascot, hud=hud)
        elif scenes:
            print("  🎞  Ken Burns slideshow (xfades)…")
            long_mp4 = video_render.from_images(
                [OUT / f"ep{ep:03d}_scene{i}.png" for i in range(len(scenes))],
                dur, OUT / f"ep{ep:03d}.mp4", wav=wav, chip=chip,
                lyrics=lrc_entries, mascot=mascot, hud=hud)
    return long_mp4, clip, scenes


def _write_summary(path: Path, meta: dict, sched: dict, video_today: bool,
                   vid: str | None, sid: str | None) -> None:
    link = lambda i: f"https://youtu.be/{i}" if i else "_(dry run / n/a)_"
    path.write_text(
        f"## 🌙 Nix Speech — daily release\n\n"
        f"| | |\n|---|---|\n"
        f"| track | **{meta['name']}** ({meta['genre']}, {meta['bpm']} bpm, {meta['key']}) |\n"
        f"| video | {(link(vid) + ' · ' + str(sched['video_publish_at'] or 'immediate')) if video_today else '— (shorts-only day)'} |\n"
        f"| short | {link(sid)} · {sched['short_publish_at']} |\n"
    )


AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".oga"}


def _take_external_song(ep: int, cur_genre: str):
    """Boss's queue: incoming/ may hold a HUMAN drop (any audio file) and/or the
    bot's prefetched space song (named next_song--<genre>[--<lang>].<ext>).
    An optional `<stem>.lyrics.txt` sidecar rides with queue files — the words
    that were actually SUNG, so the short's cards quote the real song 🎤

    Priority: human drops first (the soul beats the machine), then the queue.
    Returns (wav_path, source_path, name|None, genre, lang, lyrics_path|None)
    or six Nones. Files are deleted from incoming/ only after a REAL publish.
    """
    inc = ROOT / "incoming"
    none7 = (None,) * 7
    if not inc.is_dir():
        return none7
    files = sorted(p for p in inc.iterdir()
                   if p.suffix.lower() in AUDIO_EXTS and p.is_file())
    if not files:
        return none7

    # Vocal guard: do not publish a "next_song" artifact as a vocal song unless
    # its lyrics sidecar exists. This prevents silent/failed/half-cooked queue
    # artifacts from becoming public uploads.
    require_vocals = os.environ.get("REQUIRE_VOCALS", "") == "1"
    clean_files = []
    for f in files:
        if f.stem.startswith("next_song") and require_vocals:
            if (f.parent / "error.txt").exists():
                print(f"  ⚠ skipping queued song {f.name}: kaggle error.txt present")
                continue
            if not f.with_name(f.stem + ".lyrics.txt").exists():
                print(f"  ⚠ skipping queued song {f.name}: missing .lyrics.txt sidecar")
                continue
        clean_files.append(f)
    files = clean_files
    if not files:
        return none7

    human = [p for p in files if not p.stem.startswith("next_song")]
    queue = [p for p in files if p.stem.startswith("next_song")]
    src = (human or queue)[0]

    # genre: human file → guess from filename tokens, else keep the wheel;
    # queue file → self-describing name next_song--<genre>[--<lang>].mp3
    genre = cur_genre
    if src in queue:
        for g in composer.GENRES:
            if f"--{g}" in src.stem:
                genre = g
                break
    else:
        for g in composer.GENRES:
            if g.replace("_", " ") in src.stem.lower() or g in src.stem.lower():
                genre = g
                break

    # language + sung-lyrics sidecar (both optional; queue files carry them)
    lang = "en"
    m = re.search(r"--(pt-BR|es|fr|tr|ja|ko|en)(?:\b|\.|$)", src.stem)
    if m:
        lang = m.group(1)
    lyc = src.with_name(src.stem + ".lyrics.txt")
    lyc = lyc if lyc.exists() else None
    lrc = src.with_name(src.stem + ".lrc.txt")          # 🎤⏱ karaoke map
    lrc = lrc if lrc.exists() else None

    # normalize to a 44.1 kHz mono wav for the whole pipeline
    out_wav = OUT / f"ep{ep:03d}.wav"
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg"):
        subprocess.run([shutil.which("ffmpeg"), "-y", "-v", "error",
                        "-i", str(src), "-ac", "1", "-ar", "44100",
                        "-c:a", "pcm_s16le", str(out_wav)],
                       check=True)
    elif src.suffix.lower() == ".wav":
        shutil.copy(src, out_wav)
    else:
        print(f"  ⚠ no ffmpeg to read {src.name} — engine composes instead")
        return none7

    if src in human:  # "midnight drive.mp3" → song named "midnight drive"
        name = re.sub(r"\s+", " ", re.sub(r"[^\w\s\-']", " ", src.stem)).strip()
        return out_wav, src, (name[:60] or None), genre, lang, lyc, lrc
    return out_wav, src, None, genre, lang, lyc, lrc


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--genre", default="auto",
                   choices=["auto"] + list(composer.GENRES))
    p.add_argument("--length", type=float, default=0)
    p.add_argument("--art-mode", default="auto",
                   choices=["auto", "gemini", "procedural"])
    p.add_argument("--visual-mode", default="auto",
                   choices=["auto", "clip", "scenes", "cover"])
    p.add_argument("--no-shorts", action="store_true")
    p.add_argument("--video", action="store_true",
                   help="force a long-form video today")
    p.add_argument("--shorts-only", action="store_true",
                   help="short only — skip video regardless of cadence")
    p.add_argument("--seed", type=int, default=-1)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()
    try:                       # 🕶 boss switches live in-repo (no workflow edits)
        import json as _js
        _sw = _js.loads(Path("state/boss_switches.json").read_text(encoding="utf-8"))
    except Exception:
        _sw = {}
    if _sw.get("shorts") is False:
        args.no_shorts = True
        print("  🕶 boss switch: shorts OFF — long videos only until unlocked", flush=True)
    args.two_shorts_a_day = _sw.get("two_shorts_a_day") is True
    if args.two_shorts_a_day:
        print("  🕶 boss cadence: 2 shorts on off-days (main + slowed twin), "
              "1 short on video days", flush=True)
    if _sw.get("publish") is False and os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        if args.publish:
            print("  🕶 boss gate: PUBLISH_HOLD — cron runs as PREVIEW (TG only, "
                  "zero uploads) until boss flips state/boss_switches.json", flush=True)
        args.publish = False
        args.dry_run = True

    st = state.load()
    ep = st["episode"] + 1
    seed = args.seed if args.seed >= 0 else ep * 7919 + int(
        datetime.now(timezone.utc).strftime("%j"))
    rng = np.random.default_rng(seed)
    rng_py = random.Random(seed)

    genre_key = (args.genre if args.genre != "auto"
                 else GENRE_ROTATION[ep % len(GENRE_ROTATION)])
    if args.genre == "auto":
        weights = st.get("genre_weights")
        if weights:
            keys = list(weights)
            genre_key = str(rng.choice(keys, p=[weights[k] for k in keys]))
            print(f"  🧠 adaptive weights → {genre_key} {weights}")

    # ---------- cadence ----------
    video_today = (args.video or ep % VIDEO_EVERY == 1) and not args.shorts_only
    if args.no_shorts and not video_today:
        video_today = True                 # video-only run (rare/manual)
    nxt = ep + ((1 - ep % VIDEO_EVERY) % VIDEO_EVERY)
    # ---------- KEEP-ALIVE gate (shadowban guard) ----------
    # Only ever upload a long-form video if the last one is older than
    # KEEP_ALIVE_HOURS (default 15h). Within the window → stay short-only so
    # we never spam the channel; the extra video render is simply NOT made.
    # A short still goes out (keeps the channel alive) — that's the point.
    if video_today and not args.no_shorts:
        last = _last_video_dt(st)
        if last is not None:
            age_h = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
            if age_h < _keep_alive_hours():
                print(f"  🛡 KEEP-ALIVE: last video was {age_h:.1f}h ago "
                      f"(< {_keep_alive_hours():.0f}h) — staying short-only, "
                      f"skipping today's video upload to avoid a spam signal.")
                video_today = False
                nxt = ep + ((1 - ep % VIDEO_EVERY) % VIDEO_EVERY)
    print(f"EP.{ep:03d} · genre={genre_key} · "
          f"{'FULL (video+short)' if video_today else f'short-only · next video EP.{nxt:03d}'}")

    target = args.length or float(rng.integers(95, 201))
    print(f"  target={target:.0f}s · seed={seed}")

    # ---------- song source (boss's queue): human drop > prefetched space song > engine ----------
    GENRE_LABEL = {"drift_phonk": "drift phonk", "deep_pop": "deep pop",
                   "dark_ambient": "dark ambient", "lofi": "lofi",
                   "baroque_waltz": "baroque waltz", "disco_house": "disco house",
                   "skyline_anthem": "skyline anthem",
                   "villain_pop": "villain pop", "orbit_trap": "orbit trap"}
    ext_wav = ext_src = ext_name = ext_genre = None
    ext_lang, ext_lyc, ext_lrc = "en", None, None
    everyday = os.environ.get("VOCAL_EVERYDAY", "1") != "0"   # 🎤 vocal shorts too
    if video_today or everyday:      # was video-days-only → shorts never saw the queue
        (ext_wav, ext_src, ext_name, ext_genre, ext_lang,
         ext_lyc, ext_lrc) = _take_external_song(ep, genre_key) or (None,) * 7
        ext_lang = ext_lang or "en"
    if ext_genre:
        print(f"  📦 queue says genre={ext_genre}"
              + (f" · 🌍 {lyrics.LANGS.get(ext_lang, {}).get('label', ext_lang)}"
                 if ext_lang != "en" else ""))
        genre_key = ext_genre
    if ext_wav:
        print(f"  🎁 using queued song: {ext_src.name}")
        import wave as _wave
        with _wave.open(str(ext_wav), "rb") as _w:
            dur = _w.getnframes() / _w.getframerate()
        from src import music_space as _ms
        # queue file was cooked AT this exact bpm; human drops guess the wheel
        bpm_est = _ms.GENRE_BPM.get(genre_key, 110)
        info = {"bpm": bpm_est, "key": "—", "genre": GENRE_LABEL[genre_key],
                "duration_s": dur}
    else:
        # Optional real-song mode: if there is no queued vocal song, cook a
        # vocal song NOW instead of falling straight to the offline instrumental
        # engine. Set repo variable COOK_TODAY_IF_QUEUE_EMPTY=1.
        if (video_today or everyday) and \
            os.environ.get("COOK_TODAY_IF_QUEUE_EMPTY", "1") == "1":  # default ON (was opt-in, video-only)
            print("  🎤 no queued vocal song — cooking a real vocal song TODAY…")
            try:
                today_lang = ext_lang or "en"
                try:
                    from src import copy_ai as _ca
                    today_lyc = _ca.song_lyrics(
                        {"name": "(untitled)", "genre": GENRE_LABEL[genre_key]},
                        today_lang, max(150, target))
                except Exception as e:
                    print(f"  (today songwriting: {e} — bank lyrics)")
                    today_lyc = lyrics.song_lyrics(genre_key, "(untitled)", rng_py, today_lang)
                from src import music_chain
                tmp_mp3 = OUT / f"ep{ep:03d}_vocal_source.mp3"
                tmp_lrc = OUT / f"ep{ep:03d}_vocal_source.lrc.txt"
                # 🎤 require_vocals ensues the grid drops the instrumental-only
                # MusicGen lane, so this can ONLY be satisfied by a real singing
                # lane (Suno/Kaggle/Lyria/ACE). Fix for REQUIRE_VOCALS being skipped.
                cooked, cooked_by = music_chain.cook(
                    genre_key, max(150, target), tmp_mp3,
                    lyrics=today_lyc, lang=today_lang, lrc_out=tmp_lrc,
                    require_vocals=os.environ.get("REQUIRE_VOCALS", "") == "1")
                if cooked and shutil.which("ffmpeg"):
                    ext_wav = OUT / f"ep{ep:03d}.wav"
                    subprocess.run([shutil.which("ffmpeg"), "-y", "-v", "error",
                                    "-i", str(cooked), "-ac", "1", "-ar", "44100",
                                    "-c:a", "pcm_s16le", str(ext_wav)], check=True)
                    ext_src = Path(cooked)
                    ext_lang = today_lang
                    # only ever label it "vocal" (write the lyrics sidecar) when
                    # the lane actually sang — never for a MusicGen instrumental
                    if cooked_by != "musicgen-local":
                        ext_lyc = OUT / f"ep{ep:03d}_vocal_source.lyrics.txt"
                        ext_lyc.write_text(today_lyc, encoding="utf-8")
                    ext_lrc = tmp_lrc if tmp_lrc.exists() else None
                    import wave as _wave
                    with _wave.open(str(ext_wav), "rb") as _w:
                        dur2 = _w.getnframes() / _w.getframerate()
                    from src import music_space as _ms
                    info = {"bpm": _ms.GENRE_BPM.get(genre_key, 110), "key": "—",
                            "genre": GENRE_LABEL[genre_key], "duration_s": dur2}
                    print(f"  ✅ today's vocal cooked by: {cooked_by}")
                elif os.environ.get("REQUIRE_VOCALS", "") == "1" and args.publish:
                    raise SystemExit("No vocal music lane succeeded; refusing to publish instrumental fallback")
            except SystemExit:
                raise
            except Exception as e:
                print(f"  ⚠ today vocal cook failed: {e}")
                if os.environ.get("REQUIRE_VOCALS", "") == "1" and args.publish:
                    raise SystemExit("No vocal music lane succeeded; refusing to publish instrumental fallback")

        if not ext_wav:
            # vocal refusal only on singing days (video days, or everyday mode).
            # boss 2026-08-26: shorts days dont generate music; instrumental short ok.
            want_song = video_today or everyday
            if want_song and os.environ.get("REQUIRE_VOCALS", "") == "1" and args.publish:
                raise SystemExit("No queued/cooked vocal song found; refusing to publish instrumental fallback")
            print("  composing…")
            song, info = composer.compose(genre_key, rng, target)
            song = composer.arrange_arc(song, info.get("bpm", 120))
    used_names = {h.get("name") for h in st.get("history", []) if h.get("name")}
    dur = info["duration_s"]

    # words actually SUNG on today's queue song (if any) — feed cards + tags
    lyr_today = (ext_lyc.read_text(encoding="utf-8").strip()
                 if ext_lyc and ext_lyc.exists() else None)
    if lyr_today:
        print(f"  🎤 vocals on deck: {len(lyr_today.splitlines())} sung lines "
              f"({ext_lang})")

    # karaoke map for the long video (v18 lyric-video upgrade)
    lrc_entries: list = []
    if ext_lrc and ext_lrc.exists():
        try:
            from src import music_space as _ms
            lrc_entries = _ms.parse_lrc(ext_lrc.read_text(encoding="utf-8"))
            if lrc_entries:
                print(f"  🎤⏱ karaoke map: {len(lrc_entries)} timed lines")
        except Exception:
            lrc_entries = []
    # 🔙 v8 (boss ears 2026-08-29): spectral sub-snapping made drift WORSE
    # (bed synths fooled the voice detector). Reverted — kernel timing stands
    # until a PROVEN aligner exists.

    from src import naming
    probe = {"genre": info["genre"], "genre_key": genre_key,
             "key": info["key"], "bpm": info["bpm"], "name": "(untitled)",
             "lang": ext_lang}
    ai_namer = None
    if os.environ.get("GEMINI_API_KEY", "").strip():
        try:
            from src import copy_ai as _c
            ai_namer = _c.song_name
        except Exception:
            pass
    name = naming.pick_name(genre_key, used_names, rng, probe, ai_fn=ai_namer)
    if ext_name:
        name = ext_name            # a hand-dropped file names its own song
    meta = metadata.build(genre_key, info, ep, rng_py,
                          used_names=used_names, name=name,
                          lang=ext_lang, vocal=bool(lyr_today))
    nch = 0
    if lrc_entries and video_today:            # ⏱ v23: chapters in description
        try:
            nch = metadata.add_chapters(meta, lrc_entries, dur)
            if nch:
                print(f"  ⏱ {nch} chapters burned into the description")
        except Exception as e:
            print(f"  (chapters skipped: {e})")

    copy = None
    try:
        from src import copy_ai
        print("  ✍️  Gemini writing fresh hooks + lines…")
        copy = copy_ai.episode_copy(meta)
    except Exception as e:
        print(f"  (copy_ai: {e} — using banks)")
    print(f"  '{meta['title']}' · {dur:.0f}s · {info['bpm']} bpm · {info['key']}")

    print("  rendering audio + cover…")
    wav = ext_wav if ext_wav else composer.write_wav(OUT / f"ep{ep:03d}.wav", song)
    if ext_wav and os.environ.get("CHIME_OFF", "") != "1":
        try:                                 # 🔔 queue masters skip master();
            composer.mix_logo(wav)           #    the chime still opens them
            print("  🔔 sonic logo stamped on the queue master")
        except Exception as e:
            print(f"  (sonic logo skipped: {e})")

    cover = None
    art_mode = args.art_mode
    if art_mode == "auto":
        art_mode = "gemini" if os.environ.get("GEMINI_API_KEY", "").strip() else "procedural"
    if art_mode == "gemini":
        try:
            from src import art_gemini
            base = art_gemini.generate(meta)
            cover = art.overlay(meta, ep, rng, base, OUT / f"ep{ep:03d}.png")
        except Exception as e:
            print(f"  ⚠ cover gen failed ({e}) — fallback scene cover")
    if cover is None:
        # v23.5: when Gemini art is down, cover the track with a FREE-engine
        # scene (Pollinations flux) instead of a plain gradient — thumbnails
        # stay presentable even on quota-fail days. Pure procedural is the
        # last resort.
        try:
            from src import art_free
            from src import art_gemini as _ag
            variant = (_ag.MOODS.get(meta["genre_key"]) or
                       "empty neon city street in night rain")
            scene = art_free.generate_scenes(variant, n=1, seed0=ep * 101)[0]
            cover = art.overlay(meta, ep, rng, scene,
                                OUT / f"ep{ep:03d}.png")
            print("  🖼  free-engine scene cover (Gemini quota down)")
        except Exception as e2:
            print(f"  (scene cover failed: {e2}) — procedural")
    if cover is None:
        cover = art.render(meta, ep, rng, OUT / f"ep{ep:03d}.png")

    # ---------- moving visuals (for long video AND short bg) ----------
    long_mp4, clip, scenes = None, None, []
    if args.visual_mode != "cover":
        # shorts-only days: scenes/clip still feed the short's background
        long_mp4, clip, scenes = build_visuals(
            meta, ep, rng, wav, dur, args.visual_mode, want_long=video_today,
            sung_lines=(lyrics.cards_from_lyrics(lyr_today, 6)
                        if lyr_today else None),
            lrc_entries=lrc_entries)

    # ---------- schedule ----------
    now = datetime.now(timezone.utc)
    s_off = float(rng.uniform(*SHORT_WINDOW_S))
    sched = {
        "video_offset_s": 0, "video_publish_at": None,
        "short_offset_s": round(s_off),
        "short_publish_at": _iso(now + timedelta(seconds=s_off)),
    }
    if video_today:
        v_off = float(rng.uniform(*VIDEO_WINDOW_S))
        sched["video_offset_s"] = round(v_off)
        sched["video_publish_at"] = (None if v_off < IMMEDIATE_UNDER_S
                                     else _iso(now + timedelta(seconds=v_off)))

    # ---------- long-form static fallback / final video ----------
    if video_today and long_mp4 is None and shutil.which("ffmpeg"):
        from src import video_render as _vr
        subprocess.run([shutil.which("ffmpeg"),
                        "-y", "-loop", "1", "-i", str(cover),
                        "-i", str(wav), "-c:v", "libx264", "-tune",
                        "stillimage", "-af", _vr.loudnorm_filter(wav),
                        "-c:a", "aac", "-b:a", "320k",
                        "-pix_fmt", "yuv420p", "-shortest",
                        str(OUT / f"ep{ep:03d}.mp4")],
                       check=True, capture_output=True)
        long_mp4 = OUT / f"ep{ep:03d}.mp4"

    # ---------- short ----------
    short_pack = short_mp4 = twin_mp4 = None
    if not args.no_shorts:
        from src import shorts, video_render
        print("  cutting lyric short…")
        lines = None
        if lyr_today:                      # cards = the words actually sung 🎤
            sung = lyrics.cards_from_lyrics(lyr_today, k=7)
            if sung:
                hook = copy["hook"] if copy else rng_py.choice(lyrics.HOOKS)
                lines = [hook] + sung
                print(f"  🎤 short cards quote the {ext_lang} vocals it plays")
        elif copy:
            lines = [copy["hook"]] + copy["lines"]
        short_pack = shorts.build(wav, cover, meta, info, ep, rng, rng_py, OUT,
                                  lines_override=lines)
        print(f"  hook @{short_pack['hook_t0']:.0f}s · "
              f"{short_pack['duration_s']:.1f}s · {len(short_pack['cards'])} cards")
        print(f"  hook: '{short_pack['hook_line']}'")
        if shutil.which("ffmpeg"):
            L = short_pack["duration_s"]
            if clip:
                short_pack["base_video"] = video_render.from_clip(
                    clip, L, OUT / f"ep{ep:03d}_short_bg.mp4", size=video_render.VERT)
            elif scenes:
                short_pack["base_video"] = video_render.from_images(
                    [OUT / f"ep{ep:03d}_scene{i}.png" for i in range(len(scenes))],
                    L, OUT / f"ep{ep:03d}_short_bg.mp4", size=video_render.VERT)
            short_mp4 = shorts.render_video(short_pack, OUT / f"ep{ep:03d}_short.mp4")
            try:                             # 💤 v23: slowed+reverb twin short
                every = int((os.environ.get("SLOWED_EVERY", "0") or "0").strip())
            except ValueError:
                every = 0
            if _twin_today(video_today, ep, every,
                           getattr(args, "two_shorts_a_day", False)):
                print(f"  💤 off-day second drop → slowed + reverb twin short…")
                twin = shorts.slowed_twin_pack(short_pack, OUT, ep)
                twin_mp4 = shorts.render_video(twin, OUT / f"ep{ep:03d}_slowed.mp4")
                # 🚨 shadow-ban guard (2026-08-17): the twin must NEVER land
                # near the main short — YouTube reads 2 same-time posts as spam.
                # Boss cadence 2026-08-30: 2 shorts/day, spaced within the same
                # day — twin rides ~11h after the run (short posts +1–3h).
                t_off = 11 * 3600 + float(rng.uniform(0, 5400))
                sched["twin_offset_s"] = round(t_off)
                sched["twin_publish_at"] = _iso(now + timedelta(seconds=t_off))

    print("  📅 schedule:")
    if video_today:
        print(f"     video → {'NOW' if not sched['video_publish_at'] else sched['video_publish_at']}"
              f"  (+{timedelta(seconds=sched['video_offset_s'])})")
    else:
        print("     video → — (shorts-only day)")
    print(f"     short → {sched['short_publish_at']}  (+{timedelta(seconds=sched['short_offset_s'])})")
    if twin_mp4:
        print(f"     twin (slowed) → {sched['twin_publish_at']}  "
              f"(+{timedelta(seconds=sched['twin_offset_s'])})")

    manifest = {"episode": ep, "genre": genre_key, "seed": seed, **info,
                "meta": meta, "schedule": sched, "video_today": video_today,
                "ai_copy": copy, "lang": ext_lang, "vocals": bool(lyr_today),
                "karaoke": len(lrc_entries),
                "universe": {"chapters": nch,
                             "mascot": (OUT / f"ep{ep:03d}_nyx.webm").exists(),
                             "spectrum": os.environ.get("SPECTRUM_OFF", "") != "1",
                             "loop_echo": os.environ.get("LOOP_OFF", "") != "1",
                             "slowed_twin": twin_mp4 is not None},
                "visuals": {"kind": "clip" if clip else "scenes" if scenes else "cover"},
                "short_hook": short_pack["hook_line"] if short_pack else None,
                "files": [str(f) for f in (wav, cover, long_mp4, short_mp4) if f]}
    (OUT / "latest.json").write_text(json.dumps(manifest, indent=2))

    vid = sid = None
    errors: list[str] = []
    if args.publish and not args.dry_run:
        from src import uploader, analytics
        print("  🧠 refreshing adaptive weights…")
        try:
            w = analytics.refresh_weights(st)
            if w:
                st["genre_weights"] = w
        except Exception as e:                      # weights are nice-to-have — never block a release
            print(f"  (adaptive weights skipped: {e})")
        # ---------- uploads: each isolated so one failure CANNOT kill the other ----------
        if video_today:
            if not (long_mp4 and Path(long_mp4).exists()):
                # HARD GUARD: an audio-only file on YouTube = "Processing
                # abandoned" junk on the channel (EP.001 incident). Fail loud,
                # upload nothing, alert the boss. Never `or wav` again.
                errors.append("video render missing (ffmpeg absent on runner?) — audio-only upload refused")
                print("  ❌ no rendered mp4 — refusing to upload audio-only junk")
            else:
                print("  uploading video…")
                try:
                    vid = uploader.upload(long_mp4, meta,
                                          publish_at=sched["video_publish_at"])
                    print(f"  ✅ video: https://youtu.be/{vid}")
                except Exception as e:
                    errors.append(f"video upload failed: {e}")
                    print(f"  ❌ video upload failed: {e}")
        if short_mp4:
            smeta = metadata.short_meta(meta, short_pack["hook_line"])
            print("  uploading short…")
            try:
                sid = uploader.upload(short_mp4, smeta,
                                      publish_at=sched["short_publish_at"])
                print(f"  ✅ short: https://youtu.be/{sid}")
            except Exception as e:
                errors.append(f"short upload failed: {e}")
                print(f"  ❌ short upload failed: {e}")
        if twin_mp4 and Path(twin_mp4).exists():      # bonus drop — failures
            try:                                      # never fail the run
                # boss cadence 2026-08-30: twin = second short of an off-day,
                # spaced ~11h from the run within the SAME day (never near the
                # main short's +1-3h slot — same-time doubles spam-signal YT).
                twin_at = sched.get("twin_publish_at") or _iso(
                    now + timedelta(seconds=11 * 3600 + float(rng.uniform(0, 1800))))
                smeta_t = metadata.short_meta(meta, short_pack["hook_line"],
                                              slowed=True)
                sid2 = uploader.upload(twin_mp4, smeta_t, publish_at=twin_at)
                print(f"  ✅ twin (slowed+reverb): https://youtu.be/{sid2} · {twin_at}")
            except Exception as e:
                print(f"  (twin upload skipped: {e})")
        # ---------- persist state ONLY when something actually went up ----------
        # partial day (1 of 2 uploaded) → advance so we NEVER re-upload a duplicate;
        # total failure (nothing up) → keep EP so tomorrow retries the same episode.
        if vid or sid:
            st["episode"] = ep
            state.record(st, {"episode": ep,
                              "kind": "full" if (vid and sid) else "short" if sid else "video",
                              "youtube_id": vid or sid, "video_id": vid, "short_id": sid,
                              "title": meta["title"], "name": meta["name"],
                              "genre": genre_key,
                              "publish_at": sched["video_publish_at"] or "immediate",
                              "short_publish_at": sched["short_publish_at"]})
            state.save(st)
        # refresh manifest with real upload IDs so notify/alerts can link them
        manifest["video_id"] = vid
        manifest["short_id"] = sid
        (OUT / "latest.json").write_text(json.dumps(manifest, indent=2))
        if sid and vid:
            try:
                from src import funnel
                funnel.post_link_comment(sid, vid)
                print("  🔗 funnel comment posted under the short")
            except Exception as e:
                print(f"  (funnel comment skipped: {e})")
        # ---------- community post pack (boss taps it from Telegram) ----------
        try:
            from src import posts
            posts.maybe_post(ep=ep, meta=meta, sched=sched,
                             hook=(short_pack["hook_line"] if short_pack else None),
                             cover=cover, vid=vid, sid=sid)
        except Exception as e:
            print(f"  📮 community post skipped: {e}")
        # housekeeping — upload is done, the media lives on YouTube now.
        # wipe this episode's heavy renders (ep*.wav/mp4/png); keep only the
        # tiny text records (latest.json, summary.md, run.log).
        freed = 0
        for f in OUT.glob(f"ep{ep:03d}*"):
            try:
                freed += f.stat().st_size
                f.unlink()
            except OSError:
                pass
        print(f"  🧹 cleaned {freed / 1e6:.0f} MB of renders (uploaded copies live on YouTube)")
        # ---------- boss's queue bookkeeping ----------
        if ext_src and ext_src.exists():
            ext_src.unlink()              # consumed — git records the deletion
            print(f"  📥 consumed queue file '{ext_src.name}' — never re-used")
        if ext_lyc and ext_lyc.exists():
            ext_lyc.unlink()              # its words were spent too
        if ext_lrc and ext_lrc.exists():
            ext_lrc.unlink()              # and its timings
        try:
            inc = ROOT / "incoming"
            queue_left = inc.is_dir() and any(inc.glob("next_song*"))
            if not queue_left:            # only cook when the queue is empty
                from src import music_space, music_suno
                keys = list(composer.GENRES)
                nxt_genre = keys[(keys.index(genre_key) + 1) % len(keys)]
                nxt_lang = _pick_lang(ep + 1)
                nxt_lyc = None
                try:
                    from src import copy_ai as _ca
                    print(f"  ✍️  Gemini songwriting "
                          f"({lyrics.LANGS[nxt_lang]['label']})…")
                    nxt_lyc = _ca.song_lyrics(
                        {"name": "(untitled)", "genre": GENRE_LABEL[nxt_genre]},
                        nxt_lang, max(150, dur))
                except Exception as e:
                    print(f"  (songwriting: {e} — bank lyrics tonight)")
                    nxt_lyc = lyrics.song_lyrics(nxt_genre, "(untitled)",
                                                 rng_py, nxt_lang)
                if nxt_lang != "en":
                    print(f"  🌍 WORLD TOUR drop tomorrow: "
                          f"{lyrics.LANGS[nxt_lang]['label']}")
                inc.mkdir(exist_ok=True)
                stem = f"next_song--{nxt_genre}--{nxt_lang}"
                # ⚡ cook chain v23.4 THE POWER GRID: suno → lyria → ace-v1.5
                # → ace-v1, each retried (LANE_RETRIES), then offline engine.
                from src import music_chain
                # 🎤 require_vocals so tomorrow's queued song is truly a vocal
                # song (musicgen-local excluded when REQUIRE_VOCALS=1), so the
                # next day's vocal guard can't be fooled by an instrumental.
                cooked, cooked_by = music_chain.cook(
                    nxt_genre, max(150, dur), inc / f"{stem}.mp3",
                    lyrics=nxt_lyc, lang=nxt_lang,
                    lrc_out=inc / f"{stem}.lrc.txt",   # 🎤⏱ karaoke rides too
                    require_vocals=os.environ.get("REQUIRE_VOCALS", "") == "1")
                if cooked:
                    print(f"  🎧 tomorrow cooked by: {cooked_by} "
                          f"(chain: suno → lyria → ace-v1.5 → ace-v1 → engine)")
                # only stamp the words on a song that actually sang
                if cooked and nxt_lyc and cooked_by != "musicgen-local":
                    (inc / f"{stem}.lyrics.txt").write_text(
                        nxt_lyc, encoding="utf-8")
            else:
                print("  📦 queue still stocked — nothing to cook today")
        except Exception as e:
            print(f"  (queue cook skipped: {e} — tomorrow will ask the space live)")
    else:
        print("  DRY-RUN — no upload, state untouched.")
        # 📨 dry-run = drop today's renders in the owner's Telegram instead of
        # YouTube, so a human can review the episode. The daily cron
        # (09:23 UTC / 3:23 PM BDT) still composes + publishes a FRESH one.
        try:
            from src import notify as _notify
            _tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            _cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
            _m = meta if isinstance(meta, dict) else {}
            _cap = (f"🧪 TEST PREVIEW · EP.{ep:03d} — '{_m.get('name', '?')}' "
                    f"({genre_key} · {_m.get('bpm', '?')} bpm · {_m.get('key', '?')})\n"
                    f"🎤 vocals: {'yes' if lyr_today else 'NO — instrumental'}\n"
                    f"🚫 dry-run — NOTHING went to YouTube. Real release: "
                    f"daily cron 3:23 PM BDT (a new episode).")
            _any = False
            if os.environ.get("REQUIRE_VOCALS", "") == "1" and not lyr_today:
                # 🛟 v12 (2026-08-30, boss: "now no vocals again"): a dry-run
                # MUST NEVER drop an instrumental "demo" — every vocal lane
                # failed, so there is nothing to ear-test. Say so in ONE text
                # instead of burning the boss's ears (same refusal class as
                # the publish-time SystemExit guard above).
                _sos = _notify.send_telegram(
                    _tok, _cid,
                    f"🎤❌ VOCAL COOK MISSED TODAY — demo withheld.\n"
                    f"Every singing lane missed (Kaggle bundle drop / HF ZeroGPU "
                    f"quota / lyria paywall), so today's render is an instrumental — "
                    f"refusing to waste your ears on it.\n"
                    f"Nothing went to YouTube. Nothing to review — next demo fires "
                    f"when a vocal lane lands.", dry=False)
                print(f"  📨 telegram: instrumental demo withheld ({_sos})")
            else:
                for _f in (short_mp4, twin_mp4, long_mp4):
                    if _f and Path(_f).exists():
                        print(f"  📨 telegram: {_notify.send_telegram_video(_tok, _cid, str(_f), _cap)}")
                        _any = True
            if not _any:
                print("  📨 telegram: nothing rendered to send")
        except Exception as _e:
            print(f"  📨 telegram preview failed ({_e}) — dry-run unaffected")

    _write_summary(OUT / "summary.md", meta, sched, video_today, vid, sid)
    if errors:
        # state is already saved above — exiting red only exists so the
        # failure alert fires with the real error in the log tail
        raise SystemExit("⚠️ partial release — " + " | ".join(errors))
    print("done.")


if __name__ == "__main__":
    main()

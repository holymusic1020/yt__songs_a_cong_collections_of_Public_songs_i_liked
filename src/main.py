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
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from src import art, composer, metadata, state

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
GENRE_ROTATION = ["deep_pop", "drift_phonk", "baroque_waltz",
                  "dark_ambient", "disco_house", "lofi"]

VIDEO_WINDOW_S = (0, 5 * 3600)
SHORT_WINDOW_S = (3600, 3 * 3600)
IMMEDIATE_UNDER_S = 900
VIDEO_EVERY = 3          # long-form cadence: every Nth episode


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_visuals(meta, ep, rng, wav, dur, mode, want_long=True):
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
        try:
            from src import art_gemini
            variant = rng.choice(art_gemini.SCENE_VARIANTS[meta["genre_key"]])
            print("  🖼  painting 4 matching scenes with Gemini…")
            print(f"     style: {variant[:72]}…")
            scenes = art_gemini.generate_scenes(meta, n=4, scene_text=variant)
            meta["style_variant"] = variant
            for i, im in enumerate(scenes):
                im.save(OUT / f"ep{ep:03d}_scene{i}.png")
        except Exception as e:
            print(f"  ⚠ scenes failed ({e}) — static cover it is")

    if have_ff and want_long:
        from src import video_render
        chip = art.chip_png(OUT / "chip.png")
        if clip:
            print("  🎞  looping clip to song length…")
            long_mp4 = video_render.from_clip(clip, dur, OUT / f"ep{ep:03d}.mp4",
                                              wav=wav, chip=chip)
        elif scenes:
            print("  🎞  Ken Burns slideshow (xfades)…")
            long_mp4 = video_render.from_images(
                [OUT / f"ep{ep:03d}_scene{i}.png" for i in range(len(scenes))],
                dur, OUT / f"ep{ep:03d}.mp4", wav=wav, chip=chip)
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
    print(f"EP.{ep:03d} · genre={genre_key} · "
          f"{'FULL (video+short)' if video_today else f'short-only · next video EP.{nxt:03d}'}")

    target = args.length or float(rng.integers(95, 201))
    print(f"  target={target:.0f}s · seed={seed}")

    print("  composing…")
    song, info = composer.compose(genre_key, rng, target)
    used_names = {h.get("name") for h in st.get("history", []) if h.get("name")}
    dur = info["duration_s"]

    from src import naming
    probe = {"genre": info["genre"], "genre_key": genre_key,
             "key": info["key"], "bpm": info["bpm"], "name": "(untitled)"}
    ai_namer = None
    if os.environ.get("GEMINI_API_KEY", "").strip():
        try:
            from src import copy_ai as _c
            ai_namer = _c.song_name
        except Exception:
            pass
    name = naming.pick_name(genre_key, used_names, rng, probe, ai_fn=ai_namer)
    meta = metadata.build(genre_key, info, ep, rng_py,
                          used_names=used_names, name=name)

    copy = None
    try:
        from src import copy_ai
        print("  ✍️  Gemini writing fresh hooks + lines…")
        copy = copy_ai.episode_copy(meta)
    except Exception as e:
        print(f"  (copy_ai: {e} — using banks)")
    print(f"  '{meta['title']}' · {dur:.0f}s · {info['bpm']} bpm · {info['key']}")

    print("  rendering audio + cover…")
    wav = composer.write_wav(OUT / f"ep{ep:03d}.wav", song)

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
            print(f"  ⚠ cover gen failed ({e}) — procedural")
    if cover is None:
        cover = art.render(meta, ep, rng, OUT / f"ep{ep:03d}.png")

    # ---------- moving visuals (for long video AND short bg) ----------
    long_mp4, clip, scenes = None, None, []
    if args.visual_mode != "cover":
        # shorts-only days: scenes/clip still feed the short's background
        long_mp4, clip, scenes = build_visuals(
            meta, ep, rng, wav, dur, args.visual_mode, want_long=video_today)

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
    short_pack = short_mp4 = None
    if not args.no_shorts:
        from src import shorts, video_render
        print("  cutting lyric short…")
        lines = ([copy["hook"]] + copy["lines"]) if copy else None
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

    print("  📅 schedule:")
    if video_today:
        print(f"     video → {'NOW' if not sched['video_publish_at'] else sched['video_publish_at']}"
              f"  (+{timedelta(seconds=sched['video_offset_s'])})")
    else:
        print("     video → — (shorts-only day)")
    print(f"     short → {sched['short_publish_at']}  (+{timedelta(seconds=sched['short_offset_s'])})")

    manifest = {"episode": ep, "genre": genre_key, "seed": seed, **info,
                "meta": meta, "schedule": sched, "video_today": video_today,
                "ai_copy": copy,
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
    else:
        print("  DRY-RUN — no upload, state untouched.")

    _write_summary(OUT / "summary.md", meta, sched, video_today, vid, sid)
    if errors:
        # state is already saved above — exiting red only exists so the
        # failure alert fires with the real error in the log tail
        raise SystemExit("⚠️ partial release — " + " | ".join(errors))
    print("done.")


if __name__ == "__main__":
    main()

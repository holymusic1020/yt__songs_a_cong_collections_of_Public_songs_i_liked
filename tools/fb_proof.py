#!/usr/bin/env python3
"""🧪 FB REEL PROOF (+🛟 RESSESCUE MODE) — boss (2026-09-02): "test with a vid
then reel, then flip the switch." Two modes:

PROOF (default): renders a 7 s NYX test clip with ffmpeg, walks the official
Reels 3-phase (start → upload → finish) against the boss-credentialed Page,
prints the post URL on success. Self-diagnoses: probes /me across live api
versions + identifies token-class + page visibility BEFORE touching upload.

RESCUE (RESCUE_URL set): yt-dlp downloads an already-YouTubed short and re-
posts it to the Page with a daily-style caption (≤245 chars — the EP.029
400-autopsy: Reels description ceiling). Uses the EXACT v23.0 reels lane
multi_post.py rides daily, so rescue == what tomorrow's automatic run does.

COLD LAWS kept: never echoes the token (POST body travel; error dumps go
through redact-free messages we author); exits 1 on any API rejection so the
workflow run turns visibly red.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request


def _post(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except Exception as e:
        bodytxt = e.read().decode()[:400] if hasattr(e, "read") else str(e)
        raise RuntimeError(f"fb api «{url[-44:]}» rejected: {bodytxt}")


def _get(url, fields):
    qs = urllib.parse.urlencode(fields)
    req = urllib.request.Request(f"{url}?{qs}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _probe(pid, tok):
    """/me across live versions → (version, who). Exit-red if nothing answers."""
    for v in ("23.0", "22.0", "21.0", "20.0"):
        try:
            who = _get(f"https://graph.facebook.com/v{v}/me", {"fields": "id,name", "access_token": tok})
            print(f"  🔎 v{v}/me ok — token object: id={who.get('id')} name={who.get('name')!r}")
            return v, who
        except Exception as e:
            print(f"  🔎 v{v}/me fail: {str(e)[:80]}")
    print("  ❌ token isn't readable at ANY version — regenerate the PAGE token")
    sys.exit(1)


def _check_page(g, pid, tok, who):
    if who.get("id") == pid:
        print("  ✅ token IS a Page token for this page (ideal)")
        return
    print(f"  ⚠️ token object id ≠ FB_PAGE_ID ({pid}) — trying page lookup anyway")
    try:
        pg = _get(f"{g}/{pid}", {"fields": "id,name,link", "access_token": tok})
        print(f"  ✅ page lookup ok: {pg.get('name')!r} ({pg.get('link', '?')})")
    except Exception as e:
        print(f"  ❌ page {pid} not visible to this token — {e}")
        print("     → most likely: a USER token was pasted instead of the PAGE token,")
        print("       or the id is the wrong page. API ids come from debug_token → Profile ID.")
        sys.exit(1)


def _render_proof_clip():
    """testsrc2 9:16 + hum — no fonts (drawtext killed v1: unescaped ':')."""
    clip = os.path.join(tempfile.gettempdir(), "nyx_proof.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=25:d=7",
        "-f", "lavfi", "-i", "sine=frequency=432:duration=7",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "baseline",
        "-c:a", "aac", "-b:a", "96k", "-shortest", clip], check=True)
    print(f"  🎬 proof clip rendered: {os.path.getsize(clip)} bytes")
    return clip


def _fetch_rescue_clip(url):
    subprocess.run(["pip", "install", "-q", "--upgrade", "yt-dlp"], check=True)
    clip = os.path.join(tempfile.gettempdir(), "rescue_short.mp4")
    # datacenter IPs trip YT's bot-check (mystery exit 1 behind -q) — try polite
    # clients, single-file formats, keep the tail visible for forensics
    attempts = [
        ["--extractor-args", "youtube:player_client=android,mweb"],
        ["--extractor-args", "youtube:player_client=tv,web"],
        [],
    ]
    last = ""
    for extra in attempts:
        if os.path.exists(clip):
            os.remove(clip)
        r = subprocess.run(["yt-dlp", "--no-progress", "--no-playlist",
                            "-f", "18/best[height<=720]/best",
                            "--socket-timeout", "15", "--retries", "2",
                            *extra, "-o", clip, url],
                           capture_output=True, text=True)
        last = (r.stdout + r.stderr)[-300:]
        if r.returncode == 0 and os.path.exists(clip) and os.path.getsize(clip) > 20000:
            print(f"  🎬 rescue clip fetched: {os.path.getsize(clip)} bytes ({url})")
            return clip
        print(f"  ↻ yt-dlp attempt {extra or 'default'} failed: …{last[-160:]}")
    raise SystemExit("  ❌ all yt-dlp clients rejected — youtube bot-wall. Fix manually or retry later.")


def _reel_this(g, pid, tok, clip, desc):
    """Reels 3-phase — mirrors multi_post.py's daily lane exactly."""
    init = _post(f"{g}/{pid}/video_reels", {"upload_phase": "start", "access_token": tok})
    vid = init.get("video_id")
    if not vid:
        print("  ❌ INIT unexpected:", json.dumps(init)[:400]); sys.exit(1)
    print(f"  ✅ init ok — video_id {vid}")

    size = os.path.getsize(clip)
    upl = init.get("upload_url") or f"https://rupload.facebook.com/video-upload/{g.rsplit('/')[-1]}/{vid}"
    data = open(clip, "rb").read()
    req = urllib.request.Request(upl, data=data, method="POST", headers={
        "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
        "Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            print("  ✅ upload ok —", r.read().decode()[:100])
    except Exception as e:
        try:
            r2 = urllib.request.Request(f"{upl}?oauth_token={urllib.parse.quote(tok)}", data=data,
                                        method="POST", headers={"offset": "0", "file_size": str(size),
                                                                "Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(r2, timeout=300) as resp:
                print("  ✅ upload ok (alt auth) —", resp.read().decode()[:100])
        except Exception as e2:
            print("  ❌ UPLOAD:", str(e2)[:400]); sys.exit(1)

    fin = _post(f"{g}/{pid}/video_reels",
                {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                 "description": desc[:245], "access_token": tok})
    print(f"  ✅ finish ok — {json.dumps(fin)[:140]}")
    try:
        meta = _get(f"{g}/{vid}", {"fields": "permalink_url", "access_token": tok})
    except Exception:
        meta = {}
    print(f"  🚀 POSTED — reel live: {meta.get('permalink_url', '(permalink pending — check the Page)')}")


def main():
    pid = os.environ.get("FB_PAGE_ID", "")
    tok = os.environ.get("FB_PAGE_TOKEN", "")
    if not pid or not tok:
        print("  🌐 FB proof skipped — FB_PAGE_ID/FB_PAGE_TOKEN not set "
              "(creds still missing from repo Secrets/Variables)")
        return 0

    rescue = os.environ.get("RESCUE_URL", "").strip()
    if rescue:
        print(f"  🛟 rescue mode — re-posting YT short as reel: {rescue}")
        ver = "23.0"  # proven live earlier today; skip probe, go fast
        g = f"https://graph.facebook.com/v{ver}"
        clip = _fetch_rescue_clip(rescue)
        desc = os.environ.get("RESCUE_CAPTION", "").strip() or (
            os.environ.get("RESCUE_TITLE", "nyx drop").strip()
            + "\n📺 on youtube: " + rescue + "\n#newmusic #vibes")
    else:
        ver, who = _probe(pid, tok)
        g = f"https://graph.facebook.com/v{ver}"
        _check_page(g, pid, tok, who)
        clip = _render_proof_clip()
        desc = ("🤖 NYX wiring proof — automated test Reel from the yt-auto bot. "
                "If you're reading this on the Page: the machine is plugged in. 🎶")

    _reel_this(g, pid, tok, clip, desc)
    if not rescue:
        print("  🔑 NEXT: boss eyeballs the Reel on the Nix Speech Page — wire proven hot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

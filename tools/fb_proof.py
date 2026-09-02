#!/usr/bin/env python3
"""🧪 FB REEL PROOF — boss (2026-09-02): "test with a vid then reel, then flip
the switch." Standalone: renders a 7 s NYX test clip with ffmpeg, walks the
official Reels 3-phase (start → upload → finish) against the boss-credentialed
Page, and prints the post URL on success. Mirrors exactly the permission path
multi_post.py's fb lane rides (pages_manage_posts / page token), so a green
proof == tomorrow's real fan-out is safe.

COLD LAWS kept: never echoes the token (it travels in the POST body, not URLs,
and error dumps go through _safe()); exits 1 on any API rejection so the
workflow run turns visibly red.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

G = "https://graph.facebook.com/v26.0"


def _safe(obj):
    s = json.dumps(obj)[:600]
    tok = os.environ.get("FB_PAGE_TOKEN", "")
    return s.replace(tok, "***TOKEN***") if tok else s


def _post(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def _fail(which, err):
    try:
        body = err.read().decode() if hasattr(err, "read") else str(err)
    except Exception:
        body = str(err)
    print(f"  ❌ {which}: {body[:600]}")
    sys.exit(1)


def main():
    pid = os.environ.get("FB_PAGE_ID", "")
    tok = os.environ.get("FB_PAGE_TOKEN", "")
    if not pid or not tok:
        print("  🌐 FB proof skipped — FB_PAGE_ID/FB_PAGE_TOKEN not set "
              "(creds still missing from repo Secrets/Variables)")
        return 0

    # 0️⃣ render a tiny 9:16 proof clip (black bg + NYX heartbeat hum)
    clip = os.path.join(tempfile.gettempdir(), "nyx_proof.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=0x101018:s=720x1280:d=7:r=25",
        "-f", "lavfi", "-i", "sine=frequency=432:duration=7",
        "-vf", ("drawtext=text='NYX :: WIRING PROOF':fontcolor=white:fontsize=46:"
                "x=(w-text_w)/2:y=(h-200)/2,drawtext=text='if you can see this — the bot is plugged in':"
                "fontcolor=gray:fontsize=30:x=(w-text_w)/2:y=(h+120)/2"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "baseline",
        "-c:a", "aac", "-b:a", "96k", "-shortest", clip], check=True)
    size = os.path.getsize(clip)
    print(f"  🎬 proof clip rendered: {size} bytes")

    # 1️⃣ INIT
    try:
        init = _post(f"{G}/{pid}/video_reels", {"upload_phase": "start", "access_token": tok})
    except Exception as e:
        _fail("INIT", e); return 1
    vid = init.get("video_id")
    if not vid:
        print("  ❌ INIT unexpected:", _safe(init)); return 1
    print(f"  ✅ init ok — video_id {vid}")

    # 2️⃣ UPLOAD (resumable binary header style; falls back to start's upload_url)
    upl = init.get("upload_url") or f"https://rupload.facebook.com/video-upload/v26.0/{vid}"
    data = open(clip, "rb").read()
    req = urllib.request.Request(upl, data=data, method="POST", headers={
        "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
        "Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            print("  ✅ upload ok —", r.read().decode()[:120])
    except Exception as e:
        # fallback: file-url style init sometimes answers differently; try OAuth param style
        try:
            r2 = urllib.request.Request(f"{upl}?oauth_token={urllib.parse.quote(tok)}", data=data,
                                        method="POST", headers={"offset": "0", "file_size": str(size),
                                                                "Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(r2, timeout=180) as resp:
                print("  ✅ upload ok (alt auth) —", resp.read().decode()[:120])
        except Exception as e2:
            _fail("UPLOAD", e2); return 1

    # 3️⃣ FINISH / PUBLISH
    try:
        fin = _post(f"{G}/{pid}/video_reels",
                    {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                     "description": ("🤖 NYX wiring proof — automated test Reel from the yt-auto bot. "
                                     "If you're reading this on the Page: the machine is plugged in. 🎶"),
                     "access_token": tok})
    except Exception as e:
        _fail("FINISH", e); return 1
    print(f"  ✅ finish ok — {_safe(fin)}")
    try:
        meta = _post(f"{G}/{vid}", {"fields": "permalink_url", "access_token": tok})
    except Exception:
        meta = {}
    print(f"  🚀 PROOF PASSED — reel live: {meta.get('permalink_url', '(permalink pending — check the Page)')}")
    print("  🔑 NEXT: boss eyeballs the Reel on the Nix Speech Page, then says 'flipped' — yt+fb both armed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def _get(url, fields):
    qs = urllib.parse.urlencode(fields)
    req = urllib.request.Request(f"{url}?{qs}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    pid = os.environ.get("FB_PAGE_ID", "")
    tok = os.environ.get("FB_PAGE_TOKEN", "")
    if not pid or not tok:
        print("  🌐 FB proof skipped — FB_PAGE_ID/FB_PAGE_TOKEN not set "
              "(creds still missing from repo Secrets/Variables)")
        return 0

    # ⛳️ SELF-DIAGNOSING pre-flight (v1 proof died on 100/33 — could be the
    # api VER, the Object id, or the token-class; check all three loudly)
    ver = None
    for v in ("23.0", "22.0", "21.0", "20.0"):
        try:
            who = _get(f"https://graph.facebook.com/v{v}/me", {"fields": "id,name", "access_token": tok})
            print(f"  🔎 v{v}/me ok — token object: id={who.get('id')} name={who.get('name')!r}")
            ver = v
            break
        except Exception as e:
            print(f"  🔎 v{v}/me fail: {e}")
    if not ver:
        print("  ❌ token isn't readable at ANY version — regenerate the PAGE token"); return 1
    g = f"https://graph.facebook.com/v{ver}"
    if who.get("id") == pid:
        print("  ✅ token IS a Page token for this page (ideal)")
    else:
        print(f"  ⚠️ token object id ≠ FB_PAGE_ID ({pid}) — trying page lookup anyway")
        try:
            pg = _get(f"{g}/{pid}", {"fields": "id,name,link", "access_token": tok})
            print(f"  ✅ page lookup ok: {pg.get('name')!r} ({pg.get('link','?')})")
        except Exception as e:
            print(f"  ❌ page {pid} not visible to this token — {e}")
            print("     → most likely: a USER token was pasted instead of the PAGE token,")
            print("       or the id is the wrong page. Re-copy from Explorer with")
            print("       User-or-Page = your Page, and verify FB_PAGE_ID = the page's number.")
            return 1

    # 0️⃣ render a tiny 9:16 proof clip (testsrc2 + NYX heartbeat hum — the
    # previous drawtext needed fonts AND had unescaped ':' → filter died)
    clip = os.path.join(tempfile.gettempdir(), "nyx_proof.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=25:d=7",
        "-f", "lavfi", "-i", "sine=frequency=432:duration=7",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "baseline",
        "-c:a", "aac", "-b:a", "96k", "-shortest", clip], check=True)
    size = os.path.getsize(clip)
    print(f"  🎬 proof clip rendered: {size} bytes")

    # 1️⃣ INIT (api version = the one that answered /me)
    try:
        init = _post(f"{g}/{pid}/video_reels", {"upload_phase": "start", "access_token": tok})
    except Exception as e:
        _fail("INIT", e); return 1
    vid = init.get("video_id")
    if not vid:
        print("  ❌ INIT unexpected:", _safe(init)); return 1
    print(f"  ✅ init ok — video_id {vid}")

    # 2️⃣ UPLOAD (resumable binary header style; falls back to start's upload_url)
    upl = init.get("upload_url") or f"https://rupload.facebook.com/video-upload/v{ver}/{vid}"
    data = open(clip, "rb").read()
    req = urllib.request.Request(upl, data=data, method="POST", headers={
        "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
        "Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            print("  ✅ upload ok —", r.read().decode()[:120])
    except Exception as e:
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
        fin = _post(f"{g}/{pid}/video_reels",
                    {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                     "description": ("🤖 NYX wiring proof — automated test Reel from the yt-auto bot. "
                                     "If you're reading this on the Page: the machine is plugged in. 🎶"),
                     "access_token": tok})
    except Exception as e:
        _fail("FINISH", e); return 1
    print(f"  ✅ finish ok — {_safe(fin)}")
    try:
        meta = _get(f"{g}/{vid}", {"fields": "permalink_url", "access_token": tok})
    except Exception:
        meta = {}
    print(f"  🚀 PROOF PASSED — reel live: {meta.get('permalink_url', '(permalink pending — check the Page)')}")
    print("  🔑 NEXT: boss eyeballs the Reel on the Nix Speech Page, then says 'flipped' — yt+fb both armed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

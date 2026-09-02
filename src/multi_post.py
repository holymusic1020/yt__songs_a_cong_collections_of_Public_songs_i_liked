"""🌐 Multi-post fan-out (boss 2026-08-31): one episode → every earning surface.

COLD LAW: OFF unless env MULTIPOST lists platforms (e.g. "fb,tt") AND that
platform's creds are present. Zero creds → pure no-op, a ledger line, ZERO
change to the YouTube/Telegram pipeline you already trust. Never raises:
every failure degrades to a printed reason, a release never crashes over
cross-posting.

Surfaces:
  fb — Facebook Page Reels  (Graph API video_reels 3-phase upload)
  tt — TikTok (Content Posting API init→upload→status). Unapproved dev apps
       MUST use SELF_ONLY: the video lands in the boss's TikTok as a private
       draft he publishes with one tap. Approved apps may post direct.

Each call is stdlib-only (urllib), $0. Env creds (boss adds them, then says
"cng" to flip on):  FB_PAGE_ID + FB_PAGE_TOKEN · TIKTOK_ACCESS_TOKEN
(+ optional TIKTOK_PRIVACY=public_to_everyone once the app is approved).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

_HASHTAGS = {
    "drift_phonk": ["#phonk", "#driftphonk", "#nightdrive"],
    "phonk_mafia": ["#phonk", "#phonkmafia", "#gymtok"],
    "brazilian_phonk": ["#brazilianphonk", "#funk", "#montagem"],
    "villain_pop": ["#darkpop", "#villain", "#maincharacter"],
    "villain's mirror": ["#darkpop", "#villain", "#aesthetic"],
    "emo_rap": ["#emorap", "#sadboy", "#latenight"],
    "melodic_trap": ["#melodictrap", "#trap", "#vibes"],
    "anime_titan": ["#anime", "#amv", "#animeedit"],
    "chart_pop": ["#popmusic", "#newmusic", "#lyrics"],
}
_DEFAULT_TAGS = ["#lyrics", "#vibes", "#newmusic", "#musicvideo"]


def _tags(genre_key: str) -> list:
    return _HASHTAGS.get(genre_key, []) + ["#nymusic", "#originalmusic"]


def captions(meta: dict, genre_key: str, yt_sid: str | None) -> dict:
    title = (meta.get("title") or meta.get("name") or "untitled").strip()
    tags = " ".join((_DEFAULT_TAGS + _tags(genre_key))[:8])
    link = f"\n📺 full + slowed: https://youtu.be/{yt_sid}" if yt_sid else ""
    return {
        "fb": f"{title} 🌙 {link}\n{tags}",
        "tt": f"{title} {tags}"[:150],          # TT caption hard limit ~2.2k, keep tight
        "title": title,
        "tags": tags,
    }


def build_postpack(out: Path, ep: int, meta: dict, genre_key: str,
                   yt_vid: str | None, yt_sid: str | None) -> dict:
    """One manifest per episode: the media files + per-platform captions."""
    media = {}
    for pat, kind in ((f"ep{ep:03d}_slowed.mp4", "short_twin"),
                      (f"ep{ep:03d}_short.mp4", "short"),
                      (f"ep{ep:03d}_long.mp4", "long"),
                      (f"ep{ep:03d}.mp4", "long")):
        f = out / pat
        if f.exists():
            media.setdefault(kind, str(f))
    pack = {
        "ep": ep,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "genre": genre_key,
        "youtube": {"video_id": yt_vid, "short_id": yt_sid},
        "captions": captions(meta, genre_key, yt_sid or yt_vid),
        "media": media,
    }
    try:
        (out / f"ep{ep:03d}_postpack.json").write_text(json.dumps(pack, indent=2))
    except OSError:
        pass
    return pack


# ─────────────────────────────── facebook reels ──────────────────────────────

def fb_reel(mp4: Path, caption: str) -> dict:
    pid, tok = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    # 🧪 whole-process dry run (boss 2026-09-02): report readiness, ZERO api calls
    if os.environ.get("MULTIPOST_DRYRUN") == "1":
        size = mp4.stat().st_size if mp4 and mp4.exists() else 0
        creds = "credentialed ✓" if (pid and tok) else "⚠️ creds MISSING"
        return {"fb": f"render-only — would post reel ~{size / 1e6:.1f} MB ({creds}): {caption[:60]}…"}
    if not (pid and tok):
        return {"fb": "skipped — FB_PAGE_ID/FB_PAGE_TOKEN not set"}
    # 🎯 FB Reels bullets (2026-09-02: HTTP 400 autopsy after EP.029 YT ✓ / fb ✗):
    # Reels descriptions have a tight ceiling — caption pack (title+link+tags)
    # ~260 chars died "Bad Request". Cap at 245. + surface FB's REAL error body
    # so the next soft-fail line names its poison.
    desc = caption if len(caption) <= 245 else caption[:242].rstrip() + "…"
    api = f"https://graph.facebook.com/v23.0/{pid}"
    size = mp4.stat().st_size

    def call(url, data, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {},
                                     method="POST")
        try:
            return json.loads(urllib.request.urlopen(req, timeout=180).read())
        except Exception as e:
            body = e.read().decode()[:300] if hasattr(e, "read") else str(e)
            raise RuntimeError(f"fb api «{url.split('?')[0][-36:]}» rejected: {body}")

    start = call(f"{api}/video_reels?upload_phase=start&access_token={tok}", b"")
    vid = start["video_id"]
    up = call(f"https://rupload.facebook.com/video-upload/v23.0/{vid}",
              mp4.read_bytes(),
              {"Authorization": f"OAuth {tok}", "offset": "0",
               "file_size": str(size)})
    assert up.get("success", True)
    fin = call(f"{api}/video_reels", ("upload_phase=finish&video_state=PUBLISHED"
               f"&video_id={vid}&access_token={tok}&description="
               + urllib.parse.quote(desc)).encode())
    return {"fb": "published", "fb_reel_id": fin.get("post_id") or vid}


# ──────────────────────────────── tiktok ─────────────────────────────────────

def tiktok_video(mp4: Path, caption: str) -> dict:
    tok = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
    # 🧪 whole-process dry run (boss 2026-09-02): honest readiness report, no api
    if os.environ.get("MULTIPOST_DRYRUN") == "1":
        size = mp4.stat().st_size if mp4 and mp4.exists() else 0
        return {"tt": (f"render-only — would upload ~{size / 1e6:.1f} MB (SELF_ONLY law): {caption[:60]}…" if tok
                       else "⚠️ needs TIKTOK_ACCESS_TOKEN — onboarding still open (MULTIPOST.md Part 4); lane code intact")}
    if not tok:
        return {"tt": "skipped — TIKTOK_ACCESS_TOKEN not set"}
    privacy = os.environ.get("TIKTOK_PRIVACY", "SELF_ONLY")  # pre-approval law
    size = mp4.stat().st_size
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    init = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        data=json.dumps({
            "post_info": {"title": caption, "privacy_level": privacy,
                          "disable_duet": False, "disable_comment": False,
                          "disable_stitch": False},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": min(size, 10_000_000),
                            "total_chunk_count": 1},
        }).encode(), headers=hdr, method="POST"), timeout=60).read())
    err = init.get("error", {})
    if err.get("code", "ok") not in ("ok", None):
        return {"tt": f"api error: {err.get('code')} {err.get('message', '')[:80]}"}
    d = init["data"]
    req = urllib.request.Request(
        d["upload_url"], data=mp4.read_bytes(), method="PUT",
        headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                 "Content-Range": f"bytes 0-{size - 1}/{size}"})
    urllib.request.urlopen(req, timeout=300)
    mode = "DRAFT (boss publishes in-app)" if privacy == "SELF_ONLY" else "live"
    return {"tt": f"uploaded → {mode}", "tiktok_publish_id": d.get("publish_id")}


# ──────────────────────────────── the gate ───────────────────────────────────

def fanout(ep: int, meta: dict, genre_key: str, out: Path,
           yt_vid: str | None = None, yt_sid: str | None = None) -> dict:
    want = [p.strip().lower() for p in os.environ.get("MULTIPOST", "").split(",")
            if p.strip()]
    pack = build_postpack(out, ep, meta, genre_key, yt_vid, yt_sid)
    if not want or want == ["off"]:
        print("  🌐 multi-post: OFF (set MULTIPOST=fb,tt + creds to flip on; "
              "postpack manifest written)")
        return {"enabled": False, "postpack": pack.get("media", {})}

    results: dict = {"enabled": True}
    mp4 = pack["media"].get("short") or pack["media"].get("long")
    if not mp4:
        return {"enabled": True, "error": "no rendered mp4 found"}
    mp4 = Path(mp4)
    for plat in want:
        try:
            if plat == "fb":
                results.update(fb_reel(mp4, pack["captions"]["fb"]))
            elif plat == "tt":
                results.update(tiktok_video(mp4, pack["captions"]["tt"]))
            else:
                results[plat] = "skipped — unknown platform"
        except Exception as e:                      # never crash a release
            results[plat] = f"failed softly: {e}"
    print(f"  🌐 multi-post: {json.dumps({k: v for k, v in results.items() if k != 'enabled'})}")
    return results

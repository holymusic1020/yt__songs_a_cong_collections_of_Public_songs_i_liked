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
  ig — Instagram Reels (container model: /media?media_type=REELS → poll →
       /media_publish). Added 2026-09-13 on boss request "why not we also
       connect our Instagram". Reuses the FB Page token — NO new env var, so
       this lane ships through the upgrades/ zip (Lane A) with zero workflow
       edits. Requires the page token to carry instagram_basic +
       instagram_content_publish, and the IG account to be PROFESSIONAL and
       linked to that Page.

Each call is stdlib-only (urllib), $0. Env creds (boss adds them, then says
"cng" to flip on):  FB_PAGE_ID + FB_PAGE_TOKEN · TIKTOK_ACCESS_TOKEN
(+ optional TIKTOK_PRIVACY=public_to_everyone once the app is approved).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_GRAPH_V = "v23.0"          # same Graph version the fb lane already rides

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
        # 📸 IG law (2026-09-13): links in Instagram captions are NOT clickable,
        # so a youtu.be link is pure noise (and looks spammy to the algorithm).
        # The link lives in the IG bio instead. Only the first ~125 chars show
        # before the "…more" fold → title first, hashtags last. Cap 2200 (IG max).
        "ig": f"{title} 🌙\n{tags}\n🎧 original ai-assisted music · link in bio"[:2200],
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
                      (f"ep{ep:03d}.mp4", "long"),
                      (f"ep{ep:03d}.png", "cover")):   # 📸 IG photo lane (2026-09-13)
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
    pid, tok = os.environ.get("FB_PAGE_ID", "").strip(), os.environ.get("FB_PAGE_TOKEN", "").strip()
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


def fb_video(mp4: Path, caption: str) -> dict:
    """Boss-slot full video → Page VIDEO post (2026-09-02 boss: "fb only reel?
    fb shorts too" → the song drops everywhere: reel=short + video=full)."""
    pid, tok = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    if os.environ.get("MULTIPOST_DRYRUN") == "1":   # zero-api parity with fb_reel
        size = mp4.stat().st_size if mp4 and mp4.exists() else 0
        return {"fb_video": f"render-only — would post video ~{size / 1e6:.1f} MB"}
    if not (pid and tok):
        return {"fb_video": "skipped — FB_PAGE_ID/FB_PAGE_TOKEN not set"}
    cap = caption if len(caption) <= 245 else caption[:242].rstrip() + "…"
    boundary = "-_-_-_-_-_-_-_-nyxvidboundary-_-_-_-_-_-_-_-"
    data = open(mp4, "rb").read()
    parts: list[bytes] = []
    def field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    field("description", cap)
    field("access_token", tok)
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"{mp4.name}\"\r\nContent-Type: video/mp4\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    url = f"https://graph.facebook.com/v23.0/{pid}/videos"
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=900).read())
    except Exception as e:
        body_txt = e.read().decode()[:300] if hasattr(e, "read") else str(e)
        raise RuntimeError(f"fb video post rejected: {body_txt}")
    return {"fb_video": "published", "fb_video_id": r.get("id")}


# ──────────────────────────────── tiktok ─────────────────────────────────────

def tiktok_video(mp4: Path, caption: str) -> dict:
    tok = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
    # 🧪 whole-process dry run (boss 2026-09-02): honest readiness report, no api
    if os.environ.get("MULTIPOST_DRYRUN") == "1":
        size = mp4.stat().st_size if mp4 and mp4.exists() else 0
        return {"tt": (f"render-only — would upload ~{size / 1e6:.1f} MB (SELF_ONLY law): {caption[:60]}…" if tok
                       else "⚠️ needs TIKTOK_ACCESS_TOKEN — onboarding still open (MULTIPOST.md Part 4); lane code intact")}
    if not tok:
        return {"tt": "skipped — TIKTOK_ACCESS_TOKEN not set"}
    # 🔁 token longevity machine (2026 law): tt access tokens live 24h only.
    # With GITHUB_TOKEN + the refresh chain we rotate BEFORE every use and write
    # the fresh pair back into repo secrets — boss never re-auths, ever.
    ref = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
    ck, cs = os.environ.get("TIKTOK_CLIENT_KEY", "").strip(), os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if ref and ck and cs:
        try:
            body = urllib.parse.urlencode({
                "client_key": ck, "client_secret": cs, "grant_type": "refresh_token",
                "refresh_token": ref}).encode()
            r = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://open.tiktokapis.com/v2/oauth/token/", data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST"), timeout=60).read())
            if r.get("access_token"):
                tok = r["access_token"]
                ght = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
                repo = os.environ.get("GITHUB_REPOSITORY", "")
                if ght and repo:    # persist the rolling pair (refresh lives 365d, we're day-rollers)
                    # 2026-09-03 TRUTH-FIX: was a HEAD-stub that wrote NOTHING → first live
                    # run consumed the repo's only refresh token and stranded day-2 cron.
                    import subprocess
                    for name, val in (("TIKTOK_ACCESS_TOKEN", tok), ("TIKTOK_REFRESH_TOKEN", r.get("refresh_token", ref))):
                        try:
                            subprocess.run(["gh", "secret", "set", name, "-R", repo, "--body", val],
                                           check=True, capture_output=True, timeout=30,
                                           env={**os.environ, "GH_TOKEN": ght})
                            print(f"  🔁 {name} rotated+persisted (boss never re-auths, ever)")
                        except Exception as _se:
                            print(f"  (secret persist skipped for {name}: {_se} — posting continues)")
        except Exception as e:
            print(f"  (tt refresh skipped: {e} — using stale token, may soft-fail)")
    privacy = (os.environ.get("TIKTOK_PRIVACY") or "SELF_ONLY").strip()  # pre-approval law
    size = mp4.stat().st_size
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    # 2026 direct-post truth: TT disputes un-declared auto-publishing — the
    # consent flags are mandatory on PUBLIC posts; off while drafts (SELF_ONLY).
    post_info = {"title": caption[:150], "privacy_level": privacy,
                 "disable_duet": False, "disable_comment": False,
                 "disable_stitch": False}
    if privacy != "SELF_ONLY":
        post_info["content_preview_confirmed"] = True
        post_info["express_consent_given"] = True
    try:
        init = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            data=json.dumps({
                "post_info": post_info,
                "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                "chunk_size": min(size, 10_000_000),
                                "total_chunk_count": 1},
            }).encode(), headers=hdr, method="POST"), timeout=60).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]     # TikTok's own diagnosis — never swallowed again
        print(f"  ⚠️ tt init rejected {e.code}: {body}")
        return {"tt": f"rejected {e.code}: {body[:160]}"}
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



# ───────────────────────────── instagram (2026-09-13) ────────────────────────
#
# Container model, straight from Meta's Instagram Platform docs:
#   POST /{ig-user-id}/media?media_type=REELS&video_url=<PUBLIC url>&caption=…
#   GET  /{container-id}?fields=status_code,progress      → poll to FINISHED
#   POST /{ig-user-id}/media_publish?creation_id={container-id}
# Meta FETCHES the video itself → it must sit at a public URL. We reuse the
# 'bossdrop-stage' GitHub release the engine already vaults renders into, so
# there is no new host, no new secret and no new env var.
#
# Hard limits honoured below: Reels 3–90 s · images JPEG only · containers die
# after 24 h · ~25 API calls/account/hour · 100 publishes/24 h (we do 1–2/day).
# Access level: Standard (app in Development mode) is enough because the boss
# OWNS the account and is the app admin — no Meta App Review needed. Same trick
# the fb lane has been riding since 2026-09-02.

_IG_STATE = "state/ig_account.json"


def _gh_json(url: str, tok: str, data: bytes | None = None,
             headers: dict | None = None, method: str | None = None):
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h,
                                 method=method or ("POST" if data is not None else "GET"))
    return json.loads(urllib.request.urlopen(req, timeout=300).read())


def _vault_public_url(path: Path) -> str:
    """Park one file in the public 'bossdrop-stage' release → return its URL.

    Same vault main._vault_release_asset uses (self-cleaning by name, replaced in
    place). Creates the release on first ever use so a fresh repo still works.
    Raises on any problem — the caller soft-fails, a release never dies here.
    """
    tok = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not (tok and repo):
        raise RuntimeError("no GH_TOKEN/GITHUB_REPOSITORY — cannot host the file "
                           "Meta must fetch (ig lane needs the vault)")
    api = f"https://api.github.com/repos/{repo}/releases/tags/bossdrop-stage"
    try:
        rel = _gh_json(api, tok)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        rel = _gh_json(f"https://api.github.com/repos/{repo}/releases", tok,
                       data=json.dumps({"tag_name": "bossdrop-stage",
                                        "name": "bossdrop-stage (media vault)",
                                        "draft": False, "prerelease": True}).encode(),
                       headers={"Content-Type": "application/json"})
        print("  🧲 ig vault: created the bossdrop-stage release")
    for a in rel.get("assets", []):                 # self-clean by name
        if a.get("name") == path.name:
            _gh_json(f"https://api.github.com/repos/{repo}/releases/assets/{a['id']}",
                     tok, method="DELETE")
    ctype = ("image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg")
             else "video/mp4" if path.suffix.lower() == ".mp4" else "application/octet-stream")
    # 🔁 retry law (2026-09-14): EP.039's vault step died on a transient runner-side
    # SSL EOF. Meta FETCHES the video from this URL, so a flaky upload = no ig post.
    blob = path.read_bytes()
    last = ""
    for attempt in range(1, 4):
        try:
            up = _gh_json(f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets"
                          f"?name={urllib.parse.quote(path.name)}", tok, data=blob,
                          headers={"Content-Type": ctype})
            url = up.get("browser_download_url", "")
            if url:
                return url
            last = f"no browser_download_url: {str(up)[:120]}"
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:140]}"
        if attempt < 3:
            time.sleep(4 * attempt)
    raise RuntimeError(f"vault upload failed 3× for {path.name} — {last}")


def _probe_seconds(path: Path):
    """ffprobe duration in seconds, or None when unknowable (never a hard fail)."""
    import shutil
    import subprocess
    ff = shutil.which("ffprobe")
    if not ff:
        return None
    try:
        r = subprocess.run([ff, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(path)],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip() or 0) or None
    except Exception:
        return None


def ig_discover(force: bool = False, net: bool = True) -> dict:
    """Find the Instagram professional account linked to the Facebook Page.

    GET /{page-id}?fields=instagram_business_account{id,username} with the SAME
    page token the fb lane already uses → no new credential, no new env var.
    Result cached in state/ig_account.json (committed by the state step).
    Fallback: env IG_USER_ID if the boss ever wants to pin it by hand.
    """
    pinned = (os.environ.get("IG_USER_ID") or "").strip()
    if pinned:
        return {"id": pinned, "username": "(pinned via IG_USER_ID)", "pinned": True}
    cache = Path(_IG_STATE)
    if not force and cache.exists():
        try:
            c = json.loads(cache.read_text())
            if c.get("id"):
                return c
        except Exception:
            pass
    if not net:
        # 🧪 dry-run law: ZERO api calls. No cache + no pinned id = honest "unknown".
        return {"error": "no cached state/ig_account.json — the live run will discover it "
                         "(dry-run makes no API calls by law)"}
    pid = (os.environ.get("FB_PAGE_ID") or "").strip()
    tok = (os.environ.get("FB_PAGE_TOKEN") or "").strip()
    if not (pid and tok):
        return {"error": "FB_PAGE_ID/FB_PAGE_TOKEN not set — cannot discover the IG account"}
    url = (f"https://graph.facebook.com/{_GRAPH_V}/{pid}"
           f"?fields=instagram_business_account%7Bid%2Cusername%7D&access_token={tok}")
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=60).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        hint = ""
        if "instagram_basic" in body or "(#10)" in body or "permissions" in body.lower():
            hint = (" — the page token lacks instagram_basic/instagram_content_publish; "
                    "re-mint it with those scopes (see USER_NEEDS/IG_LINK_GUIDE.md)")
        return {"error": f"graph rejected the lookup {e.code}: {body[:180]}{hint}"}
    except Exception as e:
        return {"error": f"ig lookup failed: {e}"}
    iga = (d or {}).get("instagram_business_account") or {}
    if not iga.get("id"):
        return {"error": "no Instagram account is linked to this Page yet — IG app → "
                         "Settings → Account type and tools → switch to professional → "
                         "link it to the Nix Speech Page"}
    out = {"id": str(iga["id"]), "username": iga.get("username", ""),
           "page_id": pid, "found_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, indent=2))
    except OSError:
        pass
    return out


def _ig_container(igid: str, tok: str, fields: dict) -> str:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(f"https://graph.facebook.com/{_GRAPH_V}/{igid}/media",
                                 data=data, method="POST")
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"ig container rejected {e.code}: {body}")
    if not r.get("id"):
        raise RuntimeError(f"ig container returned no id: {r}")
    return r["id"]


def _ig_wait(cid: str, tok: str, timeout_s: int = 420, every: int = 6) -> dict:
    """Poll a container until FINISHED/ERROR/timeout. Meta transcodes server-side."""
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        try:
            last = json.loads(urllib.request.urlopen(
                f"https://graph.facebook.com/{_GRAPH_V}/{cid}"
                f"?fields=status_code,progress,status&access_token={tok}", timeout=60).read())
        except Exception as e:
            last = {"status_code": "POLL_ERROR", "status": str(e)[:160]}
        code = (last.get("status_code") or "").upper()
        if code == "FINISHED":
            return last
        if code in ("ERROR", "FAILED"):
            raise RuntimeError(f"ig container {code}: {json.dumps(last)[:240]}")
        time.sleep(every)
    raise RuntimeError(f"ig container still {last.get('status_code', '?')} after {timeout_s}s "
                       f"(progress {last.get('progress')})")


def _ig_publish(igid: str, tok: str, cid: str) -> str:
    data = urllib.parse.urlencode({"creation_id": cid, "access_token": tok}).encode()
    req = urllib.request.Request(f"https://graph.facebook.com/{_GRAPH_V}/{igid}/media_publish",
                                 data=data, method="POST")
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"ig media_publish rejected {e.code}: {body}")
    mid = r.get("id")
    if not mid:
        raise RuntimeError(f"ig media_publish returned no id: {r}")
    return str(mid)


def _ig_ready(what: str) -> dict:
    """Shared credential/discovery gate for every ig_* lane."""
    tok = (os.environ.get("FB_PAGE_TOKEN") or "").strip()
    if not tok:
        return {"ig": f"skipped — FB_PAGE_TOKEN not set (the {what} lane rides the page token)"}
    acc = ig_discover()
    if acc.get("error"):
        return {"ig": f"skipped — {acc['error']}"}
    return {"_tok": tok, "_igid": acc["id"], "_user": acc.get("username", "")}


def ig_reel(mp4: Path, caption: str) -> dict:
    """Today's vertical short → Instagram Reel."""
    if os.environ.get("MULTIPOST_DRYRUN") == "1":          # zero-api parity with fb/tt
        size = mp4.stat().st_size if mp4 and Path(mp4).exists() else 0
        sec = _probe_seconds(mp4) if Path(mp4).exists() else None
        acc = ig_discover(net=False)          # 🧪 cached/pinned only — zero api calls
        who = acc.get("username") or acc.get("id") or "unknown until the live run"
        ok = "✓" if (sec is None or 3 <= sec <= 90) else f"✗ {sec:.0f}s outside 3–90s"
        return {"ig": (f"render-only — would post REEL ~{size / 1e6:.1f} MB to @{who} "
                       f"({sec:.1f}s {ok} )" if sec else
                       f"render-only — would post REEL ~{size / 1e6:.1f} MB to @{who} "
                       f"(duration unknown — ffprobe missing)")}
    g = _ig_ready("reel")
    if "ig" in g:
        return g
    tok, igid = g["_tok"], g["_igid"]
    sec = _probe_seconds(mp4)
    if sec is not None and not (3 <= sec <= 90):
        return {"ig": f"skipped — reel is {sec:.0f}s, Instagram Reels must be 3–90s "
                      f"(set MULTIPOST_IG_LONG=1 to post the long one as a feed VIDEO instead)"}
    url = _vault_public_url(Path(mp4))                     # Meta fetches it itself
    cap = (caption or "")[:2200]
    cid = _ig_container(igid, tok, {"media_type": "REELS", "video_url": url,
                                    "caption": cap, "share_to_feed": "true",
                                    "access_token": tok})
    _ig_wait(cid, tok)
    mid = _ig_publish(igid, tok, cid)
    print(f"  📸 ig reel published → https://www.instagram.com/reel/{mid}/")
    return {"ig": "published (reel)", "ig_media_id": mid, "ig_user": g.get("_user", ""),
            "ig_permalink": f"https://www.instagram.com/reel/{mid}/"}


def ig_feed_video(mp4: Path, caption: str) -> dict:
    """The long 16:9 video → Instagram feed VIDEO (opt-in: MULTIPOST_IG_LONG=1)."""
    if os.environ.get("MULTIPOST_DRYRUN") == "1":
        size = mp4.stat().st_size if mp4 and Path(mp4).exists() else 0
        return {"ig_video": f"render-only — would post feed VIDEO ~{size / 1e6:.1f} MB"}
    if os.environ.get("MULTIPOST_IG_LONG") != "1":
        return {"ig_video": "off — set MULTIPOST_IG_LONG=1 to also post the long video to IG"}
    g = _ig_ready("video")
    if "ig" in g:
        return {"ig_video": g["ig"]}
    url = _vault_public_url(Path(mp4))
    cid = _ig_container(g["_igid"], g["_tok"], {"media_type": "VIDEO", "video_url": url,
                                                "caption": (caption or "")[:2200],
                                                "access_token": g["_tok"]})
    _ig_wait(cid, g["_tok"], timeout_s=900, every=10)      # a 3-min 16:9 transcodes slower
    mid = _ig_publish(g["_igid"], g["_tok"], cid)
    print(f"  📸 ig feed video published → https://www.instagram.com/p/{mid}/")
    return {"ig_video": "published", "ig_video_id": mid,
            "ig_video_permalink": f"https://www.instagram.com/p/{mid}/"}


def ig_photo(png: Path, caption: str) -> dict:
    """Today's cover art → an IG image post. IG accepts JPEG only → we convert."""
    if os.environ.get("MULTIPOST_DRYRUN") == "1":
        size = png.stat().st_size if png and Path(png).exists() else 0
        return {"ig_photo": f"render-only — would post the cover art (~{size / 1e3:.0f} KB → JPEG 1080×1350)"}
    if os.environ.get("MULTIPOST_IG_PHOTO") == "0":
        return {"ig_photo": "off — MULTIPOST_IG_PHOTO=0"}
    g = _ig_ready("photo")
    if "ig" in g:
        return {"ig_photo": g["ig"]}
    try:
        from PIL import Image
    except Exception as e:
        return {"ig_photo": f"skipped — Pillow unavailable ({e})"}
    src = Path(png)
    if not src.exists():
        return {"ig_photo": "skipped — no cover art rendered for this episode"}
    jpg = src.with_suffix(".ig.jpg")
    try:
        im = Image.open(src).convert("RGB")
        w, h = im.size
        target = (1080, 1350)                              # 4:5 portrait = max feed real estate
        scale = max(target[0] / w, target[1] / h)
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        l = (im.width - target[0]) // 2
        t = (im.height - target[1]) // 2
        im.crop((l, t, l + target[0], t + target[1])).save(jpg, "JPEG", quality=92)
    except Exception as e:
        return {"ig_photo": f"skipped — jpeg conversion failed: {e}"}
    url = _vault_public_url(jpg)
    cid = _ig_container(g["_igid"], g["_tok"], {"image_url": url, "caption": (caption or "")[:2200],
                                                "access_token": g["_tok"]})
    _ig_wait(cid, g["_tok"], timeout_s=240)
    mid = _ig_publish(g["_igid"], g["_tok"], cid)
    print(f"  📸 ig photo published → https://www.instagram.com/p/{mid}/")
    return {"ig_photo": "published", "ig_photo_id": mid,
            "ig_photo_permalink": f"https://www.instagram.com/p/{mid}/"}


# ──────────────────────── 16:9 → 9:16 regulation fix (TT longs) ─────────────────
def _pillarbox_blur(src: Path, dst: Path) -> Path:
    """Boss (2026-09-04): 'full vid on tt too, blur upper-lower for regulation fix'.
    Landscape mastered-long gets a blurred enlarged clone of itself as the backdrop,
    sharp frame fit-width in front — TikTok-vertical without cropping a pixel."""
    import subprocess as _sp, shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("ffmpeg missing")
    W, H = 1080, 1920
    fc = (f"[0:v]split[a][b];"
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=30[bg];"
          f"[b]scale={W}:-2[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    _sp.run([ff, "-y", "-i", str(src), "-filter_complex", fc,
             "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",  # 48k-stereo social law
             str(dst)], check=True, capture_output=True)
    return dst

# ──────────────────────────────── the gate ───────────────────────────────────

def fanout(ep: int, meta: dict, genre_key: str, out: Path,
           yt_vid: str | None = None, yt_sid: str | None = None) -> dict:
    want = [p.strip().lower() for p in os.environ.get("MULTIPOST", "").split(",")
            if p.strip()]
    pack = build_postpack(out, ep, meta, genre_key, yt_vid, yt_sid)
    if not want or want == ["off"]:
        print("  🌐 multi-post: OFF (set MULTIPOST=fb,tt,ig + creds to flip on; "
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
                # boss (2026-09-02): "always both vids and short/reel huh?" →
                # video days ride the Page too: reel(short) + VIDEO(long)
                long_f = pack["media"].get("long")
                if long_f and Path(long_f).exists():
                    results.update(fb_video(Path(long_f), pack["captions"]["fb"]))
            elif plat == "tt":
                results.update(tiktok_video(mp4, pack["captions"]["tt"]))
                # boss 2026-09-04: full vid may ride TT too (blurred pillarbox). Default OFF —
                # flip repo var MULTIPOST_TT_LONG=1 (publish.yml env passes it through).
                if os.environ.get("MULTIPOST_TT_LONG") == "1" and pack["media"].get("long"):
                    long_p = Path(pack["media"]["long"])
                    if long_p.exists():
                        vert = _pillarbox_blur(long_p, Path(out) / f"ep{ep:03d}_tt_long.mp4")
                        results.update({("tt_long" if k == "tt" else f"tt_long_{k}"): v
                                        for k, v in tiktok_video(vert, pack["captions"]["tt"][:130] + " 🎬 full").items()})
            elif plat == "ig":
                # 2026-09-13 boss: "why not we also connect our Instagram" →
                # Reel(short) + cover-art photo by default; the long 16:9 rides
                # only when MULTIPOST_IG_LONG=1. All soft-fail, all dry-parity.
                results.update(ig_reel(mp4, pack["captions"]["ig"]))
                long_f = pack["media"].get("long")
                if long_f and Path(long_f).exists():
                    try:
                        results.update(ig_feed_video(Path(long_f), pack["captions"]["ig"]))
                    except Exception as _e:
                        results["ig_video"] = f"failed softly: {_e}"
                cover = pack["media"].get("cover")
                if cover and Path(cover).exists():
                    try:
                        results.update(ig_photo(Path(cover), pack["captions"]["ig"]))
                    except Exception as _e:
                        results["ig_photo"] = f"failed softly: {_e}"
            else:
                results[plat] = "skipped — unknown platform"
        except Exception as e:                      # never crash a release
            results[plat] = f"failed softly: {e}"
    print(f"  🌐 multi-post: {json.dumps({k: v for k, v in results.items() if k != 'enabled'})}")
    return results

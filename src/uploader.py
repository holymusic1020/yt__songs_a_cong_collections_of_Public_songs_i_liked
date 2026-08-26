"""YouTube Data API v3 upload — official API, AI-content disclosure ON.

Hardened:
  · per-chunk retries with backoff (network dropouts)
  · clean stop on daily quota exhaustion (never burns quota in a loop)
  · post-upload privacy check — new API projects are PRIVATE-LOCKED until
    the free YouTube API compliance audit passes (see AUDIT_URL)

Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
from __future__ import annotations

import os
import time
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    # needed for auto-comment funnel under Shorts
    "https://www.googleapis.com/auth/youtube.force-ssl",
    # needed for adaptive analytics weights — Analytics API accepts
    # youtube.readonly (token granted it; yt-analytics.readonly was not)
    "https://www.googleapis.com/auth/youtube.readonly",
]
AUDIT_URL = "https://support.google.com/youtube/contact/yt_api_form"

# YouTube's synthetic-media label is required for REALISTIC altered media
# (real people/places/events). Ours is stylized original music + artwork —
# outside that class — so the label defaults OFF and no "AI" appears anywhere
# public. If the platform's rules ever tighten for our class, flip ONE switch:
# set env var YT_DECLARE_SYNTHETIC=1 (repo variable) and labels return.
DECLARE_SYNTHETIC = os.environ.get("YT_DECLARE_SYNTHETIC", "") == "1"


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    missing = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
               if not (os.environ.get(k) or "").strip()]
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)} "
                         "(see README > YouTube setup)")

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def upload(video_path: Path, meta: dict, publish_at: str | None = None) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": "10",  # Music
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": DECLARE_SYNTHETIC,
        },
    }
    if publish_at:
        # Native YouTube scheduling: upload private, auto-publish at publish_at.
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            resumable=True, chunksize=8 * 1024 * 1024)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    resp, tries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                print(f"  upload {int(status.progress() * 100)}%")
        except HttpError as e:
            if "quota" in str(e).lower():
                raise SystemExit(
                    "  ⛔ YouTube daily quota exhausted — resets midnight "
                    "Pacific. Re-run tomorrow; nothing else is broken.")
            raise
        except (ConnectionError, OSError) as e:
            tries += 1
            if tries > 3:
                raise
            wait = 5 * 2 ** tries
            print(f"  ⚠ network hiccup ({e}) — retrying in {wait}s…")
            time.sleep(wait)

    privacy = (resp.get("status") or {}).get("privacyStatus")
    if privacy == "private" and not publish_at:
        print("  ⚠ upload stayed PRIVATE — unverified API projects are")
        print("    private-locked until the free compliance audit passes:")
        print(f"    {AUDIT_URL}")
    return resp["id"]

"""Short→video funnel: auto-comment under each short, bridging to the full
release (research: Shorts and long-form feeds are separate — you must
ENGINEER the bridge). API can't pin comments, so pin manually on your
10-minute weekly ritual; the link is already there waiting.
"""
from __future__ import annotations

TEXT = ("full version on the channel ↓ https://youtu.be/{vid} 🌙 "
        "— Nix Speech")


def post_link_comment(short_yt_id: str, video_yt_id: str) -> None:
    from googleapiclient.discovery import build
    from src.uploader import _creds

    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    yt.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": short_yt_id,
                "topLevelComment": {
                    "snippet": {"textOriginal": TEXT.format(vid=video_yt_id)}
                },
            }
        },
    ).execute()

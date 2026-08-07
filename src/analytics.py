"""Adaptive brain — reads the channel's own report card, steers future genres.

Runs BEFORE composing: pulls per-video stats via YouTube Analytics API
(works with the same broad `youtube`/readonly scopes already authorized),
computes per-genre average views, and returns SOFT weights
(sqrt-scaled, min 15% floor) so winners get favored without genres dying —
exploration never stops. Any failure -> caller keeps flat rotation.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


def _creds():
    from src.uploader import _creds as base_creds
    return base_creds()


def refresh_weights(state: dict) -> dict | None:
    """Return {'drift_phonk': .35, ...} or None. Never raises hard."""
    try:
        from googleapiclient.discovery import build
        yt = build("youtubeAnalytics", "v2", credentials=_creds(),
                   cache_discovery=False)
        today = datetime.now(timezone.utc).date().isoformat()
        resp = yt.reports().query(
            ids="channel==MINE",
            startDate="2006-01-01",
            endDate=today,
            dimensions="video",
            metrics="views,averageViewPercentage",
            maxResults=50,
            sort="-views",
        ).execute()
        rows = resp.get("rows") or []
        if len(rows) < 3:                      # not enough data to learn
            return None

        genre_of = {h.get("youtube_id"): h.get("genre")
                    for h in state.get("history", [])}
        scores: dict[str, list[float]] = {}
        for vid, views, _avp in rows:
            g = genre_of.get(vid)
            if g:
                scores.setdefault(g, []).append(float(views))
        if len(scores) < 2:
            return None

        means = {g: (sum(v) / len(v)) for g, v in scores.items()}
        # sqrt scaling = gentle preference, min 0.15 floor = no genre dies
        raw = {g: max(0.15, math.sqrt(m)) for g, m in means.items()}
        total = sum(raw.values())
        return {g: w / total for g, w in raw.items()}
    except Exception as e:
        print(f"  (analytics: {e} — flat rotation)")
        return None

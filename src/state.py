"""State: remembers episode counter + publish history across runs."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parents[1] / "state" / "state.json"
BDT = timezone(timedelta(hours=6))      # the boss's clock (Dhaka) — the day a
                                       # release "belongs to" is his, not UTC's


def load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"episode": 0, "history": []}


def save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def record(state: dict, entry: dict) -> None:
    entry = dict(entry)
    entry["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state.setdefault("history", []).append(entry)   # harden: old state.json
                                                    # without history → no crash


def real_release_today(path=None):
    """The real (non-dry) release already shipped TODAY on the boss's clock, else None.

    ONE-RELEASE-PER-DAY law (2026-09-19). GitHub's scheduler routinely fires the daily
    cron 3–6 h late (measured on the last 10 runs: 09:23 UTC cron → 12:55–15:55 UTC
    actual). A manual publish earlier in the day therefore left the evening cron free
    to ship a SECOND episode: two YouTube uploads, two TikToks, two IG reels on one
    day — exactly the spam signal the concurrency guard exists to prevent, just
    arriving hours apart instead of seconds. The cron now checks this first and
    demotes itself to a dry-run when the day already has its song.
    Manual runs are never affected: the Run-workflow button is the boss's own hand.
    """
    q = Path(path) if path else STATE_PATH
    try:
        hist = json.loads(q.read_text()).get("history", []) if q.exists() else []
    except Exception:
        return None
    # ⏱ v23.7 (2026-10-09): measure the GAP, not the calendar day.
    # GitHub fires this cron 3-6 h late, so a release that finished after
    # 18:00 UTC lands on the NEXT BDT date — and the calendar test then read
    # "already released today" on the following evening and demoted a perfectly
    # good slot to a dry run. Measured on live receipts: EP.054 shipped
    # 09-29 00:37 BDT → the 09-29 22:30 cron demoted itself; EP.060 shipped
    # 10-06 01:44 BDT → 10-06 22:41 demoted again. Two releases a fortnight,
    # lost to a timezone boundary, with the episode number re-used the next day.
    # A real double-ship is ~hours apart; a normal nightly pair is 19-22 h
    # apart, so 17 h is the honest line. Dial: repo variable RELEASE_GAP_H.
    try:
        gap_h = float(os.environ.get("RELEASE_GAP_H", "") or 17.0)
    except ValueError:
        gap_h = 17.0
    now = datetime.now(BDT)
    for e in reversed(hist if isinstance(hist, list) else []):
        if not isinstance(e, dict) or str(e.get("mode", "")).strip() == "dry_run":
            continue
        stamp = e.get("at") or e.get("published_at") or e.get("short_publish_at")
        if not stamp or not isinstance(stamp, str):
            continue
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(BDT)
        except Exception:
            continue
        age_h = (now - when).total_seconds() / 3600.0
        if age_h < 0 or age_h < gap_h:      # future-dated (scheduled) also counts
            return e
    return None

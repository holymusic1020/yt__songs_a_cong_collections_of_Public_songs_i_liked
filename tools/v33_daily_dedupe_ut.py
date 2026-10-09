"""UT-33 · ONE release per day: the evening cron must not ship a second episode.

Why: GitHub's scheduler fires the daily cron 3–6 h late (measured over the last 10
runs). On 2026-09-19 a real publish went out at 12:29 BDT by hand and the 16:00 BDT
cron was still armed to ship EP.047 in the evening → two YouTube uploads, two TikToks,
two IG reels on one day. `state.real_release_today()` is the guard the cron consults.
"""
import json, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import state

BDT = timezone(timedelta(hours=6))
now_bdt = datetime.now(BDT)
today = now_bdt.astimezone(timezone.utc).replace(tzinfo=timezone.utc)
yday = today - timedelta(days=1)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S+00:00")
TMP = Path("/tmp/ut33_state.json")


def run(history):
    TMP.write_text(json.dumps({"episode": 9, "history": history}))
    return state.real_release_today(TMP)


print("── 1. a real publish today (BDT) → the guard sees it")
e = run([{"episode": 46, "kind": "full", "at": iso(today)}])
assert e and e["episode"] == 46, e
print(f"   ✅ EP.{e['episode']} detected → cron will park")

print("── 2. only dry runs today → no guard, cron publishes normally")
assert run([{"episode": 47, "mode": "dry_run", "date": now_bdt.strftime("%Y-%m-%d"),
             "kind": "short"}]) is None
print("   ✅ dry runs never count as the day's release")

print("── 3. yesterday's release → today is still free")
assert run([{"episode": 45, "kind": "short", "at": iso(yday)}]) is None
print("   ✅ a new BDT day re-arms the engine")

print("── 4. v23.7: the guard measures the GAP, not the BDT calendar day")
# The old day-boundary rule STEAL a release: EP.054 shipped 09-28 18:37Z
# (= 09-29 00:37 BDT) and the 09-29 16:30Z cron read "already released today"
# and parked; same on 10-06 with EP.060 (01:44 BDT → 22:41 cron). GitHub fires
# this cron 3-6 h late, so "same BDT day" and "same release cycle" are not the
# same thing. The law is now: a real release inside RELEASE_GAP_H (17 h default)
# owns the slot; anything older re-arms the engine.
from datetime import timedelta as _td
got_old = run([{"episode": 60, "kind": "short",
                "at": (now_bdt - _td(hours=21)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")}])
assert got_old is None, ("a 21 h-old release must NOT steal tonight's slot", got_old)
got_recent = run([{"episode": 61, "kind": "short",
                   "at": (now_bdt - _td(hours=3)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")}])
assert got_recent and got_recent["episode"] == 61, ("3 h apart IS a double-ship", got_recent)
got_future = run([{"episode": 62, "kind": "full", "short_publish_at":
                   (now_bdt + _td(hours=2)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")}])
assert got_future and got_future["episode"] == 62, "a scheduled publish ahead also owns the slot"
print("   ✅ 21 h → free · 3 h → parked · future-dated → parked")

print("── 5. junk state never crashes the run")
TMP.write_text("{not json")
assert state.real_release_today(TMP) is None
assert state.real_release_today(Path("/tmp/ut33_missing.json")) is None
print("   ✅ corrupt / missing state → None (cron proceeds as normal)")

print("── 6. the cron branch actually consults it")
wf = (ROOT / ".github/workflows/publish.yml").read_text()
assert "real_release_today" in wf, "publish.yml no longer calls the guard"
line = [l for l in wf.splitlines() if "real_release_today" in l][0]
assert line.lstrip().startswith("elif"), "the guard must be an elif in the schedule branch"
print("   ✅ publish.yml schedule branch: elif → --dry-run")

print("\nUT-33 PASS · one release per day, on the boss's clock")

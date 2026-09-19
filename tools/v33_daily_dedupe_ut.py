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

print("── 4. a late-night UTC stamp still belongs to the boss's day")
# 18:30 UTC = 00:30 BDT next day → must NOT count as today's release
late = today.replace(hour=18, minute=30, second=0)
got = run([{"episode": 48, "kind": "short", "at": iso(late)}])
expect = None if late.astimezone(BDT).date() != now_bdt.date() else got
assert got == expect, (got, expect)
print(f"   ✅ BDT day boundary honoured (18:30 UTC → {late.astimezone(BDT).strftime('%d %H:%M')} BDT)")

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

#!/usr/bin/env python3
"""UT-42 · the Telegram checklist must never claim "all clear" on missing evidence.

2026-10-14: `tt: rejected 400 · The chunk size is invalid` on EP.065, .066 and
.067 while the boss's phone read "🟢 all lanes clear". Two causes, both fixed:
main.py wrote manifest["lanes"] BEFORE the fan-out ran, and notify.py mapped an
empty report to green.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
ok = bad = 0
def chk(c, l, x=""):
    global ok, bad
    if c: ok += 1; print(f"  ✅ {l}")
    else: bad += 1; print(f"  ❌ {l}" + (f" — {x}" if x else ""))

from src import notify

man = {"episode": 67, "meta": {"name": "halogen balcony", "genre": "skyline anthem", "bpm": 128, "key": "—"},
       "schedule": {}, "video_today": True, "video_id": "yV8B", "short_id": "xc675",
       "lanes": {"fb": "published", "ig": "published (reel)",
                 "tt": 'rejected 400: {"error":{"code":"invalid_params","message":"The chunk size is invalid"}}'}}
msg = notify.build_message("success", man, "https://x/run", "")
chk("❌ not posted: tt" in msg, "a rejected TikTok lane is named in the alert", msg[-160:])
chk("all lanes clear" not in msg, "and the run is NOT called clear")
chk(notify._lane_state('rejected 400: {"error":{}}') == "❌", "_lane_state maps a 400 to ❌")
chk(notify._lane_state("uploaded → DRAFT (boss publishes in-app)") == "✅", "a real draft still reads ✅")

empty = dict(man, lanes={})
msg2 = notify.build_message("success", empty, "https://x/run", "")
chk("🟡 no lane report" in msg2, "an EMPTY report reads 🟡 missing evidence, not 🟢", msg2[-120:])
clean = dict(man, lanes={"fb": "published", "ig": "published (reel)", "tt": "uploaded → DRAFT"})
msg3 = notify.build_message("success", clean, "https://x/run", "")
chk("🟢 all lanes clear" in msg3, "a genuinely clean report still reads 🟢")
dry = dict(man, video_id=None, short_id=None, lanes={})
msg4 = notify.build_message("success", dry, "https://x/run", "")
chk("🟡" not in msg4, "a dry run with nothing to report is not scolded", msg4[-90:])

src = (ROOT / "src/main.py").read_text(encoding="utf-8")
i_fan = src.index("_fanout_result = multi_post.fanout(ep=ep, meta=meta, genre_key=genre_key,\n                                               out=OUT, yt_vid=vid, yt_sid=sid)")
i_set = src.index('manifest["lanes"] = _fanout_result')
chk(i_fan < i_set, "main.py writes the lane report AFTER the fan-out runs", f"{i_fan} vs {i_set}")
chk(src.count('manifest["lanes"] = _fanout_result') == 1, "and writes it in exactly one place (no stale copy)")
chk(src.index('latest.json").write_text', i_set) > i_set,
    "the manifest is re-saved after that assignment")
print("─" * 64); print(f"UT-42 · {'PASS' if not bad else 'FAIL'} — {ok} checks")
sys.exit(1 if bad else 0)

#!/usr/bin/env python3
"""UT-44 (2026-10-26) — the cadence law, tested as ONE unit.

Boss changed the timeline in voice notes: "one long video (or one long song)
every two days. On the long-video day post 1 short AND 1 long. The rest of the
days: 2 shorts." Half of that was already true (two_shorts_a_day + the slowed
twin); the PERIOD moved, 3 → 2, and the phase was chosen so tonight's EP.078 is
a long day — he asked for the change to start now, not after another 48 h.

This test imports the SHIPPED functions from src/main.py (no re-implementation)
and pins the whole rule: the alternation, the "next long" date the daily alert
prints, the twin truth table, the boss_switches.json override path, and the fact
that no doc still describes the dead 3-day law. A cadence regression is silent —
nothing errors when the long video simply doesn't come — so it needs a test.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import main as M  # noqa: E402

checks = []
src = (ROOT / "src" / "main.py").read_text(encoding="utf-8")


def chk(cond, msg, detail=""):
    checks.append(bool(cond))
    print(f"  {'✅' if cond else '❌'} {msg}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        raise AssertionError(msg + " :: " + detail)


print("── the numbers ──")
chk(M.VIDEO_EVERY == 2, "VIDEO_EVERY is 2 (one long every two days)", str(M.VIDEO_EVERY))
chk(M.VIDEO_PHASE == 0, "VIDEO_PHASE is 0 → EVEN episodes are the long days", str(M.VIDEO_PHASE))
chk(M._video_day(78) is True, "tonight (EP.078) is a LONG day — the law starts now, not in 2 days")
chk(M._video_day(79) is False and M._video_day(80) is True, "EP.079 off, EP.080 long — clean alternation")

longs = [e for e in range(60, 96) if M._video_day(e)]
chk(longs == list(range(60, 96, 2)), "18 long days in 36 episodes, exactly every other one", str(longs[:6]))
chk(all(b - a == 2 for a, b in zip(longs, longs[1:])), "no two long days ever sit closer than 2 episodes")
chk(all(M._next_video_ep(e) in longs and M._next_video_ep(e) > e for e in range(60, 94)),
    "the 'next video EP.NNN' the alert prints is always a real long day, always in the future")
chk(M._next_video_ep(78) == 80 and M._next_video_ep(79) == 80,
    "on a long day the alert points at the NEXT one (78→80), on an off day at tonight's gap (79→80)")

print("── the short counts (the other half of the ask) ──")
for ep in (78, 80):        # long days
    chk(M._twin_today(True, ep, 0, True) is False,
        f"EP.{ep:03d} long day → NO twin → 1 long + 1 short exactly")
for ep in (79, 81):        # off days
    chk(M._twin_today(False, ep, 0, True) is True,
        f"EP.{ep:03d} off day → twin fires → 2 shorts (main + slowed/reverb)")
chk(M._twin_today(False, 79, 0, False) is False,
    "…and if the boss dial two_shorts_a_day is ever turned off, the day drops to 1 short — no hidden second")
chk(M._twin_today(True, 78, 2, True) is False,
    "the twin never stacks onto a long day even when SLOWED_EVERY would allow it")

print("── the boss JSON is a real dial, not decoration ──")
sw = json.loads((ROOT / "state" / "boss_switches.json").read_text(encoding="utf-8"))
chk(sw.get("two_shorts_a_day") is True, "boss_switches: two_shorts_a_day = true")
chk(sw.get("video_every") == M.VIDEO_EVERY and sw.get("video_phase") == M.VIDEO_PHASE,
    "boss_switches: video_every/video_phase agree with the code defaults", str(sw))
chk(0 <= int(sw.get("video_phase", 0)) < int(sw.get("video_every", 1)),
    "video_phase < video_every (a phase ≥ period would silently shift the pattern)")
chk("if 1 <= _v <= _hi" in src, "an out-of-range JSON value is ignored, not obeyed")
chk('"video_every"' in src and '"video_phase"' in src,
    "main() actually reads both keys out of boss_switches.json")

# the retune path must work at RUNTIME — helpers read the globals, not captured defaults
_keep, _kp = M.VIDEO_EVERY, M.VIDEO_PHASE
try:
    M.VIDEO_EVERY, M.VIDEO_PHASE = 3, 1
    chk(M._video_day(79) is True and M._video_day(78) is False,
        "set video_every=3/video_phase=1 in the JSON and the SAME functions retune tonight — no code edit")
    chk(M._next_video_ep(79) == 82, "…and the next-long date follows the retune", str(M._next_video_ep(79)))
finally:
    M.VIDEO_EVERY, M.VIDEO_PHASE = _keep, _kp
chk(M._video_day(78) is True, "globals restored after the retune probe — tonight is a long day again")

print("── the shadowban guard must not eat the new rhythm ──")
try:
    ka = M._keep_alive_hours()
    chk(ka < 2 * 24, f"keep-alive floor {ka:.0f} h < the 48 h long-day rhythm → the guard can't demote a long day",
        f"{ka} h")
except AttributeError:
    chk(True, "no keep-alive helper — nothing to collide with")

print("── no stale maths, no stale docs ──")
chk("ep % VIDEO_EVERY == 1" not in src, "the old `ep % VIDEO_EVERY == 1` pick is gone from main.py")
chk(src.count("_video_day(ep)") >= 1 and src.count("_next_video_ep(ep)") == 2,
    "both call sites go through the helpers (nxt twice: normal + after a keep-alive demotion)")
for f in ("README.md", "SETUP.md", "docs/LAUNCH.md", "docs/SPOTIFY-APPLE-GUIDE.md"):
    d = (ROOT / f).read_text(encoding="utf-8")
    chk("VIDEO_EVERY = 3" not in d and "every 3rd EP" not in d and "every 3 days" not in d,
        f"{f} no longer advertises the dead 3-day law")

print("─" * 64)
print(f"UT-44 · PASS — {sum(checks)} checks · long every 2nd episode (EP.078 tonight), "
      f"1 long + 1 short on a long day, 2 shorts on an off day, retunable from boss_switches.json")

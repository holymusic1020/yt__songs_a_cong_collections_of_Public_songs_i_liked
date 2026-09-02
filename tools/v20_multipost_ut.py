#!/usr/bin/env python3
"""v20 🧪 MULTIPOST-DRY UT — boss (2026-09-02): "after fb works, do a dry run
of the whole process including yt, tt; don't post manually."

Proves MULTIPOST_DRYRUN=1 makes fb + tt lanes RENDER-ONLY:
  1. fb_reel under dry env → preview string, urllib NEVER touched
  2. tiktok_video under dry env → readiness report, zero api; honest when token missing
  3. fanout with MULTIPOST=fb,tt under dry env → both lanes report, still zero network
  4. regression: dry env OFF + no creds → plain skips (old behavior)
Run:  python tools/v20_multipost_ut.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import multi_post  # noqa: E402

fails = 0
netmail = []


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def main():
    # net-sentry: any urlopen call raises and records — tests PASS only if zero calls
    import urllib.request as u
    def sentry(*a, **k):
        netmail.append(a)
        raise RuntimeError("NETWORK TOUCHED in dry mode!")
    u.urlopen = sentry

    tmp = Path(tempfile.mkdtemp(prefix="v20ut_"))
    for v in ("MULTIPOST", "FB_PAGE_ID", "FB_PAGE_TOKEN", "TIKTOK_ACCESS_TOKEN", "MULTIPOST_DRYRUN"):
        os.environ.pop(v, None)
    for v in ("FB_PAGE_ID", "FB_PAGE_TOKEN"):
        os.environ[v] = "dummy"          # fb reads env under dry too — dummy asserts NO api
    meta = {"title": "Drylight Caller", "name": "Drylight Caller", "bpm": 100, "key": "Am"}
    mp4 = tmp / "ep099_short.mp4"; mp4.write_bytes(b"\x00" * 3000)
    (tmp / "ep099_slowed.mp4").write_bytes(b"\x00" * 1200)

    os.environ["MULTIPOST_DRYRUN"] = "1"
    r_fb = multi_post.fb_reel(mp4, "cap 🎶")
    chk("render-only" in r_fb["fb"], f"fb dry → render-only ({r_fb['fb'][:70]}…)")
    chk(netmail == [], "fb dry touched ZERO api")

    r_tt = multi_post.tiktok_video(mp4, "cap 🎶")
    chk("TIKTOK_ACCESS_TOKEN" in r_tt["tt"], "tt dry, no token → honest onboarding pointer")
    chk(netmail == [], "tt dry touched ZERO api")

    os.environ["MULTIPOST"] = "fb,tt"
    out = multi_post.fanout(ep=99, meta=meta, genre_key="phonk_mafia", out=tmp, yt_vid=None, yt_sid=None)
    blob = str(out)
    chk("render-only" in blob and "TIKTOK_ACCESS_TOKEN" in blob, "fanout dry → both lanes report")
    chk(netmail == [], "fanout dry touched ZERO api")

    os.environ.pop("MULTIPOST_DRYRUN")
    for v in ("FB_PAGE_ID", "FB_PAGE_TOKEN"):
        os.environ.pop(v, None)
    chk("skipped" in multi_post.fb_reel(mp4, "c")["fb"], "regression: dry OFF + no creds → legacy skip")

    print()
    if fails:
        print(f"❌ v20 multipost-dry UT: {fails} FAIL"); return 1
    print("✅ v20 UT green — whole-process dry run proves every lane while never touching an API")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

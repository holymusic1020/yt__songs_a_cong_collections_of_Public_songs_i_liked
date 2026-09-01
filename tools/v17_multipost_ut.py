#!/usr/bin/env python3
"""v17 🌐 MULTI-POST UT — boss 2026-08-31: 'post it on more sites where I
can earn… I will add creds myself, then tell u to cng.'

Iron laws under test:
  1. ZERO creds = pure no-op (YouTube pipeline untouched, never raised)
  2. postpack manifest: media classified, captions per platform, hashtags
     ride the vibe, YT backlink baked in
  3. cred env present but platform not enabled → still no network attempt
Run:  python tools/v17_multipost_ut.py
"""
import os, sys, json, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import multi_post  # noqa: E402

fails = 0


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v17ut_"))
    for v in ("MULTIPOST", "FB_PAGE_ID", "FB_PAGE_TOKEN", "TIKTOK_ACCESS_TOKEN"):
        os.environ.pop(v, None)

    meta = {"title": "Midnight Caller (Official Audio)", "name": "Midnight Caller"}
    fake_mp4 = tmp / "ep099_short.mp4"
    fake_mp4.write_bytes(b"\x00" * 2048)
    (tmp / "ep099_slowed.mp4").write_bytes(b"\x00" * 1024)

    # 1 · no-cred no-op
    r = multi_post.fanout(ep=99, meta=meta, genre_key="villain_pop", out=tmp,
                          yt_vid="LONGID", yt_sid="SHORTID")
    chk(r["enabled"] is False, "no env → fanout disabled, zero posting")

    # 2 · manifest completeness
    pack = json.loads((tmp / "ep099_postpack.json").read_text())
    chk(pack["media"].get("short", "").endswith("_short.mp4"), "manifest finds the short")
    chk(pack["media"].get("short_twin", "").endswith("_slowed.mp4"), "manifest finds the slowed twin")
    chk("youtu.be/SHORTID" in pack["captions"]["fb"], "FB caption backlinks the YouTube short")
    chk("#darkpop" in pack["captions"]["fb"], "vibe hashtags ride the genre")
    chk("#nymusic" in pack["captions"]["fb"], "original-music tags always on")
    chk(len(pack["captions"]["tt"]) <= 150, "TikTok caption stays tight")

    # 3 · creds set but MULTIPOST off → still silent
    os.environ["FB_PAGE_ID"] = "123"
    os.environ["FB_PAGE_TOKEN"] = "abc"
    r2 = multi_post.fanout(ep=99, meta=meta, genre_key="phonk_mafia", out=tmp)
    chk(r2["enabled"] is False, "creds without MULTIPOST=fb → still OFF")

    # 4 · platform enabled without creds → soft skip, no network, no raise
    os.environ.pop("FB_PAGE_ID", None)
    os.environ.pop("FB_PAGE_TOKEN", None)
    os.environ["MULTIPOST"] = "fb,tt"
    r3 = multi_post.fanout(ep=99, meta=meta, genre_key="phonk_mafia", out=tmp)
    chk(r3["enabled"] is True, "MULTIPOST=fb,tt → gate opens")
    chk("skipped" in str(r3.get("fb", "")), "fb without token → soft-skipped")
    chk("#phonk" in json.dumps(multi_post.captions(meta, "phonk_mafia", None)), "phonk lane hashtags correct")

    # 5 · no media at all → graceful error entry
    (tmp / "ep099_short.mp4").unlink()
    (tmp / "ep099_slowed.mp4").unlink()
    r4 = multi_post.fanout(ep=99, meta=meta, genre_key="lofi", out=tmp)
    chk("error" in r4 or r4["enabled"] is False, "no mp4 → graceful, no raise")

    print()
    if fails:
        print(f"❌ v17 multi-post UT: {fails} FAIL")
        return 1
    print("✅ v17 UT green — cross-posting is armed-in-silence: zero creds = zero change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

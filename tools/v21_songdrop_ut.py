#!/usr/bin/env python3
"""v21 🐐 BOSS-DROP UT — boss's own song lane (tools/song_drop.py): config,
captions, cut-parsing, anti-double record. Pure offline: no network, no ffmpeg.

Proves:
  1. fb caption never exceeds 245 chars (the EP.029 400-class is impossible)
  2. parse_cut handles "", "auto", "90", "1:30" sanely
  3. yt_meta contains title/artist + sane tags, category-shaped dict
  4. publish refuses a double when the title is in boss_drops.json
  5. scenes() emits 5 valid PNGs of the right aspect from pure PIL
Run:  python tools/v21_songdrop_ut.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.song_drop as sd  # noqa: E402

fails = 0


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def main():
    # 1 · caption law
    c = sd.fb_caption("interstate humidity", "Nix Speech", "https://youtu.be/" + "x" * 11)
    chk(len(c) <= 245, f"fb caption ≤245 (={len(c)})")
    chk("#nyxspeech" in c and "#bossdrop" in c, "boss-drop tags present")

    # 2 · cut parsing
    chk(sd.parse_cut("") == 0 and sd.parse_cut("auto") == 0, "auto/empty cut = punchy first minute")
    chk(sd.parse_cut("90") == 90 and sd.parse_cut("1:30") == 90, "90s and '1:30' parse the same")

    # 3 · yt meta shape
    m = sd.yt_meta("midnight valve", "Nix Speech", ["line"])
    chk("midnight valve" in m["title"] and "Nix Speech" in m["title"], "title carries song + artist")
    chk("midnight valve" in [t.lower() for t in m["tags"]], "song name in tags")
    chk("#nyxspeech" in m["description"], "boss-drop tags in description")

    # 4 · anti-double publish guard (mode reader path)
    os.environ["BOSSDROP_URL"] = "https://example.invalid/song.mp3"
    os.environ["BOSSDROP_TITLE"] = "midnight valve"
    with tempfile.TemporaryDirectory() as td:
        st = Path(td) / "state"
        st.mkdir()
        (st / "boss_drops.json").write_text(json.dumps({"midnight valve": {"date": "x"}}))
        cwd = os.getcwd()
        try:
            os.chdir(td)
            sys.argv = ["song_drop.py", "publish"]
            rc = sd.main()
        finally:
            os.chdir(cwd)
    chk(rc == 0, f"double-publish guarded (rc={rc})")

    # 5 · scenes render pure-PIL
    with tempfile.TemporaryDirectory() as td:
        sd.OUT = Path(td)
        imgs = sd.scenes("midnight valve", "Nix Speech", size=(360, 640), stem="t")
        chk(len(imgs) == 5, "5 hero scenes composed")
        from PIL import Image
        chk(all(Image.open(str(p)).size == (360, 640) for p in imgs), "every scene correct aspect")
        chk(str(imgs[0]).endswith(".png"), "pngs on disk")

    print()
    if fails:
        print(f"❌ v21 boss-drop UT: {fails} FAIL"); return 1
    print("✅ v21 UT green — the boss's song drops safe, single, and GOAT-packaged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

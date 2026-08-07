"""Pre-flight doctor — prints environment diagnostics. Always exits 0.

Runs as a CI step so every Actions log starts with a readable health report.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(label, ok, detail=""):
    print(f"  {'✅' if ok else '⚠️ '} {label}{f' — {detail}' if detail else ''}")
    return ok


print("🩺 yt-auto doctor")
print(f"  python {sys.version.split()[0]}")

try:
    import numpy
    check("numpy", True, numpy.__version__)
except Exception as e:
    check("numpy", False, str(e))
try:
    import PIL
    check("pillow", True, PIL.__version__)
except Exception as e:
    check("pillow", False, str(e))
for lib in ("googleapiclient", "google.genai"):
    try:
        __import__(lib)
        check(lib, True)
    except Exception as e:
        check(lib, False, str(e))

check("ffmpeg", shutil.which("ffmpeg") is not None,
      shutil.which("ffmpeg") or "video render steps will be skipped")

for var in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
    v = os.environ.get(var, "")
    check(f"secret {var}", bool(v), f"set ({len(v)} chars)" if v else "MISSING")
key = os.environ.get("GEMINI_API_KEY", "")
check("GEMINI_API_KEY", bool(key),
      "set — ai copy + gemini art ON" if key else "not set — bank copy + procedural art")

st_path = ROOT / "state" / "state.json"
if st_path.exists():
    st = json.loads(st_path.read_text())
    print(f"  📚 state: episode={st.get('episode')} "
          f"history={len(st.get('history', []))} "
          f"weights={'yes' if st.get('genre_weights') else 'no'}")
print("  quota math: ~3,200 of 10,000 daily units per release — comfy")
print("  🩺 reminder: videos stuck private after publish time? → YouTube API")
print("     compliance audit (free): https://support.google.com/youtube/contact/yt_api_form")
print("  doctor done.")

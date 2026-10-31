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

# DOCTOR_SECRETS=0 = "this step was given no secrets by design". The pre-flight step in
# publish.yml runs with an empty environment (Actions gives a step only what its own `env:`
# lists), so on 2026-10-31 it printed three "secret … MISSING" lines about credentials the
# NEXT step had, and a lane-audit table full of `(empty → ALL cross-posting OFF)`. That is
# not a diagnosis, it is a false alarm with a ✅/⚠️ in front of it — and the person reading
# the log at 22:30 cannot tell them apart. So: when asked, say nothing about secrets here
# and let the release step's own doctor call answer the question with the real environment.
if os.environ.get("DOCTOR_SECRETS", "1").strip() == "0":
    print("  🤫 secret + lane checks are SKIPPED here — this step has no environment by")
    print("     design. The release step runs this same doctor with the real env; read")
    print("     THAT block (or state/receipts/latest.md, which is authoritative).")
    _skip_secrets = True
else:
    _skip_secrets = False
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
# 🩺 LANE AUDIT (2026-09-13): every cross-posting mystery so far ("nothing on tt",
# "fb silent for weeks", "the drop succeeded in 27s but posted nothing") had the
# same root cause — the truth only existed inside a run log, and logs need an admin
# token to download (403) and expire (410 Gone). So the audit prints here AND
# writes out/lane_audit.json, which the receipt step commits to state/receipts/.
# Readable by anyone, forever, with zero credentials.
try:
    sys.path.insert(0, str(ROOT))
    from src import lane_audit
    if _skip_secrets:
        print("  🩺 lane audit SKIPPED in this step (no environment to audit — see above)")
    else:
        lane_audit.run()
except Exception as _lae:                       # never fatal — it is a diagnostic
    print(f"  🩺 lane audit skipped: {_lae}")

print("  quota math: ~3,200 of 10,000 daily units per release — comfy")
print("  🩺 reminder: videos stuck private after publish time? → YouTube API")
print("     compliance audit (free): https://support.google.com/youtube/contact/yt_api_form")
print("  doctor done.")

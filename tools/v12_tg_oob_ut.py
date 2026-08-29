"""🧪 v12 UT — TG out-of-band song rescue (offline, network mocked).

Proves:
  A) src/music_ace_kaggle._tg_fetch — getFile → download → size gate
     (happy path, too-small guard, missing token, missing file_path)
  B) kernel kaggle_ace/nix_ace_cook._tg_file — parses sendAudio JSON and
     returns {message_id, file_id, method} instead of swallowing it.
Run:  python tools/v12_tg_oob_ut.py
"""
import importlib.util
import json
import sys
import textwrap
import types
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        FAIL.append(name)


# ── A) _tg_fetch (lane side) ───────────────────────────────────────────────
print("A) music_ace_kaggle._tg_fetch")
from src import music_ace_kaggle as mak

real_urlopen = urllib.request.urlopen
real_urlretrieve = urllib.request.urlretrieve
tmp = Path("/tmp/v12_ut"); tmp.mkdir(exist_ok=True)

class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()
    def read(self):
        return self._b

def fake_ok(url, timeout=30):
    return _Resp({"ok": True, "result": {"file_path": "music/file_9.mp3"}})

def fake_dl(url, filename):
    Path(filename).write_bytes(b"X" * 120_000)   # 120 KB fake song

def fake_dl_tiny(url, filename):
    Path(filename).write_bytes(b"X" * 10)

def fake_nopath(url, timeout=30):
    return _Resp({"ok": True, "result": {}})

try:
    import os
    os.environ["TELEGRAM_BOT_TOKEN"] = "0000:UTfake"

    urllib.request.urlopen = fake_ok
    urllib.request.urlretrieve = fake_dl
    mp3 = tmp / "song.mp3"
    check("happy path: getFile → download → >=80KB → True",
          mak._tg_fetch("FID", mp3, 80_000) and mp3.exists()
          and mp3.stat().st_size == 120_000)

    urllib.request.urlretrieve = fake_dl_tiny
    small = tmp / "small.mp3"
    check("too-small guard: 10B < 80KB min → False",
          mak._tg_fetch("FID", small, 80_000) is False)

    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    check("no token → False (no crash)", mak._tg_fetch("FID", small, 80_000) is False)
    os.environ["TELEGRAM_BOT_TOKEN"] = "0000:UTfake"

    check("empty file_id → False (no net call)",
          mak._tg_fetch("", small, 80_000) is False)

    urllib.request.urlopen = fake_nopath
    check("getFile without file_path → False",
          mak._tg_fetch("FID", small, 80_000) is False)
finally:
    urllib.request.urlopen = real_urlopen
    urllib.request.urlretrieve = real_urlretrieve


# ── B) kernel _tg_file (Kaggle side, stdlib-only import) ──────────────────
print("B) kernel _tg_file parses sendAudio JSON")
spec = importlib.util.spec_from_file_location(
    "nix_ace_cook", ROOT / "kaggle_ace" / "nix_ace_cook.py")
kern = importlib.util.module_from_spec(spec)
# WORK=/kaggle/working doesn't exist here — mark() tolerates it (try/except)
spec.loader.exec_module(kern)
kern.TG_TOKEN = "0000:UTfake"
kern.TG_CHAT = "-1"

class _FakeR:
    stdout = json.dumps({"ok": True, "result": {
        "message_id": 4242,
        "audio": {"file_id": "CQADFAADFILEID"}}})
    stderr = ""

real_run = kern.subprocess.run
kern.subprocess.run = lambda *a, **k: _FakeR()
try:
    got = kern._tg_file(Path("/tmp/does_not_need_to_exist.mp3"), "cap")
finally:
    kern.subprocess.run = real_run
check("returns dict (not None)", isinstance(got, dict))
check("file_id captured", got and got.get("file_id") == "CQADFAADFILEID")
check("message_id captured", got and got.get("message_id") == 4242)
check("method = sendAudio", got and got.get("method") == "sendAudio")

kern.TG_TOKEN = ""
check("no TG creds → None (silent, no crash)",
      kern._tg_file(Path("/tmp/x.mp3"), "cap") is None)

print()
if FAIL:
    print("❌ FAILURES:", *FAIL, sep="\n  - ")
    sys.exit(1)
print("✅ v12 UT green — TG out-of-band rescue is wired.")

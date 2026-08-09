"""v20 receipt: SUNO provider + chain, against a FAKE sunoapi.org server.

No real key ever touches this workspace — the mock proves the full flow:
submit -> poll -> pick best clip -> download -> karaoke LRC rebuild,
plus every failure mode falling through to the next provider cleanly.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import music_suno                                            # noqa: E402

CLIP = b"\xab" * 210_000          # > MIN_BYTES, content irrelevant to the code
POLLS = {"n": 0}

WORDS = [
    {"word": "[Verse]\nmidnight", "startS": 1.0, "endS": 1.4},
    {"word": "lights", "startS": 1.4, "endS": 1.8},
    {"word": "fade\n[Chorus]\nwe", "startS": 2.2, "endS": 2.5},
    {"word": "ride on", "startS": 2.8, "endS": 3.2},
    {"word": "\n[outro]\nfalling", "startS": 4.5, "endS": 4.9},
    {"word": "slow", "startS": 5.0, "endS": 5.4},
]


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):          # shhh
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/v1/generate/credit":
            self._json({"code": 200, "data": 137})
        elif self.path.startswith("/api/v1/generate/record-info"):
            POLLS["n"] += 1
            if POLLS["n"] == 1:
                self._json({"code": 200, "data": {"taskId": "abc12345",
                                                  "status": "PENDING"}})
            elif MODE == "task_failed":
                self._json({"code": 200, "data": {"taskId": "abc12345",
                                                  "status": "GENERATE_AUDIO_FAILED",
                                                  "errorMessage": "gpu sad"}})
            else:
                self._json({"code": 200, "data": {
                    "taskId": "abc12345", "status": "SUCCESS",
                    "response": {"taskId": "abc12345", "sunoData": [
                        {"id": "clip-one", "audioUrl": f"{BASE_URL}/clip1.mp3",
                         "duration": 95.7},
                        {"id": "clip-two", "audioUrl": f"{BASE_URL}/clip2.mp3",
                         "duration": 151.3},
                    ]}}})
        elif self.path.startswith("/clip"):
            body = CLIP
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"code": 404, "msg": "nope"}, code=404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/v1/generate":
            POSTED.append(payload)
            if MODE == "no_credits":
                self._json({"code": 429, "msg": "insufficient credits"})
            else:
                assert payload["customMode"] and not payload["instrumental"]
                assert "midnight" in payload["prompt"]          # lyrics ride
                assert payload["vocalGender"] == "m"
                assert payload["duration"] == 150
                self._json({"code": 200, "data": {"taskId": "abc12345"}})
        elif self.path == "/api/v1/generate/get-timestamped-lyrics":
            assert payload["taskId"] == "abc12345"
            assert payload["audioId"] == "clip-two"             # right clip!
            self._json({"code": 200, "data": {
                "alignedWords": WORDS, "hootCer": 0.31, "isStreamed": False}})
        else:
            self._json({"code": 404, "msg": "nope"}, code=404)


BASE_URL = None
POSTED = []
MODE = "happy"


def run_case(mode, expect_ok, expect_clip_mb=0.21, expect_lrc=True):
    global MODE
    MODE = mode
    POLLS["n"] = 0
    out = Path("/tmp/v20_song.mp3")
    lrc = Path("/tmp/v20_song.lrc.txt")
    out.unlink(missing_ok=True)
    lrc.unlink(missing_ok=True)
    lyrics = "[verse]\nmidnight lights fade\n[chorus]\nwe ride on"
    t0 = time.time()
    r = music_suno.generate("drift_phonk", 150.0, out, lyrics=lyrics,
                            lang="en", lrc_out=lrc, deadline_s=8.0, tick_s=0.05)
    dt = time.time() - t0
    if expect_ok:
        assert r and out.exists() and out.stat().st_size >= 210_000
        print(f"  ✓ cooked in {dt:.1f}s, {out.stat().st_size/1e6:.2f} MB")
        txt = lrc.read_text()
        lines = txt.splitlines()
        assert expect_lrc and len(lines) == 3, txt
        assert lines[0] == "[00:01.00] midnight lights fade", lines[0]
        assert lines[1] == "[00:02.20] we ride on", lines[1]
        assert lines[2] == "[00:04.50] falling slow", lines[2]
        assert "[" not in lines[0].split("] ", 1)[1]      # tags stripped
        print(f"  ✓ karaoke map rebuilt: {len(lines)} timed lines, "
              f"section tags stripped, word-accurate")
        print(f"    line 1: {lines[0]!r}  line 2: {lines[1]!r}")
    else:
        assert r is None and not out.exists(), f"unexpected success in {mode}"
        print(f"  ✓ {mode}: cleanly returns None in {dt:.1f}s "
              f"→ next provider takes over")


def main():
    global BASE_URL
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    BASE_URL = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    music_suno.BASE = BASE_URL + "/api/v1"      # redirect at the fake studio
    os.environ["SUNO_API_KEY"] = "fake-test-key"
    os.environ.pop("SUNO_MODEL", None)
    os.environ.pop("SUNO_OFF", None)

    print("== v20 SUNO provider receipts (fake studio, real code paths) ==")
    assert music_suno.available() is True
    c = music_suno.credits()
    assert c == 137, c
    print(f"  ✓ credits() -> {c}")

    print("\n[happy path — 2 clips, picks closest to 150s, vocals on]")
    run_case("happy", expect_ok=True)

    print("\n[failure modes]")
    run_case("no_credits", expect_ok=False)      # 429 wallet empty
    run_case("task_failed", expect_ok=False)     # render died on their side

    os.environ["SUNO_OFF"] = "1"
    assert music_suno.available() is False
    assert music_suno.generate("lofi", 60.0, Path("/tmp/x.mp3")) is None
    print("  ✓ SUNO_OFF=1: provider dark, chain falls through")
    os.environ.pop("SUNO_OFF")

    del os.environ["SUNO_API_KEY"]
    assert music_suno.available() is False
    print("  ✓ no key: skipped silently — $0 path untouched")

    # LRC unit edge: garbage in -> None out (video falls back to quote-cards)
    assert music_suno._lrc_from_aligned([{"word": "[Intro]", "startS": 0.0}]) is None
    print("  ✓ junk alignedWords -> no karaoke file (graceful)")

    srv.shutdown()
    print("\nALL GREEN ✓")


if __name__ == "__main__":
    main()

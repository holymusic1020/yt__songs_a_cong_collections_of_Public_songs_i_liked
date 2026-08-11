"""SUNO studio (sunoapi.org) — the premium cook slot in the chain.

Chain order (boss's call):  SUNO -> ACE-Step space -> offline engine.
- One key (env SUNO_API_KEY, GitHub secret). No key -> skipped silently.
- 0 credits, quota errors, maintenance -> return None fast; the FREE
  ACE-Step space + offline engine keep the channel alive, always.
- Karaoke kept: their get-timestamped-lyrics endpoint gives word-level
  timing -> we rebuild the same LRC karaoke map ACE-Step provides.

HONEST notes (for the repo, not viewers):
- sunoapi.org is a THIRD-PARTY reseller (Suno has no public API).
  They claim watermark-free/commercial; treat as "best-effort" assets.
- Stdlib only — no new dependencies.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api.sunoapi.org/api/v1"
MIN_BYTES = 80_000

# compact style tags per genre (Suno "style" box, <=1000 chars)
STYLES = {
    "drift_phonk":   ("drift phonk, dark memphis phonk, distorted 808 bass, "
                      "cowbell lead, night drive, hypnotic, gritty"),
    "deep_pop":      ("deep dark-pop, moody alt pop, warm sub bass, intimate, "
                      "midnight ballad energy, cinematic chorus"),
    "dark_ambient":  ("dark ambient, cinematic drone, sparse piano echoes, "
                      "rainy atmosphere, slow emotional swell"),
    "lofi":          ("lo-fi hip hop, golden hour chill, vinyl crackle, "
                      "rhodes chords, swung drums, cozy mellow"),
    "baroque_waltz": ("vintage baroque waltz, 6/8 lilt, harpsichord arpeggios, "
                      "amber ballroom, old tape warmth"),
    "disco_house":   ("disco house, funky four-on-the-floor, grooving bassline, "
                      "offbeat chord stabs, celebratory club energy"),
    "skyline_anthem": ("anthemic folk-EDM, festival progressive house, big "
                       "piano stabs, euphoric crowd chant energy"),
    "villain_pop":   ("dark cinematic villain pop, music-box bells, heavy "
                      "808 sub, playful menace, theatrical tension"),
    "orbit_trap":    ("melodic trap, confident rap-sung bounce, rolling "
                      "hi-hats, sliding 808 bass, brass stabs, spacey pads"),
}
GENRE_BPM = {"drift_phonk": 130, "deep_pop": 96, "dark_ambient": 60,
             "lofi": 78, "baroque_waltz": 172, "disco_house": 118,
             "skyline_anthem": 128, "villain_pop": 142, "orbit_trap": 148}
VOCAL_GENDER = {"drift_phonk": "m", "deep_pop": "f", "dark_ambient": "f",
                "lofi": "m", "baroque_waltz": "f", "disco_house": "f",
                "skyline_anthem": "m", "villain_pop": "f", "orbit_trap": "m"}
LANG_HINT = {"en": "", "pt-BR": "sung in brazilian portuguese",
             "es": "sung in spanish", "fr": "sung in french",
             "tr": "sung in turkish", "ja": "sung in japanese",
             "ko": "sung in korean"}

_TAG_RE = re.compile(r"\[[^\]]+\]")


def _key() -> str:
    return os.environ.get("SUNO_API_KEY", "").strip()


def available() -> bool:
    off = (os.environ.get("SUNO_OFF", "") or "").strip().lower()
    return bool(_key()) and off not in ("1", "true", "yes", "on")


def _req(method: str, path: str, payload: dict | None = None,
         timeout: int = 30) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Authorization": f"Bearer {_key()}",
                 "Content-Type": "application/json",
                 "User-Agent": "yt-auto/20"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    try:
        out = json.loads(body)
    except ValueError:
        raise RuntimeError(f"bad JSON: {body[:160]}")
    code = out.get("code")
    if code != 200:
        raise RuntimeError(f"api code {code}: {out.get('msg', '')[:120]}")
    return out


def credits() -> int | None:
    """Remaining balance for the run-log. None = couldn't tell (not fatal)."""
    try:
        out = _req("GET", "/generate/credit", timeout=15)
        d = out.get("data")
        return int(d) if d is not None else None
    except Exception:
        return None


def _poll(task_id: str, deadline_s: float, tick_s: float = 10.0) -> dict | None:
    """Poll record-info until SUCCESS / failure. Returns the data dict."""
    t0 = time.time()
    while time.time() - t0 < deadline_s:
        out = _req("GET", f"/generate/record-info?taskId={task_id}", timeout=20)
        data = out.get("data") or {}
        status = str(data.get("status", "")).upper()
        if status in ("CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED",
                      "SENSITIVE_WORD_ERROR"):
            print(f"    ☠ suno task failed: {status} "
                  f"{str(data.get('errorMessage'))[:100]}")
            return None
        resp = data.get("response") or {}
        clips = resp.get("sunoData") or []
        ready = [c for c in clips if c.get("audioUrl")]
        if (status == "SUCCESS" and ready) or len(ready) >= 2:
            data["_clips"] = ready
            return data
        # CALLBACK_EXCEPTION: their webhook to our dummy URL failed — the
        # AUDIO doesn't care. Accept if clips are actually there.
        if status == "CALLBACK_EXCEPTION" and ready:
            data["_clips"] = ready
            return data
        time.sleep(tick_s)
    print(f"    ⏳ suno task timed out after {int(deadline_s)}s")
    return None


def _lrc_from_aligned(words: list[dict]) -> str | None:
    """Word-level timing -> LRC karaoke map (one [mm:ss.xx] per lyric line)."""
    lines: list[tuple[float, str]] = []
    cur_t, cur_words = None, []
    for w in words:
        t0 = w.get("startS")
        if t0 is None:
            continue
        parts = str(w.get("word", "")).split("\n")
        for i, frag in enumerate(parts):
            frag = _TAG_RE.sub("", frag).strip()
            if i > 0:                                   # line boundary
                if cur_words and cur_t is not None:
                    lines.append((float(cur_t), " ".join(cur_words)))
                cur_t, cur_words = float(t0), []
            if frag:
                if cur_t is None:
                    cur_t = float(t0)
                cur_words.append(frag)
    if cur_words and cur_t is not None:
        lines.append((float(cur_t), " ".join(cur_words)))
    lines = [(t, txt[:90]) for t, txt in lines if len(txt) >= 2]
    if len(lines) < 3:
        return None
    def stamp(t: float) -> str:
        m, s = divmod(float(t), 60.0)
        return f"[{int(m):02d}:{s:05.2f}]"
    return "\n".join(f"{stamp(t)} {txt}" for t, txt in lines)


def generate(genre_key: str, seconds: float, out_path: Path,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None,
             deadline_s: float = 360.0, tick_s: float = 10.0) -> Path | None:
    """Cook one song on the SUNO studio. None = 'next provider, please'.

    Same contract as music_space.generate: success -> a real audio file at
    out_path (>=80KB) plus an LRC karaoke map at lrc_out when vocals sung.
    """
    if not available():
        return None
    vocals = bool(lyrics and lyrics.strip())
    bpm = GENRE_BPM.get(genre_key, 110)
    style = f"{STYLES.get(genre_key, genre_key)}, {bpm} bpm"
    hint = LANG_HINT.get(lang, "")
    if hint and vocals:
        style += f", {hint}"
    model = os.environ.get("SUNO_MODEL", "").strip() or "V4_5ALL"
    payload = {
        "customMode": True,
        "instrumental": not vocals,
        "model": model,
        # their server POSTs status here; a dummy URL is fine — we POLL.
        "callBackUrl": "https://example.invalid/yt-auto-callback",
        "style": style[:990],
        "title": f"Nix Speech {genre_key} session"[:80],
        "duration": int(max(60, min(int(seconds), 480))),
    }
    if vocals:
        payload["prompt"] = lyrics.strip()[:4950]      # the SUNG words
        payload["vocalGender"] = VOCAL_GENDER.get(genre_key, "m")
    try:
        t0 = time.time()
        out = _req("POST", "/generate", payload, timeout=30)
    except Exception as e:
        print(f"    ☠ suno submit failed: {e}")
        return None
    task_id = str((out.get("data") or {}).get("taskId") or "")
    if not task_id:
        print("    ☠ suno: no taskId in reply")
        return None
    print(f"    🍳 suno task {task_id[:8]}… cooking ({model}, "
          f"{int(payload['duration'])}s, {'vocals ' + lang if vocals else 'instrumental'})")
    try:
        data = _poll(task_id, deadline_s, tick_s)
    except Exception as e:
        print(f"    ☠ suno poll failed: {e}")
        return None
    if not data:
        return None

    clips = data.get("_clips", [])
    target = float(payload["duration"])
    def _score(c):
        try:
            return abs(float(c.get("duration") or target) - target)
        except (TypeError, ValueError):
            return 1e9
    clip = min(clips, key=_score)
    url = clip.get("audioUrl")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            blob = r.read()
    except Exception as e:
        print(f"    ☠ suno download failed: {e}")
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    if out_path.stat().st_size < MIN_BYTES:
        print(f"    ☠ suno: suspiciously small audio "
              f"({out_path.stat().st_size} B)")
        out_path.unlink(missing_ok=True)
        return None
    took = time.time() - t0
    print(f"    ✅ suno rendered {clip.get('duration', '?')}s in {took:.0f}s "
          f"— file {len(blob)/1e6:.1f} MB")

    if vocals and lrc_out:
        try:
            ts = _req("POST", "/generate/get-timestamped-lyrics",
                      {"taskId": task_id, "audioId": str(clip.get("id", ""))},
                      timeout=30)
            words = ((ts.get("data") or {}).get("alignedWords")) or []
            lrc = _lrc_from_aligned(words)
            if lrc:
                lrc_out.write_text(lrc, encoding="utf-8")
                print(f"    ⏱ karaoke map captured: "
                      f"{len(lrc.splitlines())} timed lines")
        except Exception as e:
            print(f"    (karaoke fetch skipped: {e} — video still fine)")
    return out_path

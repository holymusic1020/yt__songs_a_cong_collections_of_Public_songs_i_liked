"""LYRIA 3 — Google's music model via the Gemini API (always-on vocal lane).

Chain (v23.3):  SUNO studio → LYRIA (Gemini API) → ACE-Step space → engine.

Why this lane matters: ACE-Step runs on HuggingFace ZeroGPU whose anonymous
quota (180s/day) is smaller than ONE generation request (180s) — so the
free-vocal lane there is quota-IMPOSSIBLE without an HF token. Lyria needs
no GPU quota at all: it's Google's API, billed to GEMINI_API_KEY which the
repo ALREADY has as a secret. It generates full songs WITH SUNG VOCALS and
returns both the mp3 AND the lyrics text.

Same contract as music_suno / music_space:
  success  -> real audio file at out_path (>=80KB) + rough LRC karaoke map
              at lrc_out (built from the returned lyrics, evenly timed)
  failure  -> None (engine takes over; the run can never die here)
"""
from __future__ import annotations

import os
from pathlib import Path

MODEL = "lyria-3-pro-preview"        # full songs, vocals, returns lyrics
CLIP_MODEL = "lyria-3-clip-preview"  # short clips (<=~30s) — demos / tests

# reuse the same per-genre style + bpm tables as the SUNO lane so every
# lane speaks one musical language
try:
    from src.music_suno import STYLES, GENRE_BPM
except Exception:                    # import-time safety — never crash
    STYLES, GENRE_BPM = {}, {}


def generate(genre_key: str, seconds: float, out_path: Path,
             lyrics: str | None = None, lang: str = "en",
             lrc_out: Path | None = None,
             model: str = MODEL) -> Path | None:
    """Cook one song on Google Lyria. None = 'next provider, please'."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("  ⚠ lyria: GEMINI_API_KEY not set — skipping lane")
        return None

    vocals = bool(lyrics and lyrics.strip())
    bpm = GENRE_BPM.get(genre_key, 110)
    style = f"{STYLES.get(genre_key, genre_key)}, {bpm} bpm"

    # duration: Lyria honors rough second hints in the prompt
    prompt = (f"Create a {int(max(10, min(seconds, 240)))}-second "
              f"{style} song.")
    if vocals:
        prompt += f"\n\nSing these lyrics:\n\n{lyrics.strip()}"
    else:
        prompt += "\nInstrumental only, no vocals."

    from google import genai                # lazy import (CI dep)
    client = genai.Client(api_key=key)
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
    except Exception as e:
        print(f"  ⚠ lyria failed: {type(e).__name__}: {str(e)[:140]}")
        return None

    audio: bytes | None = None
    text: str | None = None
    for part in resp.parts:
        if getattr(part, "text", None):
            text = part.text
        blob = getattr(part, "inline_data", None)
        if blob is not None and str(blob.mime_type).startswith("audio"):
            audio = blob.data
    if not audio:
        print("  ⚠ lyria returned no audio — skipping lane")
        return None

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    if out_path.stat().st_size < 80_000:    # sanity: real audio, not an error
        print(f"  ⚠ lyria audio suspiciously small "
              f"({out_path.stat().st_size} B) — skipping lane")
        out_path.unlink(missing_ok=True)
        return None

    # rough karaoke map from the returned lyrics (evenly timed lines) —
    # gives the long video real sung words when Lyria is the cook
    if text and lrc_out is not None:
        lines = [ln.strip() for ln in text.splitlines()
                 if ln.strip() and not ln.strip().startswith("[")]
        if lines:
            dur = max(float(seconds), 1.0)
            step = dur / len(lines)
            lrc = "\n".join(
                f"[{int(i * step // 60)}:{int(i * step % 60):02d}] {ln}"
                for i, ln in enumerate(lines))
            try:
                lrc_out.write_text(lrc, encoding="utf-8")
            except OSError:
                pass

    mode = f"{lang} vocals 🎤" if vocals else "instrumental"
    print(f"  🎁 lyria cooked {seconds:.0f}s of '{genre_key}' ({mode}, "
          f"{out_path.stat().st_size // 1024} KB)")
    return out_path

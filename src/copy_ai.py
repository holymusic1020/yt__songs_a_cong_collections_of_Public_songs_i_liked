"""Gemini TEXT brain — fresh titles, hooks, and lyric lines every run.

Uses the same GEMINI_API_KEY as covers. ANY failure → caller falls back to
the static banks (lyrics.py / metadata.py). The pipeline never depends on it.
"""
from __future__ import annotations

import os
import re

CANDIDATES = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]


def _generate(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=key)
    errs = []
    for m in CANDIDATES:
        try:
            resp = client.models.generate_content(model=m, contents=prompt)
            if resp.text:
                return resp.text
            errs.append(f"{m}: empty")
        except Exception as e:
            errs.append(f"{m}: {e}")
    raise RuntimeError(" | ".join(errs))


def _clean_lines(txt: str) -> list[str]:
    out, seen = [], set()
    for raw in txt.splitlines():
        ln = re.sub(r"^\s*[\-\*\d\.\)\:•]+\s*", "", raw).strip().strip('"').strip()
        if not (4 <= len(ln) <= 60) or " " not in ln:
            continue
        low = ln.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(ln)
    return out


def song_name(meta: dict) -> str:
    """A fresh, original, 2-3 word lowercase title. Raises on failure."""
    prompt = (
        "Invent ONE song title for an instrumental "
        f"{meta['genre']} track ({meta['key']}, {meta['bpm']} BPM) on a "
        "night-vibes channel.\nRules: 2-3 words, all lowercase, concrete "
        "poetic imagery (weather, rooms, cities, hours, objects), MUST NOT "
        "copy or near-copy any famous existing song title, no artist names, "
        "no cliches, no quotes, no emoji.\nReturn ONLY the title."
    )
    lines = _clean_lines(_generate(prompt))
    if not lines:
        raise RuntimeError("no usable name")
    name = lines[0].lower()
    if len(name.split()) > 4 or len(name) > 32:
        raise RuntimeError(f"bad name shape: {name}")
    return name


def episode_copy(meta: dict, n_lines: int = 6) -> dict:
    """Return {'hook': str, 'lines': [..]} fresh for this track. Raises on failure."""
    prompt = (
        f"You are the lyric writer for a night-vibes music channel. "
        f"Track: \"{meta['name']}\" — genre {meta['genre']}, {meta['key']}, "
        f"{meta['bpm']} BPM, instrumental.\n"
        f"Write {n_lines + 1} short caption lines for a lyric-style YouTube Short.\n"
        f"Rules: each line 3-7 words, lowercase, poetic but concrete, "
        f"night/city/weather/late-feelings imagery matching the title, "
        f"no cliches like 'lost in the music', no emojis, no quotes.\n"
        f"Line 1 must be a scroll-stopping hook (curiosity gap or direct "
        f"recognition like 'no one talks about this feeling').\n"
        f"Return ONLY the lines, one per line, no numbering."
    )
    lines = _clean_lines(_generate(prompt))
    if len(lines) < 3:
        raise RuntimeError("too few usable lines")
    return {"hook": lines[0], "lines": lines[1:1 + n_lines - 1]}

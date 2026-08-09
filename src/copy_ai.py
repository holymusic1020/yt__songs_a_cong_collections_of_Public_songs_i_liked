"""Gemini TEXT brain — fresh titles, hooks, sung lyrics, every run.

Uses the same GEMINI_API_KEY as covers. ANY failure → caller falls back to
the static banks (lyrics.py / metadata.py). The pipeline never depends on it.
"""
from __future__ import annotations

import os
import re

CANDIDATES = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

_TAG_NAMES = {"verse": "[verse]", "pre-chorus": "[pre-chorus]",
              "chorus": "[chorus]", "hook": "[chorus]",
              "bridge": "[bridge]", "outro": "[outro]"}


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
    lang_note = ""
    lang = (meta.get("lang") or "en").lower()
    if lang != "en":
        name_map = {"pt-bR": "portuguese", "es": "spanish", "fr": "french",
                    "tr": "turkish", "ja": "japanese", "ko": "korean"}
        nat = next((v for k, v in name_map.items() if lang.startswith(k.lower())), "")
        if nat:
            lang_note = (f" It MAY include exactly ONE {nat} word in latin "
                         f"script for exotic flavor (like 'saudade'), the rest english.")
    prompt = (
        "Invent ONE song title for a vocal "
        f"{meta['genre']} track ({meta['key']}, {meta['bpm']} BPM) on a "
        f"night-vibes channel.{lang_note}\nRules: 2-3 words, all lowercase, "
        "concrete poetic imagery (weather, rooms, cities, hours, objects), "
        "MUST NOT copy or near-copy any famous existing song title, no artist "
        "names, no cliches, no quotes, no emoji.\nReturn ONLY the title."
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
        f"{meta['bpm']} BPM.\n"
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


def scene_prompt(meta: dict, sung_lines: list[str] | None = None) -> str:
    """ONE cinematic scene inspired by the actual song (title + sung lines).

    v18 'meaningful visuals' research: scenes that echo the SONG keep
    viewers longer than genre-canned anime streets. Raises on failure →
    caller falls back to the canned variants.
    """
    ev = ""
    if sung_lines:
        ev = " Its sung lines: " + "; ".join(sung_lines[:5]) + "."
    prompt = (
        f"Describe ONE cinematic environment for the music visual of a "
        f"{meta.get('genre', 'night-vibes')} song named "
        f"\"{meta.get('name', 'untitled')}\".{ev}\n"
        f"Rules: ONE sentence, 10-16 words, environment ONLY — no people, no "
        f"faces, no text, no logos. Concrete nouns (weather, streets, rooms, "
        f"light, objects). Night mood matching the title. Anime-film friendly.\n"
        f"Return ONLY the scene sentence."
    )
    for raw in _generate(prompt).splitlines():
        ln = re.sub(r"[\*\"#>]", "", raw).strip().rstrip(".")
        if 20 <= len(ln) <= 180 and " " in ln:
            return ln
def song_lyrics(meta: dict, lang: str = "en", seconds: float = 150) -> str:
    """Fresh SUNG lyrics with [verse]/[chorus] tags for the ACE-Step space.

    Written 100% in `lang` (channel core = english; World Tour weeks season
    the catalog — foreign-language virality is real, brazilian phonk proves
    it). Raises on ANY failure → caller uses lyrics.song_lyrics bank instead.
    """
    from src import lyrics as _lyr
    info_ = _lyr.LANGS.get(lang, _lyr.LANGS["en"])
    lang_line = info_["label"] + (f" ({info_['hint']})" if info_["hint"] else "")
    prompt = (
        f"You are the songwriter for the music project Nix Speech. "
        f"Write complete, original lyrics for a song named \"{meta['name']}\" — "
        f"genre {meta['genre']}, about {seconds:.0f} seconds long.\n"
        f"LANGUAGE: {lang_line}. Every sung line MUST be in that language.\n"
        f"STRUCTURE (use these tags exactly, each on its own line):\n"
        f"[verse] + 4 lines, [chorus] + 4 lines, [verse] + 4 lines, "
        f"[chorus] + 4 lines, [bridge] + 2 lines, [chorus] + 4 lines.\n"
        f"RULES: each sung line 3-7 words, singable, no profanity, no artist "
        f"names, nothing copied or paraphrased from any existing song, "
        f"concrete night/drive/love imagery tied to the title, memorable "
        f"chorus (short, repeatable), lowercase, no translations, no "
        f"explanations, no markdown.\nReturn ONLY the tagged lyrics."
    )
    raw = _generate(prompt)
    out: list[str] = []
    for ln_raw in raw.splitlines():
        ln = re.sub(r"[*_`#>]", "", ln_raw).strip().strip('"').strip()
        if not ln:
            continue
        low = re.sub(r"[\[\]\s]", "", ln.lower())
        if low in _TAG_NAMES or low.startswith("verse") or \
           (low.startswith("chorus") and len(low) < 12) or \
           low.startswith("bridge") or low.startswith("outro"):
            tag = next((v for k, v in _TAG_NAMES.items() if low.startswith(k)),
                       "[verse]")
            out.append(tag)
            continue
        if ln.startswith("[") or low in ("lyrics", "song", "here"):
            continue
        if 2 <= len(ln) <= 90:
            out.append(ln.lstrip("-• ").strip())
    txt = "\n".join(out)
    sung = [l for l in out if not l.startswith("[")]
    if "[verse]" not in out or out.count("[chorus]") < 2 or len(sung) < 12:
        raise RuntimeError("gemini lyrics failed structure check")
    return txt

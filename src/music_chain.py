"""⚡ THE POWER GRID — every music lane, retried, then fallback (v23.4).

Boss's spec: "2-4 fallbacks; if one fails once, retry 1-2x, then fallback."

LANES, in order (every lane makes a FULL A-Z song, up to ~4 min):
  1. SUNO studio    (premium; needs SUNO_API_KEY + credits > 0)
  2. Lyria 3        (Google Gemini API; needs GEMINI_API_KEY — always-on,
                     no GPU quota; SUNG VOCALS + lyrics)
  3. ACE-Step v1.5  (HF space; free but ZeroGPU quota-gated ~180s/day)
  4. ACE-Step v1    (HF space; stale deploy — best effort)
  → engine (offline composer, always works) — NOT a lane, the guarantee.

Rules:
  · a lane "succeeds" only with a REAL audio file (>=80 KB) at out_path
  · every lane is tried up to LANE_RETRIES (default 2) times
  · exceptions / empty returns = a failed try → retry → next lane
  · `_LaneSkipped` = skip the lane entirely (no key / kill-switch / empty
    wallet) — no pointless retries
  · the run can NEVER die here; None just means "engine, take over"

Kill-switches (repo variables): SUNO_OFF, LYRA_OFF, ACE_OFF, LANE_RETRIES.
"""
from __future__ import annotations

import os
from pathlib import Path


class _LaneSkipped(Exception):
    """Raise inside a lane to skip it without retrying (no key, OFF, empty)."""


def _lane_suno(genre_key, seconds, out_path, lyrics, lang, lrc_out):
    from src import music_suno
    if not music_suno.available():
        raise _LaneSkipped("SUNO_OFF or no SUNO_API_KEY")
    bal = music_suno.credits()
    if bal is not None and bal <= 0:
        print("  ☠ suno wallet empty (0 credits) — next lane takes the mic 🎤")
        raise _LaneSkipped("suno wallet empty")
    print(f"  🔮 SUNO studio cooking {genre_key} ({lang} vocals 🎤)… "
          f"({bal if bal is not None else '?'} credits left)")
    return music_suno.generate(genre_key, seconds, out_path,
                               lyrics=lyrics, lang=lang, lrc_out=lrc_out)


def _lane_lyria(genre_key, seconds, out_path, lyrics, lang, lrc_out):
    if os.environ.get("LYRA_OFF", "") == "1":
        raise _LaneSkipped("LYRA_OFF=1")
    if not (os.environ.get("GEMINI_API_KEY", "") or "").strip():
        raise _LaneSkipped("no GEMINI_API_KEY")
    from src import music_lyria
    return music_lyria.generate(genre_key, seconds, out_path,
                                lyrics=lyrics, lang=lang, lrc_out=lrc_out)


def _lane_space(space: str, genre_key, seconds, out_path, lyrics, lang,
                lrc_out):
    if os.environ.get("ACE_OFF", "") == "1":
        raise _LaneSkipped("ACE_OFF=1")
    from src import music_space
    # the grid already retries per lane → ask the space for one solid shot
    return music_space.generate(genre_key, seconds, out_path,
                                lyrics=lyrics, lang=lang, lrc_out=lrc_out,
                                spaces=[space], retries=1)


def _retries() -> int:
    try:
        return max(1, int(os.environ.get("LANE_RETRIES", "2") or "2"))
    except ValueError:
        return 2


def cook(genre_key: str, seconds: float, out_path: Path,
         lyrics: str | None = None, lang: str = "en",
         lrc_out: Path | None = None,
         retries: int | None = None) -> tuple[Path | None, str | None]:
    """Try every lane in order, each up to `retries` times, until one cooks
    a real audio file. Returns (path, provider_name) or (None, None) → the
    caller's offline engine takes over (guaranteed lane)."""
    if retries is None:
        retries = _retries()

    lanes = [
        ("suno",          lambda: _lane_suno(genre_key, seconds, out_path,
                                             lyrics, lang, lrc_out)),
        ("lyria",         lambda: _lane_lyria(genre_key, seconds, out_path,
                                              lyrics, lang, lrc_out)),
        ("ace-step-v1.5", lambda: _lane_space("ACE-Step/Ace-Step-v1.5",
                                              genre_key, seconds, out_path,
                                              lyrics, lang, lrc_out)),
        ("ace-step-v1",   lambda: _lane_space("ACE-Step/ACE-Step",
                                              genre_key, seconds, out_path,
                                              lyrics, lang, lrc_out)),
    ]
    tried: list[str] = []
    for name, fn in lanes:
        for attempt in range(1, retries + 1):
            try:
                out = fn()
            except _LaneSkipped as s:
                print(f"  (lane {name} skipped: {s})")
                break
            except Exception as e:
                print(f"  ↻ {name} try {attempt}/{retries} crashed "
                      f"({type(e).__name__}: {str(e)[:110]}) — retrying…")
                continue
            if out:
                print(f"  🎁 {name} cooked it on try {attempt}")
                return out, name
            print(f"  ↻ {name} try {attempt}/{retries} returned nothing — "
                  f"next…")
        tried.append(name)
    print(f"  ⚠ all lanes tried ({', '.join(tried)}) — engine composes live")
    return None, None

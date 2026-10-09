"""Global title safety — never name a track after an existing song.

Three-line defense:
  1. never reuse OUR OWN names (state recall)
  2. prefer fresh AI-generated names (Gemini) over the finite bank
  3. verify against the WORLD catalog via iTunes Search API (free, no key):
     an exact-match existing song = rejected and re-rolled automatically.

Unique invented titles also OWN their search results — free SEO forever.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request


def itunes_exact_match(name: str, timeout: int = 6) -> bool:
    q = urllib.parse.urlencode({"term": name, "entity": "song", "limit": 25})
    url = f"https://itunes.apple.com/search?{q}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    low = name.strip().lower()
    return any((it.get("trackName") or "").strip().lower() == low
               for it in data.get("results", []))


_STOP = {"the", "and", "for", "with", "your", "mine", "into", "onto", "than",
         "that", "this", "from", "over", "under", "upon", "one", "two", "still",
         "ever", "again", "only", "just", "like", "when", "then", "there", "here"}


def _words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (title or "").lower())
            if w not in _STOP}


def pick_name(genre_key: str, used_names: set, rng, probe: dict,
              ai_fn=None, avoid_words: set[str] | None = None) -> str:
    """Return a title that's neither ours nor the world's. Never hard-fails.

    v23.7 (hype audit): exact-name dedup alone let the channel ship "asphalt
    porch", "asphalt humid" and "wet asphalt hum" inside four days — the words
    were new, the SONG names were not. `avoid_words` (the vocabulary of the
    recent releases) makes a candidate that recycles a content word re-roll.
    It is a preference, not a hard rule: after the attempts are spent we ship
    the best candidate anyway, because a release never dies over a name.
    """
    avoid = set(avoid_words or set())
    from src import metadata
    bank = metadata.NAME_BANKS.get(                       # 🛡 v19 no-kill law:
        genre_key, metadata.NAME_BANKS["deep_pop"])[0]   # missing bank degrades,


    for attempt in range(6):
        cand = None
        if ai_fn is not None and attempt < 3:
            try:
                cand = ai_fn(probe)              # Gemini's fresh idea
            except Exception:
                cand = None
        if not cand:
            fresh = [n for n in bank if n not in used_names]
            cand = (rng.choice(fresh) if fresh
                    else metadata._fresh_name(bank, used_names, rng))
        cand = cand.strip().strip('"').strip().lower()
        if not (3 <= len(cand) <= 40) or " " not in cand or cand in used_names:
            continue
        if avoid and (_words(cand) & avoid):
            if attempt < 5:
                print(f"  🔁 title '{cand}' reuses recent wording "
                      f"({', '.join(sorted(_words(cand) & avoid)[:3])}) — re-rolling")
                used_names = used_names | {cand}
                continue
        try:
            time.sleep(0.3)                       # be polite to the catalog
            if itunes_exact_match(cand):
                print(f"  🚫 title clash: '{cand}' already exists — re-rolling")
                used_names = used_names | {cand}
                continue
            print(f"  🏷  title '{cand}' verified unique (catalog-checked)")
        except Exception as e:
            print(f"  (catalog check skipped: {e})")
        return cand
    return _fallback_unique(bank, used_names, rng)


def _fallback_unique(bank: tuple, used_names: set, rng) -> str:
    """Last resort: strip any roman suffix, then certify 'name II' style."""
    base = metadata._fresh_name(bank, used_names, rng)
    base = re.sub(r"\s+(II|III|IV|V|VI)$", "", base)
    for cand in [base] + [f"{base} {t}" for t in
                          ("II", "III", "IV", "V", "VI", "VII")]:
        try:
            time.sleep(0.3)
            if not itunes_exact_match(cand):
                return cand
        except Exception:
            return cand                      # catalog down → own-uniqueness ok
    return cand

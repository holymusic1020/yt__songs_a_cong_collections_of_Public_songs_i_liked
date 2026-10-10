"""Gemini TEXT brain — fresh titles, hooks, sung lyrics, every run.

Uses the same GEMINI_API_KEY as covers. ANY failure → caller falls back to
the static banks (lyrics.py / metadata.py). The pipeline never depends on it.
"""
from __future__ import annotations

import os

from src import keys
import re

# 2026-08 refresh: gemini-2.0-flash/-lite shut down 2026-06-01;
# gemini-2.5-flash 404s for new API keys. GA replacements (no shutdown
# dates announced as of 2026-08): gemini-3.5-flash, gemini-3.1-flash-lite.
CANDIDATES = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]

_TAG_NAMES = {"verse": "[verse]", "pre-chorus": "[pre-chorus]",
              "chorus": "[chorus]", "hook": "[chorus]",
              "bridge": "[bridge]", "outro": "[outro]"}


def _generate(prompt: str) -> str:
    key = keys.pick("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("no GEMINI_API_KEY in the pool (set the secret, or GEMINI_API_KEY_2 …)")
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
def _report_craft(txt: str, gated: bool, label: str = "") -> None:
    """One honest line in the run log about what the words actually do.

    2026-10-09 lesson: nobody could tell from a run whether the lyrics rhymed,
    so 'the song has no hype' was undiagnosable. Now the number is on screen.
    """
    try:
        from src import craft as _c
        secs = _c.section_lines(txt)
        lines = [l for tag, ls in secs if tag in ("verse", "chorus") for l in ls]
        hit, tot = _c.couplets(lines)
        sung = [l for l in (txt or "").splitlines() if not l.startswith("[")]
        med = _c.syllables(sung[len(sung) // 2]) if sung else 0
        rate = f"{hit}/{tot} = {hit / tot:.0%}" if tot else "n/a"
        tail = label or ("gate PASSED" if gated
                         else "foreign-language day (no EN rhyme gate)")
        print(f"  ✍️  craft: couplet rhyme {rate} · {len(sung)} sung lines · "
              f"median {med} syllables · {tail}", flush=True)
    except Exception:
        pass


def _strip_to_tagged(raw: str) -> str:
    """Model prose -> clean [tag]/line lyrics. Shared by the first pass and the
    rewrite pass, so both are judged on exactly the same text shape."""
    out: list[str] = []
    for ln_raw in (raw or "").splitlines():
        ln = re.sub(r"[*_`#>]", "", ln_raw).strip().strip('"').strip()
        if not ln:
            continue
        low = re.sub(r"[\[\]\s]", "", ln.lower())
        if low in _TAG_NAMES or low.startswith("verse") or \
           (low.startswith("chorus") and len(low) < 12) or \
           low.startswith("bridge") or low.startswith("outro"):
            out.append(next((v for k, v in _TAG_NAMES.items() if low.startswith(k)),
                            "[verse]"))
            continue
        if ln.startswith("[") or low in ("lyrics", "song", "here"):
            continue
        if 2 <= len(ln) <= 90:
            out.append(ln.lstrip("-• ").strip())
    return "\n".join(out)


def song_lyrics(meta: dict, lang: str = "en", seconds: float = 150) -> str:
    """Fresh SUNG lyrics with [verse]/[chorus] tags for the ACE-Step space.

    Written 100% in `lang` (channel core = english; World Tour weeks season
    the catalog — foreign-language virality is real, brazilian phonk proves
    it). Raises on ANY failure → caller uses lyrics.song_lyrics bank instead.
    """
    from src import lyrics as _lyr
    info_ = _lyr.LANGS.get(lang, _lyr.LANGS["en"])
    lang_line = info_["label"] + (f" ({info_['hint']})" if info_["hint"] else "")
    CRAFT = (
        "CRAFT RULES — these are the reason the song sticks, follow them exactly:\n"
        "  1. RHYME IN COUPLETS. Inside every [verse] and every [chorus], lines 1+2 "
        "end on the SAME vowel sound and lines 3+4 do the same (AABB). A near-rhyme "
        "is a miss: \'go/show\', \'stone/alone\', never \'go/back\'.\n"
        "  2. METRE ON ONE GRID: 5-9 syllables in every sung line. Count them.\n"
        "  3. THE CHORUS RETURNS WORD-FOR-WORD. Every [chorus] block is the same 4 "
        "lines, identical characters, every time. Do not rewrite it.\n"
        "  4. THE CHORUS SELLS THE TITLE: the title phrase appears in the chorus "
        "(line 1 or line 4 is ideal).\n"
        "  5. THE PAYOFF (this is the part my listeners miss): the LAST line of the "
        "FINAL [chorus] must be the FIRST line of the FIRST [verse], repeated "
        "exactly. That callback is what makes an ending feel earned.\n"
        "  6. NO line may repeat anywhere except inside [chorus].\n"
    )
    prompt = (
        f"You are the songwriter for the music project Nix Speech. "
        f"Write complete, original lyrics for a song named \"{meta['name']}\" — "
        f"genre {meta['genre']}, about {seconds:.0f} seconds long.\n"
        f"LANGUAGE: {lang_line}. Every sung line MUST be in that language.\n"
        f"STRUCTURE (use these tags exactly, each on its own line):\n"
        f"[verse] + 4 lines, [chorus] + 4 lines, [verse] + 4 lines, "
        f"[chorus] + 4 lines, [bridge] + 2 lines, [chorus] + 4 lines.\n"
        + CRAFT +
        f"OTHER RULES: each sung line 3-8 words, singable, no profanity, no artist "
        f"names, nothing copied or paraphrased from any existing song, "
        f"concrete imagery tied to the title and to {meta['genre']}, memorable "
        f"chorus (short, repeatable), lowercase, no translations, no "
        f"explanations, no markdown.\nReturn ONLY the tagged lyrics."
    )
    txt = _strip_to_tagged(_generate(prompt))

    # v23.7 hype audit: the tags check used to be the ONLY check, so free verse
    # with no rhyme scheme and no callback sailed into a 3-minute render. Now
    # the lyric must pass src/craft.gate — or we ask once, precisely, for the
    # lines that missed, and only then let the caller drop to the banks.
    from src import craft as _craft
    # English only: ARPAbet rhyme scanning is an English dictionary, and a
    # Portuguese/Spanish verse would "fail" it while being perfectly good —
    # World Tour days must never be pushed back onto the fallback banks.
    if lang == "en":
        ok, problems = _craft.gate(txt, meta.get("name", ""))
    else:
        ok, problems = ("[verse]" in txt.splitlines()
                        and txt.count("[chorus]") >= 2
                        and len([l for l in txt.splitlines()
                                 if not l.startswith("[")]) >= 12), \
                       ["foreign-language structure check"]
    if not ok and lang == "en":
        print(f"  ✍️  lyrics missed the craft gate ({'; '.join(problems)[:150]}) "
              "— one rewrite pass…", flush=True)
        raw2 = _generate(prompt + "\n\n" + _craft.repair_note(problems))
        txt2 = _strip_to_tagged(raw2)
        ok2, problems2 = _craft.gate(txt2, meta.get("name", ""))
        if ok2:
            print("  ✅ rewrite pass cleared the gate", flush=True)
            _report_craft(txt2, gated=True)
            return txt2
        # 2026-10-09: the rewrite that is *closer* still beats free verse — ship it
        # when the shape is right (chorus returns + callback) even if one couplet
        # is a slant rhyme; otherwise the caller's bank fallback is the better song.
        shape = [p for p in problems2 if "come back with the SAME words" in p
                 or "call back" in p]
        if not shape:
            print(f"  ✍️  second pass: couplets still slant, but the hook returns "
                  "and the callback lands — shipping it", flush=True)
            _report_craft(txt2, gated=False,
                          label="hook returns + callback ✓, couplets slant")
            return txt2
        raise RuntimeError("gemini lyrics failed the craft gate: "
                           + "; ".join(problems2)[:180])
    if not ok:
        raise RuntimeError("gemini lyrics failed the craft gate: "
                           + "; ".join(problems)[:180])
    _report_craft(txt, gated=(lang == "en"))
    return txt

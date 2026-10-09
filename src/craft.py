"""Lyric CRAFT gate — the thing that was missing (2026-10-09, hype audit).

Boss's complaint, translated into code: *"the first and second line should
match, and then the ending should match after one or two lines — that vibe is
missing."* That is: **AABB end-rhyme couplets** + **a chorus that returns** +
**an ending that calls back the opening line**. None of it was checked
anywhere — `copy_ai.song_lyrics()` only verified that tags existed and that
there were >= 12 lines, so free-verse with no scheme sailed straight into the
most expensive step of the run (a 3-minute song render).

This module measures a lyric text and says pass/fail. It is a GUARD, not a
generator: callers retry the writer, then fall back to the banks. The run is
never blocked by it (no-kill law).

Optional dependency: `pronouncing` (ARPAbet) for true rhyme. If it is missing
we degrade to a vowel-tail rhymer — looser, but never an exception.
"""
from __future__ import annotations

import re

try:                                        # real phonemes when available
    import pronouncing as _pron
except Exception:                           # pragma: no cover — degrade, never die
    _pron = None

_TAG_RE = re.compile(r"^\s*\[([a-z\- ]+)\]\s*$", re.I)
_WORD_RE = re.compile(r"[A-Za-z'’]+")
VOWELS = "aeiouy"


# ─────────────────────────────────────────────────────── primitives
def words(line: str) -> list[str]:
    return [w.lower().strip("’'") for w in _WORD_RE.findall(line)]


def _crude(word: str) -> str:
    """Letter-tail rhyme: from the last vowel group to the end, with the common
    spelling swaps folded together. The no-dictionary fallback."""
    m = re.search(r"[aeiouy]+[^aeiouy\s]*$", word)
    if not m:
        return ""
    tail = m.group(0)
    for a, b in (("ow", "o"), ("oh", "o"), ("ay", "a"), ("ai", "a"),
                 ("igh", "a"), ("ee", "e"), ("ea", "e"), ("ue", "u"),
                 ("oo", "u"), ("ew", "u")):
        tail = tail.replace(a, b)
    return tail.rstrip("e") or tail


def rime(word: str) -> str | None:
    """The rhymeable tail of a word ('slow' -> 'oʊ', 'land' -> 'AE1 N D')."""
    w = re.sub(r"[^a-z']", "", word.lower())
    if len(w) < 2:
        return None
    if _pron is not None:
        try:
            ph = _pron.phones_for_word(w)
            if ph:
                tail = _pron.rhyming_part(ph[0])
                if tail:
                    return tail
        except Exception:
            pass
    tail = _crude(w)
    if not tail:
        return None
    # cheap equivalence for the pairs the crude path always misses
    for a, b in (("ow", "o"), ("oh", "o"), ("ay", "a"), ("ai", "a"),
                 ("ee", "e"), ("ea", "e"), ("igh", "a"), ("ue", "u"),
                 ("oo", "u"), ("ew", "u")):
        tail = tail.replace(a, b)
    return tail.rstrip("e") or tail


def syllables(line: str) -> int:
    n = 0
    for w in words(line):
        if _pron is not None:
            try:
                ph = _pron.phones_for_word(w)
                if ph:
                    n += sum(1 for p in ph[0].split() if p[-1].isdigit())
                    continue
            except Exception:
                pass
        groups = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and groups > 1 and not w.endswith(("le", "ee")):
            groups -= 1
        n += max(1, groups)
    return n


def parse(text: str) -> dict[str, list[str]]:
    """'[chorus]\\nline' blocks -> {'verse': [...], 'chorus': [...], ...}"""
    out: dict[str, list[str]] = {}
    cur = "verse"
    for raw in (text or "").splitlines():
        ln = raw.strip()
        if not ln:
            continue
        m = _TAG_RE.match(ln)
        if m:
            cur = m.group(1).lower().strip()
            out.setdefault(cur, [])
            continue
        out.setdefault(cur, []).append(ln)
    return out


def section_lines(text: str) -> list[tuple[str, list[str]]]:
    """Sections in order, each with its own lines: [('verse', [..]), …]."""
    out: list[tuple[str, list[str]]] = []
    cur = "verse"
    for raw in (text or "").splitlines():
        ln = raw.strip()
        if not ln:
            continue
        m = _TAG_RE.match(ln)
        if m:
            cur = m.group(1).lower().strip()
            out.append((cur, []))
            continue
        if not out or out[-1][0] != cur:
            out.append((cur, []))
        out[-1][1].append(ln)
    return out


def _in_dict(word: str) -> bool:
    if _pron is None:
        return False
    try:
        return bool(_pron.phones_for_word(word))
    except Exception:
        return False


def couplets(lines: list[str]) -> tuple[int, int]:
    """(rhyming pairs, checked pairs) over (1,2), (3,4), …

    CMU dict gaps must not punish good writing: 'mends' is simply absent from
    it, so a line pair like "bends / mends" would score as a MISS on a
    dictionary accident. When BOTH endings are known we trust the phonemes; when
    either is missing we compare the letter-tails instead, which is what a human
    ear falls back on anyway.
    """
    hit = tot = 0
    for a, b in zip(lines[0::2], lines[1::2]):
        wa, wb = words(a), words(b)
        if not wa or not wb:
            continue
        ra, rb = rime(wa[-1]), rime(wb[-1])
        if ra is None or rb is None:
            continue
        tot += 1
        if ra == rb:
            hit += 1
        elif not (_in_dict(wa[-1]) and _in_dict(wb[-1])):
            hit += (_crude(wa[-1]) == _crude(wb[-1]))
    return hit, tot


# ─────────────────────────────────────────────────────── the gate
def gate(text: str, title: str = "", *, min_rate: float = 0.5,
                         min_lines: int = 12) -> tuple[bool, list[str]]:
    """(ok, problems). Problems doubles as the correction note for a retry.

    Hard rules (a release must meet them):
      · >= `min_lines` sung lines, and >= 2 chorus blocks of identical words
      · couplet end-rhyme rate >= `min_rate` over verse+chorus lines
      · a CALLBACK: the last line of the final chorus returns the first line
        of the opening verse (exact, or >= 3 shared words)
      · meter sits in a singable band (median 3-12 syllables/line)
    Soft (recorded, never fails): the title being present somewhere.
    """
    problems: list[str] = []
    secs = section_lines(text)
    sung = [l for _tag, ls in secs for l in ls]
    if len(sung) < min_lines:
        return False, [f"only {len(sung)} sung lines (need {min_lines}+)"]

    choruses = [tuple(ls) for tag, ls in secs if tag.startswith("chorus") and ls]
    if len(choruses) < 2:
        problems.append("need at least two [chorus] blocks")
    else:
        # the chorus must RETURN — word-for-word — except that the last pass may
        # swap its final line for the callback (that IS the payoff boss asked for)
        cores = {tuple(ls[:3]) for ls in choruses if len(ls) >= 4}
        if len(cores) > 1:
            problems.append("the chorus must come back with the SAME words every "
                            f"time (got {len(cores)} different choruses; only its "
                            "final line may change on the last pass)")

    rhymey = [l for tag, ls in secs if tag in ("verse", "chorus") for l in ls]
    hit, tot = couplets(rhymey)
    rate = (hit / tot) if tot else 0.0
    if tot < 4:
        problems.append("too few rhyming pairs found to judge (write clear end-rhymes)")
    elif rate < min_rate:
        problems.append(f"couplet rhyme {hit}/{tot} = {rate:.0%} — lines 1↔2 and "
                        "3↔4 must end on the same vowel sound (AABB)")

    first = sung[0]
    last_block = choruses[-1] if choruses else tuple(sung[-2:])
    tail = last_block[-1] if last_block else ""
    shared = set(words(first)) & set(words(tail))
    if tail.strip().lower() != first.strip().lower() and len(shared) < 3:
        problems.append("the LAST line of the final chorus must call back the "
                        f"FIRST line of the song (“{first}”)")

    syl = [syllables(l) for l in sung]
    med = sorted(syl)[len(syl) // 2] if syl else 0
    if not 3 <= med <= 12:
        problems.append(f"median line length {med} syllables is not singable (3-12)")
    spread = (max(syl) - min(syl)) if syl else 0
    if spread > 9:
        problems.append(f"line lengths swing {min(syl)}→{max(syl)} syllables — "
                        "keep the flow on one grid (spread <= 9)")

    if title and title.lower() not in (text or "").lower():
        print(f"  (craft: title ‘{title}’ not sung — soft note, not a fail)")
    return (not problems), problems


def repair_note(problems: list[str]) -> str:
    """The exact instructions we hand back to the writer for the retry."""
    return ("Fix these in the SAME structure, keep the good lines:\n"
            + "\n".join(f"  - {p}" for p in problems))

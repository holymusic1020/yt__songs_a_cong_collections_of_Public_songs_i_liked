"""🔑 Key pool — 'set all kinda api keys as fallback' (boss, 2026-10-10).

One rule: a service is available if ANY of its keys is present, and every key is
tried before a lane gives up. Keys live in repo **Secrets**, named:

    GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3 …
    SUNO_API_KEY, SUNO_API_KEY_2 …            (and so on per service)

A single secret may also hold a comma-separated pool (`KEY=k1,k2`) for people
who'd rather not click through repo settings twice. The value returned by
`pool()` is the list in priority order; `pick()` is the first one.

This module never prints a key. Nothing here can.
"""
from __future__ import annotations

import os

MAX_SLOTS = 6


def pool(name: str) -> list[str]:
    out: list[str] = []
    raw = os.environ.get(name, "").strip()
    for part in raw.replace("\n", ",").split(","):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    for slot in range(2, MAX_SLOTS + 1):
        extra = os.environ.get(f"{name}_{slot}", "").strip()
        for part in extra.replace("\n", ",").split(","):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


def pick(name: str) -> str:
    """The key to use right now, or "" = service unavailable."""
    p = pool(name)
    return p[0] if p else ""


def have(name: str) -> bool:
    return bool(pool(name))


def note(name: str, label: str = "") -> str:
    """One honest log fragment: how many keys, never which ones."""
    n = len(pool(name))
    return f"{label or name}: {n} key(s)"

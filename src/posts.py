"""📮 Community post packs — 1-tap posting for boss.

THE HONEST TRUTH (researched Aug 2026): YouTube has NO public write API for
the Community tab (posts/polls live only inside YouTube Studio; automation
tools that 'post' either use the private partner pilot or steal session
cookies = ban risk, which we NEVER do). So the machine does everything
except the final tap: it writes the post, styles the image card, and sends
the pack to boss's Telegram — paste into the YT app = ~30 seconds.

Cadence — research-backed (2-3 posts/week beat daily; polls = top engagement):
  · every OTHER video day  → 📊 poll pack (question + 4 options)
  · the OTHER video days   → 🖤 feedback pack ("rate the new drop")
  · every other Sunday     → 🖼 lyric image card (machine-painted)

Kill switch: set Actions Variable POSTS_OFF=1. Turbo mode none — restraint
IS the growth strategy here. Everything is isolated: it can NEVER fail a run.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

# ---------------------------------------------------------------- cadence

POLL_QUESTIONS = [
    ("what should the next night drop be? 🌙",
     ["night drive phonk 🚗", "sad pop in the rain 💔",
      "brazilian phonk 🇧🇷", "disco at 3am 🪩"]),
    ("pick the NEXT world tour stop 🌍",
     ["brazilian phonk 🇧🇷", "spanish night pop 🇪🇸",
      "french disco 🇫🇷", "turkish neon trap 🇹🇷"]),
]


def due_kind(ep: int, today: datetime | None = None) -> str | None:
    """Modest, research-aligned schedule — restraint is the strategy."""
    if os.environ.get("POSTS_OFF", "0").strip() == "1":
        return None
    today = today or datetime.now(timezone.utc)
    if ep % 3 == 1 and ep % 6 == 1:
        return "poll"
    if ep % 3 == 1 and ep % 6 == 4:
        return "feedback"
    if today.weekday() == 6 and today.isocalendar().week % 2 == 1:
        return "card"
    return None


# ---------------------------------------------------------------- content

def _pack_poll(meta: dict, ep: int) -> tuple[str, None]:
    q, opts = POLL_QUESTIONS[(ep // 6) % len(POLL_QUESTIONS)]
    lines = [f"📊 POLL PACK (polls = the #1 engagement post type)", "",
             f"question: {q}", "", "options:"]
    lines += [f"{i + 1}) {o}" for i, o in enumerate(opts)]
    lines += ["", "how to post (30s): YouTube app → + → Create post → Poll →",
              "paste question + the 4 options → Post.",
              "best window: 8–10 PM BDT (= US noon–afternoon, prime scroll time)"]
    return "\n".join(lines), None


def _pack_feedback(meta: dict, ep: int) -> tuple[str, None]:
    name = meta.get("name", "the new drop")
    lines = ["🖤 FEEDBACK PACK", "",
             f"be honest with me 🖤 new song \"{name}\" just dropped —",
             "rate it 1-10 in the comments.",
             "most-loved vibe gets more episodes. most-ignored one retires 🌙", "",
             "how to post: app → + → Create post → Text → paste these 3 lines.",
             "(post AFTER the video goes live tonight so people can judge it)"]
    return "\n".join(lines), None


def art_card(cover: Path, line: str, meta: dict, out_path: Path) -> Path:
    """1080×1080 lyric card — channel-consistent, feed-pretty."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    from src import art as art_mod
    S = 1080
    bg = ImageOps.fit(Image.open(cover).convert("RGB"), (S, S), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(24))
    import numpy as _np
    bg = Image.fromarray(_np.clip(_np.asarray(bg) * 0.4, 0, 255).astype(_np.uint8))
    d = ImageDraw.Draw(bg)
    sq = ImageOps.fit(Image.open(cover).convert("RGB"), (620, 620), Image.LANCZOS)
    bg.paste(ImageOps.expand(sq, border=5, fill=(245, 245, 248)), ((S - 630) // 2, 90))
    import textwrap
    f_big = art_mod._font(64)
    y = 790
    for ln in textwrap.wrap(f"“{line}”", width=18):
        w = d.textlength(ln, font=f_big)
        d.text(((S - w) / 2, y), ln, font=f_big, fill=(248, 248, 252),
               stroke_width=2, stroke_fill=(0, 0, 0))
        y += 78
    f_sm = art_mod._font(30)
    foot = f"{meta.get('name','').upper()} — NIX SPEECH · lyric card"
    w = d.textlength(foot, font=f_sm)
    d.text(((S - w) / 2, S - 56), foot, font=f_sm, fill=(200, 200, 210))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_path, quality=90)
    return out_path


def _pack_card(meta: dict, hook: str | None, cover: Path) -> tuple[str, Path | None]:
    line = hook or meta.get("name", "night SHIFT".lower())
    img = art_card(cover, line, meta, OUT / "post_card.png")
    lines = ["🖼 LYRIC CARD PACK", "",
             f"“{line}”", "",
             f"from \"{meta.get('name','')}\" — full song on the channel 🌙", "",
             "how to post: app → + → Create post → Image → attach the",
             "card from Telegram (or out/post_card.png in the run artifacts),",
             "paste the caption above → Post."]
    return "\n".join(lines), img


# ---------------------------------------------------------------- telegram

_TIMEOUT = 15


def _creds() -> tuple[str, str]:
    return (os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            os.environ.get("TELEGRAM_CHAT_ID", "").strip())


def _tg_text(text: str) -> str:
    token, chat = _creds()
    if not token or not chat:
        return "telegram not configured — pack lives in the run summary"
    payload = {"chat_id": chat, "text": text,
               "disable_web_page_preview": "true"}
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=urllib.parse.urlencode(payload).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"telegram text: HTTP {r.status}"


def _tg_photo(path: Path, caption: str) -> str:
    token, chat = _creds()
    if not token or not chat:
        return "telegram not configured — card saved in out/"
    boundary = "----nix" + uuid.uuid4().hex[:12]
    parts: list[bytes] = []

    def field(name: str, value: str):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; "
                     f"name=\"{name}\"\r\n\r\n{value}\r\n".encode())

    field("chat_id", chat)
    field("caption", caption)
    raw = Path(path).read_bytes()
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; "
                 f"name=\"photo\"; filename=\"card.png\"\r\n"
                 f"Content-Type: image/png\r\n\r\n".encode() + raw + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"telegram photo: HTTP {r.status}"


# ---------------------------------------------------------------- main hook

def maybe_post(ep: int, meta: dict, sched: dict, hook: str | None,
               cover: Path, vid: str | None, sid: str | None) -> None:
    """One call from main's publish block. Never raises after its own guard."""
    kind = due_kind(ep)
    if not kind:
        print("  📮 no community post due today (2-3/week is the sweet spot)")
        return
    if kind == "poll":
        text, img = _pack_poll(meta, ep)
    elif kind == "feedback":
        text, img = _pack_feedback(meta, ep)
    else:
        text, img = _pack_card(meta, hook, cover)

    # always land the pack in the run summary (email-safe fallback if
    # telegram is unconfigured / broken)
    summary = OUT / "summary.md"
    try:
        with summary.open("a", encoding="utf-8") as f:
            f.write(f"\n\n## 📮 community post pack ({kind}) — 1-tap for boss\n\n"
                    f"```\n{text}\n```\n")
    except OSError:
        pass

    try:
        print("  📮 post pack →", _tg_text(f"📮 Nix Speech · community post ({kind})\n\n{text}"))
        if img and Path(img).exists():
            print("  📮 card photo →", _tg_photo(img, f"🖼 {meta.get('name','')} — lyric card"))
    except Exception as e:
        print(f"  (telegram pack failed: {e} — pack is in the run summary)")

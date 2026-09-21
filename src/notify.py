"""Run-end status alerts — Telegram bot + Discord webhook. 100% OPTIONAL.

Sends a message on EVERY run:
  ✅ success → track name, video/short links, go-live times (BDT)
  🚨 failure → last lines of the run log + link to the full log

Secrets (GitHub → Settings → Secrets and variables → Actions):
  TELEGRAM_BOT_TOKEN  bot token from @BotFather
  TELEGRAM_CHAT_ID    your chat id (message the bot, then ask @userinfobot)
  NOTIFY_WEBHOOK      Discord channel webhook

Missing any secret just silences that channel. This module NEVER fails the
workflow: every send is wrapped, network errors are swallowed, exit code is
always 0.

Local test (no network, prints payloads):
  python -m src.notify --status Success --run-url http://x --dry
"""
from __future__ import annotations

import argparse
import html
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

BDT = timezone(timedelta(hours=6))          # Asia/Dhaka — no DST
REQ_TIMEOUT = 10


def _bdt(iso: str | None) -> str:
    """'2026-08-07T07:12:24Z' -> '1:12 PM BDT' (falls back to raw string)."""
    if not iso:
        return "right away"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(BDT)
        return dt.strftime("%I:%M %p").lstrip("0") + " BDT"
    except Exception:
        return iso


def _link(vid: str | None) -> str:
    return f"https://youtu.be/{vid}" if vid else "(link in run summary)"


def _lane_state(val: str) -> str:
    """Map a fanout lane result string to ✅ posted / ❌ failed / ➖ off."""
    v = (val or "").lower()
    if any(k in v for k in ("published", "uploaded", "draft")):
        return "✅"
    if any(k in v for k in ("failed", "rejected", "crashed", "refused")):
        return "❌"
    return "➖"


def build_message(status: str, manifest: dict | None,
                  run_url: str, log_tail: str) -> str:
    """ONE compact message. Boss 2026-09-19: no log dumps in Telegram, no media
    spam — a platform checklist with ✅/❌, the URLs, and the log link ONLY when
    something actually failed."""
    if status.lower() == "success" and manifest:
        m = manifest.get("meta", {})
        sched = manifest.get("schedule", {})
        vid, sid = manifest.get("video_id"), manifest.get("short_id")
        lanes = manifest.get("lanes") or {}
        lines = [
            f"✅ EP.{manifest.get('episode', 0):03d} · {m.get('name', '?')}",
            f"🎵 {m.get('genre', '?')} · {m.get('bpm', '?')} bpm · {m.get('key', '?')}",
            "─" * 22,
        ]
        if manifest.get("video_today"):
            lines.append(f"🎬 YouTube video  ✅ {_link(vid)}")
        lines.append(f"⚡ YouTube short  ✅ {_link(sid)}")
        for key, label in (("fb", "📘 Facebook"), ("tt", "🎵 TikTok"),
                           ("ig", "📸 Instagram"), ("ig_photo", "🖼️ IG photo")):
            if key in lanes:
                st = _lane_state(str(lanes.get(key, "")))
                extra = ""
                if key == "ig" and lanes.get("ig_permalink"):
                    extra = f" {lanes['ig_permalink']}"
                lines.append(f"{label:<15} {st}{extra}")
        # 📦 streaming pack — informational ONLY. It is not a lane: nothing is
        # uploaded, so a refused-rights night must never read as "not posted".
        # (Its skip string contains the word "refused" — which _lane_state maps
        # to ❌ — so it is excluded from the failure list on purpose.)
        dsp_note = str(lanes.get("dsp") or "").strip()
        if dsp_note:
            ready = dsp_note.startswith("✅")
            body = dsp_note.lstrip("✅").strip()
            body = body.removeprefix("off").lstrip(" —")
            lines.append(f"📦 Spotify pack  {'✅' if ready else '➖'} {body}")
        bad = [k for k in lanes
               if k in ("fb", "tt", "ig", "ig_photo")
               and _lane_state(str(lanes[k])) == "❌"]
        lines.append("─" * 22)
        if bad:
            lines.append(f"❌ not posted: {', '.join(bad)}")
            lines.append(f"🔗 log: {run_url}")
        else:
            lines.append("🟢 all lanes clear")
        return "\n".join(lines)

    # failure / cancelled / no manifest — link only, NEVER the log body
    ep = (manifest or {}).get("episode")
    head = f"🚨 run {status.upper()}" + (f" · EP.{ep:03d} was in progress" if ep else "")
    return f"{head}\n🔗 log: {run_url}"


def _post(url: str, data: bytes, headers: dict) -> str:
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
        return f"HTTP {r.status}"


def send_telegram(token: str, chat_id: str, text: str, dry: bool) -> str:
    if not token or not chat_id:
        return "skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)"
    payload = {
        "chat_id": chat_id,
        "text": html.escape(text, quote=False),   # plain text, safely escaped
        "disable_web_page_preview": "true",
    }
    if dry:
        return "DRY: " + json.dumps(payload)[:200]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _post(url, urllib.parse.urlencode(payload).encode(),
                 {"Content-Type": "application/x-www-form-urlencoded"})


def send_telegram_video(token: str, chat_id: str, path: str, caption: str) -> str:
    """Send a rendered mp4 to the owner's Telegram (dry-run previews).
    Bots cap uploads at 50 MB — bigger files are skipped with a note.
    Falls back to sendDocument if sendVideo rejects the file."""
    if not token or not chat_id:
        return "skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)"
    p = Path(path)
    if not p.exists():
        return f"skipped ({p.name} missing)"
    size = p.stat().st_size
    if size > 49 * 1024 * 1024:
        return f"skipped ({p.name} is {size/1e6:.1f} MB > 49 MB bot cap)"
    import requests                       # lazy — plain alerts never need it
    api = f"https://api.telegram.org/bot{token}"
    with open(p, "rb") as fh:
        r = requests.post(f"{api}/sendVideo",
                          data={"chat_id": chat_id, "caption": caption[:1024],
                                "supports_streaming": "true"},
                          files={"video": (p.name, fh, "video/mp4")},
                          timeout=300)
    if r.status_code == 200:
        return f"sent {p.name} ({size/1e6:.1f} MB)"
    with open(p, "rb") as fh:
        r2 = requests.post(f"{api}/sendDocument",
                           data={"chat_id": chat_id, "caption": caption[:1024]},
                           files={"document": (p.name, fh, "video/mp4")},
                           timeout=300)
    if r2.status_code == 200:
        return f"sent {p.name} as document ({size/1e6:.1f} MB)"
    raise RuntimeError(f"telegram {r.status_code}: {r.text[:160]}")


def send_discord(webhook: str, text: str, dry: bool) -> str:
    if not webhook:
        return "skipped (NOTIFY_WEBHOOK not set)"
    body = json.dumps({"content": text[:1900]}).encode()
    if dry:
        return "DRY: " + body.decode()[:200]
    return _post(webhook, body, {"Content-Type": "application/json"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="Success")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--log", default="out/run.log")
    ap.add_argument("--manifest", default="out/latest.json")
    ap.add_argument("--dry", action="store_true", help="print payloads, no network")
    args = ap.parse_args()

    manifest = None
    try:
        manifest = json.loads(Path(args.manifest).read_text())
    except Exception:
        pass

    log_tail = ""
    try:
        log_tail = "\n".join(Path(args.log).read_text(errors="replace")
                             .splitlines()[-12:])
    except Exception:
        pass

    msg = build_message(args.status, manifest, args.run_url, log_tail)
    print("---- alert message ----")
    print(msg)
    print("-----------------------")

    results = []
    for label, fn in (
        ("telegram", lambda: send_telegram(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
                                           os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
                                           msg, args.dry)),
        ("discord",  lambda: send_discord(os.environ.get("NOTIFY_WEBHOOK", "").strip(),
                                          msg, args.dry)),
    ):
        try:
            results.append(f"{label}: {fn()}")
        except Exception as e:                      # NEVER break the workflow
            results.append(f"{label}: failed ({e}) — ignored")
    print("\n".join(results))


if __name__ == "__main__":
    main()

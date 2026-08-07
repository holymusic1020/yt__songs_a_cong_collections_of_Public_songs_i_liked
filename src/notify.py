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


def build_message(status: str, manifest: dict | None,
                  run_url: str, log_tail: str) -> str:
    """Plain-text message (Discord). Telegram version escapes via _tg()."""
    if status.lower() == "success" and manifest:
        m = manifest.get("meta", {})
        sched = manifest.get("schedule", {})
        vid, sid = manifest.get("video_id"), manifest.get("short_id")
        lines = [
            f"✅ Nix Speech · EP.{manifest.get('episode', 0):03d} released",
            f"🎵 {m.get('name', '?')} ({m.get('genre', '?')} · {m.get('bpm', '?')} bpm · {m.get('key', '?')})",
        ]
        if manifest.get("video_today"):
            lines.append(f"🎬 video · {_link(vid)} · live {_bdt(sched.get('video_publish_at'))}")
        lines.append(f"⚡ short · {_link(sid)} · live {_bdt(sched.get('short_publish_at'))}")
        lines.append(f"🔗 log + files: {run_url}")
        return "\n".join(lines)

    # failure / cancelled / no manifest
    ep = (manifest or {}).get("episode")
    head = f"🚨 yt-auto run {status.upper()}" + (f" — EP.{ep:03d} was in progress" if ep else "")
    tail = (log_tail or "").strip()[-600:] or "(no log captured)"
    return f"{head}\n📋 last log lines:\n```\n{tail}\n```\n🔗 full log: {run_url}"


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

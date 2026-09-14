"""📋 Run receipts (2026-09-13) — the machine tells the truth in PUBLIC.

WHY THIS EXISTS
---------------
Diagnosing "did the fb/tt/ig lane actually post?" used to require downloading the
Actions run log, and GitHub answers `403 Must have admin rights to Repository` for
log downloads unless the caller holds an admin-capable token. Every audit therefore
depended on a bridge PAT being alive — and PATs die (the Sep 13 audit found the
backup copy already revoked).

So each run now writes its own receipt into the repo and pushes it:

    state/receipts/YYYY-MM-DD-epNNN.json     full receipt
    state/receipts/latest.md                 human one-screen summary

Both are readable by ANYONE over raw.githubusercontent.com — no token, no log
retention window, no 410 Gone. Forever-verifiable drops.

SAFETY LAWS (learned the hard way, see LEDGER cont.25 / cont.29)
----------------------------------------------------------------
1. NEVER raises. A receipt problem must not touch a release. Every entry point is
   wrapped by the caller too.
2. NEVER commits `state/state.json`. The workflow's own "Commit state" step owns
   that file; racing it caused a duplicate-episode class of bug before. We only
   mirror the receipt INTO state.json on disk (so the workflow commits it later)
   and we only `git add state/receipts`.
3. NEVER prints a credential. Values are masked at the door.
4. Push FIRST-class hygiene: identity is set repo-local inline (`.git/config` does
   not survive sandbox rehydration), and we `pull --rebase` before pushing.
5. Text only. Under ~4 KB per receipt, 14-file rolling window in latest.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

RECEIPT_DIR = Path("state/receipts")
_SENSITIVE = ("token", "secret", "password", "key", "authorization", "cookie",
              "access", "refresh", "client_secret", "api_key")


def _mask(obj):
    """Recursively redact anything credential-shaped. Receipts are PUBLIC."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in _SENSITIVE):
                out[k] = "***"
            else:
                out[k] = _mask(v)
        return out
    if isinstance(obj, list):
        return [_mask(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 24:
        low = obj.lower()
        if any(p in low for p in ("eaakg", "github_pat_", "ghp_", "act.ia", "rft.",
                                  "bearer ", "oauth ", "ya29.")):
            return "***redacted***"
    return obj


def _git(*args, timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:                       # noqa: BLE001 — never fatal
        return 1, f"{type(e).__name__}: {e}"


def build(ep, meta: dict, genre_key: str, kind: str, vid, sid,
          fanout: dict, started_at: float, mode: str = "",
          extra: dict | None = None) -> dict:
    """Assemble the receipt dict (no I/O)."""
    meta = meta if isinstance(meta, dict) else {}
    f = fanout if isinstance(fanout, dict) else {}
    lanes = {k: v for k, v in f.items()
             if k not in ("enabled", "postpack") and not k.endswith("_permalink")}
    rec = {
        "schema": 1,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "episode": ep,
        "mode": mode or ("dry_run" if os.environ.get("MULTIPOST_DRYRUN") == "1" else "publish"),
        "kind": kind,
        "genre": genre_key,
        "track": meta.get("name") or meta.get("title") or "",
        "bpm": meta.get("bpm"),
        "key": meta.get("key"),
        "youtube": {"video_id": vid, "short_id": sid,
                    "watch": f"https://youtu.be/{vid}" if vid else None,
                    "short": f"https://youtu.be/{sid}" if sid else None},
        "multipost_dial": os.environ.get("MULTIPOST", "") or "(empty → OFF)",
        "lanes": lanes,
        "seconds": round(time.time() - started_at, 1) if started_at else None,
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_url": (f"https://github.com/{os.environ.get('GITHUB_REPOSITORY','')}/actions/runs/"
                    f"{os.environ.get('GITHUB_RUN_ID','')}") if os.environ.get("GITHUB_RUN_ID") else "",
        "sha": _git("rev-parse", "--short", "HEAD")[1][:12],
    }
    if extra:
        rec.update(_mask(extra))
    rec = _mask(rec)
    # 🩺 fold in the pre-flight lane audit when doctor.py produced one, so the
    # committed receipt answers "why didn't it post?" without opening a run log.
    try:
        la = Path("out/lane_audit.json")
        if la.exists():
            rec["lane_audit"] = _mask(json.loads(la.read_text()))
    except Exception:
        pass
    return rec


def to_markdown(rec: dict) -> str:
    ln = rec.get("lanes") or {}
    lane_lines = "\n".join(f"| {k} | {str(v)[:150]} |" for k, v in sorted(ln.items())) or "| — | no lanes ran |"
    la = rec.get("lane_audit") or {}
    audit_md = ""
    if la:
        verdicts = "\n".join(f"- {v}" for v in (la.get("verdicts") or [])) or "- (none)"
        dial = (la.get("dials") or {}).get("MULTIPOST", "?")
        audit_md = (f"\n## 🩺 lane audit\n\nMULTIPOST dial: `{dial}` · "
                    f"lanes wanted: `{', '.join(la.get('lanes_wanted') or [])}`\n\n{verdicts}\n")
    yt = rec.get("youtube") or {}
    return (
        f"# 📋 receipt · EP.{int(rec.get('episode') or 0):03d} · {rec.get('date')}\n\n"
        f"| | |\n|---|---|\n"
        f"| track | **{rec.get('track')}** ({rec.get('genre')}) |\n"
        f"| mode | {rec.get('mode')} · {rec.get('kind')} |\n"
        f"| youtube | {yt.get('watch') or '—'} · short: {yt.get('short') or '—'} |\n"
        f"| multipost dial | `{rec.get('multipost_dial')}` |\n"
        f"| took | {rec.get('seconds')} s |\n"
        f"| run | {rec.get('run_url') or 'local'} @ {rec.get('sha')} |\n\n"
        f"## lanes\n\n| lane | result |\n|---|---|\n{lane_lines}\n"
        + audit_md
    )


def write(rec: dict, root: Path | str = ".") -> Path | None:
    """Write the receipt files (no git). Returns the json path, or None."""
    try:
        root = Path(root)
        d = root / RECEIPT_DIR
        d.mkdir(parents=True, exist_ok=True)
        ep = int(rec.get("episode") or 0)
        name = f"{rec.get('date')}-ep{ep:03d}.json"
        p = d / name
        p.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        (d / "latest.md").write_text(to_markdown(rec), encoding="utf-8")
        # rolling history in one small file (last 40), so a single raw fetch
        # answers "what happened this week?" without walking the tree.
        hist_p = d / "history.json"
        hist = []
        if hist_p.exists():
            try:
                hist = json.loads(hist_p.read_text())
            except Exception:
                hist = []
        slim = {k: rec.get(k) for k in ("date", "episode", "mode", "kind", "genre",
                                        "track", "multipost_dial", "seconds")}
        slim["youtube"] = rec.get("youtube")
        slim["lanes"] = rec.get("lanes")
        hist = [h for h in hist if h.get("date") != slim["date"] or h.get("episode") != slim["episode"]]
        hist.append(slim)
        hist_p.write_text(json.dumps(hist[-40:], indent=2, ensure_ascii=False))
        return p
    except Exception as e:                       # noqa: BLE001
        print(f"  📋 receipt write skipped: {e}")
        return None


def mirror_into_state(rec: dict, state_path: Path | str = "state/state.json") -> bool:
    """Append a slim copy into state.json ON DISK ONLY (never committed by us).

    The workflow's own 'Commit state' step pushes state.json — so the receipt also
    travels there for free, giving a second copy if the receipts push ever fails.
    """
    try:
        p = Path(state_path)
        if not p.exists():
            return False
        st = json.loads(p.read_text())
        slim = {k: rec.get(k) for k in ("date", "episode", "mode", "kind", "genre",
                                        "track", "multipost_dial", "lanes")}
        hist = st.get("receipts") or []
        hist = [h for h in hist if not (h.get("date") == slim.get("date")
                                        and h.get("episode") == slim.get("episode"))]
        hist.append(slim)
        st["receipts"] = hist[-14:]
        p.write_text(json.dumps(st, indent=2, ensure_ascii=False))
        return True
    except Exception as e:                       # noqa: BLE001
        print(f"  📋 receipt state-mirror skipped: {e}")
        return False


def commit_and_push(root: Path | str = ".") -> str:
    """Publish the receipts. Best-effort, text-only, never touches state.json.

    Returns a short human status string for the receipt itself.
    """
    if os.environ.get("RECEIPT_PUSH") == "0":
        return "push disabled (RECEIPT_PUSH=0)"
    if not (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")):
        return "no token in env — receipt written locally only"
    root = Path(root)
    rc, out = _git("rev-parse", "--is-inside-work-tree")
    if rc != 0:
        return "not a git repo — receipt written locally only"
    _git("config", "user.name", "yt-auto-bot")
    _git("config", "user.email", "actions@users.noreply.github.com")
    rc, out = _git("add", str(root / RECEIPT_DIR))
    rc, out = _git("diff", "--cached", "--quiet")
    if rc == 0:
        return "nothing new to commit"
    day = time.strftime("%Y-%m-%d", time.gmtime())
    rc, out = _git("commit", "-m", f"📋 receipt: {day} (public run truth — lanes/yt/timings)")
    if rc != 0:
        return f"commit failed: {out[:160]}"
    branch = os.environ.get("GITHUB_REF_NAME") or "main"
    rc, out = _git("pull", "--rebase", "origin", branch)
    if rc != 0:
        print(f"  📋 receipt rebase note: {out[:160]}")
    rc, out = _git("push", "origin", f"HEAD:{branch}", timeout=180)
    if rc != 0:
        # detached-HEAD ghost-push lesson (LEDGER cont.25): explicit HEAD:branch,
        # and if that still fails, the receipt still lives in state.json's mirror.
        return f"push failed (receipt still mirrored into state.json): {out[:160]}"
    sha = _git("rev-parse", "--short", "HEAD")[1][:12]
    return f"pushed {sha}"


def record(ep, meta, genre_key, kind, vid, sid, fanout, started_at,
           mode: str = "", root: Path | str = ".", extra: dict | None = None) -> dict:
    """One-call entry point used by main.py. NEVER raises."""
    try:
        rec = build(ep, meta, genre_key, kind, vid, sid, fanout, started_at, mode, extra)
        p = write(rec, root)
        mirrored = mirror_into_state(rec)
        rec["_push"] = commit_and_push(root) if p else "not written"
        rec["_state_mirror"] = mirrored
        print(f"  📋 receipt: ep{int(ep or 0):03d} · lanes="
              f"{sorted((fanout or {}).keys() - {'enabled', 'postpack'})} · {rec['_push']}")
        if p:
            try:
                p.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
            except OSError:
                pass
        return rec
    except Exception as e:                       # noqa: BLE001 — law #1
        print(f"  📋 receipt skipped: {e}")
        return {"error": str(e)}

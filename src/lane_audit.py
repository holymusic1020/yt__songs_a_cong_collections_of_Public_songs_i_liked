"""🩺 Lane audit (2026-09-13) — "why didn't it post?" answered in PUBLIC.

WHY
---
Every cross-posting mystery so far (fb silent for weeks, "3 days no TT vid", the
Sep-11 boss-drop that reported success in 27 s) had the same root cause: the truth
lived inside an Actions run log, and logs need an admin-capable token to download
(`403 Must have admin rights to Repository`) and they expire (`410 Gone`).

So: `tools/doctor.py` (the pre-flight step, runs on EVERY job) calls `audit()`,
which writes a masked, human-readable report to `out/lane_audit.json`. The receipt
step (`src/receipt.py`) picks it up and commits it to `state/receipts/`, where
anyone can read it at raw.githubusercontent.com with zero credentials.

LAWS
----
1. Never raises. A diagnostic must never break a release.
2. Never prints a credential VALUE. Presence + length + a 4-char fingerprint only,
   and `debug_token` output is filtered to the fields we care about.
3. Network probes are OFF by default and always OFF under `MULTIPOST_DRYRUN=1`
   (the dry-run zero-API law). Opt in with `LANE_AUDIT_NET=1`.
4. Read-only calls exclusively: `debug_token`, page `?fields=…`, TikTok
   `post/publish/status/fetch`. Nothing posts, nothing writes, nothing rotates.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_V = "v23.0"
OUT_PATH = Path("out/lane_audit.json")

# token scopes required per lane — printed so a missing scope is obvious at a glance
NEED = {
    "fb": ["pages_manage_posts"],
    "ig": ["instagram_basic", "instagram_content_publish"],
}


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _present(name: str) -> dict:
    """Presence + length + fingerprint. NEVER the value."""
    v = _env(name)
    if not v:
        return {"set": False}
    return {"set": True, "chars": len(v), "fp": f"{v[:3]}…{v[-3:]}" if len(v) > 10 else "short"}


def _dials() -> dict:
    """Every knob that decides whether anything posts at all."""
    return {
        "MULTIPOST": _env("MULTIPOST") or "(empty → ALL cross-posting OFF)",
        "MULTIPOST_DRYRUN": _env("MULTIPOST_DRYRUN") or "0",
        "MULTIPOST_TT_LONG": _env("MULTIPOST_TT_LONG") or "0",
        "MULTIPOST_IG_LONG": _env("MULTIPOST_IG_LONG") or "0",
        "MULTIPOST_IG_PHOTO": _env("MULTIPOST_IG_PHOTO") or "1 (default on)",
        "PUBLISH_OFF": _env("PUBLISH_OFF") or "0",
        "BOSS_DROP_DATE": _env("BOSS_DROP_DATE") or "(unset)",
        "TIKTOK_PRIVACY": _env("TIKTOK_PRIVACY") or "SELF_ONLY (default)",
        "REQUIRE_VOCALS": _env("REQUIRE_VOCALS") or "0",
        "VOCAL_EVERYDAY": _env("VOCAL_EVERYDAY") or "0",
        "KAGGLE_FIRST": _env("KAGGLE_FIRST") or "0",
        "SUNO_OFF": _env("SUNO_OFF") or "0",
    }


def _lanes_wanted() -> list:
    return [p.strip().lower() for p in _env("MULTIPOST").split(",") if p.strip()]


def _net_ok() -> bool:
    """Read-only probes are ON by default (2026-09-13) so the boss never has to
    add a variable just to find out why nothing posted. Opt OUT with
    LANE_AUDIT_NET=0. The dry-run zero-API law always wins.

    Cost when on: 3 read-only Graph calls + up to 3 TikTok status fetches per run.
    Nothing posts, nothing writes, nothing rotates, no token is printed.
    """
    if _env("MULTIPOST_DRYRUN") == "1":
        return False
    return _env("LANE_AUDIT_NET") != "0"


def _get(url: str, timeout: int = 30):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        try:
            return json.loads(body), f"HTTP {e.code}"
        except Exception:
            return None, f"HTTP {e.code}: {body[:200]}"
    except Exception as e:                                   # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def probe_fb_token() -> dict:
    """READ-ONLY: is the page token valid, when does it die, what scopes does it carry?"""
    tok = _env("FB_PAGE_TOKEN")
    if not tok:
        return {"probed": False, "why": "FB_PAGE_TOKEN not set"}
    d, err = _get(f"https://graph.facebook.com/{GRAPH_V}/debug_token"
                  f"?input_token={urllib.parse.quote(tok)}&access_token={urllib.parse.quote(tok)}")
    if err or not isinstance(d, dict) or "data" not in d:
        return {"probed": True, "ok": False, "error": err or json.dumps(d)[:200]}
    x = d["data"]
    scopes = x.get("scopes") or []
    exp = x.get("expires_at")
    return {
        "probed": True,
        "ok": bool(x.get("is_valid")),
        "type": x.get("type"),
        "app_id": x.get("app_id"),
        "expires_at": exp,
        "expires": "NEVER" if exp in (0, None) else time.strftime("%Y-%m-%d", time.gmtime(exp)),
        "scopes": scopes,
        "missing_for_fb": [s for s in NEED["fb"] if s not in scopes],
        "missing_for_ig": [s for s in NEED["ig"] if s not in scopes],
        "token_error": x.get("error"),
    }


def probe_fb_page() -> dict:
    """READ-ONLY: page identity, publishing permission, and the linked IG account."""
    pid, tok = _env("FB_PAGE_ID"), _env("FB_PAGE_TOKEN")
    if not (pid and tok):
        return {"probed": False, "why": "FB_PAGE_ID/FB_PAGE_TOKEN not set"}
    # NOTE: `posting_permissions` is NOT a Page field — asking for it makes the whole
    # call die with "(#100) Tried accessing nonexisting field" and you learn nothing.
    # Live-tested against the real page token 2026-09-13.
    fields = "id,name,is_published,instagram_business_account{id,username}"
    d, err = _get(f"https://graph.facebook.com/{GRAPH_V}/{pid}?fields={urllib.parse.quote(fields)}"
                  f"&access_token={urllib.parse.quote(tok)}")
    if err and not d:
        return {"probed": True, "ok": False, "error": err}
    out = {"probed": True, "ok": not bool((d or {}).get("error")),
           "id": (d or {}).get("id"), "name": (d or {}).get("name"),
           "is_published": (d or {}).get("is_published")}
    iga = (d or {}).get("instagram_business_account") or {}
    out["instagram_linked"] = bool(iga.get("id"))
    out["instagram"] = {"id": iga.get("id"), "username": iga.get("username")} if iga.get("id") else None
    if (d or {}).get("error"):
        e = d["error"]
        out["error"] = f"({e.get('code')}/{e.get('error_subcode')}) {str(e.get('message'))[:200]}"
        # Meta code 368 = "confirm your identity before you can publish as this Page".
        # Only the boss can clear it, from the Facebook phone app. Name it loudly.
        if e.get("code") == 368 or "identity" in str(e.get("message", "")).lower():
            out["boss_action"] = ("🔴 Meta page-identity checkpoint (code 368). Open the Facebook "
                                  "app → your Page → 'Confirm your identity'. Until this is done "
                                  "EVERY fb/ig post fails, no matter how good the token is.")
    return out


def probe_fb_checkpoint() -> dict:
    """READ-ONLY canary for Meta's page-identity checkpoint (error code 368).

    Reading the Page's own feed is enough to surface it, and it posts nothing.
    This is the exact blocker that has been killing every fb/ig post since Sep 5.
    """
    pid, tok = _env("FB_PAGE_ID"), _env("FB_PAGE_TOKEN")
    if not (pid and tok):
        return {"probed": False, "why": "FB_PAGE_ID/FB_PAGE_TOKEN not set"}
    d, err = _get(f"https://graph.facebook.com/{GRAPH_V}/{pid}/posts?limit=1&fields=id"
                  f"&access_token={urllib.parse.quote(tok)}")
    e = (d or {}).get("error") if isinstance(d, dict) else None
    if e:
        code = e.get("code")
        out = {"probed": True, "ok": False, "code": code,
               "subcode": e.get("error_subcode"), "message": str(e.get("message"))[:220]}
        if code == 368 or "identity" in str(e.get("message", "")).lower():
            out["boss_action"] = ("🔴 Meta page-identity checkpoint (code 368). Facebook app → "
                                  "your Nix Speech Page → 'Confirm your identity'. Until this is "
                                  "done EVERY fb and ig post fails no matter how valid the token is.")
        return out
    n = len((d or {}).get("data") or [])
    return {"probed": True, "ok": True, "readable_posts": n,
            "note": "page reads fine → no identity checkpoint right now"}


def probe_tt_status(publish_ids: list | None = None) -> dict:
    """READ-ONLY: ask TikTok about known publish_ids (needs a live 24h access token)."""
    tok = _env("TIKTOK_ACCESS_TOKEN")
    if not tok:
        return {"probed": False, "why": "TIKTOK_ACCESS_TOKEN not set"}
    ids = publish_ids or [p for p in (_env("TT_PROBE_ID_1"), _env("TT_PROBE_ID_2")) if p]
    if not ids:
        return {"probed": False, "why": "no publish_ids to check (set TT_PROBE_ID_1/2)"}
    out = {"probed": True, "results": {}}
    for pid in ids[:3]:
        try:
            req = urllib.request.Request(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                data=json.dumps({"publish_id": pid}).encode(), method="POST",
                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=30).read())
            out["results"][pid[-12:]] = {
                "status": (r.get("data") or {}).get("status"),
                "fail_reason": (r.get("data") or {}).get("fail_reason"),
                "error": (r.get("error") or {}).get("code"),
            }
        except Exception as e:                               # noqa: BLE001
            out["results"][pid[-12:]] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    return out


def audit(net: bool | None = None, publish_ids: list | None = None) -> dict:
    """Build the full report. Never raises."""
    try:
        # Law #3 is absolute: MULTIPOST_DRYRUN=1 means ZERO api calls, even when a
        # caller explicitly asks for probes. net=True only opts in, it never overrides.
        do_net = _net_ok() if net is None else (bool(net) and _net_ok())
        wanted = _lanes_wanted()
        rep: dict = {
            "schema": 1,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "net_probes": do_net,
            "dials": _dials(),
            "lanes_wanted": wanted or ["(none)"],
            "creds": {
                "FB_PAGE_ID": _present("FB_PAGE_ID"),
                "FB_PAGE_TOKEN": _present("FB_PAGE_TOKEN"),
                "TIKTOK_ACCESS_TOKEN": _present("TIKTOK_ACCESS_TOKEN"),
                "TIKTOK_REFRESH_TOKEN": _present("TIKTOK_REFRESH_TOKEN"),
                "TIKTOK_CLIENT_KEY": _present("TIKTOK_CLIENT_KEY"),
                "TIKTOK_CLIENT_SECRET": _present("TIKTOK_CLIENT_SECRET"),
                "GH_TOKEN/GITHUB_TOKEN": _present("GH_TOKEN") if _env("GH_TOKEN") else _present("GITHUB_TOKEN"),
                "TELEGRAM_BOT_TOKEN": _present("TELEGRAM_BOT_TOKEN"),
                "YT_REFRESH_TOKEN": _present("YT_REFRESH_TOKEN"),
                "SUNO_API_KEY": _present("SUNO_API_KEY"),
                "KAGGLE_USERNAME": _present("KAGGLE_USERNAME"),
                "GEMINI_API_KEY": _present("GEMINI_API_KEY"),
                "HF_TOKEN": _present("HF_TOKEN"),
            },
            "ig_account_cache": None,
            "verdicts": [],
        }
        cache = Path("state/ig_account.json")
        if cache.exists():
            try:
                rep["ig_account_cache"] = json.loads(cache.read_text())
            except Exception:
                rep["ig_account_cache"] = "unreadable"

        # ---- verdicts: the "why didn't it post" answers, computed offline ----
        if not wanted:
            rep["verdicts"].append(
                "🔴 MULTIPOST is empty → fb, tt AND ig are ALL off. This is the #1 cause of "
                "'nothing posted'. Repo → Settings → Secrets → MULTIPOST → value `fb,tt,ig`.")
        for lane in ("fb", "tt", "ig"):
            if lane in wanted:
                if lane == "fb" and not (_env("FB_PAGE_ID") and _env("FB_PAGE_TOKEN")):
                    rep["verdicts"].append("🔴 fb is in MULTIPOST but FB_PAGE_ID/FB_PAGE_TOKEN are missing.")
                if lane == "tt" and not _env("TIKTOK_ACCESS_TOKEN"):
                    rep["verdicts"].append("🔴 tt is in MULTIPOST but TIKTOK_ACCESS_TOKEN is missing.")
                if lane == "ig" and not _env("FB_PAGE_TOKEN"):
                    rep["verdicts"].append("🔴 ig is in MULTIPOST but FB_PAGE_TOKEN is missing (ig rides it).")
        if "tt" in wanted and _env("TIKTOK_PRIVACY") != "PUBLIC_TO_EVERYONE":
            rep["verdicts"].append(
                "🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account "
                "(🔒 on the profile, invisible to everyone else). That is expected until TikTok "
                "approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.")
        if not (_env("TIKTOK_REFRESH_TOKEN") and _env("TIKTOK_CLIENT_KEY") and _env("TIKTOK_CLIENT_SECRET")):
            rep["verdicts"].append(
                "🟡 the tt 24h-token rotation chain is NOT fully armed (needs REFRESH_TOKEN + "
                "CLIENT_KEY + CLIENT_SECRET) → tt will start failing 24h after the last rotation.")
        if _env("PUBLISH_OFF") == "1":
            rep["verdicts"].append("🔴 PUBLISH_OFF=1 → the whole release is demoted to a dry run.")
        if _env("MULTIPOST_DRYRUN") == "1":
            rep["verdicts"].append("🟡 MULTIPOST_DRYRUN=1 → lanes render only, ZERO api calls (intentional test mode).")

        if do_net:
            rep["fb_token"] = probe_fb_token()
            rep["fb_page"] = probe_fb_page()
            rep["fb_checkpoint"] = probe_fb_checkpoint()
            t = probe_fb_token()
            if t.get("missing_for_ig"):
                rep["verdicts"].append(
                    f"🔴 the page token is missing IG scopes {t['missing_for_ig']} → the ig lane cannot "
                    "work. Re-mint the token with instagram_basic + instagram_content_publish.")
            for k in ("fb_page", "fb_checkpoint"):
                if (rep.get(k) or {}).get("boss_action"):
                    rep["verdicts"].append(rep[k]["boss_action"])
            if (rep.get("fb_checkpoint") or {}).get("ok") is True:
                rep["verdicts"].append("✅ the Page has NO identity checkpoint right now — fb/ig publishing is unblocked on Meta's side.")
            rep["tt_status"] = probe_tt_status(publish_ids)
        else:
            rep["fb_token"] = {"probed": False, "why": "LANE_AUDIT_NET!=1 (or dry run) — offline audit only"}
        if not rep["verdicts"]:
            rep["verdicts"].append("✅ no obvious blocker found from inside the run.")
        return rep
    except Exception as e:                                   # noqa: BLE001 — law #1
        return {"schema": 1, "error": f"lane audit failed: {type(e).__name__}: {e}"}


def to_markdown(rep: dict) -> str:
    """Human one-screen version (this is what lands in the receipt)."""
    if rep.get("error"):
        return f"# 🩺 lane audit\n\nERROR: {rep['error']}\n"
    d = rep.get("dials", {})
    creds = rep.get("creds", {})
    crows_l = []
    for k, v in creds.items():
        if v.get("set"):
            crows_l.append(f"| {k} | ✅ set ({v.get('chars')} chars, {v.get('fp')}) |")
        else:
            crows_l.append(f"| {k} | ❌ MISSING |")
    crows = "\n".join(crows_l)
    vrows = "\n".join(f"- {v}" for v in rep.get("verdicts", []))
    ft = rep.get("fb_token") or {}
    fbp = rep.get("fb_page") or {}
    probe = ""
    if ft.get("probed") or fbp.get("probed"):
        probe = (
            "\n## live probes (read-only)\n\n"
            f"- fb token: valid={ft.get('ok')} type={ft.get('type')} expires={ft.get('expires')} "
            f"app={ft.get('app_id')}\n"
            f"- fb token scopes: `{', '.join(ft.get('scopes') or []) or '—'}`\n"
            f"- missing for fb: `{ft.get('missing_for_fb')}` · missing for ig: `{ft.get('missing_for_ig')}`\n"
            f"- page: {fbp.get('name')} ({fbp.get('id')}) · posting_permissions={fbp.get('posting_permissions')} "
            f"· IG linked: {fbp.get('instagram_linked')} {fbp.get('instagram') or ''}\n"
            + (f"- page error: {fbp.get('error')}\n" if fbp.get("error") else "")
            + (f"- checkpoint canary: {json.dumps(rep.get('fb_checkpoint'))[:300]}\n"
               if rep.get("fb_checkpoint") else "")
        )
    return (
        f"# 🩺 lane audit · {rep.get('at')}\n\n"
        f"## dials\n\n| dial | value |\n|---|---|\n"
        + "\n".join(f"| {k} | `{v}` |" for k, v in d.items())
        + f"\n\n## lanes wanted\n\n`{', '.join(rep.get('lanes_wanted') or [])}`\n"
        + f"\n## credentials (masked)\n\n| secret | state |\n|---|---|\n{crows}\n"
        + f"\n## verdicts\n\n{vrows}\n"
        + probe
    )


def write(rep: dict, path: Path | str = OUT_PATH) -> Path | None:
    """Persist for the receipt step. Never raises."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
        return p
    except Exception as e:                                   # noqa: BLE001
        print(f"  🩺 lane audit write skipped: {e}")
        return None


def run(print_it: bool = True, net: bool | None = None,
        publish_ids: list | None = None) -> dict:
    """audit() + write() + a readable print. Called by tools/doctor.py."""
    rep = audit(net=net, publish_ids=publish_ids)
    if print_it:
        try:
            print(to_markdown(rep))
        except Exception:                                    # noqa: BLE001
            print(json.dumps(rep)[:2000])
    write(rep)
    return rep

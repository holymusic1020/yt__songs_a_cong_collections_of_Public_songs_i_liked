#!/usr/bin/env python3
"""v24 🧪 INSTAGRAM LANE + PUBLIC RECEIPT UT (2026-09-13)

Boss request: "why not we also connect our Instagram account also with this".
This suite proves the new `ig` lane and the receipt writer obey every law the
fb/tt lanes already obey — WITHOUT touching the network once.

 1. dry-run parity: MULTIPOST=fb,tt,ig + MULTIPOST_DRYRUN=1 → all three lanes
    report readiness, ZERO api calls (net sentry must stay silent)
 2. ig_reel with no creds (live path) → honest skip, no crash
 3. ig_discover(net=False) → never hits the network; honest "no cache" message
 4. ig caption law → NO http link (IG captions aren't clickable), ≤2200 chars
 5. postpack now inventories the cover art (ep999.png → media["cover"])
 6. container flow with a FAKE transport: container → poll(IN_PROGRESS→FINISHED)
    → publish, and the vault URL is what gets handed to Meta
 7. duration guard: a 200 s clip is refused as a Reel (3–90 s law), no api call
 8. receipt: build masks credentials, write creates json+md+history,
    mirror_into_state never explodes, commit_and_push declines without a token
 9. receipt state mirror does NOT rewrite episode/history keys (workflow owns them)

Run:  python tools/v24_ig_receipt_ut.py
"""
import json
import os
import urllib.error
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import multi_post, receipt  # noqa: E402

fails = 0
netmail: list = []


def chk(cond, label):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        fails += 1


def _install_sentry():
    import urllib.request as u

    def sentry(*a, **k):
        netmail.append(a)
        raise AssertionError("NETWORK TOUCHED — dry/offline law broken!")
    u.urlopen = sentry
    return sentry


class FakeHTTPError(Exception):
    def __init__(self, code, body):
        super().__init__(f"HTTP {code}")
        self.code = code
        self._body = body

    def read(self):
        return self._body.encode()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v24ut_"))
    os.chdir(tmp)                      # receipts write relative state/ paths
    for v in ("MULTIPOST", "MULTIPOST_DRYRUN", "FB_PAGE_ID", "FB_PAGE_TOKEN",
              "TIKTOK_ACCESS_TOKEN", "IG_USER_ID", "GH_TOKEN", "GITHUB_TOKEN",
              "MULTIPOST_IG_LONG", "MULTIPOST_IG_PHOTO", "RECEIPT_PUSH",
              "GITHUB_RUN_ID", "GITHUB_REPOSITORY"):
        os.environ.pop(v, None)

    meta = {"title": "Neon Puddle", "name": "Neon Puddle", "bpm": 142, "key": "F#m"}
    ep = 999
    (tmp / f"ep{ep:03d}_short.mp4").write_bytes(b"\x00" * 4096)
    (tmp / f"ep{ep:03d}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    print("\n1️⃣  dry-run parity — fb + tt + ig all report, zero network")
    _install_sentry()
    os.environ.update({"MULTIPOST": "fb,tt,ig", "MULTIPOST_DRYRUN": "1",
                       "FB_PAGE_ID": "dummy", "FB_PAGE_TOKEN": "dummy"})
    res = multi_post.fanout(ep=ep, meta=meta, genre_key="drift_phonk", out=tmp,
                            yt_vid=None, yt_sid=None)
    chk(res.get("enabled") is True, "fanout enabled under the dial")
    chk("fb" in res and "render-only" in str(res["fb"]), f"fb lane dry: {str(res.get('fb'))[:60]}")
    chk("tt" in res, f"tt lane dry: {str(res.get('tt'))[:60]}")
    chk("ig" in res and "render-only" in str(res["ig"]), f"ig lane dry: {str(res.get('ig'))[:70]}")
    chk("ig_photo" in res and "render-only" in str(res["ig_photo"]),
        f"ig photo lane dry: {str(res.get('ig_photo'))[:60]}")
    chk(not netmail, f"net sentry silent ({len(netmail)} calls)")

    print("\n2️⃣  live path, no creds → honest skip, never a crash")
    netmail.clear()
    os.environ.pop("MULTIPOST_DRYRUN")
    os.environ.pop("FB_PAGE_TOKEN")
    chk(multi_post.ig_reel(tmp / f"ep{ep:03d}_short.mp4", "cap") ==
        {"ig": "skipped — FB_PAGE_TOKEN not set (the reel lane rides the page token)"},
        "ig_reel skips on missing page token")
    chk(multi_post.ig_photo(tmp / f"ep{ep:03d}.png", "cap")["ig_photo"].startswith("skipped"),
        "ig_photo skips on missing page token")
    chk(not netmail, "still zero network")

    print("\n3️⃣  ig_discover(net=False) is offline-only + honest")
    netmail.clear()
    os.environ.update({"FB_PAGE_ID": "123", "FB_PAGE_TOKEN": "dummy"})
    d = multi_post.ig_discover(net=False)
    chk("error" in d and "no cached" in d["error"], f"no cache → honest message: {d.get('error','')[:60]}")
    (Path("state")).mkdir(exist_ok=True)
    Path(multi_post._IG_STATE).write_text(json.dumps({"id": "1784", "username": "nixspeech"}))
    d2 = multi_post.ig_discover(net=False)
    chk(d2.get("id") == "1784" and d2.get("username") == "nixspeech", "cache is used when present")
    os.environ["IG_USER_ID"] = "9999"
    chk(multi_post.ig_discover(net=False)["id"] == "9999", "IG_USER_ID pin wins")
    os.environ.pop("IG_USER_ID")
    chk(not netmail, "discovery made zero network calls in dry mode")

    print("\n4️⃣  caption law — no clickable link on Instagram")
    caps = multi_post.captions(meta, "drift_phonk", "abc123")
    chk("ig" in caps, "ig caption exists")
    chk("http" not in caps["ig"], f"NO url in the ig caption: {caps['ig'][:50]}…")
    chk("http" in caps["fb"], "fb caption still carries the yt link (unchanged)")
    chk(len(caps["ig"]) <= 2200, f"ig caption ≤2200 ({len(caps['ig'])})")
    chk(caps["ig"].startswith("Neon Puddle"), "title rides above the 125-char fold")

    print("\n5️⃣  postpack inventories cover art")
    pack = multi_post.build_postpack(tmp, ep, meta, "drift_phonk", None, None)
    chk("cover" in pack["media"], f"media keys: {sorted(pack['media'])}")
    chk("short" in pack["media"], "short still detected")

    print("\n6️⃣  container flow with a fake transport (no real network)")
    calls: list = []

    class FakeResp:
        def __init__(self, payload):
            self._p = json.dumps(payload).encode()

        def read(self):
            return self._p

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        data = req.data.decode() if getattr(req, "data", None) else ""
        calls.append((url.split("?")[0], data[:120]))
        if url.endswith("/media") or "/media?" in url:
            return FakeResp({"id": "CONTAINER_1"})
        if "fields=status_code" in url:
            fake_urlopen.polls += 1
            return FakeResp({"status_code": "IN_PROGRESS", "progress": "30"}
                            if fake_urlopen.polls < 2 else {"status_code": "FINISHED"})
        if url.endswith("/media_publish"):
            return FakeResp({"id": "MEDIA_777"})
        if "instagram_business_account" in url:
            return FakeResp({"instagram_business_account": {"id": "1784", "username": "nixspeech"}})
        if "releases/tags/bossdrop-stage" in url:
            return FakeResp({"id": 55, "assets": [{"name": "x", "id": 1}]})
        if "uploads.github.com" in url:
            return FakeResp({"browser_download_url": "https://github.com/o/r/releases/download/bossdrop-stage/f.mp4"})
        if "releases/assets/" in url:
            return FakeResp({})
        raise AssertionError(f"unexpected url {url}")
    fake_urlopen.polls = 0

    import urllib.request as u
    real = u.urlopen
    u.urlopen = fake_urlopen
    try:
        os.environ.update({"GH_TOKEN": "fake", "GITHUB_REPOSITORY": "o/r",
                           "FB_PAGE_TOKEN": "dummy"})
        Path(multi_post._IG_STATE).unlink(missing_ok=True)
        out = multi_post.ig_reel(tmp / f"ep{ep:03d}_short.mp4", caps["ig"])
    finally:
        u.urlopen = real
    chk(out.get("ig") == "published (reel)", f"ig_reel published: {out}")
    chk(out.get("ig_media_id") == "MEDIA_777", "media id returned")
    chk(out.get("ig_permalink", "").startswith("https://www.instagram.com/reel/"), "permalink built")
    chk(any("uploads.github.com" in c[0] for c in calls), "the mp4 went to the vault first")
    video_url = next((c[1] for c in calls if c[0].endswith("/media")), "")
    chk("video_url=https" in video_url and "media_type=REELS" in video_url,
        f"container got a PUBLIC video_url + REELS: {video_url[:90]}")
    chk(fake_urlopen.polls >= 2, f"polled the container to FINISHED ({fake_urlopen.polls} polls)")

    print("\n7️⃣  duration guard — a long clip is refused as a Reel")
    real_probe = multi_post._probe_seconds
    multi_post._probe_seconds = lambda p: 200.0
    try:
        guarded = multi_post.ig_reel(tmp / f"ep{ep:03d}_short.mp4", "cap")
    finally:
        multi_post._probe_seconds = real_probe
    chk("3–90s" in guarded.get("ig", ""), f"guard fired: {guarded.get('ig','')[:80]}")

    print("\n8️⃣  receipt — masking, files, history")
    started = os.times()[0]
    rec = receipt.build(ep=ep, meta=meta, genre_key="drift_phonk", kind="short",
                        vid="VID1", sid="SID1",
                        fanout={"enabled": True, "ig": "published (reel)",
                                "fb": "published", "fb_reel_id": "1",
                                "FB_PAGE_TOKEN": "EAAkgxSUPERSECRET",
                                "note": "bearer github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
                        started_at=started - 42, mode="publish")
    blob = json.dumps(rec)
    chk("SUPERSECRET" not in blob, "credential-shaped dict values are masked")
    chk("github_pat_" not in blob, "token-shaped strings are masked")
    chk(rec["lanes"].get("ig") == "published (reel)", "lanes captured")
    chk(rec["youtube"]["short"] == "https://youtu.be/SID1", "yt links built")
    p = receipt.write(rec, root=tmp)
    chk(p is not None and p.exists(), f"receipt json written: {p}")
    chk((tmp / "state/receipts/latest.md").exists(), "latest.md written")
    chk("EP.999" in (tmp / "state/receipts/latest.md").read_text(), "latest.md names the episode")
    hist = json.loads((tmp / "state/receipts/history.json").read_text())
    chk(len(hist) == 1 and hist[0]["episode"] == ep, "history.json seeded")
    receipt.write(rec, root=tmp)
    hist = json.loads((tmp / "state/receipts/history.json").read_text())
    chk(len(hist) == 1, f"same-day re-write does not duplicate ({len(hist)})")

    print("\n9️⃣  state mirror never eats the workflow's own keys")
    st = {"episode": 38, "history": [{"episode": 38}], "receipts": []}
    Path("state").mkdir(exist_ok=True)
    Path("state/state.json").write_text(json.dumps(st))
    chk(receipt.mirror_into_state(rec, "state/state.json") is True, "mirror ok")
    after = json.loads(Path("state/state.json").read_text())
    chk(after["episode"] == 38 and after["history"] == [{"episode": 38}], "episode/history untouched")
    chk(len(after["receipts"]) == 1, "receipt appended")
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("GH_TOKEN", None)
    os.environ.pop("RECEIPT_PUSH", None)
    chk("no token" in receipt.commit_and_push(tmp), "push declines cleanly without a token")
    os.environ["RECEIPT_PUSH"] = "0"
    chk("disabled" in receipt.commit_and_push(tmp), "RECEIPT_PUSH=0 honoured")

    print("\n🔟  record() never raises, even when everything is broken")
    os.environ.pop("RECEIPT_PUSH", None)
    bad = receipt.record(ep=None, meta=None, genre_key=None, kind=None, vid=None,
                         sid=None, fanout=None, started_at=None, root=tmp)
    chk(isinstance(bad, dict), f"record() returned a dict: {str(bad)[:70]}")

    print("\n1️⃣1️⃣  lane audit — masked, offline by default, verdicts computed")
    from src import lane_audit
    netmail.clear()
    _install_sentry()
    for v in ("MULTIPOST", "FB_PAGE_ID", "FB_PAGE_TOKEN", "TIKTOK_ACCESS_TOKEN",
              "TIKTOK_REFRESH_TOKEN", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
              "LANE_AUDIT_NET", "MULTIPOST_DRYRUN", "PUBLISH_OFF"):
        os.environ.pop(v, None)
    os.environ["GEMINI_API_KEY"] = "gem" + "m" * 30      # keep the env non-bare
    rep = lane_audit.audit(net=False)
    chk(rep.get("net_probes") is False, "net=False → offline audit")
    chk(not netmail, "offline audit touched zero network")
    chk("creds" in rep, "offline audit still returned the credential table")
    # (a credential must be visible or the bare-env guard rightly refuses to probe —
    #  that guard is tested on its own in section 0️⃣9️⃣)
    os.environ["FB_PAGE_TOKEN"] = "EAA" + "k" * 40
    os.environ["LANE_AUDIT_NET"] = "0"
    chk(lane_audit.audit().get("net_probes") is False, "LANE_AUDIT_NET=0 opts out")
    os.environ.pop("LANE_AUDIT_NET")
    _r_def = lane_audit.audit()
    chk(_r_def.get("net_probes") is True,
        "probes are ON by default (no variable needed)")
    chk(_r_def.get("authoritative") is True, "with a credential present the report is authoritative")
    os.environ.update({"FB_PAGE_ID": "123", "FB_PAGE_TOKEN": "EAAkgxDUMMYVALUE123456"})
    # NOTE: the probes swallow their own exceptions by design (law #1), so the sentry's
    # AssertionError never propagates — but it still RECORDS every attempt in netmail.
    r2 = lane_audit.audit()
    chk(bool(netmail), f"default-ON probes really fire when creds exist ({len(netmail)} call(s))")
    chk(r2.get("fb_token", {}).get("probed") is True, "fb_token probe ran")
    chk(r2.get("fb_page", {}).get("probed") is True, "fb_page probe ran")
    chk(r2.get("fb_checkpoint", {}).get("probed") is True, "code-368 canary ran")
    netmail.clear()
    for v in ("FB_PAGE_ID", "FB_PAGE_TOKEN"):
        os.environ.pop(v, None)
    _install_sentry()
    chk(any("MULTIPOST is empty" in v for v in rep["verdicts"]),
        f"names the #1 blocker: {rep['verdicts'][0][:70]}…")
    chk(rep["creds"]["FB_PAGE_TOKEN"] == {"set": False}, "missing cred reported as MISSING")
    os.environ.update({"MULTIPOST": "fb,tt,ig", "FB_PAGE_ID": "123",
                       "FB_PAGE_TOKEN": "EAAkgxSECRETTOKENVALUE1234567890",
                       "TIKTOK_ACCESS_TOKEN": "act.SECRETVALUE1234567890",
                       "TIKTOK_REFRESH_TOKEN": "rft.SECRETVALUE1234567890",
                       "TIKTOK_CLIENT_KEY": "ck_SECRET1234567890",
                       "TIKTOK_CLIENT_SECRET": "cs_SECRET1234567890"})
    rep = lane_audit.audit()
    blob = json.dumps(rep)
    for needle in ("EAAkgxSECRETTOKENVALUE", "act.SECRETVALUE", "rft.SECRETVALUE",
                   "ck_SECRET", "cs_SECRET"):
        chk(needle not in blob, f"value never leaked: {needle[:12]}…")
    chk(rep["creds"]["FB_PAGE_TOKEN"]["set"] is True and
        rep["creds"]["FB_PAGE_TOKEN"]["chars"] == len("EAAkgxSECRETTOKENVALUE1234567890"),
        "presence+length only")
    chk("…" in rep["creds"]["FB_PAGE_TOKEN"]["fp"], "fingerprint is a 3+3 stub")
    chk(rep["lanes_wanted"] == ["fb", "tt", "ig"], "dial parsed")
    chk(any("SELF_ONLY" in v for v in rep["verdicts"]), "warns TT posts land private")
    os.environ["MULTIPOST_DRYRUN"] = "1"
    chk(lane_audit.audit(net=True).get("net_probes") is False,
        "dry-run law beats an explicit net=True")
    chk(lane_audit.audit().get("net_probes") is False,
        "dry-run law beats the ON-by-default")
    os.environ.pop("MULTIPOST_DRYRUN")
    md = lane_audit.to_markdown(rep)
    chk("🩺 lane audit" in md and "MULTIPOST" in md, "markdown report renders")
    chk("EAAkgxSECRETTOKENVALUE" not in md, "markdown is masked too")
    wp = lane_audit.write(rep, Path("out/lane_audit.json"))
    chk(wp is not None and wp.exists(), f"audit persisted for the receipt step: {wp}")

    print("\n1️⃣2️⃣  receipt picks the audit up and shows verdicts in latest.md")
    rec2 = receipt.build(ep=ep, meta=meta, genre_key="drift_phonk", kind="short",
                         vid="V2", sid="S2", fanout={"enabled": True, "ig": "published (reel)"},
                         started_at=started - 7, mode="publish")
    chk("lane_audit" in rec2, "lane_audit folded into the receipt")
    receipt.write(rec2, root=tmp)
    md2 = (tmp / "state/receipts/latest.md").read_text()
    chk("🩺 lane audit" in md2, "latest.md carries the audit section")
    chk("MULTIPOST dial" in md2, "latest.md names the dial")

    print("\n0️⃣9️⃣  REGRESSION: the audit cried wolf in a step with no env (run #99, 2026-09-14)")
    from src import lane_audit as _la
    _saved = dict(os.environ)
    _canaries = list(_la._CRED_CANARIES) + ["MULTIPOST_DRYRUN", "TIKTOK_PRIVACY", "LANE_AUDIT_NET"]
    try:
        # ── A) bare env: exactly what the `🩺 Pre-flight doctor` step gets ──
        for k in _canaries:
            os.environ.pop(k, None)
        chk(_la._bare_env(), "bare env detected when no credential is visible")
        rep = _la.audit()
        chk(rep.get("authoritative") is False, "report flagged NOT authoritative")
        joined = " ".join(rep.get("verdicts", []))
        chk("MULTIPOST is empty" not in joined, "no false 'MULTIPOST is empty' alarm")
        chk("rotation chain" not in joined, "no false 'tt chain not armed' alarm")
        chk("NOT AUTHORITATIVE" in joined, "says honestly that it could not see anything")
        chk(rep.get("net_probes") is False, "no live probes fired without credentials")
        md = _la.to_markdown(rep)
        chk("NOT AUTHORITATIVE" in md, "and the receipt markdown carries the banner")

        # ── B) populated env: the real release step ──
        os.environ.update({"MULTIPOST": "fb,tt,ig", "FB_PAGE_ID": "123",
                           "FB_PAGE_TOKEN": "EAA" + "x" * 40, "TIKTOK_ACCESS_TOKEN": "act.ia" + "y" * 20,
                           "TIKTOK_REFRESH_TOKEN": "rft." + "z" * 20, "TIKTOK_CLIENT_KEY": "ck",
                           "TIKTOK_CLIENT_SECRET": "cs", "YT_REFRESH_TOKEN": "1//0" + "q" * 30,
                           "MULTIPOST_DRYRUN": "1"})
        chk(not _la._bare_env(), "populated env is NOT bare")
        rep2 = _la.audit()
        chk(rep2.get("authoritative") is True, "authoritative when secrets are present")
        j2 = " ".join(rep2.get("verdicts", []))
        chk("MULTIPOST is empty" not in j2, "dial fb,tt,ig → no empty-dial alarm")
        chk("rotation chain" not in j2, "all four TT creds present → chain reported armed")
        chk(_la._lanes_wanted() == ["fb", "tt", "ig"], f"lanes parsed: {_la._lanes_wanted()}")
        chk("MULTIPOST_DRYRUN=1" in j2, "dry-run law still announced")
        chk(rep2["dials"]["MULTIPOST"] == "fb,tt,ig", "dial value surfaced verbatim")
        for k, v in rep2["creds"].items():
            if v.get("set"):
                chk(v.get("chars", 0) > 0 and "…" in (v.get("fp") or "short") or v.get("fp") == "short",
                    f"cred {k} masked (fp only)")
        blob2 = json.dumps(rep2)
        chk("EAA" + "x" * 40 not in blob2, "the FB token value never appears in the report")
        chk("act.ia" + "y" * 20 not in blob2, "the TT token value never appears in the report")

        # ── C) the release step must actually call it (else the wolf returns) ──
        mn = (Path(__file__).resolve().parents[1] / "src" / "main.py").read_text()
        i_aud, i_rec = mn.index("AUTHORITATIVE lane audit"), mn.index("from src import receipt")
        chk(i_aud < i_rec, "main.py runs the audit BEFORE the receipt reads out/lane_audit.json")
        chk("_la.run(print_it=False, fanout=_fanout_result)" in mn,
            "and it re-runs the full audit WITH the real fanout result, overwriting the doctor's copy")
    finally:
        os.environ.clear()
        os.environ.update(_saved)

    print("\n1️⃣3️⃣  REGRESSION: the 24-wheel queue-cook hole (EP.039 log, 2026-09-14)")
    from src import main as _main, metadata as _md, composer as _cp
    rot = list(_main.GENRE_ROTATION)
    wheel = set(_md.NAME_BANKS)
    chk(len(rot) == 24, f"GENRE_ROTATION has 24 cells ({len(rot)})")
    chk(set(rot) == wheel, "rotation == metadata wheel (no drift)")
    chk(len(_cp.GENRES) < len(rot),
        f"composer.GENRES only holds {len(_cp.GENRES)} offline recipes — this is what the bug indexed")
    src_txt = (Path(__file__).resolve().parents[1] / "src" / "main.py").read_text()
    chk("keys = list(GENRE_ROTATION)" in src_txt, "queue cook now indexes the REAL wheel")
    chk("keys = list(composer.GENRES)" not in src_txt, "the buggy line is gone")
    # every one of the 24 genres must resolve a next genre, and it must be legal
    bad = []
    for i, g in enumerate(rot):
        nxt = rot[(rot.index(g) + 1) % len(rot)] if g in rot else rot[(i + 1) % len(rot)]
        if nxt not in wheel:
            bad.append((g, nxt))
    chk(not bad, f"all 24 genres resolve a legal next genre ({bad[:3]})")
    # the exact genre that crashed EP.039
    chk("lambs_teeth" in rot, "'lambs_teeth' is in the rotation now")
    nxt = rot[(rot.index("lambs_teeth") + 1) % len(rot)]
    chk(nxt == "god_in_the_bass", f"lambs_teeth → {nxt} (was a ValueError before)")
    # GENRE_LABEL coverage (the next hard-fail waiting to happen)
    import re as _re
    i = src_txt.index("GENRE_LABEL = {")
    depth = 0
    for k in range(i, len(src_txt)):
        if src_txt[k] == "{":
            depth += 1
        elif src_txt[k] == "}":
            depth -= 1
            if depth == 0:
                j = k
                break
    labels = set(_re.findall(r'"([A-Za-z_\x27]+)"\s*:', src_txt[i:j + 1]))
    chk(not (wheel - labels), f"GENRE_LABEL covers all 24 (holes: {sorted(wheel - labels)})")
    chk("GENRE_LABEL.get(nxt_genre" in src_txt, "and the lookup is a .get() now, never a [] KeyError")

    print("\n1️⃣5️⃣  REGRESSION: the vault 403 — GH_TOKEN shadowed GITHUB_TOKEN (run #100)")
    from src import main as _mn
    toks = multi_post.vault_tokens.__doc__ or ""
    chk("ROTATION LAW" in toks, "the rotation law is documented where the next reader will see it")
    _saved2 = dict(os.environ)
    try:
        os.environ.update({"GH_TOKEN": "dead-token", "GITHUB_TOKEN": "good-token",
                           "GITHUB_REPOSITORY": "o/r"})
        got = multi_post.vault_tokens()
        chk([l for l, _ in got] == ["GH_TOKEN", "GITHUB_TOKEN"], f"priority order: {[l for l,_ in got]}")
        os.environ["GH_TOKEN"] = "good-token"
        chk(len(multi_post.vault_tokens()) == 1, "identical tokens are de-duplicated")
        os.environ.update({"GH_TOKEN": "dead-token"})

        seen = []

        def vault_urlopen(req, timeout=None):
            u = req.full_url if hasattr(req, "full_url") else str(req)
            auth = (req.get_header("Authorization") or "")
            seen.append((u.split("?")[0][-34:], auth[-11:]))
            if "releases/tags/bossdrop-stage" in u:
                return FakeResp({"id": 77, "assets": []})
            if "uploads.github.com" in u:
                if "dead-token" in auth:
                    raise urllib.error.HTTPError(u, 403, "Forbidden", {}, None)
                return FakeResp({"browser_download_url":
                                 "https://github.com/o/r/releases/download/bossdrop-stage/ep040_short.mp4"})
            return FakeResp({})
        real_u = urllib.request.urlopen
        real_sleep = _mn.time.sleep
        urllib.request.urlopen = vault_urlopen
        _mn.time.sleep = lambda s: None
        try:
            f = tmp / "ep040_short.mp4"
            f.write_bytes(b"x" * 2048)
            urls = _mn._vault_release_asset([f])
            chk(len(urls) == 1 and urls[0].endswith("ep040_short.mp4"),
                f"upload succeeded after rotating off the 403 token: {urls}")
            toks_used = [a for _, a in seen if "uploads" not in a]
            chk(any("dead-token" in a for _, a in seen), "GH_TOKEN was tried first")
            chk(any("good-token" in a for _, a in seen), "then rotated to GITHUB_TOKEN")
            n403 = sum(1 for _, a in seen if "dead-token" in a and "uploads" in _)
            chk(sum(1 for u2, a in seen if "dead-token" in a) <= 2,
                "a 403 is NOT retried 3× on the same token (that was the waste)")
        finally:
            urllib.request.urlopen = real_u
            _mn.time.sleep = real_sleep

        print("\n1️⃣6️⃣  REGRESSION: the 368 canary lied (run #100 receipt vs its own fb lane)")
        from src import lane_audit as _la2
        ev = _la2._checkpoint_evidence({"fb": 'failed softly: {"code":368,"message":"Confirm your identity"}'})
        chk(bool(ev), f"368 detected in a fanout dict: {ev[:44]}")
        chk(bool(_la2._checkpoint_evidence('{"code": 368}')), "detected with a space after the colon")
        chk(bool(_la2._checkpoint_evidence("Confirm your identity before you can publish")),
            "detected from the message alone")
        chk(_la2._checkpoint_evidence({"fb": "posted ok"}) == "", "no false positive on a clean fanout")
        chk(_la2._checkpoint_evidence(None) == "", "and on no fanout at all")
        os.environ.update({"MULTIPOST": "fb,tt", "FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "EAA" + "b" * 40,
                           "MULTIPOST_DRYRUN": "1", "TIKTOK_ACCESS_TOKEN": "act.ia" + "c" * 20,
                           "TIKTOK_REFRESH_TOKEN": "rft." + "d" * 20, "TIKTOK_CLIENT_KEY": "ck",
                           "TIKTOK_CLIENT_SECRET": "cs"})
        r368 = _la2.audit(fanout={"fb": 'rejected: {"code":368}'})   # dry-run env: probes off
        j3 = " ".join(r368.get("verdicts", []))
        chk("FACEBOOK IDENTITY CHECKPOINT IS ACTIVE" in j3, "ground truth emits the 🔴")
        chk("NO identity checkpoint" not in j3, "and the canary's ✅ is REMOVED, not just outvoted")
        chk("phone app" in j3, "the verdict tells him exactly what to do")
        chk(r368.get("checkpoint_evidence"), "evidence recorded in the JSON too")
        r_ok = _la2.audit(fanout={"fb": "posted ok"})
        j4 = " ".join(r_ok.get("verdicts", []))
        chk("FACEBOOK IDENTITY CHECKPOINT IS ACTIVE" not in j4, "clean fanout → no 🔴")
        chk("FACEBOOK IDENTITY CHECKPOINT" not in j4, "clean fanout → no checkpoint 🔴")
    finally:
        os.environ.clear(); os.environ.update(_saved2)

    print("\n1️⃣4️⃣  REGRESSION: the vault retry law (EP.039 died on one SSL EOF)")
    mp_src = (Path(__file__).resolve().parents[1] / "src" / "multi_post.py").read_text()
    mn_src = src_txt
    chk("for attempt in range(1, 4)" in mp_src, "ig vault helper retries 3×")
    chk("for attempt in range(1, 4)" in mn_src, "main vault helper retries 3×")
    attempts = {"n": 0}

    def flaky(req, timeout=None):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("EOF occurred in violation of protocol (_ssl.c:2427)")
        return FakeResp({"browser_download_url": "https://github.com/o/r/releases/download/bossdrop-stage/ok.mp4"})
    import urllib.request as _u2
    real2 = _u2.urlopen
    _u2.urlopen = flaky
    real_sleep = multi_post.time.sleep
    multi_post.time.sleep = lambda s: None
    try:
        os.environ.update({"GH_TOKEN": "fake", "GITHUB_REPOSITORY": "o/r"})
        Path(multi_post._IG_STATE).write_text(json.dumps({"id": "1784", "username": "nixspeech"}))
        # _vault_public_url first GETs the release, so let that succeed then fail uploads
        calls2 = {"n": 0}

        def flaky2(req, timeout=None):
            u = req.full_url if hasattr(req, "full_url") else str(req)
            if "uploads.github.com" in u:
                return flaky(req, timeout)
            return FakeResp({"id": 55, "assets": []})
        _u2.urlopen = flaky2
        url = multi_post._vault_public_url(tmp / f"ep{ep:03d}_short.mp4")
        chk(url.endswith("ok.mp4"), f"upload survived 2 SSL EOFs then succeeded: {url[-40:]}")
        chk(attempts["n"] == 3, f"exactly 3 attempts ({attempts['n']})")
    finally:
        _u2.urlopen = real2
        multi_post.time.sleep = real_sleep

    print()
    if fails:
        print(f"❌ {fails} check(s) FAILED")
        sys.exit(1)
    print("✅ v24 IG+RECEIPT UT — ALL GREEN (zero network touched)")


if __name__ == "__main__":
    main()

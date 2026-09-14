# 📦 UPGRADE CARD — v25 "THE FOURTH DOOR + GLASS BOX" (2026-09-13)

Two features, both shipped through the `upgrades/` zip lane (no workflow edits, no new secrets).

---

## 1. 📸 Instagram lane (`ig`)

`src/multi_post.py` gains a fourth surface next to `fb` and `tt`.

| What posts | From | Guard |
|---|---|---|
| **Reel** | today's vertical short | 3–90 s duration check via ffprobe; too-long → refused with a reason, not a mystery 400 |
| **Photo** | today's cover art, PNG → **JPEG 1080×1350** | IG accepts JPEG only; `MULTIPOST_IG_PHOTO=0` disables |
| **Feed video** | the long 16:9 | **off by default** — `MULTIPOST_IG_LONG=1` enables |

Mechanics (Meta's container model):
1. `ig_discover()` → `GET /{FB_PAGE_ID}?fields=instagram_business_account{id,username}` using the
   **existing page token** → cached in `state/ig_account.json`. Optional pin: env `IG_USER_ID`.
2. `_vault_public_url()` parks the mp4/jpg in the **`bossdrop-stage` GitHub release** the engine already
   uses as its reel vault (creates the release on first use) → returns a public URL. Meta fetches it itself.
3. `POST /{igid}/media?media_type=REELS&video_url=…&caption=…&share_to_feed=true` → container id
4. poll `GET /{cid}?fields=status_code,progress,status` every 6 s until `FINISHED` (420 s cap; 900 s for the long)
5. `POST /{igid}/media_publish?creation_id=…` → media id + permalink printed to the log

Caption law: **no URL in IG captions** (they aren't clickable → pure spam signal). Title first,
hashtags last, "link in bio", ≤2200 chars. The fb/tt captions are untouched.

Laws inherited from the existing lanes and unit-tested: OFF unless `MULTIPOST` lists `ig` **and**
`FB_PAGE_TOKEN` exists · `MULTIPOST_DRYRUN=1` = zero API calls (discovery uses the cache only) ·
every failure soft-fails with Meta's real error body surfaced · credentials never printed.

**No App Review needed** — Standard Access covers the boss's own account (he's the app admin),
the same reason the fb lane works today.

**Boss side (one time, ~15 min):** IG → professional (**Creator**, not Business) → link to the Nix Speech
Page → re-mint `FB_PAGE_TOKEN` with `instagram_basic,instagram_content_publish` added →
`MULTIPOST` = `fb,tt,ig`. Full card: `IG_LINK_GUIDE.md`.

## 2. 📋 Public run receipts

**Problem this kills:** verifying "did fb/tt/ig actually post?" required downloading the Actions run log,
which answers `403 Must have admin rights to Repository` without an admin token — and logs expire
(`410 Gone`), which is how the v13 vocal-lane question became unanswerable forever.

**Fix:** every run writes its own truth into the repo and pushes it.

```
state/receipts/2026-09-13-ep039.json   full receipt (lanes, yt ids, timings, run url, sha, errors)
state/receipts/latest.md               one human screen
state/receipts/history.json            rolling last 40
```
Readable by anyone at `raw.githubusercontent.com/.../main/state/receipts/latest.md` — **no token, no
retention window**. A slim copy is also mirrored into `state/state.json["receipts"]` on disk so the
workflow's own state commit carries a second copy.

Safety laws (all unit-tested):
- **never raises** — a receipt problem cannot touch a release
- **never commits `state/state.json`** — the workflow's "Commit state" step owns that file; racing it is
  the duplicate-episode bug class from the ledger
- **never prints a credential** — keys named like secrets and token-shaped strings are masked at the door
- git identity set inline (`.git/config` doesn't survive sandbox rehydration), `pull --rebase` before push,
  explicit `HEAD:<branch>` (the detached-HEAD ghost-push lesson)
- `RECEIPT_PUSH=0` disables the push; no token in env → writes locally and says so

## 3. 🩺 Lane audit (new in v25) — "why didn't it post?" answered in public

`src/lane_audit.py` (new) is called by `tools/doctor.py`, which already runs as the pre-flight step of
every job. It reports, **with every credential masked to presence + length + a 3+3 fingerprint**:

- all 12 dials (`MULTIPOST`, `PUBLISH_OFF`, `TIKTOK_PRIVACY`, `BOSS_DROP_DATE`, `VOCAL_EVERYDAY`, …)
- which lanes the dial actually asks for, and whether each lane's credentials exist
- **computed verdicts** — the plain-English "here is why nothing posted" lines
- optional read-only live probes (`LANE_AUDIT_NET=1`, always off under `MULTIPOST_DRYRUN=1`):
  `debug_token` (valid? type? expiry? which scopes are missing for fb / for ig?), the Page node
  (name, published, **is an IG account linked?**), a **code-368 identity-checkpoint canary**
  (reads the Page's own feed — posts nothing), and TikTok `publish/status/fetch` for known ids.

`doctor.py` writes it to `out/lane_audit.json`; `src/receipt.py` folds it into the receipt and renders
the verdicts into `state/receipts/latest.md`. So after the next run, anyone can read the truth at
`raw.githubusercontent.com/.../main/state/receipts/latest.md` — **no token, no run log, no 403/410**.

Laws: never raises · never prints a credential value · read-only probes only · dry-run = zero API calls
even if a caller passes `net=True` (unit-tested).

Field-name bug found and fixed while live-testing: `posting_permissions` is not a Page field — asking
for it made the entire call die with `(#100) Tried accessing nonexisting field`.

## 4. 🧪 Tests

`tools/v24_ig_receipt_ut.py` — **63 checks, zero network** (a sentry raises on any `urlopen`):
dry-run parity across fb+tt+ig, offline discovery, caption law, cover-art inventory, the full
container→poll→publish flow against a fake transport, the duration guard, credential masking,
receipt files/history/state-mirror, push refusal.

Regression run at build time — **all green**:
`v14_chart_ut 139` · `v15_shortsync_ut 18` · `v16_beatcap_ut 14` · `v17_multipost_ut 13` ·
`v18_tables_ut 8` · `v19_kenburns_ut 8` · `v20_multipost_ut 8` · `v21_songdrop_ut 15` = **223 existing checks unaffected**.
Total on a simulated deploy: **286/286 green**.

## 5. Files in this zip

```
src/multi_post.py          +330 lines (ig lane + captions + postpack cover)
src/receipt.py             NEW (public receipts)
src/lane_audit.py          NEW (v25 — masked lane/dial/credential audit + read-only probes)
src/main.py                +33 lines (fanout capture + receipt splice at the tail)
tools/doctor.py            +13 lines (runs the lane audit on every job)
tools/v24_ig_receipt_ut.py NEW (63 checks)
state/receipts/.gitkeep    NEW
UPGRADE-CARD-v25.md        this file
IG_LINK_GUIDE.md           boss card for Instagram
```
No `.github/` files → the self-upgrade workflow applies everything (it skips `.github/` by design).

## 6. What still needs a human click (cannot ride a zip)

| Task | Why | Who |
|---|---|---|
| `MULTIPOST` → `fb,tt` (and later `fb,tt,ig`) | repo **secret**, unreadable/unwritable without an admin token | boss, 20 s |
| `FB_PAGE_TOKEN` re-mint with IG scopes | credential rotation + the public-Drive leak | boss, 8 min |
| FB Page identity checkpoint (Meta code 368) | page-level, phone-only | boss, 2 min |
| `git rm -r --cached incoming/kaggle_out/` | stale Aug-22 junk still tracked in the repo (gitignored but committed) → misleads forensics; needs a commit | boss upload or a PAT |
| `VOCAL_EVERYDAY` still `"1"` marked *TEMP* in `publish.yml` although ACE was ear-approved ("GOAT 🐐") on Aug 29 | workflow file | boss, 1 line |

## 7. Deploy

Repo → **Add file → Upload files** → drop `v24-ig-and-receipts.zip` into **`upgrades/`** → Commit.
The `🤖 self-upgrade` workflow unpacks, rsyncs (excluding `.git/`, `.github/`, `upgrades/`), deletes the
zip and commits. Then press **Run workflow** with `run_mode=dry_run`, `multipost_override=fb,tt,ig`,
`multipost_dryrun=1` and read `state/receipts/latest.md` — that's the proof, visible with no token.

For the live probes add repo variable `LANE_AUDIT_NET=1` (Variables tab) — then every real run also
reports token validity/expiry/scopes, IG-link status and the code-368 canary into the receipt.

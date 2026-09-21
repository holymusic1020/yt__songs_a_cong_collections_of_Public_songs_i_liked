# 📋 receipt · EP.048 · 2026-09-21

| | |
|---|---|
| track | **unlit lobby** (deep_pop) |
| mode | dry_run · short |
| youtube | — · short: — |
| multipost dial | `fb,tt,ig` |
| took | 314.3 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/35566744592 @ 9b7ae37 |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | render-only — would post reel ~7.8 MB (credentialed ✓): unlit lobby — Nix Speech (official audio) 🌙 
#lyrics #vibes … |
| ig | render-only — would post REEL ~7.8 MB to @unknown until the live run (32.5s ✓ ) |
| ig_photo | render-only — would post the cover art (~1580 KB → JPEG 1080×1350) |
| tt | render-only — would upload ~7.8 MB (SELF_ONLY law): unlit lobby — Nix Speech (official audio) #lyrics #vibes #ne… |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 MULTIPOST_DRYRUN=1 → lanes render only, ZERO api calls (intentional test mode).

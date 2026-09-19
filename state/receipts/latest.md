# 📋 receipt · EP.047 · 2026-09-19

| | |
|---|---|
| track | **warm kitchen tiles** (lofi) |
| mode | dry_run · short |
| youtube | — · short: — |
| multipost dial | `fb,tt,ig` |
| took | 403.0 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/35438934078 @ 9208bbb |

## lanes

| lane | result |
|---|---|
| fb | render-only — would post reel ~7.1 MB (credentialed ✓): warm kitchen tiles — Nix Speech (official audio) 🌙 
#lyrics … |
| ig | render-only — would post REEL ~7.1 MB to @unknown until the live run (33.8s ✓ ) |
| ig_photo | render-only — would post the cover art (~1528 KB → JPEG 1080×1350) |
| tt | render-only — would upload ~7.1 MB (SELF_ONLY law): warm kitchen tiles — Nix Speech (official audio) #lyrics #vi… |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 MULTIPOST_DRYRUN=1 → lanes render only, ZERO api calls (intentional test mode).

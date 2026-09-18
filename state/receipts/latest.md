# 📋 receipt · EP.045 · 2026-09-18

| | |
|---|---|
| track | **wet asphalt steam** (dark_ambient) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/HVdwxKDDd2g |
| multipost dial | `fb,tt,ig` |
| took | 1424.7 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/35351560179 @ 888b05e |

## lanes

| lane | result |
|---|---|
| fb | failed softly: fb api «m/v23.0/1294240837106632/video_reels» rejected: {"error":{"message":"Confirm your identity before you can publish as this Page. |
| ig | failed softly: ig container still POLL_ERROR after 420s (progress None) |
| tiktok_publish_id | v_pub_file~v2-1.7686871279869642759 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🔴 FACEBOOK IDENTITY CHECKPOINT IS ACTIVE — code 368 / 'Confirm your identity' appeared on a real publish attempt this run. A read-only canary cannot see this (Meta only enforces it on writes), so ignore any ✅ or 🟡 it printed. FIX: Facebook **phone app** → ☰ → your Nix Speech Page → 'Confirm your identity' banner → follow it. Until then EVERY fb and ig post is rejected with code 368 and nothing you change in the code or the tokens helps.

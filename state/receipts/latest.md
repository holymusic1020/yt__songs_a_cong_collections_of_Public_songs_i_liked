# 📋 receipt · EP.041 · 2026-09-15

| | |
|---|---|
| track | **subway charcoal** (anime_titan) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/y2HsLPgxBWA |
| multipost dial | `fb,tt` |
| took | 1083.2 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/34940084658 @ 08ecb8f |

## lanes

| lane | result |
|---|---|
| fb | failed softly: fb api «m/v23.0/1294240837106632/video_reels» rejected: {"error":{"message":"Confirm your identity before you can publish as this Page. |
| tiktok_publish_id | v_pub_file~v2-1.7685656162372536340 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt` · lanes wanted: `fb, tt`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🔴 the page token is missing IG scopes ['instagram_basic', 'instagram_content_publish'] → the ig lane cannot work. Re-mint the token with instagram_basic + instagram_content_publish.
- 🔴 FACEBOOK IDENTITY CHECKPOINT IS ACTIVE — code 368 / 'Confirm your identity' appeared on a real publish attempt this run. A read-only canary cannot see this (Meta only enforces it on writes), so ignore any ✅ or 🟡 it printed. FIX: Facebook **phone app** → ☰ → your Nix Speech Page → 'Confirm your identity' banner → follow it. Until then EVERY fb and ig post is rejected with code 368 and nothing you change in the code or the tokens helps.

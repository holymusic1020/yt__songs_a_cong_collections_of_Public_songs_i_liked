# 📋 receipt · EP.080 · 2026-10-28

| | |
|---|---|
| track | **damp fire escape** (lofi) |
| mode | publish · full |
| youtube | https://youtu.be/KUhh385ME80 · short: https://youtu.be/p6Loh5dXIiA |
| multipost dial | `fb,tt,ig` |
| took | 1429.0 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/40727069688 @ b3d4a5c |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122122164819453777 |
| fb_video | published |
| fb_video_id | 4080084658795256 |
| ig | published (reel) |
| ig_media_id | 17950619682341834 |
| ig_photo | published |
| ig_photo_id | 18082778945385529 |
| ig_user | nixspeech |
| ig_video | off — set MULTIPOST_IG_LONG=1 to also post the long video to IG |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The chunk size is invalid","log_id":"2026102900461223BABF5B46824E2B20CA"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

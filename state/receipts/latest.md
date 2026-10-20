# 📋 receipt · EP.072 · 2026-10-20

| | |
|---|---|
| track | **lilac ruin** (deep_pop) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/pxZEQyALNwY |
| multipost dial | `fb,tt,ig` |
| took | 328.8 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/39443462234 @ a872c3e |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122120233659453777 |
| ig | published (reel) |
| ig_media_id | 18101847932335058 |
| ig_photo | published |
| ig_photo_id | 18094356746464941 |
| ig_user | nixspeech |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The total chunk count is invalid","log_id":"202610202259078524B00F16916A280A69"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

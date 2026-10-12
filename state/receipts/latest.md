# 📋 receipt · EP.065 · 2026-10-12

| | |
|---|---|
| track | **zinc skyline frost** (anime_titan) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/vErLcsyc02I |
| multipost dial | `fb,tt,ig` |
| took | 788.2 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/38299661663 @ fbab91d |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122118179385453777 |
| ig | published (reel) |
| ig_media_id | 18077912330434456 |
| ig_photo | published |
| ig_photo_id | 18128144116873512 |
| ig_user | nixspeech |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The chunk size is invalid","log_id":"20261013035729297383B2C1598744491F"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

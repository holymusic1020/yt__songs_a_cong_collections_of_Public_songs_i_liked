# 📋 receipt · EP.071 · 2026-10-19

| | |
|---|---|
| track | **fading hallway bulb** (lofi) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/t9zpXn16t10 |
| multipost dial | `fb,tt,ig` |
| took | 6869.6 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/39289496917 @ d471887 |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122120033109453777 |
| ig | published (reel) |
| ig_media_id | 18022170887927579 |
| ig_photo | published |
| ig_photo_id | 17895057390681212 |
| ig_user | nixspeech |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The total chunk count is invalid","log_id":"20261020023835AD6CBF706A89AAA38A2D"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

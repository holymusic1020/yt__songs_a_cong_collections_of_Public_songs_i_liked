# 📋 receipt · EP.067 · 2026-10-14

| | |
|---|---|
| track | **halogen balcony** (skyline_anthem) |
| mode | publish · full |
| youtube | https://youtu.be/yV8B-jVyoAA · short: https://youtu.be/xc675c7CAvk |
| multipost dial | `fb,tt,ig` |
| took | 1232.1 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/38511134473 @ 971ea11 |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122118541317453777 |
| fb_video | published |
| fb_video_id | 1682111036775427 |
| ig | published (reel) |
| ig_media_id | 18128032133500387 |
| ig_photo | published |
| ig_photo_id | 18115887572051344 |
| ig_user | nixspeech |
| ig_video | off — set MULTIPOST_IG_LONG=1 to also post the long video to IG |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The chunk size is invalid","log_id":"202610141239345A010F005DF1B6099145"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

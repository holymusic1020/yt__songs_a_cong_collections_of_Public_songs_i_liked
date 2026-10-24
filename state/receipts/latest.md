# 📋 receipt · EP.076 · 2026-10-24

| | |
|---|---|
| track | **three am radiator** (melodic_trap) |
| mode | publish · full |
| youtube | https://youtu.be/AMBxYfMX8fs · short: https://youtu.be/rDhKYc7MocU |
| multipost dial | `fb,tt,ig` |
| took | 354.4 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/40100280527 @ abd41af |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122121184365453777 |
| fb_video | published |
| fb_video_id | 974374645723206 |
| ig | published (reel) |
| ig_media_id | 18078308474430763 |
| ig_photo | published |
| ig_photo_id | 18170708542465561 |
| ig_user | nixspeech |
| ig_video | off — set MULTIPOST_IG_LONG=1 to also post the long video to IG |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The total chunk count is invalid","log_id":"202610242201498A256B94B7AD45D53675"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

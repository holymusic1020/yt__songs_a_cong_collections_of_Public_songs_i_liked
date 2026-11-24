# 📋 receipt · EP.095 · 2026-11-24

| | |
|---|---|
| track | **copper pipe hum** (lofi) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/m3X937kc7qo |
| multipost dial | `fb,tt,ig` |
| took | 309.7 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/45482346773 @ e0db047 |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122128205259453777 |
| ig | published (reel) |
| ig_media_id | 18107847275571926 |
| ig_photo | published |
| ig_photo_id | 17888122965625389 |
| ig_user | nixspeech |
| tiktok_publish_id | v_pub_file~v2-1.7711839928505813010 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

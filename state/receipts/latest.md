# 📋 receipt · EP.082 · 2026-10-30

| | |
|---|---|
| track | **marzipan elegy** (deep_pop) |
| mode | publish · full |
| youtube | https://youtu.be/8p2-IQ8hQnY · short: https://youtu.be/mnz_SGrV1mY |
| multipost dial | `fb,tt,ig` |
| took | 369.1 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/41091768068 @ 8ee843a |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122122671633453777 |
| fb_video | published |
| fb_video_id | 1770612130682812 |
| ig | published (reel) |
| ig_media_id | 18198820798390963 |
| ig_photo | published |
| ig_photo_id | 18146711890572375 |
| ig_user | nixspeech |
| ig_video | off — set MULTIPOST_IG_LONG=1 to also post the long video to IG |
| tiktok_publish_id | v_pub_file~v2-1.7702502405431134214 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

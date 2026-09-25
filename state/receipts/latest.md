# 📋 receipt · EP.052 · 2026-09-25

| | |
|---|---|
| track | **silk slander** (melodic_trap) |
| mode | publish · full |
| youtube | https://youtu.be/4Tk-tCNPPH4 · short: https://youtu.be/z5LVB-sUqN4 |
| multipost dial | `fb,tt,ig` |
| took | 1926.8 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/36152029950 @ 64360e0 |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122112645669453777 |
| fb_video | published |
| fb_video_id | 1594096058830778 |
| ig | published (reel) |
| ig_media_id | 18147448459553239 |
| ig_photo | published |
| ig_photo_id | 18074744015450372 |
| ig_user | nixspeech |
| ig_video | off — set MULTIPOST_IG_LONG=1 to also post the long video to IG |
| tiktok_publish_id | v_pub_file~v2-1.7689494902832613396 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

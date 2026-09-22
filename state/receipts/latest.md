# 📋 receipt · EP.049 · 2026-09-22

| | |
|---|---|
| track | **cloverleaf drizzle** (drift_phonk) |
| mode | publish · full |
| youtube | https://youtu.be/8RIjyRqE1lY · short: https://youtu.be/G7IqfCfmnXE |
| multipost dial | `fb,tt,ig` |
| took | 2624.6 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/35741700710 @ 23e27eb |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122111543349453777 |
| fb_video | published |
| fb_video_id | 2318715722217348 |
| ig | published (reel) |
| ig_media_id | 18099447785620699 |
| ig_photo | published |
| ig_photo_id | 17888633361460532 |
| ig_user | nixspeech |
| ig_video | off — set MULTIPOST_IG_LONG=1 to also post the long video to IG |
| tiktok_publish_id | v_pub_file~v2-1.7688373403313080338 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

# 📋 receipt · EP.085 · 2026-11-14

| | |
|---|---|
| track | **cold hallway tile** (saint_of_leaving) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/6lHnLPKP1gg |
| multipost dial | `fb,tt,ig` |
| took | 549.5 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/43615857108 @ c87e477 |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122126159007453777 |
| ig | published (reel) |
| ig_media_id | 18022795802954039 |
| ig_photo | published |
| ig_photo_id | 18214148836364885 |
| ig_user | nixspeech |
| tiktok_publish_id | v_pub_file~v2-1.7708067034248120340 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

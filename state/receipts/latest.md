# 📋 receipt · EP.060 · 2026-10-05

| | |
|---|---|
| track | **fumaça de diesel** (brazilian_phonk) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/xjd7h1cZe20 |
| multipost dial | `fb,tt,ig` |
| took | 1858.2 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/37361601479 @ 20cac7b |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122115958455453777 |
| ig | published (reel) |
| ig_media_id | 17960394165212647 |
| ig_photo | published |
| ig_photo_id | 17949840663338631 |
| ig_user | nixspeech |
| tiktok_publish_id | v_pub_file~v2-1.7693267568869787654 |
| tt | uploaded → DRAFT (boss publishes in-app) |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

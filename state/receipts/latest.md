# 📋 receipt · EP.079 · 2026-10-27

| | |
|---|---|
| track | **fogged balcony glass** (lofi) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/UbgJB5UKzCs |
| multipost dial | `fb,tt,ig` |
| took | 1524.9 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/40534783733 @ 0b3b93d |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122121930375453777 |
| ig | published (reel) |
| ig_media_id | 18139976812625734 |
| ig_photo | published |
| ig_photo_id | 18030428213691013 |
| ig_user | nixspeech |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The chunk size is invalid","log_id":"20261028000324C9603A2876F58023E04D"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

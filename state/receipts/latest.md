# 📋 receipt · EP.068 · 2026-10-15

| | |
|---|---|
| track | **tallow on velvet** (baroque_waltz) |
| mode | publish · short |
| youtube | — · short: https://youtu.be/998WLndTn5g |
| multipost dial | `fb,tt,ig` |
| took | 868.8 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/38754862899 @ 821994c |

## lanes

| lane | result |
|---|---|
| dsp | off — DSP_PACK=0 — streaming packs off |
| fb | published |
| fb_reel_id | 122118978165453777 |
| ig | published (reel) |
| ig_media_id | 18157094944518716 |
| ig_photo | published |
| ig_photo_id | 18007010484031580 |
| ig_user | nixspeech |
| tt | rejected 400: {"error":{"code":"invalid_params","message":"The total chunk count is invalid","log_id":"202610152304017F88332C95721D9D9734"}} |

## 🩺 lane audit

MULTIPOST dial: `fb,tt,ig` · lanes wanted: `fb, tt, ig`

- 🟡 tt posts as SELF_ONLY (pre-approval law) → they land PRIVATE on the account (🔒 on the profile, invisible to everyone else). That is expected until TikTok approves the app, then flip repo var TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE.
- 🟡 the read-only canary saw no checkpoint flag — but it CANNOT prove you are unblocked (run #100: clean canary, real post still rejected with code 368). Trust the fb lane result in this receipt, not this line.

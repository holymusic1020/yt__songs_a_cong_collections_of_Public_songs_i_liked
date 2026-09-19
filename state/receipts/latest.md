# 📋 receipt · EP.046 · 2026-09-19

| | |
|---|---|
| track | **orbit receipt** (orbit_trap) |
| mode | publish · full |
| youtube | https://youtu.be/YVu8GvCqxXY · short: https://youtu.be/RFl1xDI4ea0 |
| multipost dial | `fb,ig` |
| took | 2856.9 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/35426016550 @ 3131ce4 |

## lanes

| lane | result |
|---|---|
| fb | failed softly: fb api «m/v23.0/1294240837106632/video_reels» rejected: {"error":{"message":"Confirm your identity before you can publish as this Page. |
| ig | failed softly: ig container still POLL_ERROR after 420s (progress None) last={"status_code": "POLL_ERROR", "status": "HTTP Error 400: Bad Request"} |

## 🩺 lane audit

MULTIPOST dial: `fb,ig` · lanes wanted: `fb, ig`

- 🔴 FACEBOOK IDENTITY CHECKPOINT IS ACTIVE — code 368 / 'Confirm your identity' appeared on a real publish attempt this run. A read-only canary cannot see this (Meta only enforces it on writes), so ignore any ✅ or 🟡 it printed. FIX: Facebook **phone app** → ☰ → your Nix Speech Page → 'Confirm your identity' banner → follow it. Until then EVERY fb and ig post is rejected with code 368 and nothing you change in the code or the tokens helps.

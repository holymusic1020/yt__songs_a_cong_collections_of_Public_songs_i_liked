# 📋 receipt · EP.040 · 2026-09-14

| | |
|---|---|
| track | **deep voice amen** (god_in_the_bass) |
| mode | publish · full |
| youtube | https://youtu.be/pnIuriTyu80 · short: https://youtu.be/kBY5AP9ju3Y |
| multipost dial | `fb` |
| took | 1736.6 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/34865319067 @ 90f5cb8 |

## lanes

| lane | result |
|---|---|
| fb | failed softly: fb api «m/v23.0/1294240837106632/video_reels» rejected: {"error":{"message":"Confirm your identity before you can publish as this Page. |

## 🩺 lane audit

MULTIPOST dial: `fb` · lanes wanted: `fb`

- 🔴 the page token is missing IG scopes ['instagram_basic', 'instagram_content_publish'] → the ig lane cannot work. Re-mint the token with instagram_basic + instagram_content_publish.
- ✅ the Page has NO identity checkpoint right now — fb/ig publishing is unblocked on Meta's side.

# 📋 receipt · EP.040 · 2026-09-14

| | |
|---|---|
| track | **harbor diesel** (god_in_the_bass) |
| mode | dry_run · full |
| youtube | — · short: — |
| multipost dial | `fb,tt,ig` |
| took | 992.7 s |
| run | https://github.com/holymusic1020/yt__songs_a_cong_collections_of_Public_songs_i_liked/actions/runs/34801715133 @ 793e185 |

## lanes

| lane | result |
|---|---|
| fb | render-only — would post reel ~6.6 MB (credentialed ✓): harbor diesel — Nix Speech (official audio) 🌙 
#lyrics #vibe… |
| fb_video | render-only — would post video ~17.3 MB |
| ig | render-only — would post REEL ~6.6 MB to @unknown until the live run (30.9s ✓ ) |
| ig_photo | render-only — would post the cover art (~1641 KB → JPEG 1080×1350) |
| ig_video | render-only — would post feed VIDEO ~17.3 MB |
| tt | render-only — would upload ~6.6 MB (SELF_ONLY law): harbor diesel — Nix Speech (official audio) #lyrics #vibes #… |

## 🩺 lane audit

MULTIPOST dial: `(empty → ALL cross-posting OFF)` · lanes wanted: `(none)`

- 🔴 MULTIPOST is empty → fb, tt AND ig are ALL off. This is the #1 cause of 'nothing posted'. Repo → Settings → Secrets → MULTIPOST → value `fb,tt,ig`.
- 🟡 the tt 24h-token rotation chain is NOT fully armed (needs REFRESH_TOKEN + CLIENT_KEY + CLIENT_SECRET) → tt will start failing 24h after the last rotation.

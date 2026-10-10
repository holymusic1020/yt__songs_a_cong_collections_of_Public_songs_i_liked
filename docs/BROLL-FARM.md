# 🎬 The b-roll farm — real moving video, without the song ever waiting for it

Boss, 2026-10-10: *"why not we set a very powerful local vid renderer … if it takes 1h for a 5 sec
vid, then in 24*3 h we get 24*3*5 sec of video … no need to worry about shorts, shorts r just short
versions of long vid … we can pause/checkpoint vid render while using other work … BUTTT main goal
is song. and set all kinda api keys as fallback … if u want to run super hyper biggest vid renderer
local model on kaggle or smtg, u should think really hard so it doesnt effect to my song even an inch."*

This is the whole answer, in that order.

## 0. First, the measurement (because the premise was "2-3 days")

A release is **not** 2-3 days. From the Actions API, just now, on the live repo:

| run | created | wall clock |
|---|---|---|
| `yt-auto · publish episode` | 2026-10-09 16:55 UTC | **13 min** |
| `yt-auto · publish episode` | 2026-10-01 16:58 UTC | **35 min** |

Song + master + subtitles + b-roll art + YouTube upload + FB/IG/TikTok in thirteen minutes. The
thing that costs 2-3 days is *nothing* in this pipeline — so a heavy renderer would not be buying
speed, it would be buying **picture quality**, and it would have to be paid for out of the same
Kaggle GPU wallet the vocals drink from. That reframes everything below: this is a quality feature,
built as a library, so it can never become a schedule.

## 1. Why a farm and not a live render

`super hyper biggest renderer` (HunyuanVideo 13B, Wan 14B) needs 24-40 GB of VRAM and
**~4-25 min per 5 seconds** of footage [1][2][3]. A 3-minute video needs ~30 cuts → 2.5-12 GPU-hours
per release, on a free account capped at **30 h/week, 12 h/session**, which is the exact quota the
ACE-Step vocal lane already uses. Run it live and one bad night = no song. That is the failure the
boss told me to design against, so:

```
GPU (Kaggle, 22:00 UTC nightly, ≤3 h, ≤9 h/week)      GH runner (10:00 UTC, 13-35 min)
        ┌───────────────────────────┐                 ┌──────────────────────────┐
        │ Wan2.1-1.3B → 8s clips    │  release asset  │ src/broll.py  → plan()   │
        │ normalise 1080p/24/h264   ├────────────────►│   ├─ clips → from_clips() │
        │ manifest.json, self-kill  │  broll-<g>.tar.xz│   └─ empty → from_images│
        └───────────────────────────┘                 └──────────────────────────┘
                 shelf grows silently                    song never waits, never blocks
```

* **Publishing never generates.** It downloads at most one genre archive (byte cap 220 MB, 90 s wall
  clock) and if anything at all is off — no archive, corrupt, too few clips, slow CDN, no ffmpeg —
  `broll.plan()` returns `[]` and the video renders **exactly** the way EP.001→EP.063 rendered.
* **The song keeps the GPU.** `tools/broll_farm.py` keeps its own ledger (`quota.json` on the release)
  and refuses to start when the rolling 7-day farm spend would cross `BROLL_WEEK_HOURS` (default 9
  of the 30 h free allowance; vocals need ~1.5-2 h/week). No lock is shared with the vocal kernel, no
  temp dir is shared, and `publish.yml` does not know this workflow exists (UT-36 #25 asserts it).
* **A failed shelf is not an alarm.** Every exit path in the farm driver is `exit 0` with one line of
  reason — a red ❌ on a decorative feature would train us both to ignore the real ones.

## 2. The model choice, with the trade-off stated out loud

| model | VRAM | speed (5 s clip) | licence | in this farm? |
|---|---|---|---|---|
| **Wan 2.1 1.3B** [1][2] | 8-16 GB, fits a T4 | ~3-6 min on T4 | **Apache-2.0 → monetisable** | ✅ the workhorse |
| LTX-Video 700M [5] | 8 GB | <1-2 min | Apache-2.0 | optional (`BROLL_MODEL`) — softer, faster |
| Wan 2.1 14B [1] | 16-24 GB (quant) | 15-40 min | Apache-2.0 | ⚠ only 2-3 hero shots/week, never nightly |
| HunyuanVideo 13B [2][5] | 24-40 GB | 20-60 min | community licence | ❌ free tier cannot host it, licence is murky |

The 1.3B renders at 832×480 and the farm upscales to 1920×1080 with lanczos, so a clip is **soft on a
phone screen** — acceptable *because our frames are backgrounds behind karaoke text and the mascot*;
it is not acceptable as the hero shot of a music video. Hence the ladder: generated b-roll under the
text, never instead of the cover art, never instead of the subtitle layer. If a genre's shelf is empty
you get the Ken Burns stills, which are genuinely good and cost 0 GPU minutes.

## 3. Shorts: he is right, with one exception

`shorts.py` already cuts the vertical from the long render's own lyric timing, and the background now
rides the same bpm grid (v23.8) — so the short *is* a short version of the long video. What it cannot
be is a **crop of the finished 16:9 master**: our subtitles, the title card and the mascot are
positioned for 1920×1080, and cropping 16:9→9:16 after burning text cuts the words in half. Reusing
the *source material* (clips, lyric lines, chorus position) is the cheap and correct version of his
idea, and that's what the code does.

## 4. "Set all kinda api keys as fallback" → `src/keys.py`

Any service now reads a **pool**: `GEMINI_API_KEY`, `GEMINI_API_KEY_2` … up to `_6`, or a comma list
inside one secret. Wired into `art_gemini`, `copy_ai`, `video_gemini`, `music_lyria` (Gemini) and
`music_suno` (Suno); `lane_audit` reports how many keys a service has, never which. Add a dead key's
replacement as `_2` and the lane keeps working without a code change. Kaggle stays single-account on
purpose: rotating accounts would silently rotate the GPU quota the song lane depends on.

## 5. Dials

| dial | default | meaning |
|---|---|---|
| `BROLL` | `1` | release side may use the shelf. `0` = never look at it |
| `BROLL_FETCH` | `1` | allow the one-time archive download (`0` = only what's already in the workspace) |
| `BROLL_MAX_MB` | `220` | hard byte cap on that download |
| `BROLL_FARM` | `1` | farm workflow on/off |
| `BROLL_HOURS` | `3` | GPU hours per session (kernel self-kills at the line) |
| `BROLL_WEEK_HOURS` | `9` | rolling 7-day ceiling, so the vocals always win |

Sources: crepal.ai open-source video generators 2026 [1], ltx.io best open-source video models [2],
videotoprompt model comparison [3], apatero VRAM/speed table [4], videodubber licence/feature matrix [5].

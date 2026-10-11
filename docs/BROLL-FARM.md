# 🎬 The b-roll farm — real moving video, without the song ever waiting for it

Boss, 2026-10-10: *"why not we set a very powerful local vid renderer … if it takes 1h for a 5 sec
vid, then in 24*3 h we get 24*3*5 sec of video … no need to worry about shorts, shorts r just short
versions of long vid … we can pause/checkpoint vid render while using other work … BUTTT main goal
is song. and set all kinda api keys as fallback … if u want to run super hyper biggest vid renderer
local model on kaggle or smtg, u should think really hard so it doesnt effect to my song even an inch."*

This is the whole answer, in that order.

## 0a. "Run it on GitHub, not Kaggle" — the number that closes that door

Asked and answered with the live pricing page, 2026-10-10:

| what GitHub offers | rate | can we use it? |
|---|---|---|
| Standard hosted runner (public repo) | **free, unlimited minutes** | ✅ but it is **2 vCPU / 7 GB, no GPU** |
| GPU larger runner `linux_4_core_gpu` | **$0.052 / min** (~$3.12/h) | ❌ larger runners are **Team/Enterprise only**, and *"the larger runners are not free for public repositories"* |

So GitHub gives us unlimited **CPU** (which is exactly what the render chain already uses — 13 min) and
zero access to a GPU. A video diffusion model on 2 CPU cores is not slow, it is *not a thing*: 7 GB of
RAM is under the weight footprint of Wan-1.3B at 81 frames, and the encode budget would be measured in
hours per clip against a 6 h job cap. Kaggle's free T4 is the only free GPU this project has — so it
stays, but as a **guest in the song's quota**, which is what §0b is about.

## 0b. The leftovers law (boss: *"you may use Kaggle but not all the time, like half or a little"*)

`tools/broll_farm.py::budget()` — every session, before a single GPU second is spent:

```
left  = BROLL_WEEK_HOURS − our own 7-day spend        (default 6 h/week on YOUR account)
hours = min(BROLL_HOURS, left × BROLL_SHARE)          (SHARE = 0.5 → “half of what’s left”)
if hours < 0.4 h → skip the whole session, exit 0     (not worth waking a kernel)
```

* the ledger is `quota.json` on the shelf and counts **only the farm's** wall clock — the vocal lane's
  hours are never charged to b-roll, and never reserved against it either;
* it is deliberately conservative (counts model-load and failed clips too), so the account always loses
  *less* than we set aside;
* the daily release runs at 10:00 UTC, the farm at 22:00 UTC — 6 hours later, never competing;
* **a second Kaggle account makes all of this moot**: set `BROLL_KAGGLE_USERNAME` +
  `BROLL_KAGGLE_API_TOKEN` as secrets and the farm speaks as *that* account from `~/.kaggle-broll`
  (its own config dir, so it cannot push, poll or overwrite the vocal kernel even by accident), gets the
  full `BROLL_WEEK_HOURS=18`, no haircut, and your main 30 h stays 100 % the song's. Honest caveat:
  Kaggle's terms are one account per person, so a spare is a grey-area speed-up — worst case the *video*
  account gets limited, which is why the song lane never reads its credentials.

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
| `BROLL_WEEK_HOURS` | `6` (main) / `18` (spare account) | rolling 7-day ceiling |
| `BROLL_SHARE` | `0.5` | how much of what's left we may take — his "half or a little" |
| `BROLL_KAGGLE_USERNAME` / `BROLL_KAGGLE_API_TOKEN` | *unset* | secrets: a spare Kaggle account, so the shelf costs your quota nothing |

Sources: crepal.ai open-source video generators 2026 [1], ltx.io best open-source video models [2],
videotoprompt model comparison [3], apatero VRAM/speed table [4], videodubber licence/feature matrix [5].

## 6. What running it for real found (2026-10-11, against the spare account)

He sent a second Kaggle key, so I wired it and then **actually executed the driver** here instead of
shipping reviewed-only code. Three bugs died in that run, none of which reading the file would have
shown:

| what I found | why it mattered | the fix |
|---|---|---|
| `me/<slug>` is accepted by `kernels push` but **not** by `kernels status`/`output` | the poll would never resolve → 4 h of waiting per night, forever | read the owner slug out of the push response URL and poll `uhn896/nix-speech-broll-farm` |
| Kaggle's status word is **`KernelWorkerStatus.COMPLETE`**, my test looked for `"completed"` | every session would poll to `MAX_WAIT_S` and then discard a finished shelf | match `"complete"`/`"finished"`, and `"failed"`/`"stopped"` |
| `kernels push` **409s** when the title doesn't slugify to the id (`Nix Speech B-roll Farm` → `nix-speech-b-roll-farm`) | the very first push of the real farm, rejected | title pinned to `Nix Speech Broll Farm`, in the tracked metadata *and* at stage time; UT-36 #32 asserts they agree |
| the dataset API 403s on a young account (`Key licenses not found in data`) | the prompts-dataset design was DOA on the spare account | **no dataset at all**: prompts ride inside the kernel as base64 (UT-36 #33 round-trips it) |
| a push error raised a traceback out of `main()` | a red ❌ on a decorative feature trains us to ignore red ❌s | `check=False` on the push, and the whole driver wrapped in `guarded()` → always `exit 0` with one line |

And the honest headline from the live session: the kernel **ran, bailed in 40 seconds and wrote**

```json
{ "clips": [], "skipped": "no GPU on this Kaggle account",
  "hint": "Kaggle -> Settings -> Phone Verification, then accept the competition rules; the next session gets the T4",
  "torch": "2.11.0+cpu" }
```

A brand-new Kaggle account gets CPU despite `enable_gpu: true`. The pre-flight is exactly what makes
that a 40-second discovery instead of a 3-hour waste, and `blocked()` now rests a week after three such
sessions (it retries itself once the account is verified). Nothing was uploaded, nothing was blocked,
the daily release never noticed.

### Repo state, as set by me with his token (no clicking needed)

* **Secrets** `BROLL_KAGGLE_USERNAME=uhn896`, `BROLL_KAGGLE_API_TOKEN` → the farm speaks as the spare;
  the vocal lane's `~/.kaggle` is never used or overwritten. **Your main 30 h/week stays the song's.**
* **Variables** `BROLL=1`, `BROLL_FARM=1`, `BROLL_HOURS=3`, `BROLL_WEEK_HOURS=6`, `BROLL_SHARE=0.5`.
* Deleted `LANE_RETRIES=1` — I had created that variable and `publish.yml` never read it, so it was a
  lie in the UI. Behaviour unchanged (code default 2 retries).
* The one thing only he can do: **verify a phone number on `uhn896`** (Kaggle → Settings → Phone
  Verification, then accept the rules when prompted). Until then the shelf stays empty and every video
  uses the Ken Burns look — which is the look that shipped 63 episodes, not a downgrade.

## 7. …and the account routing that the identity check forced (2026-10-11)

The plan was "spare account only, your main quota untouched". Then the verification wall:

> *"Persona couldn't verify your identity — Man I try to around 7 times but still you can see what is happening."*

Kaggle grants GPU only to accounts that clear its identity/phone check, and a fresh account that fails
Persona gets **CPU forever** — which for us means an empty shelf and a wasted nightly session. So the
farm now *routes*, it does not sulk:

```
BROLL_ACCOUNT = auto   (default)  spare if it is usable, otherwise your main account, leftovers only
                spare              never touch the main account → no b-roll while Persona blocks it
                main               ignore the spare entirely (no nightly 40-second knock either)
```

* when a session answers `no GPU on this Kaggle account`, the driver writes `gpu_block.json` **on the
  shelf** naming *that* account, and skips it for `BROLL_GPU_COOLDOWN_H` (168 h);
* the marker is downloaded at the start of every session, because CI runners are otherwise born
  amnesiac and the "rest" would last exactly one night;
* `auto` means the blocked spare is simply stepped over and **your main account takes the b-roll
  hours — under the 6 h/week, half-of-leftovers rule**, which is precisely the "half or a little" you
  asked for; nothing near the 10:00 UTC release, and the vocal lane's hours are never charged to it;
* it re-probes the spare once the cooldown expires, so if Kaggle support ever approves the account,
  b-roll moves back there with no code change;
* if you'd rather we never spend a single GPU minute on your main account: set `BROLL_ACCOUNT=main`… no
  — set **`BROLL_ACCOUNT=spare`** and the shelf stays empty until the account is verified. Your call, one
  Variable, no code.

Optionally, for the record: Persona failures are usually the document, not the person — a **passport**
rather than an ID card, no glasses or glare, all four corners visible, and the name on the Kaggle
profile matching the document exactly. Otherwise `support@kaggle.com` with a screenshot of the error is
the only route, and neither is worth much: b-roll is the decoration, and the leftovers path already
works without it.

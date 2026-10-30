# 🎛 CONTROL PANEL — every switch in the machine

Boss asked (2026-09-19): *"give me a clue whenever I have to turn something on or off."*
This is that clue. Every dial, what it does, where it lives, and the exact one-line change.

**Two ways to flip almost anything:**

- **Way A — no code, 30 seconds (recommended):** GitHub → repo `yt-auto` → **Settings** →
  **Secrets and variables** → **Actions** → **Variables** tab → *New repository variable* →
  name + value. A Variable always beats the code default. Delete the Variable → back to default.
- **Way B — code:** open the file, **Ctrl+F the search string given below**, change one number,
  commit. Takes effect on the next run.

Nothing in this file needs a rebuild, a reinstall, or a restart. The engine re-reads everything
at the start of each daily run.

---

## 🌀 1. The dimensional moment (spin) — **ON**, but only for needy songs

What it does: one 12-second window of the song slowly orbits left↔right (±20°), crossfaded at
both edges. Earbuds hear "the song opened up". Phone speakers hear nothing wrong (mono-safe,
measured 0.52 dB worst case).

**The taste gate is what keeps it rare** — it fires only when BOTH are true:
1. the song's genre is on the allow-list (`dark_ambient`, `lofi`, `orbit_trap`), and
2. the window is almost entirely instrumental (≤25% sung) — the voice stays dead centre, always.

It weighs the song's **distinct loud sections** (the drop, the break, the outro) and takes the first
instrumental one. So on a lofi track with a sung hook, the moment lands on the track's own **break**
instead of never happening at all. If every loud section is sung, that song gets no orbit and the
log says why. Proved by `tools/v32_spin_window_ut.py`.

| Want to… | Where | Do this |
|---|---|---|
| **Turn it OFF forever** | Way A (no code) | New Variable `SPIN` = `0` |
| Turn it OFF for **one run only** | Actions → *publish* → Run workflow | field **spin** = `0` |
| Turn it back ON | Way A | delete the `SPIN` Variable (or set `1`) |
| Change the **default in code** | `.github/workflows/publish.yml` ~line 170 — search `SPIN: "${{ vars.SPIN` | last number `1` → `0` |
| **Which genres** may orbit | `src/spin.py` ~line 89 — search `ALLOW_GENRES` | add/remove a name: `{"dark_ambient", "lofi", "orbit_trap"}` |
| **How strict** about vocals | `src/spin.py` ~line 90 — search `VOCAL_MAX` | `0.25` = strict · `0.10` = stricter · `0.40` = looser |
| **How strong** the orbit is | `src/spin.py` ~line 39 — search `DEPTH =` | `0.25` gentle · **`0.35` current** · `0.45` obvious. **Do not go past 0.50** — the phone-speaker test fails above that |
| **How long** the moment lasts | `src/spin.py` ~line 42 — search `WIN_S` | seconds, `12.0` current |
| How fast it orbits | `src/spin.py` ~line 41 — search `RATE` | Hz, `0.18` = one circle per ~5.5 s |

**Proof in the daily log** — one of these lines always prints:
```
🌀 spin: this one earns it — dimensional moment 19.5s → 31.5s (lofi, 0% sung, ±20° orbit)
🌀 spin: skipped — disco_house doesn't earn an orbit (vocal-driven)
🌀 spin: skipped — window is 58% sung; the voice stays centre
```

---

## 🔉 2. Loudness match — **ON**
Every song lands at **-14 LUFS / -1 dB true-peak** (YouTube/Spotify/TikTok standard), so nothing
sounds quieter than the next video. Level only — tone and structure untouched.

- **OFF:** Way A → Variable `LOUDNORM` = `0` (or `publish.yml` ~line 171, search `LOUDNORM: "${{ vars.LOUDNORM`, last `1` → `0`).
- **ON again:** delete the Variable.
- Log proof: `🔉 loudness: -14.0 LUFS · TP -1.0 dB` per song.

## 🔔 3. The opening "ting-tong" chime — **OFF (killed)**
The 0.75 s station chime at the head of every video is dead by default (`CHIME_OFF=1`).

- **Bring it back:** Way A → Variable `CHIME_OFF` = `0`.
- **Kill again:** `CHIME_OFF` = `1`.
- Log proof: `🔔 sonic logo stamped` appears only when it's on.

## 🎤 4. Vocals required — **ON, hardwired**
A real release **refuses to publish an instrumental**. `publish.yml` ~line 137 — search
`REQUIRE_VOCALS`. Leave it at `"1"`. Setting `"0"` would allow voiceless songs through; don't.

## 🎬 5. Shorts: the hook window must be a **sung** window — **ON, no dial**
Fixed 2026-09-19 after your report ("subtitles, no vocals"). The short's 30 s are now picked
where the karaoke map says singing actually happens, so caption cards always quote lines you hear.
- Log proof: `🎤 hook vocal coverage: 78% (best available in track: 84%)`
- If that number is ever low, tell me — that's the alarm bell.

---

## 🛑 6. MASTER SWITCH — parks everything
Variable `PUBLISH_OFF` = `1` → the daily cron still runs, renders and reports, but **uploads
nothing** (YouTube, Facebook, TikTok, Instagram all parked). Delete the Variable → live again.
This is the "stop the machine today" button. No code change ever needed.

## 🌐 7. Which platforms post (lane list)
Secret **or** Variable `MULTIPOST`, value = comma list.
- Current: `fb,tt,ig` (Facebook reel · TikTok draft · Instagram reel + cover photo)
- Drop TikTok only → `fb,ig` · Everything off → delete/empty it.
- Extra lanes, all **OFF** by default, each its own Variable:
  - `MULTIPOST_TT_LONG=1` → the full 16:9 video also rides TikTok (blurred pillarbox)
  - `MULTIPOST_IG_LONG=1` → the full video also posts to the Instagram feed
  - `MULTIPOST_IG_PHOTO=0` → stop the Instagram cover-photo post (it's ON today)

## 🧪 8. Test mode — render only, zero API calls
Variable `MULTIPOST_DRYRUN` = `1` → every platform lane renders the file and reports what it
*would* post, but calls nothing. Delete → real posting resumes. Use it whenever you want to watch
a full pipeline run without anything going public.

## ▶ 9. The Run-workflow button (manual runs)
Actions → **📀 publish** → *Run workflow*:
- **run_mode** = `dry_run` (nothing uploads, you get a preview on Telegram) or `publish` (real release)
- **multipost_override** = e.g. `fb,tt` for that one run
- **multipost_dryrun** = `1` for that one run
- **spin** = `0` to skip the orbit for that one run

---

## 📦 10. Streaming delivery (Spotify / Apple Music) — **PARKED (off) since 2026-09-21**

Boss's call: RouteNote has no artist API, so the last step is always a human pasting a form —
*"then OK we will leave it."* Channel stays on YouTube / TikTok / Facebook / Instagram.
**Want it back:** repo Variable `DSP_PACK` = `1`. That is the entire switch — packer, rights gate,
artwork, lyrics, provenance, Telegram line and the 90-day artifact all wake up together.
When it's off, the run logs one line and carries on: `📦 DSP pack: skipped — DSP_PACK=0 — streaming packs off`.
Full guide (still accurate): [DSP-ROUTE-NOTE / SPOTIFY-APPLE-GUIDE.md](SPOTIFY-APPLE-GUIDE.md).

**Reality check, once and for all:** there is no API anywhere in the free path. RouteNote has no
artist API at all — a human fills their web form, ~8 minutes per song, and no code of ours can
change that. The engine's job is to make those 8 minutes pure copy-paste with zero decisions.
Full step-by-step: **[`docs/SPOTIFY-APPLE-GUIDE.md`](SPOTIFY-APPLE-GUIDE.md)**. Every full song
cooked by a legally sellable lane gets a delivery box zipped at `out/dsp/epNNN-dsp-pack.zip`
(audio + 3000×3000 art + metadata + copy-paste sheet + lyrics + rights provenance), shipped as the
run's `episode-latest` artifact. Nothing uploads itself — a distributor is mandatory, and the free
no-card one we picked is RouteNote (15% of royalties).

| Want to… | Do this |
|---|---|
| Stop building packs | Variable `DSP_PACK` = `0` |
| Make **every** song streamable | Variable `DSP_SAFE_FIRST` = `1` — commercial-safe lanes cook first. ⚠️ a different model sings, so the sound can change; test with a dry run first (`dsp_safe_first=1`) |
| Change the DSP artist name | Variable `DSP_ARTIST` |
| Change the songwriter credit | Variable `DSP_WRITER` (defaults to the artist name) |
| Change the release lead time | Variable `DSP_LEAD_DAYS` (default 21 days) |

The zip waits in the Actions run → artifact **`dsp-pack`** (90 days, public repo = free
storage). The pack ships the **un-branded** artwork (no frame / "OFFICIAL AUDIO" chip / EP number —
stores reject borders and overlay text); the video thumbnail keeps them. Its label field is the
artist name, never "Independent" — RouteNote rejects that word. Telegram carries one line, and it is *informational only* — a refused night is never
counted as a failed platform:
```
📦 Spotify pack  ✅ ep049-dsp-pack.zip · 41.3 MB · release 2026-10-16
📦 Spotify pack  ➖ short-only day — streaming gets full songs, not shorts
```
Log proof: `📦 DSP pack: ep047-dsp-pack.zip · 3.9 MB · lane=ace-kaggle (Apache-2.0)` or
`📦 DSP pack: skipped — rights: lane 'suno' is not commercial-safe`.

## 🔁 11. One release per day — **automatic**, dial `RELEASE_GAP_H` (17)
If a real release already went out today (your clock, BDT) — a manual run, a rescue, a boss drop —
the evening cron **parks itself** and ships nothing. Log line:
```
🔁 EP.46 already published today (BDT) — one release per day, so the cron demotes itself to a dry-run.
```
Why it exists: GitHub's scheduler fires this cron **3–6 hours late** most days (measured over 10
runs), so a midday release used to leave the evening slot free to ship a second episode — two
uploads, two TikToks, two reels in one day. Your Run-workflow button is never blocked by this:
that's your own hand.

**v23.7 — the law measures the GAP, not the calendar day.** Measured on live receipts: GitHub fires this
cron so late that a run finishing after 18:00 UTC lands on the *next* BDT date, so the following evening
read "already released today" and parked a perfectly good slot. EP.054 (shipped 09-29 00:37 BDT) cost
the 09-29 slot; EP.060 (10-06 01:44 BDT) cost the 10-06 slot. Two releases a fortnight, stolen by a
timezone boundary, with the episode number re-used the next day.

| Dial | Where | What it means |
|---|---|---|
| `RELEASE_GAP_H` | repo **Variables**, default `17` | hours a real release owns the slot. A normal nightly pair is 19–22 h apart, a real double-ship is 1–6 h apart, so 17 separates them cleanly. Set `24` to return to the old strictness, `12` to allow two a day |

## 📅 12. Daily time — **16:00 BDT (requested)** · lands ~19:30–22:00 BDT in practice
`.github/workflows/publish.yml` ~line 27 — search `cron:`. It reads `0 10 * * *` (UTC).
Dhaka is UTC+6, so `10` = 16:00. Want 18:00 BDT → `0 12 * * *`. Want 09:00 BDT → `0 3 * * *`.
Formula: **UTC hour = BDT hour − 6.**

⚠️ **Honest measurement (2026-09-19):** GitHub does not run crons on the minute. The last 10
scheduled runs were set for 09:23 UTC and actually started at 12:55, 13:38, 13:40, 13:46, 13:49,
14:14, 14:19, 14:21, 15:55 UTC — i.e. **3 h 32 m to 6 h 32 m late, average 4 h 39 m**. That is
GitHub's queue, not our code, and it cannot be turned off. So the real upload times have been
**~19:30–22:00 BDT**, not 16:00.
If you want the video to actually *appear* near 16:00 BDT, set the cron to
`0 5 * * *` (05:00 UTC = 11:00 BDT) and the usual delay lands it at ~15:30–17:30 BDT.
Say the word and I'll move it; until then it stays at the time you asked for.

## 🐐 13. Your own song drops
Two Variables together: `BOSS_DROP_DATE` = a date like `2026-09-26` and `BOSSDROP_ARMED` = `1`.
That day the engine parks its own slot and the boss-drop workflow takes over. Clear the date →
engine resumes normal duty.

## 🌍 14. Small extras (all optional, all OFF unless set)
- `POSTS_OFF=1` → silence the YouTube community post packs
- `WORLD_TOUR_EVERY=N` → every Nth episode ships a foreign-language version; `WORLD_LANGS` = list
- `SHORT_SFX=1` → chirp sound effects on short caption flips (**OFF** by your order, 2026-09-15)
- `LOOP_OFF=1` → no seamless loop-back tail on shorts · `MASCOT_OFF=1` → no NYX on the cover

---

## ✍️ 15. The songwriting core (v23.7 — "songs have no hype")

Boss, 2026-10-09: the last releases had no hook, the lines did not rhyme with each other, and nothing
came back at the end. All three were true in the code, and this is where you fix them from now on.

| What you want to change | Where | How |
|---|---|---|
| **The hook (chorus) of a genre** | `src/sung_banks.py` — search `"<genre>": (` | 4 lines. Lines 1+2 must end on the same vowel sound and 3+4 too (AABB). `tools/v35_hype_ut.py` checks every couplet — run it after editing |
| **The bridge of a genre** | same tuple, the 2 lines after the chorus | must rhyme with each other |
| **Verse material** | `src/sung_banks.py` — search `VERSE_COUPLETS` | each entry is one rhymed couplet; the engine takes 4 different couplets per song (2 per verse) |
| **Shorts caption lines** | `src/lyrics.py` — search `LINES = {` | unchanged, still one bank per genre |
| **The rules a lyric must pass** | `src/craft.py` — search `def gate` | `min_rate=0.5` is the rhyme bar. `0.7` = stricter, `0.35` = looser |
| **How hard Gemini is pushed** | `src/copy_ai.py` — search `CRAFT = (` | the brief the songwriter obeys. Keep rule 5 (the callback) unless you want to lose the ending-match feeling |

**How it flows on a real day:** Gemini writes → `craft.gate` judges → miss = one targeted rewrite with the
exact problems listed → still bad = the banks above. Never a crash, never a skipped release. The run log
now says the verdict out loud:
```
✍️  craft: couplet rhyme 9/10 = 90% · 23 sung lines · median 8 syllables · gate PASSED
```
Two guard-rails on purpose: the gate is **English only** (an English rhyme dictionary would wrongly fail
Portuguese/Spanish World-Tour lyrics), and the title being sung is a **soft note**, never a blocker.

## 🥁 16. Beat-cut editing — `BEATCUT` (**ON** since 2026-10-09)

`src/video_render.py`. Four Gemini scene images used to sit for 43 seconds each over a 172-second song —
one crossfade a minute, nothing landing on the chorus. With `BEATCUT=1` (repo **Variable**):

* cut length = a whole number of bars (`bar_s(bpm)`, 2 bars by default, clamped to 2.5–12 s),
* **a cut is placed exactly on the chorus** (`metadata.chorus_start()` reads it off the karaoke map —
  no guessing, so if the map is missing the graph just keeps its old timing),
* the scene set cycles, so the frame changes every few seconds instead of freezing,
* colour/saturation lift over the chorus window (`eq` with `enable='between(t,…)'`, timeline-safe).

**Armed by default on purpose** (boss, 2026-10-09: *"no need for a dry run… upload straight to the
channel"*), but with a hard safety net: when the beat layout is on, the **untouched pre-v23.7 graph is
appended as a third and fourth ffmpeg variant**, so `_run_variants` always has the exact old command set to
fall back to. Worst case a video looks like last week's; it cannot come out black or missing. `tools/v35`
block 14 proves both halves (4 variants armed → `[29, 29, 4, 4]` inputs; `BEATCUT=0` → 2 variants, `[4, 4]`).

Kill switch: **`BEATCUT=0`** (repo Variable) → exactly the graph that shipped EP.062. `KB_STILL=1` still
overrides motion entirely, and the short's background now rides the same bpm grid.

## 🎬 17. B-roll scene per genre — `src/video_gemini.py`

`SCENES` now carries **one environment per wheel genre** (it had 9 while the wheel had 24, so 15 genres
were all quietly getting the same dark-ambient fog shot). Environments only — no people, no faces, no text —
that is the anti-plastic law and `tools/v35_hype_ut.py` block 15c enforces it. Add a genre to the wheel and
you must add its scene here, or you get the fallback.

## 🏷 18. Titles stop recycling words — automatic

`naming.pick_name` used to reject only an *identical* title, which is how the channel shipped
`asphalt porch`, `asphalt humid` and `wet asphalt hum` inside four days. It now re-rolls anything that reuses
a content word from the **last 8 releases** (soft rule: after 6 attempts it ships the best candidate anyway —
a release never dies over a name). No dial; the window is `-8` in `src/main.py` (search `avoid_words`).

---

## ✅ How to check you broke nothing
After any code edit, run these three from the repo root — all must say PASS:
```
python3 tools/v29_spin_ut.py      # orbit stays mono-safe
python3 tools/v30_spin_gate_ut.py # gate still refuses 3 of 5 songs
python3 tools/v31_vocal_hook_ut.py# shorts still land on sung windows
python3 tools/v32_spin_window_ut.py # moment lands on the break, never the hook
python3 tools/v33_daily_dedupe_ut.py # never two releases in one day
python3 tools/v34_dsp_pack_ut.py    # streaming pack + rights gate
python3 tools/yamlcheck.py        # workflow files still valid
```
Or the lazy version: dispatch a **dry_run** from the Actions button. It renders the whole thing,
posts nothing, and sends you the checklist on Telegram. If the checklist arrives green, you're fine.

## 📋 Current state of every dial (2026-09-19)
| Dial | State |
|---|---|
| 🌀 SPIN dimensional moment | **ON** — gated to dark_ambient / lofi / orbit_trap, instrumental windows only |
| 🔉 LOUDNORM | **ON** (-14 LUFS / -1 dBTP) |
| 🔔 CHIME_OFF | **ON = chime dead** |
| 🎤 REQUIRE_VOCALS | **ON** (hardwired) |
| 🎬 vocal-aware short hook | **ON** (no dial) |
| 🛑 PUBLISH_OFF | not set = **live** |
| 🌐 MULTIPOST | `fb,tt,ig` |
| 🧪 MULTIPOST_DRYRUN | not set = **real posting** |
| 📦 DSP_PACK streaming delivery | **OFF — parked by boss 2026-09-21** (set `DSP_PACK=1` to wake) |
| 🧾 DSP_SAFE_FIRST | **OFF** — flip to 1 to make every song streamable |
| 🔁 one release per day | **ON** (automatic) |
| 📅 schedule | cron says 16:00 BDT · GitHub fires it ~19:30–22:00 BDT |
| 🔇 SHORT_SFX / LOOP_OFF / MASCOT_OFF / POSTS_OFF | all **OFF** |

## 🎬 19. The b-roll farm (`BROLL`, `broll-farm.yml`) — generated video, offline

The release pipeline no longer only paints stills: if the **shelf** has clips for tonight's genre, the
video is cut from real moving b-roll; if it doesn't (or the download is slow, or ffmpeg is unhappy, or
`BROLL=0`), it renders the exact Ken Burns graph that shipped EP.001→EP.063. Nothing in between.

* write side: `.github/workflows/broll-farm.yml` → `tools/broll_farm.py` → Kaggle kernel
  `kaggle_cook/broll/broll_farm.py` (Wan2.1-1.3B, 8 s clips, normalised to 1080p/24 fps **on the farm**,
  so the runner pays nothing) → assets on release `broll-lab`.
* read side: `src/broll.py` (`plan()` can only return a list or `[]`; it never raises).
* 🔒 the song is protected by construction: publish.yml does not call the farm, the farm never uploads
  anything, and it refuses to start if its 7-day GPU spend would cross `BROLL_WEEK_HOURS` (default 9 of
  Kaggle's 30) while the vocal lane needs ~2. Full design + the measured timings: `docs/BROLL-FARM.md`.
* kill it: repo Variable `BROLL=0` (release side) and/or `BROLL_FARM=0` (stop the nightly GPU spend).
* 🎟 **which account**: `BROLL_ACCOUNT=auto` (default, set) — the spare first; while Kaggle's identity
  check blocks it, the farm steps over it for a week (`gpu_block.json` on the shelf) and uses the
  leftovers of your main account instead. `=spare` = "no b-roll rather than one GPU minute of mine",
  `=main` = stop knocking on the spare. Spare sessions get 18 h/wk (`BROLL_SPARE_WEEK_HOURS`), main 6 h.
* The spare account `uhn896` is **GPU-blocked** for now: Persona refused his ID ~7 times, and Kaggle
  gives CPU-only to accounts that haven't cleared that check — which is why the kernel pre-flights
  `torch.cuda.is_available()` and quits in 40 s instead of burning 3 h on a CPU. Re-probes weekly.
* 🔋 it spends **½ of what the week leaves** of a 6 h/week allowance on your Kaggle account (`BROLL_SHARE`,
  `BROLL_WEEK_HOURS`) and skips a session under 0.4 h — GitHub's own GPU runners are $0.052/min and
  Team/Enterprise-only, so Kaggle is the only free GPU here and the vocals come first, by arithmetic.
* ✅ **done 2026-10-11**: the spare account is wired — secrets `BROLL_KAGGLE_USERNAME=uhn896` +
  `BROLL_KAGGLE_API_TOKEN` are set, so the farm runs there and your main 30 h/week is untouched. One
  gate is his: a fresh Kaggle account gets **CPU only** until a phone number is verified on it
  (Settings → Phone Verification). The kernel now checks and bails in 40 s with an honest manifest
  instead of rendering junk for 3 h, and rests a week after three such sessions.
* Want more b-roll than the leftovers? That spare account is exactly it (own `~/.kaggle-broll` config dir, 18 h/wk,
  no haircut). The song lane never reads those two, so a limit on the spare can't reach a release.

## 🔑 20. Key pools — every service takes a fallback list

`GEMINI_API_KEY`, `GEMINI_API_KEY_2` … `GEMINI_API_KEY_6` (or `k1,k2,k3` in one secret) for Gemini —
art, copy, scenes, Lyria; `SUNO_API_KEY(_2…)` for the studio lane. `src/keys.py::pool()` dedupes and
keeps order; `lane_audit` prints how many keys exist, never which. A dead key is now a rename, not a
bug hunt. (Kaggle creds stay single-account deliberately — the weekly GPU quota is per account.)

## §20 · 🔓 The dry-run → public protocol (boss law, 2026-10-11)

**His rule:** "I'm not spending a cent. Do a dry run; if the dry run succeeds, just flip the
switch to public." So the switch is now self-driving:

| knob | value | meaning |
|---|---|---|
| repo Variable `PUBLISH_OFF` | `1` | every cron run is demoted to `--dry-run`: song cooked, video rendered, **nothing uploaded**, state untouched, Telegram preview only |
| same | `0` | normal real release |
| step **🔓 Dry run proved itself → flip to public** | — | runs after Compose+render, and flips `PUBLISH_OFF` back to `0` **only if** `out/latest.json` proves a real ≥3 MB `.mp4` was rendered for tonight's episode |

* The proof is the artifact manifest, never the log text — a night that printed nice words and
  rendered nothing keeps the switch parked.
* `if: success()` + `continue-on-error: true` + the script ends in `exit 0`: this step can
  **never** turn a red night redder or a green night red. If the Variable API rejects it, the run
  summary says "flip it by hand" and nothing else changes.
* Needs a PAT in `secrets.GH_TOKEN` **with repo Administration scope** (repo default workflow
  permissions are `read`, so `GITHUB_TOKEN` alone cannot PATCH Variables). Measured 2026-10-11:
  the PAT currently stored there answers `403 Resource not accessible by personal access token`
  on `PATCH /actions/variables/PUBLISH_OFF`, so the step printed its "flip it by hand" line and the
  run stayed green (that is the designed behaviour). An admin-scoped PAT answers `204` — verified.
  So: self-flipping works the moment `GH_TOKEN` is swapped for a token with Variables write; until
  then the dry run still tells him, in the run summary, exactly what to set.
* `tools/v38_flip_ut.py` (in the sweep) executes the **shipped YAML text** against fake nights:
  green → flips; no mp4 / 1 MB mp4 / half-written manifest → refuses; `PUBLISH_OFF=0` → inert.
* Money: nothing here ever asks for a card. `DSP_PACK=0` stays, the 0-credit Suno/Apiframe keys
  are tried and skipped in favour of the free Kaggle ACE lane, and the render is ffmpeg on a
  GitHub runner. Free forever is the design, not the fallback.


> **2026-10-30 audit note (both farms):** `gh release upload --cfile` is not a real gh flag, and
> both farms were using it — so release `broll-lab` has never existed and `thumb-lab` was created
> with zero assets. Both files now upload with `--clobber`, `broll-farm.yml` runs with
> `contents: write` + the workflow token (his fine-grained PAT returns 403 on Releases), and
> b-roll's "uploaded" line only prints when `gh` exits 0. Until the next farm night the b-roll
> shelf is legitimately empty and every video uses `src/broll.py`'s fallback,
> `"stills (Ken Burns)"` — which is what has actually been on screen all month.

## 🖼 21. The AI thumbnail lane (`THUMB*`) — pixels from models, never from me

Boss law, 2026-10-30: *"don't make the thumbnails by you. I have already added my Gemini API
key there to keep the thumbnails as backup. Generate hundreds and thousands of combination
thumbnails… If a Gemini API key fails or any other API key fails, then that workflow will run
and generate a new thumbnail based on the prompt."* The old complaint was "all the video
thumbnail is same" — measured as mean luma 8-25/255 and a portrait frame pillarboxed into black.

**Where a frame comes from, in order** (`src/thumb_bank.py` → `src/thumb.py pick()`):

| # | source | needs | status measured live |
|---|---|---|---|
| 1 | the **bank shelf** (`thumb-lab` release, `index.json` + jpgs) | nothing (public asset) | filled by the farm; `thumb-lab` is a rolling prerelease |
| 2 | **Gemini** — his key, `gemini-3.1-flash-image` → `gemini-2.5-flash-image`, SDK then raw REST | `GEMINI_API_KEY` (+`_2…_6`) | 2026-10-30: `429 RESOURCE_EXHAUSTED` (free-tier quota, day-wide) — the engine is right, the quota is empty |
| 3 | **Hugging Face router** `FLUX.1-schnell` / `sdxl-turbo` | `HF_TOKEN` with inference permission | 401 path is live; `api-inference.huggingface.co` is a dead host (URLError -5) — do not re-add it |
| 4 | **FLUX.1-schnell demo Space** (no key at all) | nothing | ✅ works from a runner: 4-17 s, 1280×720, luma 101-136. Shared demo → paces 25 s, retries once, then says no politely |
| 5 | **Pollinations** (his 2022 engine) | nothing | 503 (flux) / 402 (turbo) from a datacenter IP — works from a home browser, which is why his page still uses it |
| 6 | **episode cover, relit** (`11ed998`) | nothing | last-ditch safety net only; `THUMB_RELIGHT=0` disables it (then we ship no custom thumbnail rather than a fake) |

Nothing between 1 and 6 can fail a release: every path returns `None` with a one-line reason,
the manifest records `thumbnail.<slot>.source` (which engine, or `cover-relight`), and the
cosmetic lane is wrapped so a dead image API is a log line, never a red night.

**The matrix** — `genre (20) × time (6) × weather (6) × framing (6) × texture (6) × palette (7)
× lens (5)` = **907,200 combinations**, walked by the farm at stride 61 (coprime with every axis,
or whole columns become unreachable — pinned in v46). Prompts always ask for 16:9 and always
forbid text/letters/watermark/people: lettering is `art.overlay()`'s job. Every byte that arrives
must pass `usable()` — ≥18 kB, ≥900×500, aspect within 0.30 of 16:9, mean luma ≥ 38 (≤ 225),
contrast spread ≥ 9, dHash ≥ 8 bits from everything already on the shelf — so an engine that
answers with an error page or a black rectangle cannot poison the bank.

**Dials** (repo Variables under Settings → Secrets and variables → Actions → Variables):

* `THUMB=0` — master off: no pick, no set, no relight. Ship what YouTube picks.
* `THUMB_BANK=0` — ignore the shelf (live generation still allowed).
* `THUMB_AI=0` — no live generation (shelf only). Both off = cover relight only.
* `THUMB_BRAND=0` — no title/logo overlay on the generated art.
* `THUMB_RELIGHT=0` — no cover fallback; if the AI lane is empty we simply set nothing.
* `THUMB_GEMINI=0` / `THUMB_HF=0` / `THUMB_SPACE=0` / `THUMB_POLLINATIONS=0` — one engine off.
  (The farm sets `THUMB_GEMINI=0` for its own process after a 429 — a daily quota is a wall.)
* `THUMB_FARM=0` — park the nightly `thumb-farm.yml` (cron `35 5 * * *` = 11:05 BDT, 5 h 25 m
  clear of the release window). `THUMB_FARM_N` (default 24 per night), `THUMB_BANK_TARGET`
  (900), `THUMB_SLEEP_S` (2), `THUMB_BUDGET_S` (1500), `THUMB_GENRES` (comma list), `THUMB_STAGE`.
* Model overrides: `GEMINI_IMAGE_MODEL`, `THUMB_SPACE_ID` (default `black-forest-labs/FLUX.1-schnell`),
  `THUMB_SPACE_API` (default `infer`).

**His page**: `tools/thumbgen.html` — the upgraded FluxGEN v2 (one file, no build, no CDN, no
billing), also hosted at
`https://holymusic1020.github.io/yt__songs_a_cong_collections_of_Public_songs_i_liked/thumbgen.html`.
Same ladder, same 907,200 grid, same gate in the browser (a rejected frame is shown in red with the
reason), plus `index.json` + file export in the shelf's exact shape. Use it as the manual second
farm on a day the runners are refused: *Generate* → look at the badges → *download index.json* +
*download the kept files* → `gh release upload thumb-lab out/*.jpg out/index.json --clobber`.
`tools/v47_thumbgen_ut.py` runs the page's JavaScript under node and fails if it ever disagrees
with `thumb_bank.build_prompt()`, so the two halves cannot drift.

**Money**: ₹0 — free tiers and public demo endpoints only. Never apiframe, never a paid image API.
**Tests**: `tools/v46_thumb_bank_ut.py` (79) + `tools/v45_thumb_ut.py` (34) + `tools/v47_thumbgen_ut.py`
(37), all inside the `for t in tools/v*_ut.py tools/yamlcheck.py` sweep.

---

## 🐢 22. The third backup — a model that runs on the runner's own CPU (`THUMB_CPU`)

Added 2026-10-30 after the boss said: *"it will be their 3rd backup if both of those first two get
failed then the third backup will start its work. I don't care about how long… we can at least spend
10 hours for 1 thumbnail on workflow."* Measured answer first: **one Actions job may run 6 hours
(max 360 min) and free public-repo runners are 4 vCPU / 16 GB** — so 10 hours inside a single job is
impossible, and no runner has a GPU. The lane therefore runs **stable-diffusion-v1-5 in fp32 on CPU**
(~3–8 min per 768×448 frame, ~4 GB of weights), inside its own workflow, with a 5-hour self-imposed
stop, banking frames into the **same shelf** the releases read.

**The engine** — `src/thumb_cpu.py`: `StableDiffusionPipeline.from_pretrained(MODEL, torch_dtype=float32)`
+ attention-slicing + VAE-slicing/tile decode, `DDIMGenerator`, default **20 steps @ 7.5 guidance**,
`safety_checker=None` (the farm gate is the judge — it rejects blank/black frames, so the checker's
watermark-hunting false refusals would only waste the night). Same `(bytes|None, why)` contract as every
other engine, same `usable()` gate, and the gate is **never bypassed** by the retry: a rejected frame is
reported as `gate said: …`, not shipped.
Model choice is a fact, not a preference: `stable-diffusion-v1-5/stable-diffusion-v1-5` is **ungated**
(CreativeML OpenRAIL-M, commercial use allowed, no token needed in CI); `runwayml/…` was deleted;
SD 3 / 3.5 need an accepted licence + a token and cannot be cloned unattended. `runwayml` would fail
CI; this one cannot.

**The workflow** — `.github/workflows/thumb-cpu.yml`: `workflow_dispatch` (`n`, `steps`) + a **Sunday
12:10 BDT** schedule, `timeout-minutes: 300`, `actions/cache@v4` on `~/.cache/huggingface` so the 4 GB
is fetched once, and it calls the same farm with `--cpu-only`, so the shelf, the index, the cursor,
the dedupe and the release-night picker are all untouched. The pip install has **no `|| true`** — a
missing torch must read as a failed step, not as 25 silent refusals (that is how night 1 lost the SDK).

**The wiring** — `thumb-farm.yml` gained a step that wakes the CPU lane when the AI shelf is thin, and
nothing else. Both sides are **off until he says so**:

| dial | default | meaning |
|---|---|---|
| `THUMB_CPU` | unset | engine **in** the ladder at all. Set it and the release itself will wait for CPU inference if every API is dead — which is what "third backup" means. |
| `THUMB_CPU_AUTO` | unset | the nightly farm dispatches the CPU job when the shelf holds fewer than `THUMB_CPU_MIN` rows. |
| `THUMB_CPU_MIN` | `3` | that "thin" line. |
| `THUMB_CPU_N` | `12` | frames per wake-up. |
| `THUMB_CPU_MODEL` / `_STEPS` / `_GUIDANCE` / `_W` / `_H` / `_RETRY` | SD 1.5 / 20 / 7.5 / 768 / 448 / 2 | the knobs. `_STEPS 25`, `_GUIDANCE 90` (9.0) and `_RETRY 4` are the answers to "it looks soft"; `THUMB_CPU_MODEL=stabilityai/stable-diffusion-xl-base-1.0` is the answer to "make it stronger" — it will just take ~4× longer, which he has already said is fine. |

**Also in this change** (measured, then fixed, because research said so):

1. **Cloudflare Workers AI is now engine #2** (`THUMB_CF`): `@black-forest-labs/flux.1-schnell`, 4 steps,
   **10,000 free neurons/day ≈ 173 images**, no card, no proxy, resets 00:00 UTC. Needs two secrets —
   `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` (Models role only). Without them the engine refuses
   in one line. When his Gemini key hits a 429 at 04:00, this lane is awake and can hold the whole day;
   a *quota* answer stops the ladder immediately instead of burning the remaining engines.
2. **Pollinations is paced at 16 s**, not 2.5 s. Their published rate table is **1 request / 15 s per
   IP, anonymous** — night 4 burned 25 of 40 attempts on 429s because we were 6× faster than the rule.
   `POLLINATIONS_TOKEN` (free "Seed" tier, 1/5 s) is honoured if he ever registers.
3. **A small answer is no longer a wrong answer**: `_fit_frame()` crops to 16:9 then Lanczos-upscales +
   sharpens to 1280×720 when an engine replies 512² or 768×512 (FLUX.1-schnell's free path can). Before,
   18 kB/900 px rejected real frames that YouTube would have scaled identically.
4. **Gemini is protected from us**: the farm caps itself at `THUMB_GEMINI_MAX_RUNS` (4) frames per night
   and stops trying it for the rest of the night on the first 429 — measured reason: **only
   `GEMINI_API_KEY` exists as a secret; there is no `GEMINI_API_KEY_2…_6`, so the pool is one key**. The
   429 was our own nightly bulk spending the day's allowance before the release could ask. Add a second
   Gemini key as a secret and the pool grows by itself — `src/keys.py` already rotates it.
5. **The bank now reads two sources.** `releases/download/thumb-lab/index.json` as before, **plus**
   `raw.githubusercontent.com/<repo>/main/thumb-inbox/index.json`. The hosted page has a
   *📦 commit pack for `thumb-inbox/`* button: browser → download → drag the files onto github.com.
   No `gh`, no terminal, no release. Rows are de-duplicated by sha256 and each keeps its `_src` so a
   frame is fetched from the right base URL.

**Verification order** (nothing here is believed until the runner says so): `v46` (125 checks, offline —
the Cloudflare refusal/decode/quota line, the upscale through the real gate, the CPU lane's
"off / no-torch / refuses-cleanly" states, both shelf sources, both workflow files) → `v47` (45 checks,
the page's ladder order + the new Cloudflare/Space engines + the pack export) → the 33-file sweep →
`workflow_dispatch` of `thumb-cpu.yml` with `n=2` → read the log (model download, per-image seconds,
`🚫` lines) → `GET /releases` for `cpu/stable-diffusion-v1-5` rows in `index.json`.

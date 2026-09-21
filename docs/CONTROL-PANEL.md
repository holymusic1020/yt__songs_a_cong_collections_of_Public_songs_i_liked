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

## 🔁 11. One release per day — **automatic, no dial**
If a real release already went out today (your clock, BDT) — a manual run, a rescue, a boss drop —
the evening cron **parks itself** and ships nothing. Log line:
```
🔁 EP.46 already published today (BDT) — one release per day, so the cron demotes itself to a dry-run.
```
Why it exists: GitHub's scheduler fires this cron **3–6 hours late** most days (measured over 10
runs), so a midday release used to leave the evening slot free to ship a second episode — two
uploads, two TikToks, two reels in one day. Your Run-workflow button is never blocked by this:
that's your own hand.

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

# 🎧 Spotify + Apple Music — the free route, step by step

Boss 2026-09-19: *"Cannot we push this thing… add this with Spotify? or Apple Music?"*
Yes. Here is the honest shape of it, and every click.

---

## 0 · The one rule that decides everything

**Spotify and Apple Music do not accept uploads from artists.** Not you, not me, not
any app. Spotify ran a direct-upload pilot and closed it in 2019; Apple never had one.
Every track arrives through an approved **distributor**, which assigns the ISRC/UPC
codes, delivers the files, and collects the royalties for you.

So the real question is *which distributor*, and for us three filters apply:
1. **$0 and no credit card** (your words: "I don't even have a credit card")
2. **accepts AI-generated music** (CD Baby refuses it outright; TuneCore refuses
   100%-AI works — both are dead ends for us)
3. **pays out somewhere reachable from Bangladesh**

**Winner: RouteNote — Free tier.**
- $0 to join, $0 per release, releases stay live forever. They take **15%** of royalties, you keep 85%.
- No card at signup (it's a revenue share, not a subscription).
- Accepts AI music on both tiers, with disclosure. Their moderation asks you to
  confirm your AI tool grants commercial rights and to link the tools used — the
  engine now writes that proof for you (`PROVENANCE.md` inside every pack).
- Pays by **PayPal, Bank Transfer or Payoneer** once you pass **$50** (Payoneer is
  the one that works cleanly from Bangladesh).
- Backups if they ever refuse us: **Amuse** (accepts AI, max 10 AI releases per
  7 days, no free tier now) and **UnitedMasters** (free revenue-share tier).
  Never send the same song through two distributors at once — that splits the
  catalogue and creates duplicate artist profiles.

**Do not use** any service that advertises "make your AI track undetectable" or
"remove AI watermarks". That is fraud against the distributor's policy: the documented
outcomes are silent takedowns, royalty claw-back and permanent account termination.
We disclose and stay clean.

---

## 1 · What the engine now does for you (already built)

Every day it makes a **full song** (not a short) whose cooking lane is legally
sellable, it builds a delivery box and zips it:

```
out/dsp/ep047-dsp-pack.zip
├── Nix Speech - porcelain static.wav   ← the loudness-matched master (-14 LUFS / -1 dBTP)
├── cover_3000x3000.jpg                 ← square artwork — the 16:9 cover centred on a
│                                         blurred copy of itself (no black bars: stores
│                                         reject bordered artwork; no cropping either)
├── metadata.json                       ← machine-readable, every store field
├── metadata.md                         ← COPY-PASTE SHEET for the web form
├── lyrics.txt                          ← plain lyrics (stores require them)
├── lyrics.lrc                          ← synced lyrics (Apple Music timed lyrics)
└── PROVENANCE.md                       ← the rights receipt their moderators ask for
```

Log line on a release day:
```
📦 DSP pack: ep047-dsp-pack.zip · 3.9 MB · lane=ace-kaggle (Apache-2.0) · suggested release 2026-10-12
```
Telegram gets its own line — `📦 Spotify pack ✅ …` when a pack waits, `➖ off — <why>`
when a night is refused. **It is informational, never a red ❌**: a skipped pack is a
missing single, not a broken release. The receipt records `music_lane` + the pack
summary, so provenance is on file forever.

**Where to download it:** GitHub → repo → **Actions** → the day's run → **Artifacts**
at the bottom → **`dsp-pack`** → `out/dsp/epNNN-dsp-pack.zip`.
That artifact lives **90 days** (the packs ride their own artifact, not the 14-day log
one) and the repo is public, so GitHub charges nothing for the storage.

## 2 · The rights gate (why some days have no pack)

Distributors make you confirm you can *sell* the recording. Per music lane:

| Lane | Model | Licence | May it stream? |
|---|---|---|---|
| `ace-kaggle` | ACE-Step v1 3.5B on our Kaggle GPU | Apache-2.0 | ✅ yes |
| `ace-step-v1.5` / `ace-step-v1` | ACE-Step (HF space) | Apache-2.0 | ✅ yes |
| `kaggle-gpu` | DiffRhythm on Kaggle | Apache-2.0 | ✅ yes |
| `engine` | our own `composer.py` | ours, no model | ✅ yes |
| `human-drop` | your own recording in `incoming/` | yours | ✅ yes |
| `lyria` | Google Lyria 3 (Gemini API) | API terms | ⚠️ yes, but a no-card key is free-tier: Google may log prompts and the audio carries a SynthID watermark |
| `suno` | Suno **free** account | Suno ToS | ❌ **no** |
| `musicgen-local` | Meta MusicGen | weights CC-BY-NC | ❌ **no** |
| anything unknown | — | — | ❌ refused by law |

Suno's own help page: *"Songs made on the free plan (not subscribed) are only
available for non-commercial use and cannot be monetized."* Subscribing later does
**not** retroactively licence an old song. That is also why a Suno-cooked song on a
**monetized** YouTube channel is a terms problem, independent of Spotify.

**The switch that makes every song streamable:** Variable `DSP_SAFE_FIRST` = `1`.
It reorders the cooking lanes so a commercial-safe singer (ACE-Step on your free
Kaggle GPU) cooks first and Suno drops to last resort.
⚠️ Trade-off, stated plainly: it can change how the songs *sound*, because a
different model is singing. Default is `0` (nothing changes until you say so).
Prove it first with a dry run: Actions → publish → Run workflow →
`run_mode=dry_run`, `dsp_safe_first=1` — you get the preview video on Telegram and
the pack in the artifacts, and nothing is published.

---

## 3 · Your clicks (one time, ~10 minutes, no card)

1. Go to **routenote.com** → **Sign up** → email + password. Free tier is the default; never enter card details.
2. Verify the email, then fill the profile: artist name **Nix Speech**, your country, and a **payment method** (Payoneer is the Bangladesh-friendly one; add it later if you prefer — it only matters once you pass $50).
3. Dashboard → **Distribution** → **Create a new release**.

## 4 · Your clicks (per song, ~8 minutes)

1. **Release type:** Single · **Release title:** from `metadata.md` → `release_title`
2. **Upload audio:** the `.wav` from the pack (they ask for WAV 16/24-bit 44.1 kHz — ours is exactly that)
3. **Artwork:** `cover_3000x3000.jpg` (must be square, no URLs, no extra branding)
4. **Track details:** copy the fields straight off `metadata.md` — primary artist,
   songwriter/composer, publisher, language, genre, explicit = No.
   **ISRC and UPC: leave blank.** RouteNote assigns them. Never invent one.
5. **Lyrics:** paste `lyrics.txt`. Tick the synced-lyrics option and upload `lyrics.lrc` if they offer it.
6. **AI disclosure:** paste the statement from `PROVENANCE.md`, and give them the
   tool link it lists (e.g. the ACE-Step model page). If they ask for proof of
   commercial rights, send `PROVENANCE.md` itself — it names the licence.
7. **Stores:** tick everything (Spotify, Apple Music, Amazon, YouTube Music, TikTok, Tidal…).
8. **Release date:** use `suggested_release_date` — the next **Friday** at least 21 days
   out (music lands worldwide on Fridays; that's also the day charts and editorial
   playlists are cut). Delivery and
   moderation take days, and a date 3–4 weeks out is what unlocks pre-saves and
   Spotify's editorial pitch form.
9. **Submit.** Expect a moderation review; if they ask a question, answer fast —
   unanswered requests are the #1 reason releases stall.

## 5 · After the first release goes live (free, 10 minutes)

- Claim **Spotify for Artists** (artists.spotify.com) and **Apple Music for Artists**
  (artists.apple.com). You get stats, a bio/photo you control, and the ability to
  pitch an *unreleased* song to editorial playlists — which is why the +21-day
  release date matters.
- Send me the Spotify artist/track link once and I'll have the engine put it in
  every YouTube description automatically. (Not built yet — it's a one-line
  addition when you want it.)

## 6 · Expectations, honest

- **Timing:** YouTube stays same-day. Streaming lands **days to weeks later**. They are different pipelines; that's normal, not a bug.
- **Money:** streaming pays fractions of a cent per stream. At our scale the value is *presence* — a Spotify link under every video, a searchable artist profile, playlists — not income. RouteNote pays at $50 accumulated.
- **Content ID:** distributors exclude AI content from YouTube Content ID. We don't need it — we publish the audio ourselves.
- **Volume:** you asked for "same as YouTube, whenever we make a song". That's what's built. Be aware that platforms filter mass-releases as spam; if we ever see rejections, the fix is to slow to a curated weekly single (one Variable, `DSP_PACK=0`, plus a hand-picked upload).
- **Back catalogue:** the 46 already-published episodes can't be certified — the engine didn't record which lane cooked them. Streaming starts with the next full song. (From now on every song carries its provenance.)

---

## Dials (also in `docs/CONTROL-PANEL.md`)

| Want | Do this |
|---|---|
| Stop building streaming packs | Variable `DSP_PACK` = `0` |
| Make every song streamable | Variable `DSP_SAFE_FIRST` = `1` (changes which model sings — test with a dry run first) |
| Different artist name on DSPs | Variable `DSP_ARTIST` = `Your Name` |
| Different songwriter credit | Variable `DSP_WRITER` = `Your Legal Name` |
| Different release lead time | Variable `DSP_LEAD_DAYS` = `28` |

Proof it all works: `python3 tools/v34_dsp_pack_ut.py` → **UT-34 PASS**, 16 blocks:
every refusal path, the pack contents, the metadata, **byte-identical audio** (the pack
can never alter your sound), the Friday date, no-black-bar artwork, the Telegram
false-alarm guard, and the artist/writer dials.

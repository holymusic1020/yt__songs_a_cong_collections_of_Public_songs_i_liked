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
- **There is no API.** RouteNote has none for artists — every release is a human in the web
  dashboard. That is why our half of the job is "produce a zip that needs zero thinking", not
  "auto-upload". Nobody can automate this step from the outside; if a service ever offers to,
  it is a scraping bot and it will get the account banned.
- **Moderation is fast:** most releases clear in **1–3 business days**, then stores take 1–5
  more. No signup limit on the free tier; releases stay live even if you stop uploading.
- **AI content is excluded from Korean stores** (in addition to YouTube Content ID). Everything
  else delivers normally.
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
sellable, it builds a delivery box and zips it. Cadence needs no dial: a long-form song lands
every 3rd episode (`VIDEO_EVERY = 3`) ≈ **2.3 per week**, which is already the "one song every
two-to-three days" the channel runs on. Shorts-only days produce no pack, by design:

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

### Do this on day one, before any pack exists (~5 minutes)

Only two things matter on a fresh account, and only one of them is permanent:

1. **Artist / profile name: `Nix Speech` — typed exactly like that, once.** Stores merge by
   name; a second spelling (`NixSpeech`, `Nix Speech Music`) splits your catalogue across two
   profiles and the fix is a support ticket measured in weeks.
2. Country **Bangladesh**, tier **Free**. Skip the payout method — it only matters past **$50**.
3. You **may** open the wizard and look around — nothing is reviewed until the final
   **Distribute Free** button, and an unfinished release just sits in *Discography* as
   *In Progress* (there's even a "delete all unfinished releases" action). What you must not do
   is **submit** a release with no audio, or a placeholder "test" track: that is what burns
   moderation goodwill on a fresh account. Walk the form, close the tab, submit only a real pack.
4. **Do not** pull an older published track out of YouTube and register it as `human-drop` just to
   have something to upload today. `human-drop` means *you* performed it; used on a machine-cooked
   master it is a false rights declaration, and that — not low streams — is what terminates
   distributor accounts. The engine refuses uncertifiable audio for exactly this reason.

## 3 · The wizard, screen by screen (this is the whole job)

RouteNote's flow is a linear wizard: each section ends with **Save and Continue** and drops you
back on the "release in progress" page, where the next section is waiting. Nothing is reviewed or
sent anywhere until the very last button, so **you can stop halfway and come back** — it sits in
Discography as *In Progress*. Verified wording below is theirs.

### Screen 1 — `Create a Release` (`/rn/create_album`) → *Release Data*
| Box | Type |
|---|---|
| **UPC** | **leave EMPTY.** They generate one free. Only fill it if you're migrating from another distributor. |
| **Release Title** | the `release_title` line from `metadata.md`. For a single this IS the song title. |
| **Create Release** | click it. |

### Screen 2 — *Album Details*
| Box | Type |
|---|---|
| Language | the `language` line (match the sung language, not the video's captions) |
| Album/Single/EP Title | already filled — skip |
| Album Version | leave empty (put `Instrumental` only if it truly is one) |
| **Artist Name** | `Nix Speech` — spelled EXACTLY like the profile, every time |
| **Artist page on Spotify** | pick **Create a new profile** (first release). Once claimed, later releases must select that page or your streams split across two profiles. |
| **Writers** | `Nix Speech` — first + last name format. Tick the lyricist box and repeat it (our lyrics are written for the song, so both credits are the same). |
| **Primary Genre** | from `primary_genre` · **Secondary Genre** from `secondary_genre` |
| **Composition Copyright (C line)** | `c_line` from the sheet, e.g. `© 2026 Nix Speech` |
| **Sound Recording Copyright (P line)** | `p_line`, e.g. `(℗) 2026 Nix Speech` |
| **Record Label Name** | **`Nix Speech`.** ⚠️ Their own rule: `none`, `unsigned`, `indie`, `N/A` and **`independent` are all rejected** — no label means put your artist name. |
| **Originally Released** | **today's date** — first time it reaches stores. Leave Pre-Order and Sales Start blank. |
| **Explicit Content** | **Non-explicit** |
| Save and Continue | click |

### Screen 3 — *Add Audio*
**Track Name** = the song title (for a single it must match the release title) → **Choose File** →
drop in `Nix Speech - <title>.wav` from the pack → wait for 100% → **Save and Continue**.
(If it stalls under 100% it's usually the file: ours is WAV 44.1 kHz / 16-bit, which is their
spec, so check it wasn't renamed to `.wav.wav` by your OS on the way out of the zip.)

### Screen 4 — *Track Metadata*
Track name / track number `1` / artist are prefilled — skip. **Title Version** empty.
**Composer** `Nix Speech`, tick **Yes** on lyrics and add **Lyricist** `Nix Speech`.
**ISRC** — auto-filled by them; leave it. **Explicit** Non-explicit. **Audio Language** match screen 2.
→ **Save and Continue** → **I'm Finished**.

### Screen 5 — *Artwork*
Drag in `cover_3000x3000.jpg`. It's square, 3000 px, and **deliberately has no frame, no
"OFFICIAL AUDIO" chip and no episode number** — the video thumbnail has those, and Apple/Spotify
reject borders and overlay text on artwork. Their no-list: website addresses, emails, **@handles**,
**hashtags**, phone numbers, QR codes, store or social **logos**, "coming soon"/"follow me"
**advertising**, prices, CD/DVD logos, barcodes. → **Save and Continue**.

### Screen 6 — *Manage Stores*
Tick **Select all stores**. **Pricing = Standard**. **Territories: add nothing** — empty means
worldwide, which is their documented rule. → **Save and Continue**.

### Screen 7 — *Localisation*
Skip it (that's translated metadata; `VOCAL_EVERYDAY`/world-tour episodes can wait until a
language actually earns something).

### Screen 8 — *Finalise*
Read the summary, tick the **Artist/Label Agreement** box, then:

> ### ⚠️ press **Distribute Free** — NOT "Distribute Premium"
> Premium is the paid one (card required, $9.99/single). Free = $0, they keep 15% of royalties.
> The site will offer you Premium in several places (the welcome page has a "Choose Premium"
> button). Every one of them is an upsell. Ignore all of them, always.

Done. Status → *In Review*. Moderation 1–3 business days, then stores take 1–5 more.

### What moderation writes back if something's wrong
They email + put a note in **Discography** with the fix needed. Edit the field, re-submit. That is
normal, not a strike — the only thing that actually hurts an account is *lying* (rights, AI,
impersonation). Common asks from our side would be a title-format note or artwork text; answer
once, it's cleared forever.

### The three traps on this form
1. `independent` in the label box → rejected (use `Nix Speech`).
2. An ISRC/UPC typed in by hand → duplicate-registry mess. Both boxes stay empty, forever.
3. A different spelling of the artist name on release #2 → two Spotify profiles, split stats.

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

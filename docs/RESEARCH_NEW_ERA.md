# 🧠 NEW ERA RESEARCH DOSSIER — Nix Speech, next era
*(agent research notes · 2026-08-10 · this doc is the thinking; `TODO` at the bottom is MINE to build)*

Boss's reference point: his own site (mdhojayfa.github.io) — a **360° cyber-HUD
universe** with matrix rain, controller navigation, an admin panel, manifesto copy.
Taste profile read: terminal aesthetics, motion, secrets, things that *feel alive*.
So the channel's next era = not "another lyric video channel" but **a cyberpunk
universe that happens to make songs.**

---

## 1. What the 2026 Shorts algorithm actually rewards (verified research)

Sources: 2026 retention-curve playbooks (aibrify, joinbrands, fliki, virvid).

- **The first frame IS the hook.** Killing intro cards = +10–20 pts average view
  duration. ✅ We already open on hook card #1 — keep it, never add a logo intro.
- **Sound-off captions by second 1.** 60–80% of feed views are muted. ✅ our lyric
  cards cover this; karaoke burn covers long videos.
- **THE LOOP IS DESIGNABLE.** Last frame should visually match frame one →
  retention spikes >100% at second 1 = the algorithm's favorite signal
  ("plateau curve"). ❌ We don't do this yet. **Build: shorts end-card = card #1
  echoed, same base composition, cut fades land exactly on loop point.**
- **Cut pacing 1.5–2.5s per visual change.** ✅ our quick-cut chunks (~2s) already.
- **Trending sounds = tailwind, but ORIGINAL SOUND pages compound.** Every short
  posts its audio as a reusable sound; others reusing it feeds our source videos.
  **Build: description + first comment with "use this sound 🎧" CTA, always.**
- **Volume + iteration beats perfection.** ✅ daily cron covers volume; the
  iteration loop needs analytics feedback (see §4).

## 2. The lesson of Lofi Girl (the billion-view moat nobody can copy)

- One REcurring character + connected world = fan attachment, fan art, collabs
  (LEGO!), 1.5B+ views. The universe mechanic: characters' windows appear in
  each other's videos — small continuity drips make viewers feel the canon.
- **Our translation at $0:** a mascot that is 100% CODE-DRAWN (so it's identical
  in every frame forever — a PNG pixel-art sigil from a grid spec), who shows up
  in every scene, blinks on the beat, and whose journey IS the channel's lore:
  **NYX, the signal-cat** 🐱‍🎧 travels the 9-genre map (City of Chrome → Festival
  Skyline → the Villain Theatre → Orbit…). World Tour stops = lore postcards.
- Easter eggs = his taste (admin panel energy): tiny hidden coordinates in one
  frame per video (the next EP's city coords), whisper it in comments weeks
  later. Costs nothing. Makes a universe.

## 3. Audio-reactive visuals, the honest $0 way

- ffmpeg's **showfreqs/showspectrum/showwaves** filters are core avfilters — they
  need NO drawtext plugin (even the static build has them). A thin live spectrum
  strip under the karaoke line + HUD frame = the video *physically moves with
  the song*. Nobody else in our niche burns REAL audio physics into their videos;
  they use templates. This is a signature.
- Mascot blink: two PNG overlays swapped on kick windows via `enable=between()`
  — zero render cost, reads as "alive".
- Long-video retention: karaoke (have) + spectrum motion (new) + scene changes
  every ~8s (have) = the microwave-timer complaint stays dead forever.

## 4. Feasibility of API superpowers (checked against YouTube docs)

| power | verdict | notes |
|---|---|---|
| Chapters (00:00 …) in description | ✅ FREE NOW | from our LRC karaoke map: intro/verse/chorus/outro — needs ≥3 stamps ≥10s apart; also feeds Google SEO |
| Captions upload (LRC→SRT) | ✅ API exists (captions.insert) | needs `youtube.force-ssl` scope → ONE re-consent click by boss, then automatic forever |
| First comment w/ lyrics + CTA | ✅ commentThreads.insert | same scope; pinning itself is Studio-only (API can't pin — honest) |
| Scheduled publish (8:30PM BDT drops) | ✅ publishAt flag | near-premiere effect, upload scope already covers |
| TRUE Premieres badge | ❌ Studio-only | skip |
| Analytics self-tuner (Read VVSA/retention → tune next hook) | ✅ Analytics API is free | `analytics.py` exists → wire into `shorts.pick_hook_window` weighting = the channel learns which seconds retain |

## 5. The "1 cook, 3 posts" multiplier (music-niche proven format)

- **slowed + reverb / sped-up** versions are a whole genre of channels with
  billions of views. **We own our masters forever** → slicing a slowed+reverb
  twin short costs ~0 (pure ffmpeg: asetrate + aecho). Every 4th short =
  "midnight slowed cut" of the same EP. Different packaging, same song, two
  audiences. (Honesty stamp: format is proven, OUR lift is an experiment —
  we measure via analytics loop.)

## 6. Sonic branding — the thing nobody in our lane has

- 0.7s **Nix chime** (synthesized signature motif, identical every time) at the
  head/tail of every track + every short. Any repost anywhere = recognizable.
  One function in `master()`. Radio stations did this for a century because it
  works.

---

# 📋 MY TODO (build list for THE FINAL ZIP — not boss's)

**v23 codename: "THE UNIVERSE UPDATE"** 🌌

### ✅ P0 SHIPPED — v23 "THE UNIVERSE UPDATE" (built 2026-08-11, 32 receipt checks green)
1. ☑ **NYX the signal-cat mascot** — `src/mascot.py` pixel-grid spec (drift-asserted),
   alpha loop webm blinks ON the kick (2-beat cycle, bpm-matched)
2. ☑ **HUD karaoke skin** — scanlines + corner brackets + ON AIR tag overlay
   + REAL showfreqs spectrum strip (verified: 1518 live cyan px on, 0 when off)
3. ☑ **Designed loop shorts** — final card is a pixel-EXACT echo of card #1
   (receipt: last bytes == first bytes)
4. ☑ **Chapters in description** from the karaoke map (0:00 intro leads,
   ≥10 s gaps, ≥3 or untouched; hashtags stay last)
5. ☑ **Sonic logo chime** — 4-bell 0.75 s motif in `master()` + queue masters
   (`mix_logo`) + every short's loop point (CHIME_OFF kills)
6. ☑ **Slowed+reverb twin short** every 4th (SLOWED_EVERY) — pure-numpy
   asetrate+aecho on our OWN master, centroid-verified pitch drop
7. ☑ **"Use this sound" CTA** — every short description + end card ink

### P1 — superpowers (needs ONE boss re-consent click for wider OAuth scope)
8. ☐ captions.insert: karaoke LRC→SRT upload (accessibility + search)
9. ☐ first-comment auto-post (lyrics + sound CTA)
10. ☐ scheduled 8:30PM BDT drops for long videos (publishAt)
11. ☐ analytics self-tuner: retention/VVSA → next short's hook-window weights

### P2 — parked deliberately (honesty shelf)
- True Premieres (Studio-only), TikTok/IG auto-posting (fake-API ban risk),
  suno multi-account rotation (ban-bait, manual 30s swap stays the way),
  Telegram community engine (blocked until TELEGRAM_BOT_TOKEN fixed by boss)

### Packaging — "FINAL EVER" edition (2026-08-11)
- Zip now CARRIES `.github/workflows/` (publish/upgrade/unpack) — a wiped
  repo loses them; the zip is the backup. Bot-token push law: automation
  (unpack.yml/upgrade.yml) always strips `.github` from payloads — workflow
  files only ever land via boss's own web upload.
- Secrets live in repo Settings, NOT files: wiping FILES never kills secrets;
  DELETING THE REPO does (he'd redo 7 secrets + vars). Card says: never delete.
- Policy sweep 2026-08-11 (3 sources): AI music monetizable when rights-owned,
  disclosed-when-required (realistic altered media — not our stylized class),
  genuinely unique (vs mass-auto spam). Our counter: 9-genre universe, arc
  mastering, art + mascot = the "human creative elements" reviewers ask for.
  Suno note: rights-clean lane stays ACE-Step (Apache-2.0); suno slot optional.

### Design invariants (never break)
- $0/month or the era is fake • originals only, no covers • no viewer-facing
  AI tells • zero-config: anything new must default sane with env kill-switches
  (SPECTRUM_OFF, MASCOT_OFF, LOOP_OFF, CHIME_OFF, SLOWED_EVERY)

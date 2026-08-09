# 🧠 The Playbook — how this machine is tuned to human brains

Distilled from current short-form/music research. Every rule below is
*implemented in code*, not just advice.

## 1. The first 2–3 seconds decide everything
- Most viewers swipe within 3 seconds. Faceless channels carry double weight
  on the opening frame. → **Shorts card #1 is always a HOOK line**
  (curiosity gap / direct recognition in `lyrics.py`), and the cut starts
  *mid-energy*, never from silence.
- No intros, no logos before the hook. Music starts instantly.

## 2. Length = 15–34s (the viral sweet spot)
Shorts under ~30s dominate completion rates, and completion + replays are
the two signals the Shorts feed ranks hardest. → `shorts.py` cuts 18–34s
windows (bar-snapped).

## 3. Sound-off readability
A huge share watch muted. → Every lyric card is styled to be fully readable
without audio (big type, stroke, one thought per card).

## 4. The loop is the replay engine
"Loop your video so the last frame connects to the first" — boosts watch
time 25–50%. → Window start/end snap to bar boundaries; fade edges are
beat-tight, so the Short rolls seamlessly into itself.

## 5. Cut where the physical energy peaks
Instead of a random slice, `pick_hook_window()` finds the **highest-energy
contiguous window** by RMS scan — the moment bodies react to is the moment
brains replay.

## 6. One idea per Short; series over lottery tickets
Consistent format = recognition. Same frame, same chip, same typography
every EP → the audience learns the "brand" and stops for it. That's the
OFFICIAL look doing psychology work.

## 7. Shorts ≠ automatic fans for long-form
The Shorts feed and main feed are separate systems — you must *engineer* the
bridge: short description points to "full version on the channel". Pin a
comment on each short (manual, 10s): link the EP video.

## 8. Titles are hooks, not labels
Long-form: clean official label style (`name — Nix Speech (official audio)`)
builds catalog trust. Shorts: the hook line IS the title. 2–3 hashtags max —
tag-stuffing reads as spam.

## 9. Why randomized publish windows (honest version)
Varying publish times lets you *learn* from analytics when YOUR audience is
awake — after ~10 EPs, check YouTube Studio → Analytics → Audience →
"When your viewers are on YouTube", then we narrow the windows to your
peak hours. The randomness is a 2-week experiment, not a disguise:
YouTube sees API uploads either way.

## 10. The weekly 10-minute ritual (the only "work")
- Studio → Content: find top Short by retention.
- Tell me its title/hook — I clone that structure across more cards.
- Anything with <25% retention → tell me, we kill that hook type.

## 11. Phonk DNA note (why our engines work here)
Drift phonk was *designed* for 15–30s edits: immediate impact, cowbell hook,
808 pressure. Our engines build hooks every 8 bars by section — the hook
window detector almost always lands on one. Dark-pop/lo-fi run less energy,
so their windows bias to the piano/arp phrases.

## 12. The road to monetization (think like an owner)
YouTube Partner Program needs **1,000 subs + 4,000 public watch-hours**
(12 months) **or 10M Shorts views** (90 days). Strategy:
- **Shorts = reach machine.** Cheap impressions, subs trickle in.
- **Watch-hours don't come from Shorts.** Long-form does that: later we add a
  "weekly mix" job (ffmpeg-concat the week's EPs into a 30–60 min compilation
  — 1 loyal listener looping a mix = hours).
- **Review-day rule:** when you hit thresholds, a *human* may review the
  channel. Variety (4 genres, fresh AI copy, evolving covers) + original
  composition + declared synthetic media = looks like a real label, because
  it is one. Mass-produced sameness is what fails review — the weekly ritual
  (rule 10) is literally our anti-sameness program.
- First income won't be life-changing; treat the channel as an asset that
  compounds (catalog size × back-catalog streams).

## 13. 2026 policy snapshot (why our architecture survives review)
Mid-2026 YPP clarification names exactly THREE guilty classes:
repetitive/template uploads with little variation · emotionally
manipulative distress-farming · AI personas on sensitive topics. We are
structurally none of them: every EP = fresh composition (6 engines),
fresh verified-unique title (catalog-checked), fresh AI copy, rotating
art styles; the weekly human ritual is documented "human curation" —
which the policy explicitly rewards. Official YouTube line: "channels
that use AI in their content remain eligible for monetization" as long
as original + disclosed. Our disclosure flag is always ON. Five gates to
keep passing: inauthentic ✓ · reused ✓ (never re-uploads) · disclosure ✓
· advertiser-friendly ✓ (instrumental, no distress) · Content ID ✓
(fully synthesized originals, no samples, no third-party AI dumps).

Sources: Boost Collective (2026 shorts-for-music guide), virvid.ai hook
structures (2026), Chartlex musician marketing guides (2026), UpMyViews
shorts strategy (2025), Orphiq "What is phonk" (2026), Melodigging slowed+
reverb culture notes (2026), Veo 3 prompting guides (2025–26),
SocialMediaToday YPP clarification (2025), MetaMusicMedia demonetization
rules (2026), Outlierkit AI-music monetization playbook (2026).

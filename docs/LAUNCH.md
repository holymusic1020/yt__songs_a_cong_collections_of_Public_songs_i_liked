# 🚀 LAUNCH CARD — zero to running in one sitting (~45 min)

Everything you need, in order. No re-reading, no guessing.

## ✅ Already done by you
- [x] YouTube channel created
- [x] Google Cloud project `yt-auto` + YouTube Data API v3 enabled
- [x] Consent screen **PUBLISHED** (this is what makes the token immortal)
- [x] Web OAuth client with `https://developers.google.com/oauthplayground`
  as authorized redirect URI
- [x] Refresh token minted via OAuth Playground

## 🩺 CRITICAL — YouTube API compliance audit (submit TODAY, takes days)
Hard truth from Google's own docs: **unverified API projects (yours is new)
have ALL uploads locked to PRIVATE** until the project passes a free
compliance audit. The scheduled "publish" won't make them public without it.

➡️ **Fill this form now** (5 min, free, approval usually within days):
`https://support.google.com/youtube/contact/yt_api_form`
(The **YouTube API Services – Audit and Quota Extension** form. Answer
honestly: "Automated original-music uploads to my own channel via
videos.insert, ~2 uploads per release every 3 days, within the 10k daily
quota; AI-synthetic content is self-declared on every upload.")

While it processes: run EP.001 anyway — uploads just stay Private (zero
harm, they queue). After approval, everything publishes normally. If after
EP.001's scheduled time it's still private → this audit is the reason.

## 📦 Today — the final 20 minutes
1. **Push code**: GitHub repo `yt-auto` (PUBLIC) → drag this folder in
   ("uploading an existing file"). Same-name files auto-replace.
   Verify `.github/workflows/publish.yml` shows up in the repo.
2. **Secrets**: Repo → Settings → Secrets and variables → Actions → 4 secrets:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `GEMINI_API_KEY`
   (the web client's id/secret — the same one that minted the token).
3. **Fire**: Actions tab → enable workflows → "yt-auto · publish episode"
   → Run workflow ▶️ (button top-right).
4. **Watch** the run: 🩺 doctor (all checks green?) → compose → 🏷 unique
   title → Gemini hooks/cover → Veo-or-slideshow → 📅 schedule → uploads.
5. **Verify**: YouTube Studio → Content → EP.001 video + short = "Scheduled".
   The machine is live. 🎬

## 🔁 After launch — your entire job
- **Nothing, for 3 days.** Cron fires alone at 09:23 UTC.
- **Weekly 10-minute ritual** (Friday chai ☕):
  1. Studio → Analytics → top Short by retention → note its hook style
  2. Studio → Audience → "when your viewers are online" → note peak hours
  3. Shorts: pin the funnel comment (the machine posts it, you pin it)
  4. Bring screenshots to me → I tune engines/copy/windows

## 🎯 Milestone triggers
| When | Do |
|---|---|
| EP.004 released | Tell me — we build the **weekly mix compilation** (watch-hours engine) |
| ~10 releases | Narrow publish windows to your peak hours (analytics data) |
| 100 subs | Small celebration 🎉 + review which genre the weights favor |
| 1,000 subs + 4,000 watch-hours **or** 10M Shorts views (90d) | Apply to YPP. Human review: we pass (original, varied, declared) |

## 🚑 Troubleshooting (one line each)
| Symptom | Fix |
|---|---|
| Red run, `invalid_grant` | Re-mint token (README Phase 4, 5 min) → update `YT_REFRESH_TOKEN` |
| Red run, `quotaExceeded` | Wait — resets midnight Pacific; run again tomorrow |
| Gemini/art steps warn, still green | Quota hiccup — fallbacks covered it; ignore |
| "workflow disabled" email (60-day GitHub rule) | Actions tab → re-enable. Our commits prevent this anyway |
| Veo always fails | Key tier has no video gen → slideshow is your fate (it's good) |
| Everything red, first line | Secret name typo. Fix, re-run. |
| Video stuck **Private** after publish time | Subscription to the **API compliance audit** (top of this page) — pending; submit & wait |
| Constant network timeouts mid-upload | Nothing — per-chunk retries ride it out automatically |
| No Discord ping on failure | Optional: add `NOTIFY_WEBHOOK` secret (Discord channel → Edit → Integrations → Webhooks) |

## 💰 Honest money note
Nothing here *guarantees* income — nobody can. What this machine does is
remove every excuse: consistency, originality, disclosure compliance,
funnels, hooks, adaptation. Growth = catalog × time × iteration. The
channels that lose are the ones that stop. This one can't stop unless you
do. 🤝

# yt-auto — setup sheet

Automated release pipeline. One Short every day, one full video every 3rd
episode, composed/rendered/uploaded by GitHub Actions for $0.
Publishing uses YouTube's native `publishAt` scheduling, so releases land in
random windows without burning runner minutes.

## 1 · Upload this pack

Extract the zip → drag **all** files into your repo's web upload
(make sure `.github/workflows/publish.yml` appears in the list) → Commit.
Keep the repo **Private** (Settings → General → Danger Zone → Change visibility).

## 2 · Add secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Where the value comes from |
|---|---|
| `YT_CLIENT_ID` | Google Cloud → APIs & Services → Credentials → your OAuth client |
| `YT_CLIENT_SECRET` | same client |
| `YT_REFRESH_TOKEN` | the one minted before — deleting the old repo did **not** revoke it. Lost it? Put the OAuth client JSON next to `tools/get_refresh_token.py` as `client_secret.json`, `pip install google-auth-oauthlib`, run it, log in with the channel account, copy the three printed values |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key (art + video scenes; pipeline falls back to procedural art without it) |
| `TELEGRAM_BOT_TOKEN` | optional — status alerts. Telegram → **@BotFather** → `/newbot` → copy the token |
| `TELEGRAM_CHAT_ID` | optional — open YOUR new bot → press **START** → ask **@userinfobot** → copy your Id |
| `NOTIFY_WEBHOOK` | optional — Discord channel webhook (kept alongside Telegram; both fire) |

**Alerts:** every run pings you — ✅ success (track name, video/short links,
go-live times in BDT) or 🚨 failure (last log lines + run link). Skip any of
these secrets and that channel just stays silent — the pipeline NEVER breaks.

Also confirm in Google Cloud that **YouTube Data API v3** is enabled on the
project.

## 3 · Start button

**Actions** tab → first visit: click *"I understand my workflows, go ahead and
enable them"* → select **"yt-auto · publish episode"** in the left list →
**Run workflow ▾ → Run workflow**.

First run publishes EP.001 (full video + short, both auto-scheduled).
No other repo settings needed — the workflow declares its own token permissions.

## 4 · From then on — nothing to press

- Cron fires daily at **09:23 UTC** and publishes the day's episode.
- Each run commits `state/state.json` back, so episodes advance on their own.
- Zero junk: heavy renders are deleted right after upload (the videos live on
  YouTube), artifacts keep only tiny text records that auto-expire in 14 days,
  and the runner machine itself is destroyed after every run.

## 5 · Watch the first log for

```
🩺 doctor green        → secrets + ffmpeg OK
🏷 title … verified     → unique song name picked
✅ video: youtu.be/…    → uploaded + scheduled
✅ short: youtu.be/…    → uploaded + scheduled
```

If uploads stay **Private** while scheduled, the log tells you — that means the
API project is privacy-locked and the uploader will print the compliance-audit
link to submit once.

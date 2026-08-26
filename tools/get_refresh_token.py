"""Run ONCE on your own machine to mint the refresh token.

Steps:
  1. Download your OAuth client JSON from Google Cloud Console
     (APIs & Services > Credentials > your Desktop client > Download JSON)
     and save it next to this file as  client_secret.json
  2. pip install google-auth-oauthlib
  3. python tools/get_refresh_token.py
  4. A browser opens > log in with the channel's Google account >
     click through the "unverified app" warning (it's YOUR app, that's fine)
  5. Copy the three values below into GitHub:
     Repo > Settings > Secrets and variables > Actions > New repository secret
"""
from google_auth_oauthlib.flow import InstalledAppFlow

# ⚠️ 2026-08-25 fix: ALL THREE scopes are required. A token minted with only
# youtube.upload throws invalid_scope on videos.insert + the funnel comment +
# analytics — the pipeline then publishes NOTHING (this hit EP.023; nothing
# has gone up since EP.022).
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=8765)

print("\n=== add these as GitHub Actions secrets ===")
print("YT_CLIENT_ID:     ", flow.client_config["client_id"])
print("YT_CLIENT_SECRET: ", flow.client_config["client_secret"])
print("YT_REFRESH_TOKEN: ", creds.refresh_token)

# Privacy Policy — Nix Speech (TikTok app)

_Effective: 2026-09-03_

The **Nix Speech** TikTok integration exists for a single purpose: posting
short music videos, created by the account owner, to **the owner's own
TikTok account** via the TikTok Content Posting API.

## Data we access
- **user.info.basic** — open id, display name, avatar of the owner's TikTok account.
- **video.upload / video.publish** — publish permission only. We never read
  videos or analytics of other users.

## Data we store
- OAuth refresh/access tokens for the owner's own account, stored as
  encrypted secrets in this GitHub repository and rotated automatically.
- No cookies, no tracking, no analytics of TikTok users, no sale/sharing of
  any data with third parties.

## Third parties
- TikTok for Developers (OAuth + Content Posting API) — the only processing
  counterpart. No other third-party SDKs.

## Owner rights
The operator (account owner, the only data subject) may revoke access any
time from TikTok app → Settings → Privacy → Apps, or delete this app in the
TikTok developer portal. Secrets are destroyed on deletion.

## Contact
Via the YouTube channel's business contact link: youtube.com/@nixspeech.

"""🧾 RIGHTS — which music lane is allowed to leave the building for streaming.

Boss 2026-09-19: "I want all that are free… I don't even have a credit card."
That single sentence decides everything in this file, because a distributor
(RouteNote / DistroKid / whoever) makes you CONFIRM you hold commercial rights
to the recording, and each music lane has a different licence:

  lane            model                    licence            commercial?
  ─────────────── ──────────────────────── ────────────────── ───────────
  ace-kaggle      ACE-Step v1 3.5B         Apache-2.0         ✅ YES
  ace-step-v1.5   ACE-Step v1.5 (HF)       Apache-2.0         ✅ YES
  ace-step-v1     ACE-Step v1 (HF)         Apache-2.0         ✅ YES
  kaggle-gpu      DiffRhythm (Kaggle)      Apache-2.0         ✅ YES
  engine          our own composer.py      ours, no model     ✅ YES
  lyria           Google Lyria 3 (Gemini)  API terms          ⚠️ CONDITIONAL
  suno            Suno (FREE tier)         Suno ToS           ❌ NO
  musicgen-local  Meta MusicGen            weights CC-BY-NC   ❌ NO

Two of those are not opinions, they are the vendors' own words:
  · Suno: "Songs made on the free plan (not subscribed) are only available for
    non-commercial use and cannot be monetized." Subscribing later does NOT
    retroactively licence a song. (help.suno.com/en/articles/2416769)
  · MusicGen weights ship under CC-BY-NC 4.0 — non-commercial, full stop.

`lyria` is conditional, not banned: Google's API terms hand you the output, but
a key with no billing (the boss has no card) is a FREE-tier key, which means
Google may log and use our prompts/outputs to improve their models, and Lyria
audio carries an invisible SynthID watermark. Distributable, just not private.

Anything not on this table is treated as ❌ until proven otherwise. Law: an
unknown lane never ships to a DSP. YouTube keeps working exactly as before —
this file only gates the streaming-delivery pack.
"""
from __future__ import annotations

APACHE = "Apache-2.0"

LANES: dict[str, dict] = {
    "ace-kaggle": {
        "commercial": True, "license": APACHE,
        "tool": "ACE-Step v1 (3.5B) on our own Kaggle GPU",
        "url": "https://huggingface.co/ace-step/ACE-Step-v1-3.5B",
        "why": "open weights under Apache-2.0 → commercial use granted by the licence",
    },
    "ace-step-v1.5": {
        "commercial": True, "license": APACHE,
        "tool": "ACE-Step v1.5 (Hugging Face space)",
        "url": "https://huggingface.co/spaces/ACE-Step/Ace-Step-v1.5",
        "why": "open weights under Apache-2.0 → commercial use granted by the licence",
    },
    "ace-step-v1": {
        "commercial": True, "license": APACHE,
        "tool": "ACE-Step v1 (Hugging Face space)",
        "url": "https://huggingface.co/spaces/ACE-Step/ACE-Step",
        "why": "open weights under Apache-2.0 → commercial use granted by the licence",
    },
    "kaggle-gpu": {
        "commercial": True, "license": APACHE,
        "tool": "DiffRhythm on our own Kaggle GPU",
        "url": "https://github.com/ASLP-lab/DiffRhythm",
        "why": "Apache-2.0 → commercial use granted by the licence",
    },
    "engine": {
        "commercial": True, "license": "original code, no third-party model",
        "tool": "Nix Speech offline composer (this repo's src/composer.py)",
        "url": "",
        "why": "every note is written by our own synthesis code — no model output at all",
    },
    "lyria": {
        "commercial": True, "license": "Gemini API terms (free tier)", "conditional": True,
        "tool": "Google Lyria 3 via the Gemini API",
        "url": "https://ai.google.dev/gemini-api/terms",
        "why": "Google's API terms assign the output to you; a no-billing key means "
               "prompts/outputs may be logged and used to improve Google's models, and "
               "the audio carries an invisible SynthID watermark. Distributable, not private.",
    },
    "suno": {
        "commercial": False, "license": "Suno ToS — FREE tier is non-commercial",
        "tool": "Suno (free account)",
        "url": "https://help.suno.com/en/articles/2416769",
        "why": "\"Songs made on the free plan are only available for non-commercial use and "
               "cannot be monetized.\" Upgrading later does NOT retroactively licence them.",
    },
    "human-drop": {
        "commercial": True, "license": "the boss's own recording",
        "tool": "human drop in incoming/ (not machine-generated)",
        "url": "",
        "why": "audio the boss supplied himself — he owns it; AI disclosure = none",
    },
    "musicgen-local": {
        "commercial": False, "license": "weights CC-BY-NC 4.0 (code MIT)",
        "tool": "Meta MusicGen (local CPU)",
        "url": "https://huggingface.co/facebook/musicgen-small",
        "why": "the model weights are non-commercial — no DSP delivery, ever",
    },
}

# Lane order when DSP_SAFE_FIRST=1: commercial-safe singers first, so a song
# destined for Spotify is cooked by a lane we can actually certify. Suno stays
# in the grid as a last resort (it still cooks fine for YouTube-only days).
SAFE_FIRST_ORDER = ("ace-kaggle", "ace-step-v1.5", "ace-step-v1", "lyria",
                    "kaggle-gpu", "suno", "musicgen-local")


def verdict(lane) -> dict:
    """Rights verdict for a lane name. Unknown lanes are refused (law)."""
    key = str(lane or "").strip().lower()
    if not key or key in ("none", "null"):
        key = "engine"                      # no lane cooked it → our own composer
    info = LANES.get(key)
    if info is None:
        return {"lane": key or "(unknown)", "commercial": False, "license": "UNKNOWN",
                "tool": key, "url": "", "why": "lane not in the rights table — refused until proven safe"}
    out = dict(info)
    out["lane"] = key
    out.setdefault("conditional", False)
    return out


def commercial_safe(lane) -> bool:
    return bool(verdict(lane).get("commercial"))


def disclosure(lane) -> str:
    """The honest sentence to paste into a distributor's AI-disclosure box."""
    v = verdict(lane)
    tool = v.get("tool") or v["lane"]
    url = f" ({v['url']})" if v.get("url") else ""
    return (f"AI-assisted: the recording was generated by {tool}{url} under "
            f"{v.get('license', '?')}. No voice cloning, no imitation of any real "
            f"artist, no third-party samples. Lyrics and arrangement direction, "
            f"artwork selection, mastering and release decisions are human.")


def tool_links(lane) -> list[str]:
    """Links a distributor asks for to verify where the audio came from."""
    v = verdict(lane)
    return [u for u in (v.get("url"),) if u]

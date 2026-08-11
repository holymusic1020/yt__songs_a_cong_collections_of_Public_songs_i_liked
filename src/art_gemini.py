"""Gemini image generation for cover scenes.

Prompt is built from the actual episode (song name, genre, mood), so every
cover is art-directed by the music. We ask for NO text — our own overlay
(art.py) stamps the branding on top for series consistency.

Needs env var:  GEMINI_API_KEY
Optional:       GEMINI_IMAGE_MODEL (pins a specific model id)
"""
from __future__ import annotations

import io
import os

from PIL import Image

# Tried in order; first one that returns an image wins.
MODEL_CANDIDATES = [
    "gemini-2.5-flash-image",                      # nano banana (fast, free-tier friendly)
    "gemini-2.5-flash-image-preview",
    "gemini-2.0-flash-preview-image-generation",
]

MOODS = {
    "drift_phonk": "deserted neon-lit city street at night, drifting car "
                   "taillights in pink haze, wet asphalt reflections, "
                   "VHS grain, phonk aesthetic",
    "deep_pop": "rainy window bokeh at blue hour, lonely balcony, golden "
                "and blue dusk light, melancholic cinematic still",
    "dark_ambient": "endless fog over an empty landscape, one distant light "
                    "source, teal-black palette, liminal and quiet",
    "lofi": "cozy bedroom studio at golden hour, warm lamp light, plants on "
            "the windowsill, rain outside, cats sleeping, nostalgic film photo",
    "baroque_waltz": "grand old ballroom at candle-lit dusk, chandeliers, "
                     "empty marble floor in warm amber light, dust in the air, "
                     "vintage film photo",
    "disco_house": "empty roller-disco at night, mirror ball scattering light "
                   "over a polished floor, magenta haze, glossy reflections",
}

# "Edit-aesthetic" variants — the anime/car edit look, but ORIGINAL art
# (license-clean), one picked at random per episode for variety.
SCENE_VARIANTS = {
    "drift_phonk": [
        "deserted neon-lit city street at night, puddles mirroring pink neon, "
        "haze drifting through the light, 35mm film photo, phonk aesthetic",
        "a fictional Japanese sports coupe mid-drift on a wet mountain road "
        "at night, tail-light streaks, backlit tire smoke, cinematic film "
        "photo, no visible driver, no brand logos",
        "1990s retro anime film still: empty neon city street in night rain, "
        "hand-painted cel background, VHS scanlines and grain, no characters",
    ],
    "deep_pop": [
        "rainy window bokeh at blue hour, lonely balcony, golden and blue "
        "dusk light, melancholic cinematic still",
        "empty rooftop at dusk over city bokeh, one plastic chair, cold wind "
        "feeling, warm-vs-blue cinematic grade",
        "1990s retro anime film still: quiet bedroom at blue hour, rain "
        "streaks on glass, cel-shaded background art, no characters",
    ],
    "dark_ambient": [
        "endless fog over an empty landscape, one distant light source, "
        "teal-black palette, liminal and quiet",
        "abandoned concrete interior, single light shaft cutting through dust, "
        "brutalist silence, cinematic still",
        "1990s retro anime film still: dense fog over an empty field, one "
        "far light, muted watercolor background, no characters",
    ],
    "lofi": [
        "cozy bedroom studio at golden hour, warm lamp light, plants on the "
        "windowsill, rain outside, nostalgic film photo",
        "rainy café window from inside, steam over a cup, warm interior vs "
        "blue street outside, film photo",
        "1990s retro anime film still: cozy room at golden hour, plants and "
        "books, warm cel shading, no characters",
    ],
    "baroque_waltz": [
        "grand old ballroom at candle-lit dusk, chandeliers over empty marble, "
        "warm amber light, dust motes floating, vintage film photo",
        "antique harpsichord detail in a candle-lit parlour, brass and dark "
        "wood, baroque still life, film grain",
        "1990s retro anime film still: opulent old ballroom glowing amber, "
        "hand-painted background, empty and romantic",
    ],
    "disco_house": [
        "empty roller-disco at night, mirror ball light fields on polished "
        "floor, magenta haze, glossy reflections",
        "neon-lit empty dance floor from above, disco ball glow, magenta and "
        "violet grade, cinematic film photo",
        "1990s retro anime film still: retro disco hall aglow, mirror ball "
        "sparkles, cel-shaded, no dancers",
    ],
    "skyline_anthem": [
        "rooftop crowd silhouettes against a giant pink-orange sunrise, "
        "raised hands, lens flare, euphoric festival film still",
        "open highway at golden hour from inside a moving car, hands "
        "out the window, wide cinematic composition, warm film grain",
        "small town rooftops under a sky full of summer fireworks, "
        "seen from a hill, cinematic wide shot, hopeful mood",
    ],
    "villain_pop": [
        "empty baroque theatre lit by a single red spotlight, velvet "
        "curtain, dust motes in the beam, cinematic villain still",
        "rainy mansion window at night, candlelight inside, silhouette "
        "with a wine glass, gothic pop mood, film noir palette",
        "antique music box open on a black marble table, smoke curling, "
        "dramatic low-key lighting, cinematic macro",
    ],
    "orbit_trap": [
        "low-orbit view of city lights at night from a capsule window, "
        "stars and neon below, cinematic sci-fi still, no people",
        "empty launchpad at 4am, floodlights and fog, countdown clock "
        "glowing, cinematic wide shot",
        "mirror-tiled space helmet visor reflecting neon city lights, "
        "macro cinematic photo, no face visible",
    ],
}


def build_prompt(meta: dict) -> str:
    mood = MOODS.get(meta["genre_key"], MOODS["dark_ambient"])
    return (
        f"Cinematic wide 16:9 album-cover photograph for a {meta['genre']} "
        f"song called \"{meta['name']}\" ({meta['key']}, {meta['bpm']} BPM). "
        f"Scene: {mood}. Dark cinematic color grade, heavy film grain, "
        "moody, no people looking at the camera. "
        "IMPORTANT: absolutely no text, no words, no letters, no numbers, "
        "no logos, no watermark anywhere in the image."
    )


def generate(meta: dict) -> Image.Image:
    """Return the base scene as a PIL Image. Raises if every model fails."""
    from google import genai                      # imported lazily (CI dep)

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=key)
    models = ([os.environ["GEMINI_IMAGE_MODEL"]] if os.environ.get("GEMINI_IMAGE_MODEL")
              else []) + MODEL_CANDIDATES

    prompt = build_prompt(meta)
    errors = []
    for model in dict.fromkeys(models):           # dedupe, keep order
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            for part in resp.candidates[0].content.parts:
                blob = getattr(part, "inline_data", None)
                if blob and str(blob.mime_type).startswith("image"):
                    return Image.open(io.BytesIO(blob.data)).convert("RGB")
            errors.append(f"{model}: no image in response")
        except Exception as e:                    # quota / model missing / etc
            errors.append(f"{model}: {e}")
    raise RuntimeError(" | ".join(errors))


SHOT_TYPES = [
    "wide establishing shot",
    "intimate close-up detail of the key object",
    "slow dolly-through perspective, low angle",
    "aerial / elevated view of the same scene",
]


def generate_scenes(meta: dict, n: int = 4, scene_text: str | None = None) -> list[Image.Image]:
    """N matching but varied scenes of the SAME song-world (slideshow fuel)."""
    mood = scene_text or MOODS.get(meta["genre_key"], MOODS["dark_ambient"])
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=key)
    models = ([os.environ["GEMINI_IMAGE_MODEL"]] if os.environ.get("GEMINI_IMAGE_MODEL")
              else []) + MODEL_CANDIDATES

    scenes = []
    for i in range(n):
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        prompt = (
            f"Photorealistic cinematic still, {shot}: {mood}. Consistent "
            f"scene across a series — track \"{meta['name']}\" "
            f"({meta['genre']}, {meta['key']}). 35mm film, grain, analog "
            "bloom, cinematic grade, dark and moody. No people. Absolutely "
            "no text, no words, no letters, no numbers, no logos, no watermark."
        )
        got = None
        for model in dict.fromkeys(models):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                for part in resp.candidates[0].content.parts:
                    blob = getattr(part, "inline_data", None)
                    if blob and str(blob.mime_type).startswith("image"):
                        got = Image.open(io.BytesIO(blob.data)).convert("RGB")
                        break
            except Exception:
                continue
            if got:
                break
        if got:
            scenes.append(got)
    if len(scenes) < 2:
        raise RuntimeError(f"only {len(scenes)} scenes generated")
    return scenes

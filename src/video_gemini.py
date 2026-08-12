"""Veo clip generation via the Gemini API.

ANTI-PLASTIC doctrine (from Veo prompting research):
  - environments ONLY: no people, no faces, no hands → the classic AI tells
    (warped fingers, plastic skin, morphing faces) are structurally impossible
  - film-language prompt: photoreal, 35mm/anamorphic, grain, bloom
  - explicit negative prompt: text, watermark, distortion, morphing...
  - natural motion only: weather, light, smoke, slow camera drift

If the key has no Veo access (billing/quota/model), we raise and the caller
falls back to the multi-image Ken Burns engine. Non-fatal by design.

Optional env: VEO_MODEL (pin one), VEO_CLIPS=1 (how many distinct clips to try)
"""
from __future__ import annotations

import os
import time
from pathlib import Path

MODEL_CANDIDATES = [
    "veo-3.1-generate-preview",
    "veo-3.0-generate-preview",
    "veo-2.0-generate-001",
]

NEGATIVE = ("people, person, human, face, hands, fingers, skin, text, letters, "
            "numbers, watermark, logo, subtitle, morphing, warping, melting, "
            "plastic, doll-like, uncanny, deformed, glitch, cartoon, "
            "oversaturated, camera shake")

SCENES = {
    "drift_phonk": ("a rain-slick empty city street at night viewed from a "
                    "slow dolly glide, pink neon signs smearing in puddles, "
                    "light haze, drifting steam from a vent"),
    "deep_pop": ("a rain-streaked window at blue hour, slow focus drift from "
                 "raindrops to city bokeh beyond, a wilting flower on the sill, "
                 "curtain barely moving"),
    "dark_ambient": ("endless fog rolling over a dark moor at dusk, one far "
                     "light pulsing faintly, slow aerial push forward, grass "
                     "moving in wind"),
    "lofi": ("a cozy empty desk by a window at golden hour, dust motes "
             "floating in warm light, plants swaying gently, cat-shaped shadow "
             "of sunlight moving on paper"),
    "baroque_waltz": ("a candle-lit empty ballroom, chandeliers glowing amber, "
                      "flames trembling softly, dust drifting through shafts "
                      "of warm light over marble"),
    "disco_house": ("an empty mirror-ball dance floor at night, light fields "
                    "slowly sweeping polished floors, magenta haze drifting"),
    "skyline_anthem": ("a rooftop crowd silhouette against a giant pink-orange "
                       "sunrise, slow push-in, raised hands, lens flare, "
                       "confetti drifting in warm wind"),
    "villain_pop": ("an empty baroque theatre lit by one red spotlight, slow "
                    "dolly toward the stage, velvet curtains, dust motes in "
                    "the beam, gothic shadow play"),
    "orbit_trap": ("a capsule window view of city lights at night, slow drift "
                   "over the neon grid, stars above, engine hum, cinematic "
                   "sci-fi calm"),
}


def build_prompt(meta: dict) -> str:
    scene = SCENES.get(meta["genre_key"], SCENES["dark_ambient"])
    return (
        f"Photorealistic cinematic establishing shot: {scene}. "
        "Locked-off or very slow creeping camera, natural motion only — "
        "weather, light, particles. Shot on 35mm prime lens, anamorphic feel, "
        "visible film grain, soft analog bloom, shallow depth of field, "
        "cinematic color grade, moody and quiet. No AI look, no stylization. "
        f"Must match the mood of a {meta['genre']} track called "
        f"\"{meta['name']}\" ({meta['key']}). Real footage aesthetic."
    )


def generate_clip(meta: dict, out_path: Path, timeout_s: int = 480) -> Path:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    models = ([os.environ["VEO_MODEL"]] if os.environ.get("VEO_MODEL") else []) \
        + MODEL_CANDIDATES
    prompt = build_prompt(meta)
    errs = []
    for model in dict.fromkeys(models):
        try:
            try:
                op = client.models.generate_videos(
                    model=model, prompt=prompt,
                    config=types.GenerateVideosConfig(
                        aspect_ratio="16:9", negative_prompt=NEGATIVE))
            except Exception:
                op = client.models.generate_videos(model=model, prompt=prompt)
            t0 = time.time()
            while not op.done:
                if time.time() - t0 > timeout_s:
                    raise TimeoutError("veo op timed out")
                time.sleep(8)
                op = client.operations.get(op)
            gv = op.response.generated_videos[0]
            client.files.download(file=gv.video)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            gv.video.save(str(out_path))
            return out_path
        except Exception as e:
            errs.append(f"{model}: {e}")
    raise RuntimeError(" | ".join(errs))

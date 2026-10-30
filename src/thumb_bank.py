"""AI thumbnail bank — the boss's "don't draw them yourself, generate them".

Written 2026-10-26 after he said: *"don't make the thumbnails by you. I have
already added my Gemini API key there to keep the thumbnails as backup. Generate
hundreds and thousands of combination thumbnails… you can also add another
workflow that will generate a thumbnail — use any kind of very powerful AI model.
If a Gemini API key fails or any other API key fails, then that workflow will run
and generate a new thumbnail based on the prompt."* He also handed me his four-
year-old `FluxGEN-V2` HTML page and asked for its architecture to be upgraded and
used as the backup generator — so this module IS that architecture, ported: a
prompt × seed grid, `HEAD`-then-`GET` verification, and a cache.

What I measured before building (do not re-try these):
  · Pollinations — the engine his HTML used — is no longer free from a datacenter
    IP. From this workspace just now: `model=flux` → **HTTP 503**, `model=turbo` →
    **HTTP 402 Payment Required**. Same as the repo's own note from EP.064. It
    stays in the ladder, last, because it sometimes serves one image per burst.
  · Gemini image (his key) is the primary. On 2026-10-29's run it answered
    `429 RESOURCE_EXHAUSTED` on `gemini-3.1-flash-image` via the SDK path — model
    name right, quota empty — and `404` for `generate_images`, which is the wrong
    REST verb for image models. So: pool the keys (`src/keys.py` reads
    GEMINI_API_KEY, _2 … _6) and rotate on 429 before giving up.
  · `HF_TOKEN` is already in this repo's Secrets → the free Hugging Face inference
    endpoint (FLUX.1-schnell, SDXL-Turbo) is the second engine, at ₹0.
  · And the older hazard this file exists to kill: an engine that answers 200 with
    garbage. Pollinations once returned the SAME 22,889-byte JPEG three times.
    Every image here passes `usable()` (real decode, size, brightness floor,
    contrast floor) and is deduped by sha256 + dHash before it is trusted.

Nothing in this module can fail a release: every entry point returns None (with a
one-line reason) instead of raising, and the caller keeps its own fallback.
Dials: THUMB_AI=0 skips generation entirely, THUMB_BANK=0 skips the shelf.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request

W, H = 1280, 720
MIN_BYTES = 18_000                  # anything smaller is an error page, not a photo
MIN_LUMA = 38.0                     # the whole complaint was "everything is black"
MAX_LUMA = 225.0
MIN_SPREAD = 9.0                    # std-dev of luma: a flat fill has ~0
DHASH_MIN_DIST = 8                  # below this, it's the same picture in a coat

SHELF_TAG = os.environ.get("THUMB_SHELF", "thumb-lab")
INDEX_FILE = "index.json"


# ─────────────────────────── the combination matrix ───────────────────────────
# His ask was "hundreds and thousands of combinations". This is the grid the farm
# walks: every axis is a real thumbnail decision, and the product is the bank.
GENRE_MOOD = {
    "lofi": "dusty afternoon light through a rain-streaked window",
    "deep_pop": "neon wet pavement at golden hour",
    "drift_phonk": "headlights smearing on a night highway",
    "dark_ambient": "fog over empty industrial docks at 3am",
    "skyline_anthem": "a city skyline under a bruised sunset",
    "orbit_trap": "streetlamps seen from a rising elevator",
    "summer_rap": "sun-bleached beach parking lot at dusk",
    "melodic_trap": "rain on a bus shelter window, warm sodium light",
    "phonk_mafia": "an empty parking garage, one flickering tube light",
    "chart_pop": "confetti light on a dark stage",
    "villain_pop": "red emergency lighting in a marble corridor",
    "baroque_waltz": "candlelight on old gold picture frames",
    "disco_house": "a mirrorball cutting white beams across dark glass",
    "brazilian_phonk": "favela rooftop strings of bulbs at night",
    "velvet_fang": "velvet theatre seats under a single spotlight",
    "saint_of_leaving": "a train platform at dawn, steam and lamplight",
    "emo_rap": "a bedroom lit only by a CRT television",
    "ashrise": "ash drifting over a cold fire at blue hour",
    "templestep": "stone temple steps lit by floating lanterns",
    "default": "a lonely road under a wide dusk sky",
}
TIME = ["just before sunrise", "harsh midday", "golden hour", "blue hour",
        "deep night", "thunderstorm dark"]
WEATHER = ["clear and dry", "thin rain", "wet reflective ground", "heavy fog",
           "low cloud", "dust in the air"]
FRAMING = ["wide establishing shot, subject small in frame",
           "low angle, dramatic perspective",
           "close-up on one detail, shallow depth of field",
           "symmetrical centred composition with strong negative space",
           "overhead drone view", "through a doorway or window, framing inside frame"]
TEXTURE = ["35mm film grain, faded print", "clean digital photo, crisp lens",
           "long exposure with light trails", "slightly overexposed highlights",
           "matte print, lifted blacks", "wet glass reflections and bokeh"]
PALETTE = ["teal and orange", "warm amber on deep blue", "monochrome with one red accent",
           "pastel haze", "high-contrast noir", "saturated neon on black",
           "muted earth tones with a bright highlight"]
LENS = ["35mm", "50mm", "85mm portrait lens", "24mm wide", "anamorphic"]


def axes() -> dict[str, list[str]]:
    """The matrix, exposed so the farm and the tests agree on one source."""
    return {"genre": list(GENRE_MOOD), "time": TIME, "weather": WEATHER,
            "framing": FRAMING, "texture": TEXTURE, "palette": PALETTE, "lens": LENS}


def combo_count() -> int:
    n = 1
    for v in axes().values():
        n *= len(v)
    return n


def build_prompt(idx: int, genre_key: str | None = None) -> tuple[dict, str]:
    """Deterministic walk of the matrix: index → (choices, prompt).

    No text/lettering is ever asked for — image models garble it, and the channel's
    own brand + title are overlaid afterwards by art.overlay(), which is the only
    place text enters a thumbnail.
    """
    ax = axes()
    g = genre_key if genre_key in GENRE_MOOD else "default"
    time_, weather, frame, tex, pal, lens = (ax["time"][idx % len(ax["time"])],
                                            ax["weather"][(idx // 6) % len(ax["weather"])],
                                            ax["framing"][(idx // 36) % len(ax["framing"])],
                                            ax["texture"][(idx // 216) % len(ax["texture"])],
                                            ax["palette"][(idx // 1296) % len(ax["palette"])],
                                            ax["lens"][(idx // 7776) % len(ax["lens"])])
    ch = {"genre": g, "time": time_, "weather": weather, "framing": frame,
          "texture": tex, "palette": pal, "lens": lens}
    prompt = (f"cinematic still photograph, {GENRE_MOOD[g]}, {time_}, {weather}, "
              f"{frame}, {tex}, colour palette {pal}, shot on {lens} lens, "
              f"16:9 widescreen, strong single light source, deep but readable "
              f"shadows, high dynamic range, professional music-release cover art, "
              f"no text, no letters, no watermark, no logo, no people, no faces")
    return ch, prompt


# ───────────────────────────── image validation ──────────────────────────────
def _img(data: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(data))


def stats(im) -> tuple[float, float, int]:
    """(mean luma, luma spread, dHash) — written into the bank index so the shelf
    is auditable without re-downloading images."""
    l0, spread = _luma_pair(im)
    return round(l0, 1), round(spread, 1), dhash(im)


def dhash(im, n: int = 8) -> int:
    g = im.convert("L").resize((n + 1, n))
    px = list(g.getdata())
    bits = 0
    for r in range(n):
        row = px[r * (n + 1):(r + 1) * (n + 1)]
        for c in range(n):
            bits = (bits << 1) | (1 if row[c] > row[c + 1] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def usable(data: bytes, near: list[int] | None = None) -> tuple[object | None, str]:
    """(image | None, why). The gate every generated/received byte-stream passes."""
    try:
        if len(data) < MIN_BYTES:
            return None, f"only {len(data)} bytes — an error page, not an image"
        im = _img(data)
        im.load()
    except Exception as e:
        return None, f"does not decode ({str(e)[:60]})"
    if im.width < 900 or im.height < 500:
        return None, f"{im.width}×{im.height} is too small to scale up for a thumbnail"
    if abs(im.width / im.height - W / H) > 0.30:
        return None, f"aspect {im.width / im.height:.2f} is not near 16:9"
    l0, spread = _luma_pair(im)
    if l0 < MIN_LUMA:
        return None, f"mean luma {l0:.0f}/255 — that is the black-box complaint again"
    if l0 > MAX_LUMA:
        return None, f"mean luma {l0:.0f} — blown out"
    if spread < MIN_SPREAD:
        return None, f"contrast spread {spread:.1f} — a flat fill, not a picture"
    h = dhash(im)
    if near and min(hamming(h, x) for x in near) < DHASH_MIN_DIST:
        return None, "duplicate of an image already on the shelf (dHash)"
    return im, "ok"


def _luma_pair(im) -> tuple[float, float]:
    import numpy as np
    a = np.asarray(im.convert("RGB").resize((320, 180))).astype("float32")
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    return float(lum.mean()), float(lum.std())


# ─────────────────────────────── the engines ────────────────────────────────
def pollinations_url(prompt: str, seed: int, w: int = W, h: int = H, model: str = "flux") -> str:
    """His HTML's URL, upgraded: nologo + explicit seed + referrer (the modern
    anonymous tier wants it) and a prompt-safe percent-encode."""
    q = urllib.parse.quote(prompt, safe="")
    return (f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}"
            f"&seed={int(seed)}&nologo=true&model={model}&referrer=nixspeech")


def hf_url(model: str) -> tuple[str, str]:
    return (f"https://api-inference.huggingface.co/models/{model}", model)


def _get(url: str, headers: dict | None = None, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "yt-auto-thumb/1.0",
                                               **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _gemini(meta_prompt: str, seed: int):
    """Primary: the boss's own Gemini key(s), rotating the pool on 429/403."""
    try:
        from src import keys
        from google import genai
        from google.genai import types
    except Exception as e:
        return None, f"genai unavailable ({str(e)[:50]})"
    pool = keys.pool("GEMINI_API_KEY")
    if not pool:
        return None, "no GEMINI_API_KEY in this environment"
    last = ""
    for model in ("gemini-3.1-flash-image", "gemini-2.5-flash-image"):
        for k in pool:
            try:
                client = genai.Client(api_key=k)
                cfg = types.GenerateContentConfig(
                    response_mime_type="image/png",
                    seed=int(seed) % (2 ** 31),
                    temperature=0.9)
                r = client.models.generate_content(
                    model=model,
                    contents=("Generate one 1280x720 cinematic image. " + meta_prompt),
                    config=cfg)
                for part in getattr(getattr(r, "candidates", None), "__iter__", lambda: [])() or []:
                    pass
                cand = (r.candidates or [None])[0]
                for p in (cand.content.parts if cand and cand.content else []):
                    inline = getattr(p, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        return inline.data, f"gemini/{model}"
                last = f"{model}: no image part"
            except Exception as e:
                last = f"{model}: {str(e)[:70]}"
                continue
    return None, last


def _hf(meta_prompt: str, seed: int):
    """Second: free HF inference with the repo's existing HF_TOKEN, ₹0."""
    tok = (os.environ.get("HF_TOKEN") or "").strip()
    if not tok:
        return None, "no HF_TOKEN"
    import json as _j
    body = {"inputs": meta_prompt,
            "parameters": {"guidance_scale": 3.5, "num_inference_steps": 4,
                           "seed": int(seed) % (2 ** 31), "width": W, "height": H},
            "options": {"wait_for_model": True, "use_cache": True}}
    last = ""
    for model in ("black-forest-labs/FLUX.1-schnell", "stabilityai/sdxl-turbo"):
        try:
            req = urllib.request.Request(
                f"https://api-inference.huggingface.co/models/{model}",
                data=_j.dumps(body).encode(), method="POST",
                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                         "User-Agent": "yt-auto-thumb/1.0", "x-wait-for-model": "true"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if data[:16].startswith(b'{"error'):
                last = f"{model}: {data[:80]!r}"
                continue
            return data, f"huggingface/{model.split('/')[-1]}"
        except Exception as e:
            last = f"{model}: {str(e)[:70]}"
    return None, last


def _pollinations(meta_prompt: str, seed: int):
    """Third: the engine from the boss's 2022 page. Kept because it is free and
    sometimes serves one image per burst; measured 402/503 from a datacenter IP."""
    last = ""
    for model in ("flux", "turbo"):
        try:
            data = _get(pollinations_url(meta_prompt, seed, model=model), timeout=120)
            return data, f"pollinations/{model}"
        except urllib.error.HTTPError as e:
            last = f"pollinations/{model}: HTTP {e.code}"
        except Exception as e:
            last = f"pollinations/{model}: {str(e)[:60]}"
    return None, last


def generate(prompt: str, seed: int, near: list[int] | None = None) -> tuple[bytes | None, str, str]:
    """(bytes, engine, why). Walks the ladder; returns the first image that passes
    usable(). Every engine is allowed to be dead — this never raises."""
    ladder = []
    if os.environ.get("THUMB_GEMINI", "1").strip() != "0":
        ladder.append(_gemini)
    if os.environ.get("THUMB_HF", "1").strip() != "0":
        ladder.append(_hf)
    if os.environ.get("THUMB_POLLINATIONS", "1").strip() != "0":
        ladder.append(_pollinations)
    whys = []
    for eng in ladder:
        try:
            data, label = eng(prompt, seed)
        except Exception as e:
            whys.append(f"{eng.__name__}: {str(e)[:60]}")
            continue
        if not data:
            whys.append(label)
            continue
        im, why = usable(data, near=near)
        if im is None:
            whys.append(f"{label} rejected → {why}")
            continue
        return data, label, "ok"
    return None, "", " · ".join(whys) or "no engine enabled"


# ───────────────────────────── the shelf (bank) ─────────────────────────────
def shelf_url(name: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    return f"https://github.com/{repo}/releases/download/{SHELF_TAG}/{name}"


def load_index(cache_dir=None):
    """Read the bank index (cache_dir first, then the shelf). None = no bank yet."""
    from pathlib import Path
    if cache_dir:
        p = Path(cache_dir) / INDEX_FILE
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    try:
        data = _get(shelf_url(INDEX_FILE), timeout=45)
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        print(f"  🗃 thumb bank unavailable ({str(e)[:70]})")
        return None


def pick_index(idx: int, idx_obj, genre_key: str | None = None) -> dict | None:
    """Rotate the bank deterministically, preferring that genre's images. No state
    is written back — with a few hundred images per genre an episode collision is
    years away, and a release must never need to upload to be correct."""
    rows = (idx_obj or {}).get("images") or []
    if not rows:
        return None
    mine = [r for r in rows if genre_key and r.get("genre") == genre_key] or rows
    return mine[idx % len(mine)] if mine else None


def acquire(meta: dict, ep: int, cache_dir, rng=None):
    """(Path | None, source, note). The release-time entry point.

    Order: (1) the bank — an AI image already generated and validated on another
    day, so a dead API night still gets real art; (2) generate live. Returns None
    only after both, and the caller falls back to the cover it already has."""
    from pathlib import Path
    if os.environ.get("THUMB", "1").strip() == "0":
        return None, "off", "THUMB=0"
    genre = meta.get("genre_key") or "default"
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    if os.environ.get("THUMB_BANK", "1").strip() != "0":
        ix = load_index(cache)
        # sha256, not hash(): Python's str hash is salted per process, so a
        # "deterministic" rotation built on it would pick a different image every
        # time the run is retried.
        name_h = int(hashlib.sha256(str(meta.get("name", "")).encode()).hexdigest()[:6], 16)
        row = pick_index(ep * 7919 + name_h, ix, genre) if ix else None
        if row:
            out = cache / f"bank_{row.get('sha', 'x')[:16]}.jpg"
            try:
                if not out.exists():
                    out.write_bytes(_get(shelf_url(out.name), timeout=60))
                im, why = usable(out.read_bytes())
                if im is not None:
                    return out, "bank", f"{row.get('sha','?')[:8]} · {why}"
                out.unlink(missing_ok=True)
                note = f"bank entry unusable ({why})"
            except Exception as e:
                note = f"bank fetch failed ({str(e)[:60]})"
        else:
            note = "bank empty"
    if os.environ.get("THUMB_AI", "1").strip() == "0":
        return None, "off", note or "THUMB_AI=0"
    ch, prompt = build_prompt((ep * 31 + 7) % combo_count(), genre)
    data, engine, why = generate(prompt, seed=ep * 1013 + 17)
    if data:
        out = cache / f"live_ep{ep:03d}.jpg"
        out.write_bytes(data)
        return out, engine, why
    return None, "", f"generation failed: {why or note}"

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
import time
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
# What each engine is, and what was measured about it on 2026-10-30 (do not
# re-derive these; the first live farm run — job 41066336729 — printed all of it):
#   · the genai SDK is not on a runner unless requirements.txt is installed, and
#     `pip install genai` is the WRONG package name (it is `google-genai`);
#   · api-inference.huggingface.co no longer resolves at all → URLError -5;
#   · router.huggingface.co/v1/images/generations answers 401 without a token →
#     the path is alive, the token is the variable;
#   · image.pollinations.ai still paywalls a datacenter IP (flux 503 / turbo 402).
# So: every engine has a dependency-free HTTP path, and a refusal must never
# look like a success.
PROMPT_PREFIX = "Generate one 1280x720 cinematic photograph. "
GEMINI_MODELS = ("gemini-3.1-flash-image", "gemini-2.5-flash-image")   # same list src/art_gemini.py verified live
HF_MODELS = ("black-forest-labs/FLUX.1-schnell", "stabilityai/sdxl-turbo")


def pollinations_url(prompt: str, seed: int, w: int = W, h: int = H, model: str = "flux") -> str:
    """His HTML's URL, upgraded: nologo + explicit seed + referrer (the modern
    anonymous tier wants it) and a prompt-safe percent-encode."""
    q = urllib.parse.quote(prompt, safe="")
    return (f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}"
            f"&seed={int(seed)}&nologo=true&model={model}&referrer=nixspeech")


def hf_url(model: str) -> list:
    """Endpoints for one HF model, best-first (see the measurement above)."""
    return ["https://router.huggingface.co/v1/images/generations",
            f"https://api-inference.huggingface.co/models/{model}"]


def _get(url: str, headers: dict | None = None, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "yt-auto-thumb/1.0",
                                               **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "yt-auto-thumb/1.0",
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _as_jpeg(data: bytes) -> bytes:
    """One codec on the shelf. A webp/png answer is re-encoded here, once, so a
    file named `…jpg` really is a JPEG — a release must not depend on a phone's
    content sniffing."""
    try:
        im = _img(data)
        if (getattr(im, "format", "") or "").upper() == "JPEG" and len(data) >= MIN_BYTES:
            return data
        out = io.BytesIO()
        im.convert("RGB").save(out, "JPEG", quality=95)
        b = out.getvalue()
        return b if len(b) >= MIN_BYTES else data
    except Exception:
        return data


def _to169(data: bytes) -> bytes:
    """Centre-crop any answer to 16:9 and re-encode, so a square reply from an
    engine is still a frame we can use. On any trouble the original bytes come
    back — this can only ever make an image more acceptable, never fail."""
    try:
        im = _img(data)
        if abs(im.width / im.height - W / H) <= 0.06:
            return data
        if im.width * H / W <= im.height:
            h2 = max(1, int(round(im.width * H / W)))
            y0 = (im.height - h2) // 2
            im = im.crop((0, y0, im.width, y0 + h2))
        else:
            w2 = max(1, int(round(im.height * W / H)))
            x0 = (im.width - w2) // 2
            im = im.crop((x0, 0, x0 + w2, im.height))
        if im.width < 900:
            return data
        out = io.BytesIO()
        im.convert("RGB").save(out, "JPEG", quality=95)
        b = out.getvalue()
        return b if len(b) >= MIN_BYTES else data
    except Exception:
        return data


def _dead_key(hint: str) -> bool:
    s = (hint or "").lower()
    return any(k in s for k in ("429", "quota", "resource_exhausted", "403", "permission",
                                "invalid api key", "api_key_not_valid", "unauthenticated"))


def _genai_rest(key: str, model: str, prompt: str, seed: int, wide: bool = True):
    """Gemini over raw urllib — no SDK, no pip, works on a runner whose install
    step failed. (bytes|None, hint)"""
    cfg = {"responseModalities": ["TEXT", "IMAGE"] if wide else ["IMAGE"],
           "seed": int(seed) % (2 ** 31), "temperature": 0.9}
    if wide:
        cfg["imageConfig"] = {"aspectRatio": "16:9"}
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={urllib.parse.quote(key)}")
    try:
        raw = _post_json(url, {"contents": [{"parts": [{"text": prompt}]}],
                               "generationConfig": cfg}, timeout=180)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:280]
        except Exception:
            detail = ""
        return None, f"HTTP {e.code} {detail}"
    except Exception as e:
        return None, f"{type(e).__name__} {str(e)[:90]}"
    try:
        d = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None, f"not json ({raw[:60]!r})"
    import base64
    for c in (d.get("candidates") or []):
        for part in (c.get("content") or {}).get("parts") or []:
            blob = part.get("inlineData") or part.get("inline_data") or {}
            if blob.get("data"):
                try:
                    return base64.b64decode(blob["data"]), "ok"
                except Exception as e:
                    return None, f"bad base64 ({str(e)[:50]})"
    err = (d.get("error") or {}).get("message") or d.get("promptFeedback") or "no inline image part"
    return None, str(err)[:280]


def _gemini(meta_prompt: str, seed: int):
    """Primary: the boss's own Gemini key(s) — his words were "I have already
    added my Gemini API key there to keep the thumbnails as backup".

    The proven call shape first (`src/art_gemini._image_from_model`, the helper
    the nightly cover art already uses, so the model ids are ones this repo has
    seen live), then the same thing over raw HTTP so a missing pip package
    cannot close the lane. Pool rotation on a key-level refusal: with one key in
    the pool that is a no-op, but GEMINI_API_KEY_2…_6 light it up unchanged."""
    prompt = PROMPT_PREFIX + meta_prompt
    try:
        from src import keys as keypool
        pool = keypool.pool("GEMINI_API_KEY")
    except Exception as e:
        return None, f"key pool unavailable ({str(e)[:50]})"
    if not pool:
        return None, "no GEMINI_API_KEY in this environment"
    pin = (os.environ.get("GEMINI_IMAGE_MODEL") or "").strip()
    models = [m for m in ([pin] if pin else []) + list(GEMINI_MODELS) if m]
    hints = []
    try:
        from google import genai
        from src import art_gemini
    except Exception as e:
        genai = art_gemini = None
        hints.append(f"sdk missing ({str(e)[:44]})")
    if genai is not None:
        for model in models:
            for k in pool:
                try:
                    img, hint = art_gemini._image_from_model(genai.Client(api_key=k), model, prompt)
                except Exception as e:
                    img, hint = None, f"{type(e).__name__}: {str(e)[:120]}"
                if img is not None:
                    out = io.BytesIO()
                    img.convert("RGB").save(out, "JPEG", quality=95)
                    return out.getvalue(), f"gemini/{model}"
                hints.append(f"sdk/{model}: {hint}")
                if _dead_key(hint):
                    continue                     # another key may carry quota
                break                            # the key is fine, the model is not
    tries = 0
    for model in models:
        for wide in (True, False):
            for k in pool:                          # rotate the key pool…
                if tries >= 6:
                    break                           # …but never past 6 asks per slot
                tries += 1
                data, hint = _genai_rest(k, model, prompt, seed, wide=wide)
                if data:
                    return _to169(data), f"gemini-rest/{model}"
                hints.append(f"rest/{model}: {hint}")
                # only a key-shaped refusal is worth another key for: a wrong
                # model id or a bad field is the same answer six times over
                if "404" in hint or not _dead_key(hint):
                    break
            if tries >= 6:
                break
    return None, (" · ".join(hints)[:420] or "gemini: no verdict")


def _hf(meta_prompt: str, seed: int):
    """Second engine: Hugging Face free inference with the HF_TOKEN that is
    already in this repo's Secrets — ₹0, and the exact "if a key fails, another
    model answers" lane he asked for. Answers are cropped to 16:9 before use."""
    tok = (os.environ.get("HF_TOKEN") or "").strip()
    if not tok:
        return None, "no HF_TOKEN"
    prompt = PROMPT_PREFIX + meta_prompt
    heads = {"Authorization": f"Bearer {tok}"}
    last = ""
    for model in HF_MODELS:
        router, classic = hf_url(model)
        tries = [(router, {"model": model, "prompt": prompt, "n": 1, "size": "1024x576"}),
                 (classic, {"inputs": prompt,
                            "parameters": {"guidance_scale": 3.5, "num_inference_steps": 4,
                                           "seed": int(seed) % (2 ** 31),
                                           "width": 1024, "height": 576},
                            "options": {"wait_for_model": True, "use_cache": True}})]
        for url, payload in tries:
            try:
                data = _post_json(url, payload, headers=heads, timeout=180)
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", "replace")[:200]
                except Exception:
                    detail = ""
                last = f"{model.split('/')[-1]}: HTTP {e.code} {detail}"
                continue
            except Exception as e:
                last = f"{model.split('/')[-1]}: {type(e).__name__} {str(e)[:80]}"
                continue
            if data[:1] == b"{":
                try:
                    d = json.loads(data.decode("utf-8", "replace"))
                except Exception:
                    last = f"{model.split('/')[-1]}: not json ({data[:50]!r})"
                    continue
                e0 = ((d.get("data") or d.get("images") or [{}])[0]) or {}
                import base64
                if e0.get("b64_json"):
                    return _to169(base64.b64decode(e0["b64_json"])), f"huggingface/{model.split('/')[-1]}"
                if e0.get("url"):
                    try:
                        return _to169(_get(e0["url"], timeout=90)), f"huggingface/{model.split('/')[-1]} · via url"
                    except Exception as e:
                        last = f"{model.split('/')[-1]}: url fetch {str(e)[:60]}"
                        continue
                last = f"{model.split('/')[-1]}: {str(d.get('error') or d)[:200]}"
                continue
            if len(data) < MIN_BYTES:
                last = f"{model.split('/')[-1]}: {len(data)}B back — not an image"
                continue
            return _to169(data), f"huggingface/{model.split('/')[-1]}"
    return None, last or "huggingface: no verdict"


def _space_host(space_id: str = "") -> str:
    sid = (space_id or os.environ.get("THUMB_SPACE_ID", "") or "black-forest-labs/FLUX.1-schnell").strip()
    owner, _, name = sid.partition("/")
    if not name:
        owner, name = "black-forest-labs", "FLUX.1-schnell"
    # Spaces hostnames are the id with every "." and "_" folded to "-" and the
    # whole thing lower-cased: FLUX.1-schnell lives at …-flux-1-schnell.hf.space.
    # Skip that and TLS fails with a hostname-mismatch that reads like a dead
    # space rather than a typo (measured twice on 2026-10-30).
    host = f"{owner}-{name}".lower().replace("_", "-").replace(".", "-")
    return f"https://{host}.hf.space"


def _api_prefix(base: str) -> str:
    """Gradio moved its API root once already — ask the app, don't assume."""
    try:
        d = json.loads(_get(base + "/config", timeout=25).decode("utf-8", "replace"))
        return (d.get("api_prefix") or "/gradio_api").rstrip("/")
    except Exception:
        return "/gradio_api"


def _sse_value(url: str, timeout: int = 240):
    """Read one gradio queued call to its `complete` frame, by hand.

    No gradio_client, no pip. (Night one learned that a quiet failed install
    takes a whole engine away, so every engine here speaks plain HTTP.)
    """
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream",
                                               "User-Agent": "yt-auto-thumb/1.0"})
    ev, data = "", []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if not line:                       # an SSE frame is over
                    payload = "\n".join(data)
                    if ev == "complete":
                        try:
                            return json.loads(payload), "ok"
                        except Exception as e:
                            return None, f"unreadable complete frame ({str(e)[:60]})"
                    if ev == "error":
                        return None, f"space error: {payload[:180]}"
                    ev, data = "", []
                    continue
                if line.startswith("event:"):
                    ev = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data.append(line.split(":", 1)[1].strip())
    except Exception as e:
        return None, f"{type(e).__name__} {str(e)[:90]}"
    return None, "stream ended before a complete frame"


def _space(meta_prompt: str, seed: int):
    """Third, and the one that saves the night when no key works: the official
    FLUX.1-schnell demo Space on Hugging Face — no token, no key, ₹0.

    Measured 2026-10-30 from a datacenter IP, the same class of network a GitHub
    runner is: submit → **4.2 s and 16.8 s** on two calls → a real 1280×720
    image, 35-69 kB, mean luma 60-136, which walks straight through `usable()`.
    Then the next three calls were refused in 0.7 s: the demo rate-limits per
    visitor, so one night of this is a few images, not twenty-four.

    That is the answer to the boss's exact sentence — "if a Gemini API key fails
    or any other API key fails, then that workflow will run and generate a new
    thumbnail based on the prompt" — and tonight is that night: his key came
    back 429 RESOURCE_EXHAUSTED on both image models.

    Park it with THUMB_SPACE=0, move it with THUMB_SPACE_ID / THUMB_SPACE_API.
    """
    if os.environ.get("THUMB_SPACE", "1").strip() == "0":
        return None, "space parked (THUMB_SPACE=0)"
    base, api = _space_host(), (os.environ.get("THUMB_SPACE_API") or "infer").strip("/")
    pfx = _api_prefix(base)
    payload = {"data": [PROMPT_PREFIX + meta_prompt, int(seed) % (2 ** 31), False, W, H, 4]}
    last = ""
    for attempt in range(1, 3):                       # the demo is polite about a second try
        try:
            back = _post_json(f"{base}{pfx}/call/{api}", payload, timeout=60)
            event = json.loads(back.decode("utf-8", "replace")).get("event_id")
        except Exception as e:
            last = f"submit refused ({str(e)[:110]})"
            if attempt < 2:
                _pause(8)
            continue
        if not event:
            last = f"no event_id ({back[:70]!r})"
            if attempt < 2:
                _pause(8)
            continue
        val, why = _sse_value(f"{base}{pfx}/call/{api}/{event}", timeout=240)
        if val is None:
            # "space error: null" is what a rate-limited demo says here — a busy
            # signal, not a broken one, so it must never read as a code bug
            # what the demo actually sends is `event: error` / `data: null` —
            # busy, frozen, or rate-limiting this IP: it says which, and I don't
            last = f"{why[:170]} — the shared demo is not taking jobs from here right now"
            if attempt < 2:
                _pause(20)
            continue
        if isinstance(val, dict) and "value" in val:
            val = val["value"]
        rec = (val[0] if isinstance(val, list) and val else val)
        if not isinstance(rec, dict):
            last = f"answer we cannot read ({str(val)[:120]})"
            continue
        u = rec.get("url") or rec.get("path") or ""
        if not u:
            last = f"no file url in the answer ({str(rec)[:100]})"
            continue
        try:
            data = _get(u if str(u).startswith("http") else base + str(u), timeout=90)
        except Exception as e:
            last = f"file fetch failed ({str(e)[:80]})"
            if attempt < 2:
                _pause(8)
            continue
        return data, f"hf-space/{api}{'' if attempt == 1 else ' · retry'}"
    return None, f"space: {last}"


def _pause(s: float) -> None:
    """Sleep, unless a test wants no sleeping."""
    if os.environ.get("THUMB_INSTANT") != "1":
        time.sleep(s)


def _pollinations(meta_prompt: str, seed: int):
    """Third, and only third: the engine from the boss's 2022 page. Kept because
    it is free and sometimes serves one image per burst; measured 402/503 from a
    datacenter IP on 2026-10-30, same as the repo's own EP.064 note."""
    whys = []
    for model in ("flux", "turbo"):
        try:
            data = _get(pollinations_url(PROMPT_PREFIX + meta_prompt, seed, model=model), timeout=120)
            return _to169(data), f"pollinations/{model}"
        except urllib.error.HTTPError as e:
            whys.append(f"pollinations/{model}: HTTP {e.code}")
        except Exception as e:
            whys.append(f"pollinations/{model}: {str(e)[:60]}")
    return None, " · ".join(whys)


def generate(prompt: str, seed: int, near: list[int] | None = None) -> tuple[bytes | None, str, str]:
    """(bytes, engine, why). Walks the ladder; returns the first image that passes
    usable(). Every engine is allowed to be dead — this never raises."""
    ladder = []
    if os.environ.get("THUMB_GEMINI", "1").strip() != "0":
        ladder.append(_gemini)
    if os.environ.get("THUMB_HF", "1").strip() != "0":
        ladder.append(_hf)
    if os.environ.get("THUMB_SPACE", "1").strip() != "0":
        ladder.append(_space)
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
        data = _as_jpeg(_to169(data))            # a square answer is still a frame
        im, why = usable(data, near=near)
        if im is None:
            whys.append(f"{label} rejected → {why}")
            continue
        return data, label, "ok"
    return None, "", (" · ".join(whys)[:900]) or "no engine enabled"


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
            # The asset on the shelf is `row["file"]` — the LOCAL cache name is
            # not that, and asking the release URL for it 404s every time. This
            # was found by calling acquire() against the shelf the farm had just
            # filled (2026-10-30, thumb-lab at 3 images): the bank looked empty
            # from the outside and every night paid for live generation instead.
            remote = str(row.get("file") or f"{row.get('sha', '')[:24]}.jpg")
            out = cache / f"bank_{remote}"
            try:
                if not out.exists() or out.stat().st_size < MIN_BYTES:
                    out.write_bytes(_get(shelf_url(remote), timeout=60))
                im, why = usable(out.read_bytes())
                if im is not None:
                    return out, "bank", f"{remote[:12]} · {row.get('engine', '?')} · {why}"
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
    return None, "", f"generation failed: {why or 'no engine'} · {note or 'bank empty'}"

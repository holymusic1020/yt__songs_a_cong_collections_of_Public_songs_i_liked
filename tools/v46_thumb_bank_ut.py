#!/usr/bin/env python3
"""UT-46 (2026-10-26) — the AI thumbnail bank: the ladder, the gate, the shelf.

Boss's instruction: *"don't make the thumbnails by you … generate hundreds and
thousands of combination thumbnails … if a Gemini API key fails or any other key
fails, then that workflow will run and generate a new thumbnail."* So the things
that must be true — and each one is a check below, not a hope:

  1. the combination matrix really is in the thousands (his words) and a walk of
     it covers every axis value instead of reusing three prompts forever;
  2. NOTHING enters the bank without passing usable(): decodes, is big enough,
     is 16:9-ish, is bright enough (mean luma ≥ 38 — the whole complaint was 8–25),
     has contrast, and is not a near-duplicate of what is already on the shelf.
     That last clause exists because Pollinations once answered with the IDENTICAL
     22,889-byte JPEG three nights running;
  3. every engine is allowed to be dead: generate() walks Gemini → HF → Pollinations
     and returns a reason instead of raising, and load_index/acquire/pick all
     return None on a total outage so the release falls back to its own cover;
  4. the farm is decorative: exit 0 on every failure path, and the workflow runs
     it behind `|| true` on its own schedule, 7 h from the b-roll farm and ~11 h
     from the release;
  5. main.py uses the ladder (pick → brand → relight → set on all three uploads)
     and records WHICH engine produced the image in the manifest, so "🟢 all
     lanes clear" can never again be a lie about a cosmetic lane.

Network is faked (monkeypatched transports) — this test makes zero real calls.
"""
import io
import json
import base64
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw                          # noqa: E402
import numpy as np                                         # noqa: E402
from src import thumb, thumb_bank as TB                    # noqa: E402

TMP = ROOT / "out_ut_bank"
TMP.mkdir(exist_ok=True)
checks = []


def chk(cond, msg, detail=""):
    checks.append(bool(cond))
    print(f"  {'✅' if cond else '❌'} {msg}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        raise AssertionError(msg + " :: " + detail)


def art(seed=1, w=1280, h=720, bright=True, flat=False):
    """A synthetic 'AI image': gradient + shapes, or a flat/degenerate variant."""
    rng = np.random.default_rng(seed)
    if flat:
        a = np.full((h, w, 3), 128 if bright else 4, dtype=np.uint8)
    else:
        yy, xx = np.mgrid[0:h, 0:w]
        g = (xx / w * 120 + 40) if bright else (xx / w * 22 + 3)
        a = np.stack([g + (yy / h) * 40, g * 0.8, g * 0.6], axis=-1).astype(np.uint8)
        im0 = Image.fromarray(a)
        d = ImageDraw.Draw(im0)
        for i in range(14):
            x0, y0 = int(rng.integers(0, w - 200)), int(rng.integers(0, h - 160))
            d.rectangle([x0, y0, x0 + int(rng.integers(40, 240)), y0 + int(rng.integers(30, 180))],
                        fill=tuple(int(v) for v in rng.integers(30, 255, 3)))
        return im0
    return Image.fromarray(a)


def jpg(im) -> bytes:
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)
    return b.getvalue()


print("── 1 · the matrix is 'hundreds and thousands', and a walk covers it ──")
n = TB.combo_count()
chk(n > 100_000, f"combination matrix = {n:,} (he asked for hundreds and thousands)", str(n))
seen = {k: set() for k in TB.axes()}
# A stride that shares a factor with an axis's period silently NEVER visits that
# axis again (226 with a 6-long axis hits only 3 of 6 values) — so the walk uses
# an odd stride that is not a multiple of 3, the same requirement the farm's own
# step of 61 satisfies. This is the one real coverage risk in a matrix walk.
step = max(1, (n // 4000) | 1)
while step % 3 == 0:
    step += 2
for i in range(0, n, step):
    ch, _p = TB.build_prompt(i, list(TB.GENRE_MOOD)[(i // 7) % 20])
    for k, v in ch.items():
        seen[k].add(v)
missing = {k: len(TB.axes()[k]) - len(seen[k]) for k in TB.axes()}
chk(all(x == 0 for x in missing.values()), f"a stride-{step} walk of the matrix hits every axis value",
    str(missing))
fstride = [TB.build_prompt((0 + j * 61) % n, "lofi")[0] for j in range(24)]
chk(len({f["time"] for f in fstride}) >= 4 and len({f["weather"] for f in fstride}) >= 4,
    "one farm night (step 61, 24 images) does not freeze on the same 2-3 moods",
    str(sorted({f["time"] for f in fstride})))
p1 = TB.build_prompt(1234, "lofi")[1]
p2 = TB.build_prompt(1235, "lofi")[1]
chk(p1 != p2, "two neighbours are two different pictures (a seed-locked bank is a dead bank)")
chk("no text" in p1 and "no watermark" in p1 and "no people" in p1,
    "the prompt forbids text, watermarks and people — branding is ours, faces are never")
chk("16:9" in p1, "and it asks for the 16:9 shape a thumbnail needs")
chk(TB.build_prompt(7, "not_a_genre")[0]["genre"] == "default",
    "an unknown genre falls to the default mood instead of raising")

print("── 2 · usable(): nothing enters the bank that can make the grid black again ──")
good = jpg(art())
im, why = TB.usable(good)
chk(im is not None, f"a real 1280×720 varied JPEG is accepted ({why})")
chk(TB.usable(b"x" * 400)[0] is None, "an error page (< 18 KB) is rejected")
chk(TB.usable(b"not an image at all, but long enough to pass the size gate......")[0] is None,
    "non-image bytes are rejected by the decoder, not trusted")
chk(TB.usable(jpg(art(flat=True, bright=False)))[0] is None,
    "a flat near-black image is rejected — mean luma floor is 38, the live channel measured 8–25")
chk(TB.usable(jpg(art(w=400, h=225)))[0] is None, "an undersized image is rejected")
wide = jpg(art(w=1280, h=400))
chk(TB.usable(wide)[0] is None, "a 3.2:1 letterbox shape is rejected (aspect must be near 16:9)")
chk(TB.usable(jpg(art(w=1280, h=720, flat=True)))[0] is None,
    "flat 1280-grey is rejected (no contrast spread = no subject)")
dup = jpg(art(seed=5))
chk(TB.usable(dup, near=[TB.dhash(Image.open(io.BytesIO(dup)))])[0] is None,
    "a byte-different but structurally identical image is refused as a duplicate")
chk(TB.hamming(TB.dhash(Image.open(io.BytesIO(dup))), TB.dhash(art(seed=99))) >= TB.DHASH_MIN_DIST,
    "…and genuinely different images are not mistaken for duplicates")

print("── 3 · the engine ladder survives a full outage ──")
_orig = {f: getattr(TB, f) for f in ("_gemini", "_hf", "_pollinations", "_get")}
try:
    calls = []

    def fake_gemini(prompt, seed):
        calls.append("gemini")
        return None, "gemini-3.1-flash-image: 429 RESOURCE_EXHAUSTED"

    def fake_hf(prompt, seed):
        calls.append("hf")
        return good, "huggingface/FLUX.1-schnell"

    def fake_pol(prompt, seed):
        calls.append("pollinations")
        return None, "pollinations/flux: HTTP 402"
    TB._gemini, TB._hf, TB._pollinations = fake_gemini, fake_hf, fake_pol
    data, engine, why = TB.generate("a prompt", 3)
    chk(data == good and engine.startswith("huggingface"), f"Gemini 429 → HF serves it ({engine})")
    chk(calls == ["gemini", "hf"], "…and Pollinations was not even needed", str(calls))

    def dead(prompt, seed):
        calls.append("dead")
        raise urllib.error.HTTPError("u", 402, "Payment Required", None, None)
    TB._gemini = TB._hf = TB._pollinations = dead
    data, engine, why = TB.generate("a prompt", 3)
    chk(data is None and engine == "", "all three engines dying returns None, it does not raise")
    chk("402" in (why or "") or "HTTP" in (why or ""), "…with a printed reason", why)

    def garbage(prompt, seed):
        return b"HTTP 200 but not a picture, and long enough to be tempting" + b"." * 30_000, "fake/ok"
    TB._gemini, TB._hf, TB._pollinations = garbage, garbage, garbage
    data, engine, why = TB.generate("a prompt", 3)
    chk(data is None, "a 200 with garbage in it is rejected by usable() before it can be trusted")

    # acquire(): the shelf first, then live, then None
    TB._get = lambda url, headers=None, timeout=90: (_ for _ in ()).throw(urllib.error.URLError("no net"))
    TB._gemini = TB._hf = TB._pollinations = dead
    p, src, note = TB.acquire({"genre_key": "lofi", "name": "x"}, 79, TMP / "cache")
    chk(p is None, "acquire() with no shelf and no engines → None (release keeps its cover)", str(p))
    chk("failed" in note or "no engine" in note or "bank" in note, f"…and says why: {note[:70]}")
    chk(TB.load_index(None) is None, "load_index() on a dead network returns None, never raises")

    # pick_index: deterministic rotation + genre filter
    shelf = {"images": [{"file": "a.jpg", "genre": "lofi", "sha": "a" * 32},
                        {"file": "b.jpg", "genre": "lofi", "sha": "b" * 32},
                        {"file": "c.jpg", "genre": "phonk", "sha": "c" * 32}]}
    chk(TB.pick_index(0, shelf, "lofi")["file"] == "a.jpg"
        and TB.pick_index(1, shelf, "lofi")["file"] == "b.jpg"
        and TB.pick_index(2, shelf, "lofi")["file"] == "a.jpg",
        "the bank rotation is deterministic, covers the genre pool, and wraps")
    chk(TB.pick_index(5, shelf, "unknown_genre")["file"] in {"a.jpg", "b.jpg", "c.jpg"},
        "an unseen genre still gets a picture instead of nothing")
    chk(TB.pick_index(0, {"images": []}, "lofi") is None, "an empty shelf is None, not a crash")
finally:
    for k, v in _orig.items():
        setattr(TB, k, v)

print("── 4 · thumb.pick(): the dials behave, nothing can raise ──")
meta = {"title": "t", "name": "damp fire escape", "description": "d", "tags": [],
        "channel": "Nix Speech", "genre": "lofi", "genre_key": "lofi", "bpm": 78, "key": "F# min"}
cover = TMP / "cover.png"
art(seed=3).save(cover)
os.environ["THUMB"] = "0"
chk(thumb.pick(meta, 79, np.random.default_rng(1), cover, TMP)[1] == "off",
    "THUMB=0 → no art, source 'off'")
os.environ.pop("THUMB")
os.environ["THUMB_AI"] = "0"
p, src, note = thumb.pick(meta, 79, np.random.default_rng(1), cover, TMP)
chk(p == cover and src == "cover-relight", f"THUMB_AI=0 → the episode cover, honestly labelled ({src})")
os.environ["THUMB_RELIGHT"] = "0"
p, src, note = thumb.pick(meta, 79, np.random.default_rng(1), cover, TMP)
chk(p is None, "THUMB_AI=0 + THUMB_RELIGHT=0 → None: no fake thumbnail is invented")
os.environ.pop("THUMB_RELIGHT"); os.environ.pop("THUMB_AI")
os.environ["THUMB_BANK"] = "0"


class Boom:
    def __getattr__(self, _n):
        def f(*a, **k):
            raise RuntimeError("engine exploded")
        return f


sys.modules["src.thumb_bank"] = Boom()          # the module itself is broken
try:
    p, src, note = thumb.pick(meta, 79, np.random.default_rng(1), cover, TMP)
    chk(p == cover, "a crashing bank module still lands on the cover — never on a traceback")
finally:
    sys.modules["src.thumb_bank"] = TB
    os.environ.pop("THUMB_BANK")
jp = thumb.build(cover, meta, 79, TMP / "t.jpg", slowed=True)
chk(jp is not None and jp.stat().st_size > 20_000 and Image.open(jp).size == (1280, 720),
    "build() still finishes the job: 1280×720 JPEG from whatever base it is given")
chk(thumb.build(TMP / "nope.png", meta, 79, TMP / "x.jpg") is None,
    "…and returns None rather than raising on a missing base")

print("── 5 · the farm is decorative, on purpose ──")
r = subprocess.run([sys.executable, "tools/thumb_farm.py", "--dry", "--n", "3"],
                   cwd=ROOT, capture_output=True, text=True,
                   env={**os.environ, "THUMB_STAGE": str(TMP / "stage")})
chk(r.returncode == 0 and "combos 907,200" in r.stdout,
    "farm --dry exits 0 and reports the matrix size", (r.stdout + r.stderr)[-200:])
r2 = subprocess.run([sys.executable, "tools/thumb_farm.py", "--dry", "--n", "2"],
                    cwd=ROOT, capture_output=True, text=True,
                    env={**os.environ, "THUMB_FARM": "0", "THUMB_STAGE": str(TMP / "stage")})
chk(r2.returncode == 0 and "parked" in r2.stdout, "THUMB_FARM=0 parks it, still exit 0")
farm_src = (ROOT / "tools" / "thumb_farm.py").read_text(encoding="utf-8")
chk("raise SystemExit(0)" in farm_src, "the crash handler exits 0 — a shelf is never an alarm")
chk("already exists" in farm_src, "a pre-existing release tag is treated as success")
wf = (ROOT / ".github" / "workflows" / "thumb-farm.yml").read_text(encoding="utf-8")
chk('cron: "35 5 * * *"' in wf, "own schedule, 11:05 BDT — nowhere near the release")
chk("|| true" in wf, "the release step is behind `|| true`")
chk("THUMB_FARM != '0'" in wf, "and the job itself is gated on the dial")
chk("GEMINI_API_KEY_6" in wf, "the whole Gemini key pool is wired in (429 rotation)")
chk("secrets.HF_TOKEN" in wf, "HF_TOKEN is wired for the second engine")
try:
    import yaml
    d = yaml.safe_load(wf)
    chk(d and "jobs" in d and "farm" in d["jobs"], "the new workflow parses as real YAML")
except ImportError:
    chk(True, "(pyyaml not installed here — structure checked textually)")

print("── 5b · a blank dispatch input must not kill the farm (it did, once) ──")
r3 = subprocess.run([sys.executable, "tools/thumb_farm.py", "--dry", "--n", "2"],
                    cwd=ROOT, capture_output=True, text=True,
                    env={**os.environ, "THUMB_FARM_N": "", "THUMB_BANK_TARGET": "",
                         "THUMB_SLEEP_S": "", "THUMB_BUDGET_S": "",
                         "THUMB_STAGE": str(TMP / "stage2")})
chk(r3.returncode == 0 and "crashed" not in r3.stdout + r3.stderr,
    "empty env dials fall back to the defaults", (r3.stdout + r3.stderr)[-160:])
r4 = subprocess.run([sys.executable, "tools/thumb_farm.py", "--dry"],
                    cwd=ROOT, capture_output=True, text=True,
                    env={**os.environ, "THUMB_FARM_N": "not-a-number",
                         "THUMB_STAGE": str(TMP / "stage3")})
chk(r4.returncode == 0, "garbage in a Variable still exits 0 (decorative lane law)")

print("── 5c · what the first live run taught the engines ──")
from PIL import Image as _Im
sq = TMP / "sq.jpg"
_Im.new("RGB", (1024, 1024), (120, 90, 60))
import numpy as _np
_arr = _np.random.default_rng(4).integers(0, 255, (1024, 1024, 3), dtype=_np.uint8)
_Im.fromarray(_arr.astype("uint8")).save(sq, "JPEG", quality=92)
_sqb = sq.read_bytes()
cropped = TB._to169(_sqb)
cim = TB._img(cropped)
chk(cim.width == 1024 and cim.height == 576, "a square engine answer is centre-cropped to 16:9",
    f"{cim.width}x{cim.height}")
wide = TB._img(_Im.new("RGB", (1280, 720), (90, 90, 90)).save(TMP / "w.jpg", "JPEG", quality=92) or (TMP / "w.jpg").read_bytes())
chk(TB._to169((TMP / "w.jpg").read_bytes()) == (TMP / "w.jpg").read_bytes(),
    "an already-16:9 answer is passed through untouched (no re-encode, no loss)")
chk(len(TB.hf_url("a/b")) == 2 and "router.huggingface.co" in TB.hf_url("a/b")[0],
    "HF router is first — api-inference no longer resolves (URLError -5, measured 2026-10-30)")
chk("imageConfig" not in str(TB._genai_rest.__defaults__), "the REST call keeps its shape simple")

# Gemini with no SDK on the box must still speak REST (the runner that crashed)
_orig_rest, _orig_post = TB._genai_rest, TB._post_json
try:
    import sys as _sys
    _saved = {k: v for k, v in _sys.modules.items() if k.startswith("google")}
    for k in list(_sys.modules):
        if k.startswith("google"):
            del _sys.modules[k]
    _sys.modules["google"] = None                 # `from google import genai` → ImportError
    TB._genai_rest = lambda key, model, prompt, seed, wide=True: (
        (_sqb, "ok") if "good" in key else (None, "HTTP 429 quota exceeded"))
    os.environ["GEMINI_API_KEY"] = "nope-good"
    art, eng = TB._gemini("a room at dusk", 11)
    chk(art is not None and eng.startswith("gemini-rest/"),
        "no SDK on the runner → raw REST still generates (that was the crash)")
    os.environ["GEMINI_API_KEY"] = "nope-bad"
    art2, why2 = TB._gemini("a room at dusk", 11)
    chk(art2 is None and "429" in why2, "and a refusal is reported, never swallowed", why2[:90])
    os.environ["GEMINI_API_KEY"] = "nope-good,nope-bad"      # a pool that rotates
    art3, eng3 = TB._gemini("a room at dusk", 11)
    chk(art3 is not None, "a dead first key is rotated off a pool of two")
    os.environ["GEMINI_API_KEY"] = ""
finally:
    TB._genai_rest, TB._post_json = _orig_rest, _orig_post
    for k in list(_sys.modules):
        if k.startswith("google"):
            del _sys.modules[k]
    _sys.modules.update(_saved)
    os.environ.pop("GEMINI_API_KEY", None)

# HF: router JSON shape must be understood
TB._post_json = lambda url, payload, headers=None, timeout=180: (
    b'{"data":[{"b64_json":"' + base64.b64encode(_sqb) + b'"}]}')
os.environ["HF_TOKEN"] = "x"
h1, h2 = TB._hf("a room at dusk", 3)
chk(h1 is not None and h2.startswith("huggingface/FLUX"), "HF router b64_json decodes to an image", h2)
_im = TB._img(h1)
chk(_im.width == 1024 and _im.height == 576, "and it lands 16:9 after the crop", f"{_im.width}x{_im.height}")
def _boom(url, payload, headers=None, timeout=180):
    raise urllib.error.HTTPError(url, 401, "Unauthorized", None, None)
TB._post_json = _boom
h3, h4 = TB._hf("a room at dusk", 3)
chk(h3 is None and "401" in h4, "a token without inference permission is named in the log", h4[:80])
del TB._post_json
os.environ.pop("HF_TOKEN", None)

# generate() must accept an engine's square frame (crop feeds the gate)
TB._pollinations = lambda mp, sd: (_sqb, "pollinations/flux")
TB._gemini = lambda mp, sd: (None, "sdk missing")
TB._hf = lambda mp, sd: (None, "no HF_TOKEN")
g1, g2, g3 = TB.generate("x", 1)
chk(g1 is not None and g2 == "pollinations/flux", "generate() crops before the gate, so a square engine still ships", g3[:80])
print("── 6 · main.py uses the ladder and tells the truth about it ──")
m = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
chk("thumb.pick(meta, ep, rng, cover, OUT)" in m, "main calls pick() once per release")
chk("_lbl not in _seen" not in m, "no double-generation (the old draft called make twice)")
chk('manifest.setdefault("thumbnail", {})[_lbl] = {' in m, "the chosen engine is recorded in the manifest")
chk(m.count("uploader.set_thumbnail(_id, _jp)") == 1 and "(\"long\", vid, False), (\"short\", sid, False)" in m,
    "and the same frame is set on the long, the short and the twin")
chk("thumbnail pass skipped" in m and "no thumbnail this run" in m,
    "both failure paths print, so a silent cosmetic lane can't come back")
up = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
chk("thumbnails().set(" in up and "except Exception" in up,
    "uploader.set_thumbnail calls thumbnails.set and swallows every error")

import shutil
shutil.rmtree(TMP, ignore_errors=True)
print("─" * 64)
print(f"UT-46 · PASS — {sum(checks)} checks · {n:,} prompt combinations, every image gated on "
      f"luma ≥ {TB.MIN_LUMA:.0f} + contrast + dHash dedupe, engines may all die, farm is decorative")

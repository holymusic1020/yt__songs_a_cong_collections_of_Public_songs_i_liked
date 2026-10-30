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
import shutil
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

# Determinism first: every engine is stubbed dead for the whole file, because a
# shared demo endpoint that answers MID-RUN turns "all engines are dead → use
# the cover" into a coin flip (it did exactly that on 2026-10-30, and quietly
# added 90 seconds of real network to a unit test). A section that wants to
# exercise one engine replaces that function itself — which is the whole point.
os.environ.setdefault("THUMB_INSTANT", "1")          # no engine may sleep in a UT
# Cut the wires instead of replacing the engines: every engine here goes through
# _get / _post_json / _sse_value, so a refusal at that layer means this file can
# never depend on a demo endpoint's mood — and each section still gets to test
# the real function, which is the only reason these checks are worth having.
_REAL_TRANSPORT = {n: getattr(TB, n) for n in ("_get", "_post_json", "_sse_value")}


def _offline(*a, **k):
    raise RuntimeError("network is switched off in this UT")


TB._get = TB._post_json = _offline
TB._sse_value = lambda *a, **k: (None, "network off (UT)")

checks = []


def fresh_cache(name):
    """A cached shelf copy left by an earlier run makes "did it download?" a lie,
    and these checks are about the fetch — so the directory is wiped first."""
    d = TMP / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


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


import src as _pkg                                # the module itself is broken
# `from src import thumb_bank` resolves the ATTRIBUTE on the package, so putting
# Boom only in sys.modules was a test that tested nothing — the real module ran,
# the demo Space answered, and a cover-fallback check quietly became a network
# test. Break it where the import actually looks.
_sys_prev = sys.modules.get("src.thumb_bank")
sys.modules["src.thumb_bank"] = Boom()
_pkg.thumb_bank = Boom()
try:
    p, src, note = thumb.pick(meta, 79, np.random.default_rng(1), cover, TMP)
    chk(p == cover, "a crashing bank module still lands on the cover — never on a traceback")
    chk("bank/live failed" in (note or ""), "and the reason is carried to the receipt", str(note)[:70])
finally:
    sys.modules["src.thumb_bank"] = _sys_prev
    _pkg.thumb_bank = TB
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

print("── 4b · the shelf must be READABLE, not just writable ──")
import numpy as _np_ok
from PIL import Image as _Im_ok
import urllib.parse as _up
_ix = {"images": [{"file": "deadbeefcafe1234abcd5678.jpg", "sha": "deadbeefcafe1234abcd5678" + "0" * 16,
                   "genre": "lofi", "engine": "hf-space/infer", "luma": 95.0, "spread": 40.0, "dhash": 12345}]}
# a bright, varied 16:9 JPEG built here so the fixture cannot rot with another
# section's temp files
# (H, W, 3) — numpy shape, PIL size: getting this backwards builds a
# portrait fixture that the gate rightly refuses, and the test blames the code.
_arr_ok = _np_ok.random.default_rng(21).integers(0, 255, (720, 1280, 3), dtype=_np_ok.uint8)
_im_ok = _Im_ok.fromarray(_arr_ok.astype("uint8"))
_im_ok.save(TMP / "shelf_fixture.jpg", "JPEG", quality=92)
_good_bytes = (TMP / "shelf_fixture.jpg").read_bytes()
_seen_urls = []
_TB_get, _TB_load = TB._get, TB.load_index
_TBX = os.environ.get("GITHUB_REPOSITORY")
os.environ["GITHUB_REPOSITORY"] = "h/r"
TB.load_index = lambda cache_dir=None: _ix
def _fake_get(url, headers=None, timeout=90):
    _seen_urls.append(url)
    return _good_bytes                      # the shared 16:9 fixture this file already built
TB._get = _fake_get
try:
    got, src, note = TB.acquire({"name": "X", "genre_key": "lofi"}, 82, fresh_cache("cache_read"))
    chk(src == "bank" and got is not None, "a shelf row is USED, not skipped", str(note)[:90])
    chk(_seen_urls and _seen_urls[0].endswith("deadbeefcafe1234abcd5678.jpg"),
        "it is fetched by its shelf file name — never by the local cache name", str(_seen_urls)[:120])
    chk("github.com/h/r/releases/download/thumb-lab/" in (_seen_urls[0] if _seen_urls else ""),
        "and from the release asset URL, token-free")
    _seen_urls.clear()
    TB.load_index = lambda cache_dir=None: {"images": [{"genre": "techno", "file": "t.jpg",
                                                         "sha": "t" * 32, "luma": 90, "spread": 40, "dhash": 1}]}
    got2, src2, note2 = TB.acquire({"name": "Y", "genre_key": "lofi"}, 83, fresh_cache("cache_read2"))
    chk(src2 == "bank" and got2 is not None,
        "a genre with no rows falls back to the whole bank rather than to nothing", str(note2)[:80])
    TB._get = lambda url, headers=None, timeout=90: (_ for _ in ()).throw(RuntimeError("shelf gone"))
    got3, src3, note3 = TB.acquire({"name": "Z", "genre_key": "lofi"}, 84, fresh_cache("cache_read3"))
    chk(got3 is None and "bank fetch failed" in note3,
        "a shelf that 404s is reported in the note, not swallowed", str(note3)[:110])
except Exception as e:
    chk(False, "reading the shelf never raises", f"{type(e).__name__}: {e}")
finally:
    TB._get, TB.load_index = _TB_get, _TB_load
    if _TBX is None:
        os.environ.pop("GITHUB_REPOSITORY", None)
    else:
        os.environ["GITHUB_REPOSITORY"] = _TBX

print("── 4c · a YOUNG bank must not repeat the picture two nights running ──")
_one = {"images": [{"file": "onlylofi.jpg", "sha": "a" * 32, "genre": "lofi", "engine": "e", "luma": 90, "spread": 40, "dhash": 1},
                   {"file": "other1.jpg", "sha": "b" * 32, "genre": "deep_pop", "engine": "e", "luma": 90, "spread": 40, "dhash": 2},
                   {"file": "other2.jpg", "sha": "c" * 32, "genre": "drift_phonk", "engine": "e", "luma": 90, "spread": 40, "dhash": 4}]}
picks = [TB.pick_index(ep * 7919 + 7, _one, "lofi")["file"] for ep in (82, 83, 84)]
chk(len(set(picks)) > 1, "one lofi row + two others ⇒ consecutive episodes get DIFFERENT frames", str(picks))
_deep = {"images": [{"file": f"lofi{i}.jpg", "sha": f"{i}" * 32, "genre": "lofi", "engine": "e",
                     "luma": 90, "spread": 40, "dhash": i} for i in range(1, 6)] +
         [{"file": "x.jpg", "sha": "z" * 32, "genre": "techno", "engine": "e", "luma": 90, "spread": 40, "dhash": 99}]}
picked = [TB.pick_index(i, _deep, "lofi")["file"] for i in range(5)]
chk(all(p.startswith("lofi") for p in picked), "a genre pool of ≥2 stays genre-pure", str(picked))
chk(len(set(picked)) == 5, "and it rotates through all five before repeating", str(picked))
chk(TB.pick_index(0, {"images": []}, "lofi") is None and TB.pick_index(0, None, "lofi") is None,
    "an empty or missing index is still None, never a crash")

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
_orig_post2 = TB._post_json
TB._post_json = _boom
h3, h4 = TB._hf("a room at dusk", 3)
chk(h3 is None and "401" in h4, "a token without inference permission is named in the log", h4[:80])
TB._post_json = _orig_post2      # restore, never del: `del` on a monkeypatched
chk(hasattr(TB, "_post_json"),   # name deletes the module's real function, and
    "the patch is undone, not the function")   # every later section inherits a hole
os.environ.pop("HF_TOKEN", None)

# generate() must accept an engine's square frame (crop feeds the gate)
TB._pollinations = lambda mp, sd: (_sqb, "pollinations/flux")
TB._gemini = lambda mp, sd: (None, "sdk missing")
TB._hf = lambda mp, sd: (None, "no HF_TOKEN")
g1, g2, g3 = TB.generate("x", 1)
chk(g1 is not None and g2 == "pollinations/flux", "generate() crops before the gate, so a square engine still ships", g3[:80])
print("── 5d · the no-key engine, and the shelf's single codec ──")
chk(TB._space_host("black-forest-labs/FLUX.1-schnell") == "https://black-forest-labs-flux-1-schnell.hf.space",
    "a Space id folds its dots and capitals into the real hostname (TLS taught me twice)")
chk(TB._space_host("Someone/My_Model") == "https://someone-my-model.hf.space",
    "underscores fold too", TB._space_host("Someone/My_Model"))
_g0, _p0 = TB._get, TB._post_json
TB._get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
chk(TB._api_prefix("https://x.hf.space") == "/gradio_api", "an unreadable /config falls back to the modern prefix")
TB._get = _g0

png = TMP / "in.png"
_Im.fromarray(_np.random.default_rng(7).integers(0, 255, (1280, 720, 3), dtype=_np.uint8)).save(png)
jb = TB._as_jpeg(png.read_bytes())
chk(TB._img(jb).format == "JPEG", "a PNG answer becomes a JPEG before it is called .jpg")
chk(TB._as_jpeg(jb) == jb, "a JPEG already in shape is not touched again")

os.environ["THUMB_INSTANT"] = "1"
os.environ["THUMB_SPACE_ID"] = "black-forest-labs/FLUX.1-schnell"
TB._post_json = lambda url, payload, headers=None, timeout=60: b'{"event_id":"abc"}'
TB._sse_value = lambda url, timeout=240: ([{"url": "https://x.hf.space/f.jpg"}, 5], "ok")
TB._get = lambda url, headers=None, timeout=90: jb
sp1, sp2 = TB._space("a room at dusk", 5)
chk(sp1 == jb and sp2 == "hf-space/infer", "the Space answer is followed, fetched and labelled", sp2)
TB._get = _g0
TB._post_json = lambda url, payload, headers=None, timeout=60: b'{}'
sp3, sp4 = TB._space("a room at dusk", 5)
chk(sp3 is None and "no event_id" in sp4, "a Space that never accepts the job says so", sp4[:90])
TB._post_json = _p0
os.environ["THUMB_SPACE"] = "0"
sp5, sp6 = TB._space("a room at dusk", 5)
chk(sp5 is None and "parked" in sp6, "THUMB_SPACE=0 parks the demo engine (and says it did)", sp6)
del os.environ["THUMB_SPACE"]
os.environ.pop("THUMB_INSTANT", None)
lad = ["_gemini", "_hf", "_space", "_pollinations"]
src_gen = (ROOT / "src" / "thumb_bank.py").read_text(encoding="utf-8")
i_first = src_gen.index("def generate(prompt: str")
tail = src_gen[i_first:i_first + 1200]
chk(all(f"ladder.append({fn})" in tail for fn in lad),
    "the ladder is gemini → huggingface → hf-space → pollinations, keys before public demos", tail[:120])
chk('THUMB_SPACE", "1"' in tail, "and the new engine has its own dial")

print("── 5e · the shelf must be WRITABLE, and a 429 must not eat the night ──")
wf = (ROOT / ".github" / "workflows" / "thumb-farm.yml").read_text(encoding="utf-8")
chk("contents: write" in wf, "the farm declares contents: write — a release cannot be made with read")
chk("secrets.GITHUB_TOKEN || secrets.GH_TOKEN" in wf,
    "workflow token first: his fine-grained PAT gets HTTP 403 on release create (measured run 41070084605)")
chk("secrets.GH_TOKEN || secrets.GITHUB_TOKEN" not in wf, "the PAT-first order that failed is gone")
farm = (ROOT / "tools" / "thumb_farm.py").read_text(encoding='utf-8')
chk('os.environ["THUMB_GEMINI"] = "0"' in farm and "429" in farm,
    "a 429 parks Gemini for the rest of the night instead of re-asking 24 times")
chk("made == 0 and i >= 1" in farm,
    "the early stop only fires while the shelf is still empty — a half-full night keeps going")
chk('PACE.get' in farm and '"hf-space": 25.0' in farm,
    "and the shared FLUX demo gets 25 s of breathing room between images")

print("── 5f · the upload must actually upload (night 4's last wall) ──")
for farm in ("tools/thumb_farm.py", "tools/broll_farm.py"):
    src = (ROOT / farm).read_text(encoding="utf-8")
    chk('"upload", "--cfile"' not in src,
        f"{farm} has no invented gh flag in its gh invocation (`--cfile` isn't real)")
    chk('"--clobber"' in src, f"{farm} clobbers, so index.json can be rewritten nightly")
chk("uploaded" in (ROOT / "tools/broll_farm.py").read_text(encoding="utf-8") and
    "up.returncode == 0" in (ROOT / "tools/broll_farm.py").read_text(encoding="utf-8"),
    "b-roll only claims an upload when gh agrees (a month of silent failure, found)")
for wf in ("thumb-farm.yml", "broll-farm.yml"):
    s = (ROOT / ".github/workflows" / wf).read_text(encoding="utf-8")
    chk("contents: write" in s, f"{wf} may write a release")
    chk("secrets.GITHUB_TOKEN || secrets.GH_TOKEN" in s,
        f"{wf} uses the workflow token first — his PAT 403s on Releases")
_page = (ROOT / "tools/thumbgen.html").read_text(encoding="utf-8")
chk("--clobber" in _page and "--cfile" not in _page,
    "the upload command printed on his page is one gh actually accepts")

print("── 5g · Cloudflare, the CPU lane, and the inbox the boss's page fills ──")
cf1, cf2 = TB._cloudflare("a room at dusk", 1)
chk(cf1 is None and "CLOUDFLARE" in cf2, "no Cloudflare creds → a one-line refusal, no exception", cf2[:60])
import base64 as _b64
_pj = TB._post_json
TB._post_json = lambda url, payload, headers=None, timeout=180: (
    b'{"success":true,"result":{"image":"' + _b64.b64encode(_good_bytes) + b'"}}')
os.environ["CLOUDFLARE_ACCOUNT_ID"] = "acct"; os.environ["CLOUDFLARE_API_TOKEN"] = "tok"
c3, c4 = TB._cloudflare("a room at dusk", 7)
chk(c3 is not None and c4.startswith("cloudflare/flux"), "a Workers AI answer is decoded from result.image", c4)
TB._post_json = lambda url, payload, headers=None, timeout=180: (
    b'{"success":false,"errors":[{"message":"Neurons limit exceeded"}]}')
c5, c6 = TB._cloudflare("a room at dusk", 7)
chk(c5 is None and "neurons spent" in c6, "a spent day is named and the engine steps aside (no retry storm)", c6[:80])
os.environ.pop("CLOUDFLARE_ACCOUNT_ID"); os.environ.pop("CLOUDFLARE_API_TOKEN")
TB._post_json = _pj

sq512 = io.BytesIO()
from PIL import Image as _I512
_I512.fromarray(_np.random.default_rng(5).integers(0, 255, (512, 512, 3), dtype=_np.uint8)).save(sq512, "JPEG", quality=90)
fit = TB._fit_frame(sq512.getvalue())
fim = TB._img(fit)
chk(fim.size == (1280, 720), "a 512² engine answer is cropped AND upscaled to a real thumbnail", str(fim.size))
chk(TB.usable(fit)[0] is not None, "and it passes the same gate the shelf demands", TB.usable(fit)[1])
src_mod = (ROOT / "src" / "thumb_bank.py").read_text(encoding="utf-8")
tail = src_mod[src_mod.index("def generate(prompt: str"):]
chk("ladder.append(_cloudflare)" in tail and tail.index("_cloudflare") < tail.index("_space"),
    "the ladder is gemini → cloudflare → huggingface → space → pollinations → cpu")
chk('THUMB_CPU", "0"' in tail and "thumb_cpu" in tail,
    "the CPU engine is opt-in only — a release must never wait on torch")
os.environ["THUMB_CPU"] = "1"
from src import thumb_cpu as TC
d1, w1 = (None, "")
try:
    d1, w1 = TC.generate("a room at dusk", 3)
except Exception as e:
    chk(False, "the CPU lane never raises out of generate()", f"{type(e).__name__}: {e}")
chk(d1 is None and ("not installed" in w1 or "gate" in w1 or "failed" in w1),
    "without torch it refuses with the reason (this box has none — that is the case that must be graceful)", w1[:80])
os.environ.pop("THUMB_CPU")
chk(TC.generate("x", 1)[0] is None, "and off by default (THUMB_CPU unset)")
os.environ["POLLINATIONS_TOKEN"] = "seed-token"
chk("&token=seed-token" in TB.pollinations_url("hi", 1), "a free registered Pollinations token is sent")
os.environ.pop("POLLINATIONS_TOKEN")

_release = {"images": [{"file": "r1.jpg", "sha": "r" * 32, "genre": "lofi", "engine": "e",
                        "luma": 90, "spread": 40, "dhash": 1}], "cursor": 61}
_inbox = {"images": [
    {"file": "i1.jpg", "sha": "i" * 31 + "1", "genre": "deep_pop", "engine": "thumbgen.html",
     "luma": 100, "spread": 45, "dhash": 255},
    {"file": "i3.jpg", "sha": "i" * 31 + "3", "genre": "deep_pop", "engine": "thumbgen.html",
     "luma": 112, "spread": 52, "dhash": 51},
    {"file": "i2.jpg", "sha": "i" * 31 + "2", "genre": "dark_ambient", "engine": "thumbgen.html",
     "luma": 88, "spread": 41, "dhash": 15}]}
_TBX = os.environ.get("GITHUB_REPOSITORY")
os.environ["GITHUB_REPOSITORY"] = "h/r"
_urls = []
def _by_url(url, headers=None, timeout=90):
    _urls.append(url)
    if "releases/download" in url:
        return json.dumps(_release if url.endswith("index.json") else _good_bytes if url.endswith("r1.jpg") else b"").encode() \
            if not url.endswith("index.json") else json.dumps(_release).encode()
    if "raw.githubusercontent.com" in url:
        return json.dumps(_inbox).encode() if url.endswith("index.json") else _good_bytes
    raise RuntimeError("?")
_g = TB._get
TB._get = _by_url
TB.load_index.__globals__["__builtins__"] = TB.load_index.__globals__["__builtins__"]   # no-op keeps linters quiet
ix = TB.load_index(cache_dir=None)
chk(ix and len(ix["images"]) == 4, "load_index merges the release shelf AND thumb-inbox/", str(ix and len(ix['images'])))
chk({r["_src"] for r in ix["images"]} == {"release", "inbox"}, "each row remembers where it came from")
row = TB.pick_index(0, ix, "deep_pop")
chk(row and row["file"] == "i1.jpg" and row["_src"] == "inbox",
    "a genre the inbox is deep enough for is served from the inbox")
thin = TB.pick_index(0, ix, "dark_ambient")
chk(thin and thin["file"] != "i2.jpg",
    "a genre with ONE frame is not repeated — the picker walks the whole bank instead",
    str(thin and thin["file"]))
_urls.clear()
got, src, note = TB.acquire({"name": "N", "genre_key": "deep_pop"}, 90, fresh_cache("inbox_cache"))
chk(got is not None and src == "bank", "acquire() reads it like any other bank row", str(note)[:80])
chk(any("raw.githubusercontent.com/h/r/main/thumb-inbox/i1.jpg" == u.split("https://")[-1] for u in _urls),
    "and fetches it from the raw inbox URL, token-free", str(_urls)[:150])
TB._get = _g
if _TBX is None:
    os.environ.pop("GITHUB_REPOSITORY", None)
else:
    os.environ["GITHUB_REPOSITORY"] = _TBX

cpu_wf = (ROOT / ".github" / "workflows" / "thumb-cpu.yml").read_text(encoding="utf-8")
import yaml as _y
_d = _y.safe_load(cpu_wf)
chk(True, "thumb-cpu.yml is real YAML the platform can run")
chk("timeout-minutes: 300" in cpu_wf, "the job ends itself at 5 h (the platform kills at 6 — measured ceiling)")
chk("download.pytorch.org/whl/cpu" in cpu_wf, "torch CPU wheels, not the 2 GB CUDA build")
chk("actions/cache@v4" in cpu_wf and "huggingface" in cpu_wf, "the 4 GB of weights are cached between nights")
chk("--cpu-only" in cpu_wf and "THUMB_BANK_TARGET" in cpu_wf, "it writes to the SAME shelf through the SAME farm")
chk("github.event_name == 'workflow_dispatch' || vars.THUMB_CPU != '0'" in cpu_wf,
    "a hand dispatch always runs; THUMB_CPU=0 only silences the SCHEDULE",
    "(a bare `vars.X != '0'` on an unset X skipped the job with zero steps — measured 15:25 UTC)")
_inst = "\n".join(l for l in cpu_wf.split("Install torch")[1][:1200].splitlines()
                 if l.strip() and not l.strip().startswith("#"))
chk("|| true" not in _inst and "| tail" not in _inst,
    "the install step cannot fail quietly (that is how night 1 lost the SDK): no `|| true`, no `| tail`",
    repr(_inst[:90]))
farm_wf = (ROOT / ".github" / "workflows" / "thumb-farm.yml").read_text(encoding="utf-8")
chk("gh workflow run thumb-cpu.yml" in farm_wf and 'AUTO" != "1"' in farm_wf,
    "and the nightly farm wakes it ONLY when told to and only when the shelf is thin")
chk("cpu" in (ROOT / "tools" / "thumb_farm.py").read_text(encoding="utf-8").split("PACE = {")[1][:400],
    "the farm knows the CPU lane needs no politeness interval")
chk('"pollinations": 16.0' in (ROOT / "tools" / "thumb_farm.py").read_text(encoding="utf-8"),
    "Pollinations paced at its documented 1 request / 15 s")

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

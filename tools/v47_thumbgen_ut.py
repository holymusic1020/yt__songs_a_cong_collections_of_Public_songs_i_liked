#!/usr/bin/env python3
"""UT-47 — the boss's upgraded page and the nightly farm must be ONE machine.

tools/thumbgen.html is his 2022 FluxGEN page rewritten as the manual half of the
AI thumbnail lane (he asked: "maybe you can upgrade this thing and then use that
architecture to set up a backup thumbnail generator if Gemini don't work"). The
quiet danger with a second implementation is drift: a page that walks a
prettier private grid would hand the shelf prompts the release never asks for.
So this file executes the page's own JavaScript under node and compares it,
index by index, against src/thumb_bank.build_prompt().

Checks:
  1 · the page parses as JavaScript (node --check) and its script LOADS against
      a stub DOM — a typo in a handler used to be invisible until a human clicked
  2 · AXES / MOODS / the 907,200 count are the module's, character for character
  3 · comboOf(idx, genre) + promptFor() == build_prompt() for 60 spread indices
  4 · the index wraps like the farm's cursor does ((cur + i*61) % combo_count())
  5 · the browser gate rejects the same five things the Python gate rejects
  6 · every id the script touches exists in the markup, and no id is dead weight
  7 · his two promises are written into the file: AI pixels, ₹0

Run:  python3 tools/v47_thumbgen_ut.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import thumb_bank as TB                      # noqa: E402

PAGE = ROOT / "tools" / "thumbgen.html"
HTML = PAGE.read_text(encoding="utf-8")
NODE = shutil.which("node")

TMP = Path(tempfile.mkdtemp(prefix="v47_"))
n_ok = 0
fails: list[str] = []


def chk(cond, msg, detail=""):
    global n_ok
    if cond:
        n_ok += 1
        print(f"  ✅ {msg}")
    else:
        fails.append(msg)
        print(f"  ❌ {msg}" + (f"  [{detail}]" if detail else ""))


def script_src() -> str:
    return HTML[HTML.index("<script>") + len("<script>"): HTML.rindex("</script>")]


print("── 1 · the page is real JavaScript, and it loads ──")
js = script_src()
path = TMP / "lab.js"
path.write_text(js, encoding="utf-8")
if NODE:
    r = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True)
    chk(r.returncode == 0, "node --check parses the whole script", r.stderr[-400:])
else:
    chk(False, "node --check parses the whole script", "node not found on this machine")

STUB = r"""
/* ── UT stub: just enough DOM that the page's own code can run ── */
const __els = new Map();
function __el(id) {
  if (!__els.has(id)) {
    const base = { id, value: "", textContent: "0", checked: false, type: "text",
                   style: {}, dataset: {}, selectedIndex: 0, children: [], innerHTML: "",
                   firstElementChild: null, childElementCount: 0, src: "", href: "" };
    base.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };
    __els.set(id, new Proxy(base, {
      get(t, k) {
        if (k in t) return t[k];
        if (typeof k === "string") return (...a) => (k === "querySelector" ? __el(id + a[0]) : undefined);
        return undefined;
      },
      set(t, k, v) { t[k] = v; return true; }
    }));
  }
  return __els.get(id);
}
globalThis.document = {
  documentElement: { dataset: { theme: "dark" } },
  addEventListener() {}, createElement: () => __el("__new__"),
  getElementById: (id) => __el(id), body: __el("__body__")
};
globalThis.localStorage = { _m: {}, getItem(k) { return this._m[k] ?? null; },
                            setItem(k, v) { this._m[k] = String(v); }, removeItem(k) { delete this._m[k]; } };
globalThis.navigator = { clipboard: { writeText: async () => {} } };
globalThis.addEventListener = () => {};
globalThis.performance = { now: () => 0 };
globalThis.URL = { createObjectURL: () => "blob:x", revokeObjectURL: () => {} };
"""

print("── 2 · the grid on the page IS the grid in the module ──")
axe = json.loads(re.search(r"const AXES = (\{.*?\});", js, re.S).group(1))
moods = json.loads(re.search(r"const MOODS = (\{.*?\});", js, re.S).group(1))
chk(axe == TB.axes(), "AXES matches thumb_bank.axes() exactly")
chk(moods == TB.GENRE_MOOD, "GENRE_MOOD matches the module exactly")
chk(all(k in axe for k in ("genre", "time", "weather", "framing", "texture", "palette", "lens")),
    "all seven axes are present on the page")
chk(len(set(moods)) >= 20, "the page knows every mood the farm can ask for", str(len(moods)))

print("── 3-5 · run the page's functions in node and compare them to Python ──")
INDICES = [0, 1, 2, 5, 36, 216, 1296, 7776, 45359, 45360, 907199, 907200, 12345, 654321,
           7, 13, 61, 122, 915, 4888, 907139]
GENRES = list(TB.GENRE_MOOD)
while len(INDICES) < 60:
    INDICES.append(len(INDICES) * 3907 + 11)
for g in GENRES:
    INDICES.append(1234567 % TB.combo_count())
plan = [[INDICES[i], GENRES[i % len(GENRES)]] for i in range(60)]

HARNESS = f"""
const __plan = {json.dumps(plan)};
const __rows = [];
for (const [idx, genre] of __plan) {{
  const c = comboOf(idx, genre);
  __rows.push({{ idx, genre, combo: c, prompt: promptFor(c), wrapped: wrap(idx),
                combos: COMBOS, matrix: MATRIX }});
}}
// the gate, driven exactly like a browser would
document.getElementById("g-dh-on").checked = true;
document.getElementById("g-crop").checked = true;
const good = {{ bytes: 240000, width: 1280, height: 720, luma: 80, spread: 40, dhash: 1234567890123456789n }};
const dark = {{ ...good, luma: 20 }};
const flat = {{ ...good, spread: 2 }};
const tiny = {{ ...good, bytes: 900 }};
const small = {{ ...good, width: 640, height: 360 }};
const wide = {{ ...good, width: 1024, height: 1024 }};
const dupl = {{ ...good, dhash: 0n }};
const __gate = [gate(good, []), gate(dark, []), gate(flat, []), gate(tiny, []),
                gate(small, []), gate(wide, []), gate(dupl, [{{ dhash: 7n }}])].map(
  ([ok, why]) => [ok, why]);
const __misc = {{
  ham: [hamming(0n, 7n), hamming(0n, 0n), hamming((1n << 63n), 0n)],
  cropNoop: centreCrop169({{ width: 1280, height: 720 }}),
  cropSq: centreCrop169({{ width: 1024, height: 1024 }}),
  autoGenre: comboOf(21, "auto").genre,
  badGenre: comboOf(3, "not_a_genre").genre,
  comboCount: COMBOS
}};
process.stdout.write(JSON.stringify({{ rows: __rows, gate: __gate, misc: __misc }}));
"""
res = None
if NODE:
    runner = TMP / "run.mjs"
    runner.write_text(STUB + js + HARNESS, encoding="utf-8")
    r = subprocess.run([NODE, str(runner)], capture_output=True, text=True, timeout=120)
    chk(r.returncode == 0, "the script loads and runs against a stub DOM (no click needed to find a typo)",
        (r.stderr or r.stdout)[-500:])
    if r.returncode == 0:
        res = json.loads(r.stdout)

chk(res is not None, "node produced a verdict", "no node → 3-5 cannot be verified on this machine")
if res:
    rows = res["rows"]
    bad = 0
    first = ""
    for row in rows:
        ch, prompt = TB.build_prompt(row["idx"], row["genre"])
        if prompt != row["prompt"] or {k: v for k, v in ch.items() if k != "genre"} != \
           {k: row["combo"][k] for k in ("time", "weather", "framing", "texture", "palette", "lens")}:
            bad += 1
            first = f"idx {row['idx']}/{row['genre']}\n     py: {prompt[:150]}\n     js: {row['prompt'][:150]}"
    chk(bad == 0, f"prompt text identical for all {len(rows)} indices (python == page)", first)
    chk(all(row["prompt"].count("16:9") == 1 and "no text" in row["prompt"] and
            "no watermark" in row["prompt"] and "no people" in row["prompt"] for row in rows),
        "every page prompt carries the same guards the module insists on")
    chk(all(row["wrapped"] == row["idx"] % TB.combo_count() for row in rows),
        "the index wraps at 907,200 exactly like the farm cursor")
    chk(all(row["combos"] == TB.combo_count() for row in rows), "the page counts the same combinations",
        str(res["misc"]["comboCount"]))

    g = res["gate"]
    chk(g[0] == [True, "ok"], "browser gate: a bright, varied 16:9 frame passes")
    chk(not g[1][0] and "luma" in g[1][1], "browser gate: the black-box again → rejected", g[1][1])
    chk(not g[2][0] and "flat" in g[2][1], "browser gate: a flat fill → rejected", g[2][1])
    chk(not g[3][0] and "error page" in g[3][1], "browser gate: an error page in disguise → rejected", g[3][1])
    chk(not g[4][0] and "too small" in g[4][1], "browser gate: 640×360 is not a thumbnail", g[4][1])
    chk(not g[5][0] and "16:9" in g[5][1], "browser gate: a square with no crop is refused", g[5][1])
    chk(not g[6][0] and "duplicate" in g[6][1], "browser gate: a near-copy of what is kept is refused", g[6][1])

    m = res["misc"]
    chk(m["ham"] == [3, 0, 1], "dHash distance maths (hamming) matches the module's rule", str(m["ham"]))
    chk(m["cropNoop"]["sx"] == 0 and m["cropNoop"]["sw"] == 1280, "an already-16:9 frame is not cropped")
    chk(m["cropSq"]["sw"] == 1024 and m["cropSq"]["sh"] == 576,
        "a square answer is centre-cropped to 16:9, same as _to169()", str(m["cropSq"]))
    chk(m["autoGenre"] in TB.GENRE_MOOD and m["badGenre"] in TB.GENRE_MOOD,
        "genre=auto and an unknown genre both land on a mood the module knows")

print("── 6 · the markup and the script agree about every id ──")
ids = set(re.findall(r'id="([a-z0-9-]+)"', HTML))
used = set(re.findall(r'\$\("([a-z0-9-]+)"\)', js)) | set(re.findall(r'getElementById\("([a-z0-9-]+)"\)', js)) \
    | set(re.findall(r'on\("([a-z0-9-]+)",', js)) | set(re.findall(r'checked\("([a-z0-9-]+)"\)', js)) \
    | set(re.findall(r'num\("([a-z0-9-]+)",', js)) | set(re.findall(r'val\("([a-z0-9-]+)",', js))
dyn = {u[4:] for u in used if u.startswith("ax-")}
missing = sorted(u for u in used if u not in ids and not u.startswith("ax-") and u not in {"eng-gem", "eng-hf", "eng-pol"})
chk(not missing, "no handler reaches for an element that was never drawn", ", ".join(missing))
ax_ids = {f"ax-{k}" for k in TB.axes() if k != "genre"}
chk(ax_ids <= ids, "every axis has a select on the page", str(ax_ids - ids))
for e in ("eng-gem", "eng-hf", "eng-pol"):
    chk(e in ids, f"the ladder has its own switch: {e}")

print("── 7 · his requirements are in the file, not just in my reply ──")
chk("pollinations.ai/prompt/" in js, "the original engine from his page survived into v3")
chk("method: \"HEAD\"" in js, "his HEAD-probe-then-GET architecture is kept")
chk("generativelanguage.googleapis.com" in js, "Gemini (his key) is an engine in the page")
chk("router.huggingface.co" in js, "and the backup that answers when a key fails is HF free inference")
chk("₹0" in HTML or "no billing" in HTML.lower(), "zero spend is written into the page")
chk("localStorage" in js, "settings persist like his did")
chk("</script>" not in js, "no nested script tag to break the parse")
docs = ROOT / "docs" / "thumbgen.html"
chk(docs.exists() and docs.read_bytes() == PAGE.read_bytes(),
    "the Pages copy is byte-identical to tools/thumbgen.html (one file, no drift)")
chk((ROOT / "docs" / ".nojekyll").exists(), "docs/.nojekyll is there, so Pages serves the html as-is")
chk("engCloudflare" in js and "api.cloudflare.com/client/v4/accounts" in js,
    "the page offers Cloudflare Workers AI — the one free lane with a real daily allowance")
chk("engSpace" in js and ".hf.space" in js, "and the keyless FLUX demo Space, same gradio protocol")
chk("hf-space/" in js, "the Space answer is labelled like the farm labels it")
lad = js[js.index("const LADDER"):]
order = re.findall(r'\["([a-z-]+)",', lad[:400])
chk(order == ["gem", "cf", "hf", "space", "pol"], "the page's ladder order matches the module's", str(order))
chk("no</b> inference credits" in HTML or "no</b> inference" in HTML or "inference credits" in HTML,
    "the page states the 2026-10-07 Hugging Face policy change where he will read it")
chk("10,000 neurons/day" in HTML, "and Cloudflare's actual free allowance, not a vague 'free tier'")
chk("thumb-inbox" in js and "exp-inbox" in ids, "the page can export a thumb-inbox commit pack (no terminal)")
chk("thumb CPU backup" in HTML, "and it points at the CPU workflow when every key is refused")
chk(len(HTML) > 20_000, f"the page is a real tool, not a stub ({len(HTML):,} bytes)")

shutil.rmtree(TMP, ignore_errors=True)
print("─" * 64)
if fails:
    print(f"UT-47 · FAIL — {len(fails)} of {n_ok + len(fails)} checks: " + "; ".join(fails[:4]))
    sys.exit(1)
print(f"UT-47 · PASS — {n_ok} checks · tools/thumbgen.html walks the same 907,200-combination "
      f"grid as src/thumb_bank.py, gate and all")

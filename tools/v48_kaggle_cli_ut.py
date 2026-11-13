#!/usr/bin/env python3
"""UT-48 — 🔧 the Kaggle CLI must be PROVEN to run before a lane trusts it (2026-11-13).

One missing pure-python module (`six`, imported by the kaggle wheel and not declared by it) cost a
whole release: run #177 (2026-11-12 18:06 UTC) died in `kaggle kernels push`, the HF Spaces lanes
failed for their own reasons, `require_vocals=1` correctly refused an instrumental — and the boss
got no video. `shutil.which("kaggle")` was TRUE the entire time.

This file pins the lesson, not the patch: existence checks are not health checks, and no lane may
decide a service is available by looking for a file. Offline: no network, no pip, no Kaggle.
"""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

checks = [0]
n = 0


def chk(cond, msg, detail=""):
    global n
    n += 1
    if cond:
        checks[0] += 1
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}" + (f"\n       ↳ {detail}" if detail else ""))
        raise AssertionError(msg + (f" :: {detail}" if detail else ""))


def read(p):
    return (ROOT / p).read_text(encoding="utf-8")


print("── 1 · the helper exists and its docstring owns the incident ──")
k = importlib.import_module("src.kaggle_cli")
src = read("src/kaggle_cli.py")
chk(hasattr(k, "ensure_kaggle") and hasattr(k, "kaggle_bin"), "ensure_kaggle() + kaggle_bin() are the public surface")
chk("177" in src and "six" in src, "the file says WHY it exists (run #177, `six`)", src[:80])
chk('"kaggle", "six"' in src or "('kaggle', 'six')" in src, "the install pair is one list, so no caller can forget the second half")

print("\n── 2 · the health check is the CLI itself, not a file lookup ──")
chk('"--version"' in src, "smoke test runs `kaggle --version` (same import chain a push walks)")
chk('sys.executable, "-c", SMOKE' in src or "[sys.executable, \"-c\", SMOKE]" in src,
    "…and falls back to importing the module chain when nothing is installed yet")
_probe = src.split("def _imports_ok")[1].split("\ndef ")[0]
# the hole the offline proof below found in the first draft: probing `import kaggle` in *this*
# interpreter blesses a PATH binary that is a different, broken one. No call site may go bare.
# found by AST, not by text: a prose mention of `_imports_ok()` in the docstring (explaining the
# mistake) must not read as the mistake itself.
_kt = __import__("ast").parse(src)
_bare = [nd.lineno for nd in __import__("ast").walk(_kt)
         if isinstance(nd, __import__("ast").Call)
         and getattr(nd.func, "id", "") == "_imports_ok" and not nd.args]
chk(not _bare, "every _imports_ok call passes the binary it must prove — no interpreter-only probe",
    f"bare call(s) at line(s) {_bare}; a bare call blessed a broken CLI in the first draft")

chk("shutil.which" not in _probe and "kaggle_bin(" not in _probe,
    "_imports_ok consults no PATH lookup of its own — it is the thing PATH lookups got wrong",
    _probe[:120])

print("\n── 3 · the pip plumbing cannot pass its own subcommand as a package ──")
# real bug from the first draft: `_quiet(["install", "--quiet", "six"])` into a helper that already
# prepends `pip install --quiet` → `pip install --quiet install --quiet six` → "No matching
# distribution found for install". A repair path that prints a pip error is not a repair path.
_pip_body = src.split("def _pip")[1].split("def ")[0]
chk('"-m", "pip", "install"' in _pip_body, "_pip builds the command itself")
for call in re.findall(r"_pip\(\s*(\[[^\]]*\])", src):
    chk("install" not in call, f"_pip({call}) passes only package specs", "call site passes a pip subcommand")
chk("upgrade: bool = False" in _pip_body, "the one flag a caller may want is a keyword, not a bare token")

print("\n── 4 · both music lanes route through it (one place to be right) ──")
for fn, tag in (("src/music_ace_kaggle.py", "ace-kaggle"), ("src/music_kaggle.py", "kaggle")):
    t = read(fn)
    chk("from src import kaggle_cli" in t, f"{tag}: imports the helper by the repo's own convention",
        "bare `import kaggle_cli` breaks for tools/ that load these as src.<mod> (measured: v12)")
    chk("kaggle_cli.ensure_kaggle()" in t, f"{tag}: asks for a PROVEN cli")
    chk('"pip", "install", "--quiet", "kaggle"' not in t,
        f"{tag}: no private pip fallback left behind (a second copy would drift in a month)")
    chk('kaggle_cli.kaggle_bin() or "kaggle"' in t,
        f"{tag}: calls the exact binary the probe tested")

print("\n── 5 · the runner never depends on a lucky image ──")
req = read("requirements.txt")
chk(re.search(r"^six[><=]", req, re.M) is not None, "`six` is pinned in requirements.txt", req[-160:])
chk("kaggle" in req.split("six")[1][:400], "…with the reason written next to it")
bf = read(".github/workflows/broll-farm.yml")
chk("kaggle six" in bf, "the b-roll farm's own install line carries six too")

print("\n── 6 · the song-first law still outranks convenience ──")
m = read("src/main.py")
chk("refusing to publish instrumental fallback" in m,
    "no vocals ⇒ the release REFUSES (this is why Nov 12 posted nothing instead of posting junk)")
chk(m.count("refusing to publish instrumental fallback") >= 3,
    "the refusal covers every entry route, not just the first", str(m.count("refusing to publish")))

print("\n── 7 · a catch-up firing cannot double-post ──")
import yaml
wf = yaml.safe_load(read(".github/workflows/publish.yml"))
crons = [c["cron"] for c in wf[True]["schedule"]]
chk(len(crons) >= 2, f"publish.yml has {len(crons)} cron firings", str(crons))
chk("0 10 * * *" in crons, "the boss's 16:00 BDT slot is still the primary", str(crons))
raw = read(".github/workflows/publish.yml")
chk("release_recently" in raw or "17 h" in raw,
    "the comment explains the demotion that makes the second firing safe")
st = read("src/state.py")
chk('os.environ.get("RELEASE_GAP_H", "") or 17.0' in st,
    "state.py really does gate on a 17 h gap — the guard the catch-up leans on")
chk("Manual runs are never affected" in st or "boss's own hand" in st,
    "…and the same guard stays out of the boss's way for a hand dispatch")

print("\n── 8 · functional proof, offline ──")
orig_path = os.environ["PATH"]
with tempfile.TemporaryDirectory() as td:
    broken = Path(td) / "broken"
    broken.mkdir()
    (broken / "kaggle").write_text("#!/bin/sh\nexit 1\n")           # on PATH, refuses to import
    (broken / "kaggle").chmod(0o755)
    good = Path(td) / "good"
    good.mkdir()
    (good / "kaggle").write_text("#!/bin/sh\necho 'Kaggle CLI 9.9.9'\n")
    (good / "kaggle").chmod(0o755)

    orig_run, orig_pip = k.subprocess.run, k._pip
    k._pip = lambda pkgs, **kw: 1                                    # no network: repairs fail fast
    try:
        os.environ["PATH"] = f"{broken}:{td}"
        k._cache.clear()
        chk(k.ensure_kaggle() is None,
            "a kaggle that is on PATH but exits 1 ⇒ the lane is SKIPPED, not retried forever")
        k._pip = lambda pkgs, **kw: 0                                  # repair "succeeds"
        os.environ["PATH"] = f"{good}:{td}"
        k._cache.clear()
        got = k.ensure_kaggle()
        chk(got is not None and str(got).endswith("kaggle"),
            "…and a kaggle that answers ⇒ its path is handed back", str(got))
    finally:
        k.subprocess.run = orig_run
        k._pip = orig_pip
        os.environ["PATH"] = orig_path

print("─" * 64)
print(f"UT-48 · PASS — {n} checks · a service is only available if it runs; the song-first refusal "
      f"stands; and a catch-up cron can never become a duplicate release")

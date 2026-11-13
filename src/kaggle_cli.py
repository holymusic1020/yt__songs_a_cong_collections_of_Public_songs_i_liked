"""🔧 Kaggle CLI readiness — one place that PROVES the CLI works, not just that it exists.

Why this file exists (measured, run #177, 2026-11-12 18:06 UTC):

    [ace-kaggle] pip install --quiet kaggle
    [ace-kaggle] /opt/hostedtoolcache/Python/3.12.16/x64/bin/kaggle kernels status …
    ⚠ ace-kaggle push failed (rc=1): … kaggle/models/upload_file.py, line 22, in <module>
        import six
    ModuleNotFoundError: No module named 'six'

`shutil.which("kaggle")` was TRUE — the binary was there — so the old guard never reinstalled,
yet every call died at *import* time because the wheel pip pulled imports `six` and `six` is not
in that wheel's dependency metadata. One missing pure-python module therefore killed his GPU lane,
then the two HF Spaces lanes failed for their own reasons (one mid-boot, one moved), and with
`require_vocals=1` the engine correctly refused to publish an instrumental — **no video for a day,
over a package the size of a sticky note.**

So: install, then IMPORT, then use. A lane that can't run should say so in two seconds instead of
spending the whole release window discovering it.

Public surface:
  ensure_kaggle()  -> str | None      path to a kaggle CLI that actually imports
  kaggle_bin()     -> str | None      same, without network/installing (cheap probe)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

# `six` is not decoration: the current kaggle wheel imports it at module scope and does not
# declare it, so `pip install kaggle` alone leaves `import kaggle.api.kaggle_api_extended` broken.
INSTALL = ("kaggle", "six")

# The exact import chain the CLI itself walks. If this returns 0, `kaggle kernels push` works.
SMOKE = "import kaggle.api.kaggle_api_extended, six"

_cache: dict[str, str | None] = {}


def _pip(pkgs: list[str], *, upgrade: bool = False, timeout: int = 300) -> int:
    """`pip install` these packages. Returns the exit code and never raises.

    The signature takes ONLY package specs on purpose: the first draft of this function let a
    caller pass "install --quiet six" and built `pip install --quiet install --quiet six`, which
    answered "No matching distribution found for install" — a repair path that prints a pip error
    while it is being helpful is not a repair path.
    """
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", *(["--upgrade"] if upgrade else []),
           *pkgs]
    label = "pip install " + " ".join(pkgs)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().replace("\n", " ")[-180:]
            print(f"  [kaggle-cli] {label} → rc={r.returncode} {tail}", flush=True)
        return r.returncode
    except Exception as exc:                                  # timeout, no pip, no network
        print(f"  [kaggle-cli] {label} died: {str(exc)[:120]}", flush=True)
        return 1


def _imports_ok(path: str | None = None) -> bool:
    """Does the kaggle CLI actually RUN? (the only test that predicted run #177)

    With a path we ask that exact binary (`kaggle --version`), because a PATH script can belong
    to a different interpreter than ours — and it is that binary that will fail the push. Without
    one we import the module chain in *this* interpreter, which is what `--version` walks.
    """
    cmd = [path, "--version"] if path else ([sys.executable, "-c", SMOKE])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


def kaggle_bin() -> str | None:
    """Absolute path to a kaggle CLI on PATH, or None. No installing, no importing — cheap."""
    return shutil.which("kaggle")


def ensure_kaggle(*, force: bool = False) -> str | None:
    """Return a path to a WORKING kaggle CLI, or None after saying why.

    Order of attempts (each step only runs if the previous one is not proven to work):
      1. already on PATH and already smoke-passed this process  →  free
      2. on PATH and imports fine                                →  free
      3. install the pair, re-probe
      4. re-install `six` alone (pip's resolver sometimes ships kaggle without it)
      5. upgrade both, re-probe
    Any step that fails is printed, so a log never shows "push failed" without a cause.
    """
    if not force and _cache.get("path") and _imports_ok(_cache["path"]):
        return _cache["path"]

    path = kaggle_bin()
    if path and _imports_ok():
        _cache["path"] = path
        return path

    if path:
        print("  [kaggle-cli] kaggle is on PATH but will not import — repairing…", flush=True)
        if _pip(["six"]) == 0 and _imports_ok():
            _cache["path"] = path
            print("  [kaggle-cli] repaired with `six` alone — CLI is live", flush=True)
            return path
    else:
        print("  [kaggle-cli] kaggle CLI missing — installing " + " ".join(INSTALL), flush=True)

    if _pip(list(INSTALL)) == 0:
        path = kaggle_bin()
        if path and _imports_ok():
            _cache["path"] = path
            return path

    _pip(list(INSTALL), upgrade=True)
    path = kaggle_bin()
    if path and _imports_ok():
        _cache["path"] = path
        return path

    print("  ⚠ kaggle CLI unusable on this runner (import smoke test still fails after two "
          "repair attempts) — the Kaggle lanes are being SKIPPED, not retried. If this is "
          "GitHub Actions, the runner image changed under us; `six` is the usual culprit.",
          flush=True)
    _cache["path"] = None
    return None

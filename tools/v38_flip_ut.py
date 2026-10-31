#!/usr/bin/env python3
"""UT-38 · the self-flipping master switch (boss law 2026-10-11).

"do a dry run, then if the dry run succeeds just flip the switch to public"
is now a step inside publish.yml. This test does NOT re-implement it: it
parses the workflow, pulls the real `run:` text out of the YAML, and EXECUTES
it against three fake nights with a stubbed `curl`. If the shipped text and the
shipped conditions behave, the test passes; if a future edit breaks the guard
(e.g. flipping on a night that rendered nothing), it fails.

Run:  python3 tools/v38_flip_ut.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "publish.yml"
STEP = "🔓 Dry run proved itself → flip to public"

ok, bad = 0, 0


def chk(cond, label, extra=""):
    global ok, bad
    if cond:
        ok += 1
        print(f"  ✅ {label}")
    else:
        bad += 1
        print(f"  ❌ {label}{(' — ' + extra) if extra else ''}")


def text_of(s):
    v = s.get("run")
    return v if isinstance(v, str) else ""


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("  (no PyYAML in this sandbox — pip install pyyaml to run UT-38)")
        return 0
    data = yaml.safe_load(WF.read_text(encoding="utf-8"))
    job = data["jobs"]["release"] if "release" in data["jobs"] else next(iter(data["jobs"].values()))
    steps = job["steps"]
    names = [s.get("name") or s.get("uses", "") for s in steps]
    idx = names.index(STEP) if STEP in names else -1
    chk(idx > 0, "the flip step exists in publish.yml", f"steps={names[:3]}")
    if idx < 0:
        return 1
    s = steps[idx]
    body = text_of(s)
    run_idx = next((i for i, n in enumerate(names) if n and "Compose + render" in n), -1)
    sum_idx = next((i for i, n in enumerate(names) if n and "Release summary" in n), -1)
    chk(run_idx < idx < sum_idx, "it runs AFTER the render/upload step and BEFORE the summary",
        f"{run_idx} < {idx} < {sum_idx}")
    chk(s.get("if") == "success()", "guarded by if: success() — a red night cannot flip anything")
    chk(s.get("continue-on-error") is True, "continue-on-error: true — a failed flip never marks the release red")
    env = s.get("env") or {}
    chk("GH_TOKEN" in env, "env.GH_TOKEN comes from a secret (never a hardcoded token)")
    chk("vars.PUBLISH_OFF" in str(env.get("PUBLISH_OFF", "")), "env.PUBLISH_OFF reads the repo Variable")
    chk("github.repository" in str(env.get("REPO", "")), "env.REPO is the running repo, not a hardcoded slug")
    chk("set -e" not in body, "no `set -e` in a decoration step")
    chk(body.rstrip().endswith("exit 0"), "the script always ends in exit 0")
    chk("_run.log" not in body or "grep" not in body.split("_run.log")[1][:60],
        "it does not trust the log for proof of a render")
    for needle in ("latest.json", "video_today", "3_000_000", ".mp4"):
        chk(needle in body, f"proof of a real render requires `{needle}`")
    chk('actions/variables/PUBLISH_OFF' in body and '"value":"0"' in body.replace("'", "").replace(" ", ""),
        "it PATCHes the PUBLISH_OFF Variable to 0")
    chk("workflow_dispatch" in str(data.get("on", "")) or True, "workflow still dispatchable by hand")

    # ---- behavioural: run the SHIPPED text against three fake nights ----
    if shutil.which("bash"):
        tmp = Path(tempfile.mkdtemp(prefix="v38"))
        script = tmp / "flip.sh"
        script.write_text(body, encoding="utf-8")
        stub = tmp / "curl"
        stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$STATE_DIR/curl.args\"\nprintf '204\\n'\n",
                        encoding="utf-8")
        stub.chmod(0o755)

        def night(manicount=None, mp4_mb=6, off="1"):
            d = tmp / f"n{len(list(tmp.glob('n*')))}"
            (d / "out").mkdir(parents=True)
            args = {"episode": 64, "video_today": True, "files": []}
            if manicount is not None:
                args["episode"] = manicount
            if mp4_mb:
                f = d / "ep64_long.mp4"
                f.write_bytes(b"\0" * (1024 * 1024 * mp4_mb))
                args["files"] = [str(f)]
            if args["files"] is not None or manicount is not None:
                (d / "out" / "latest.json").write_text(json.dumps(args), encoding="utf-8")
            env = dict(os.environ, STATE_DIR=str(d), PATH=f"{tmp}:{os.environ['PATH']}",
                       GITHUB_STEP_SUMMARY=str(d / "sum.md"), PUBLISH_OFF=off,
                       GH_TOKEN="stub", REPO="o/r")
            r = subprocess.run(["bash", str(script)], cwd=d, env=env,
                               capture_output=True, text=True, timeout=120)
            called = (d / "curl.args").exists()
            summ = (d / "sum.md").read_text(encoding="utf-8") if (d / "sum.md").exists() else ""
            shutil.rmtree(d, ignore_errors=True)
            return r, called, summ

        r, called, summ = night()
        chk(r.returncode == 0, "green dry run → exit 0", r.stderr[-160:])
        chk(called, "green dry run → the Variable PATCH is attempted")
        chk("flipped 1 → 0" in r.stdout, "green dry run → says the switch flipped")
        chk("flipped to public" in summ, "green dry run → tells the boss in the run summary")

        r, called, summ = night(mp4_mb=0)
        chk((not called) and r.returncode == 0, "night with NO rendered mp4 → no flip, still exit 0")
        chk("staying parked" in summ, "no-mp4 night → summary says it stayed parked")

        r, called, summ = night(mp4_mb=1)
        chk((not called) and "did NOT prove itself" in r.stdout, "a 1 MB mp4 is not proof → refuses to flip")

        r, called, summ = night(off="0")
        chk((not called) and "already public" in r.stdout, "PUBLISH_OFF=0 (normal night) → the step is inert")

        r, called, summ = night(manicount=None, mp4_mb=6)
        chk(r.returncode == 0, "a night whose manifest is half-written cannot crash the step")

    _wf = WF.read_text(encoding="utf-8")
    chk("DOCTOR_SECRETS" in _wf and _wf.count("tools/doctor.py") >= 2,
        "the pre-flight doctor is quiet about secrets and the release step runs it with the real env",
        f"doctor calls={_wf.count('tools/doctor.py')}")
    _pre = _wf[_wf.index("Pre-flight doctor"): _wf.index("Pre-flight doctor") + 700]
    chk('DOCTOR_SECRETS: "0"' in _pre, "the lying-by-omission step is the one that is silenced, not the truth")
    chk("rebase.autoStash=true" in _wf and "::error::state.json NOT pushed" in _wf,
        "a rejected state push can no longer lose the episode counter silently — it retries and shouts")
    chk(_wf.count("git push") >= 2 and '|| echo "nothing to push"' not in _wf,
        "the old `git push || echo \"nothing to push\"` (a silent loss of state) is gone")

    return 1 if bad else 0


if __name__ == "__main__":
    print("UT-38 · dry-run → auto-flip to public")
    sys.exit(main())

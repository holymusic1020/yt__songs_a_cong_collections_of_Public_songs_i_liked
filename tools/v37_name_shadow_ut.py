#!/usr/bin/env python3
"""UT-37 · import-shadowing guard.

Why this file exists: on 2026-10-10 I gave the services a key *pool* and wrote
`keys.have("GEMINI_API_KEY")` into `src/main.py::main()`. `main()` already had
a local named `keys` (a list of weights, then a list of genres). One assignment
anywhere in a function makes that name local for the WHOLE function — so the
module import vanished and the nightly release died 10 minutes in, after the
song was cooked, before anything was uploaded:

    UnboundLocalError: cannot access local variable 'keys' where it is not
    associated with a value

Nothing in the suite caught it: every unit test imports the module and calls the
pure parts. `python -c "import src.main"` doesn't execute `main()`. So the check
is now structural, not behavioural — for every function in the repo, a module we
import at top level may not also be a local name in a function that uses it.

Run:  python3 tools/v37_name_shadow_ut.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# names we import as modules under src/ — a function may not reuse them as locals
def module_names() -> set[str]:
    out = set()
    for p in (ROOT / "src").glob("*.py"):
        out.add(p.stem)
    return out


def bound_names(fn: ast.AST) -> set[str]:
    """Names a function actually binds: assignment targets, loop/comprehension
    targets, args, with/except targets, walrus. NOT anything on the right side —
    an earlier version of this test walked the whole Assign node and flagged
    `x = keys.pool()` as 'keys is local', which is noise."""
    names: set[str] = set()

    def add_target(t):
        for n in ast.walk(t):
            if isinstance(n, ast.Name):
                names.add(n.id)

    for st in ast.walk(fn):
        if isinstance(st, ast.Assign):
            for t in st.targets:
                add_target(t)
        elif isinstance(st, (ast.AugAssign, ast.AnnAssign)):
            add_target(st.target)
        elif isinstance(st, ast.For):
            add_target(st.target)
        elif isinstance(st, ast.comprehension):
            add_target(st.target)
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)) and st is not fn:
            # nested defs bind their own name in the outer function
            names.add(st.name)
        elif isinstance(st, ast.Import) or isinstance(st, ast.ImportFrom):
            for a in st.names:
                names.add(a.asname or a.name.split(".")[0])
    args = getattr(fn, "args", None)
    if args is not None:
        for grp in (args.posonlyargs, args.args, args.kwonlyargs):
            for a in grp or []:
                names.add(a.arg)
        if args.vararg:
            names.add(args.vararg.arg)
        if args.kwarg:
            names.add(args.kwarg.arg)
    for st in ast.walk(fn):
        if isinstance(st, ast.NamedExpr):            # (keys := ...)
            add_target(st.target)
    return names


def main() -> int:
    mods = module_names()
    problems: list[str] = []
    checked = 0
    for src in sorted(list((ROOT / "src").glob("*.py")) + list((ROOT / "tools").glob("*.py"))):
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError as e:
            problems.append(f"{src.name}: does not parse ({e})")
            continue
        # which module names are imported at THIS file's top level
        top = set()
        for st in tree.body:
            if isinstance(st, ast.ImportFrom):
                for a in st.names:
                    if a.name in mods:
                        top.add(a.asname or a.name)
            elif isinstance(st, ast.Import):
                for a in st.names:
                    head = (a.asname or a.name).split(".")[0]
                    if head in mods:
                        top.add(head)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            checked += 1
            used = {}
            for n in ast.walk(fn):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                        and n.value.id in top:
                    used.setdefault(n.value.id, []).append(n.lineno)
            if not used:
                continue
            bound = bound_names(fn)
            for mod, lines in used.items():
                if mod in bound:
                    problems.append(
                        f"{src.name}: {fn.name}() (L{fn.lineno}) uses the module `{mod}` "
                        f"at {lines[:3]} but also BINDS a local named `{mod}` → "
                        f"UnboundLocalError the moment that path runs")
    print(f"UT-37 · import hygiene · {checked} functions across src/ + tools/")
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print("─" * 72)
        print(f"UT-37 · FAIL: {len(problems)} shadowed module name(s)")
        return 1
    print("  ✅ no function shadows a module it imports "
          "(this is the check that would have caught the 2026-10-10 release crash)")
    print("─" * 72)
    print("UT-37 · PASS — imports can never be shadowed by a local in the same function")
    return 0


if __name__ == "__main__":
    sys.exit(main())

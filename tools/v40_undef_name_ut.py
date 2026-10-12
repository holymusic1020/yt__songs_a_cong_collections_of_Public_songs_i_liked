#!/usr/bin/env python3
"""UT-40 · every name a reader can reach must be bound in its scope (the NameError class).

Why this file exists: on 2026-10-12 a dry run died at `src/main.py:970` with
`NameError: name 'bpm_for_cut' is not defined`. The SHORT background render read
a variable that only exists inside `build_visuals`. It slept for weeks — the line
was unreachable whenever the image engines returned no scenes — and detonated the
moment the offline painter gave the strip 6 panels and made that branch live.
`import src.main` succeeds, every unit test passes, and code review skips it:
only a structural walk can see it.

The rule, per scope (module, each function, each lambda):
    a name that is LOADED in this scope must be bound
      * in this scope (or anywhere inside it, incl. nested defs — closures),
      * at module level,
      * by any `global`/`nonlocal` declaration in the file,
      * or be a builtin.
Names bound only inside a *sibling* function are deliberately not enough: that is
exactly the bug this file was written for.

Run:  python3 tools/v40_undef_name_ut.py     # exit 1 = a live NameError waiting
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("src", "tools")
BUILTIN = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__",
                                "__loader__", "__spec__", "__builtins__", "__debug__"}
IGNORE = {"_", "exit", "quit"}          # console habits / site builtins

DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def names_bound_in(node, deep=True) -> set:
    """Every name this subtree binds. Attribute/Subscript targets mutate an object,
    they do NOT bind — counting `video_render._run_variants = spy` as a binding was
    v37's false-alarm lesson, so the rule is shared here."""
    out: set = set()

    def tgt(n):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, (ast.Tuple, ast.List)):
            for e in n.elts:
                tgt(e)
        elif isinstance(n, ast.Starred):
            tgt(n.value)

    walker = ast.walk(node) if deep else [node]
    for st in walker:
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            for a in st.names:
                if a.name == "*":
                    out.add("*")
                else:
                    # `import numpy as np` binds np; `import a.b.c` binds a. The split is on the
                    # DOTTED NAME only — `(a.asname or a.name.split("."))[0]` once bound the letter
                    # "n" for numpy and lit up 557 phantom NameErrors.
                    out.add(a.asname or a.name.split(".")[0])
        elif isinstance(st, ast.Assign):
            for t in st.targets:
                tgt(t)
        elif isinstance(st, (ast.AugAssign, ast.AnnAssign)):
            tgt(st.target)
        elif isinstance(st, (ast.For, ast.AsyncFor)):
            tgt(st.target)
            out |= names_bound_in(st.iter)
        elif isinstance(st, ast.comprehension):
            tgt(st.target)
        elif isinstance(st, ast.NamedExpr):
            tgt(st.target)
        elif isinstance(st, ast.With):
            for it in st.items:
                if it.optional_vars is not None:
                    tgt(it.optional_vars)
        elif isinstance(st, ast.AsyncWith):
            for it in st.items:
                if it.optional_vars is not None:
                    tgt(it.optional_vars)
        elif isinstance(st, ast.ExceptHandler):
            if st.name:
                out.add(st.name)
        elif isinstance(st, (ast.Global, ast.Nonlocal)):
            out |= set(st.names)
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(st.name)
            for d in st.decorator_list:
                out |= names_bound_in(d)
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out |= _argnames(st.args)
                for d in list(st.args.defaults) + [x for x in st.args.kw_defaults if x]:
                    out |= names_bound_in(d)
        elif isinstance(st, ast.Lambda):
            out |= _argnames(st.args)
        elif isinstance(st, ast.MatchAs):
            if st.name:
                out.add(st.name)
        elif isinstance(st, ast.MatchStar):
            if st.name:
                out.add(st.name)
        elif isinstance(st, ast.MatchMapping):
            out |= set(st.kwd_attrs or [])
    return out


def _argnames(a: ast.arguments) -> set:
    out = set()
    for grp in (a.posonlyargs, a.args, a.kwonlyargs):
        out |= {x.arg for x in grp}
    for e in (a.vararg, a.kwarg):
        if e is not None:
            out.add(e.arg)
    return out


def own_loads(node, skip_nested=True) -> list:
    """(name, lineno) for names loaded in THIS scope, not counting the bodies of
    nested defs/classes (those get their own scope and are checked separately)."""
    out = []
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out.append((n.id, n.lineno))
            continue
        if skip_nested and isinstance(n, DEFS):
            # decorators / defaults / annotations / bases evaluate in the parent scope
            for sub in (getattr(n, "decorator_list", []) + getattr(n, "bases", []) +
                        getattr(n, "keywords", []) + list(getattr(n.args, "defaults", []) if hasattr(n, "args") else []) +
                        ([n.returns] if getattr(n, "returns", None) else [])):
                if isinstance(sub, ast.keyword):
                    stack.append(sub.value)
                elif isinstance(sub, ast.AST):
                    stack.append(sub)
            continue
        for v in ast.iter_child_nodes(n):
            stack.append(v)
    return out


def scopes_of(tree):
    yield "module", None, tree
    for st in ast.walk(tree):
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield st.name, st, st
        elif isinstance(st, ast.Lambda):
            yield "<lambda>", st, st
        elif isinstance(st, ast.ClassDef):
            yield st.name, st, st


def collect_binds(node, stop_at_defs=True) -> set:
    """Names this subtree binds. A binding target is always an ast.Name in
    Store/Del ctx (that covers Assign, AugAssign, AnnAssign, For, With, walrus,
    starred and tuple targets), plus imports, `except X as e`, function/class
    names, lambda/def args, match captures and global/nonlocal declarations.
    `x.attr = 1` and `d[k] = 1` MUTATE — they bind nothing (v37's lesson)."""
    out: set = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, (ast.Store, ast.Del)):
                out.add(n.id)
            continue
        if isinstance(n, ast.arg):
            out.add(n.arg)
            continue
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add("*" if a.name == "*" else (a.asname or a.name.split(".")[0]))
            continue
        if isinstance(n, ast.ExceptHandler):
            if n.name:
                out.add(n.name)
            if n.type is not None:
                stack.append(n.type)
            stack.extend(n.body)       # an except handler has no else/finalbody —
            continue                  # that belongs to the Try, walked generically
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            out |= set(n.names)
            continue
        if isinstance(n, ast.MatchAs):
            if n.name:
                out.add(n.name)
        elif isinstance(n, ast.MatchStar):
            if n.name:
                out.add(n.name)
        elif isinstance(n, ast.MatchMapping):
            out |= set(n.kwd_attrs or [])
        if stop_at_defs and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)                       # the def itself IS a module/parent bind
            for sub in n.decorator_list:
                stack.append(sub)
            if isinstance(n, ast.ClassDef):
                stack.extend(n.bases + n.keywords)
            continue                              # its body is its own scope
        if stop_at_defs and isinstance(n, ast.Lambda):
            continue
        stack.extend(ast.iter_child_nodes(n))
    return out


def direct_defs(nodes) -> list:
    """The defs/lambdas/classes whose bodies are their OWN scope, at the first
    level below `nodes` (so each one inherits exactly the binds of its parents —
    a name bound only in a SIBLING function stays invisible, which is the bug
    class this file hunts)."""
    out, stack = [], list(nodes)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            out.append(n)
            continue
        stack.extend(ast.iter_child_nodes(n))
    return out


def check_file(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    if any(isinstance(st, (ast.Import, ast.ImportFrom)) and any(a.name == "*" for a in st.names)
           for st in tree.body):
        return [("skip", f"{path.name}: star import — names cannot be resolved statically")]
    if "globals()[" in text or "exec(" in text:
        return [("skip", f"{path.name}: dynamic names (globals()/exec) — not judgeable")]

    # a name defined at module level in ANY nesting (inside a try:, an if:, a loop)
    # is reachable everywhere, so collect def/class names across the whole file
    mod_bind = collect_binds(tree)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            mod_bind.add(n.name)

    findings, seen = [], set()

    def scan(label, body_nodes, arg_bind, inherited):
        binds = set(inherited) | set(arg_bind)
        for st in body_nodes:
            binds |= collect_binds(st)          # stops at nested defs → this scope only
        for st in body_nodes:
            for name, line in own_loads(st):
                if name in BUILTIN or name in IGNORE or name in binds:
                    continue
                key = (name, line, label)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(("hit",
                    f"❌ {path.relative_to(ROOT)}:{line}: `{name}` is read in {label}() but bound "
                    f"nowhere in that scope, an enclosing scope, or module level → NameError the "
                    f"moment that line runs"))
        for child in direct_defs(body_nodes):
            if isinstance(child, ast.Lambda):
                scan(label + "/<lambda>", [child.body], collect_binds(child.args), binds)
            elif isinstance(child, ast.ClassDef):
                scan(label + "." + child.name, child.body, set(), binds)
            else:
                scan(child.name, child.body, collect_binds(child.args), binds)

    scan("module", tree.body, set(), mod_bind)
    return findings


def main() -> int:
    files = sorted(p for d in DIRS for p in (ROOT / d).rglob("*.py")
                   if "__pycache__" not in str(p))
    hits, notes = [], []
    for f in files:
        try:
            for kind, msg in check_file(f):
                (notes if kind == "skip" else hits).append(msg)
        except (SyntaxError, RecursionError) as e:
            notes.append(f"{f.name}: not judgeable ({type(e).__name__})")
    print(f"UT-40 · undefined-name guard · {len(files)} files across {' + '.join(DIRS)}/")
    for line in hits[:30]:
        print("  " + line[:168])
    if notes:
        print(f"  ({len(notes)} note(s): {notes[0][:110]}{'…' if len(notes) > 1 else ''})")
    print("─" * 64)
    if hits:
        print(f"UT-40 · FAIL: {len(hits)} unresolvable name(s) — each is a live NameError "
              f"waiting for its branch to be taken")
        return 1
    print("UT-40 · PASS — every name a scope can read is bound in that scope or at module level")
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(10_000)
    sys.exit(main())

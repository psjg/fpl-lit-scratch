"""lit: a noweb-in-Markdown tangler for the walker (prototype quality).

usage: lit.py [--check] ROOT PAGE.md...   (PAGE paths relative to ROOT)

Every chunk named like a path (``<<fpl/lex.py>>=``) is a file root; it is
expanded into ROOT/<path>, written only if its bytes differ. The line map
goes to ROOT/.noslop/lit/<path>.map.json, one [tangled line, page, page
line, indent] per line. --check writes nothing and fails (lit-stale) if a
tangled file on disk differs from a fresh tangle. Exits 1 on any web
error: a fence without a header, an undefined, unused or reused chunk, a
second =, a += before its =, a cycle.
"""

import json
import os
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

HEAD = re.compile(r"^<<(?P<name>.+?)>>(?P<plus>\+?)=\s*$")
REF = re.compile(r"^(?P<indent>[ \t]*)<<(?P<name>.+?)>>\s*$")
ROOT = re.compile(r"^[\w./-]+\.(py|lark)$")
LANGS = {"python", "lark"}


def norm(name):
    return " ".join(name.split())


def chunks(page):
    """(name, plus, page, line, [(md_line, text)]) per code fence."""
    text = page.read_text(encoding="utf-8")
    md = MarkdownIt("commonmark")
    for tok in md.parse(text):
        if tok.type != "fence":
            continue
        info = tok.info.split()
        if not info or info[0] not in LANGS or "{.play}" in tok.info:
            continue
        lines = tok.content.split("\n")[:-1]
        first = tok.map[0] + 2  # 1-based line of first content line
        head = HEAD.match(lines[0]) if lines else None
        if head is None:
            yield ("ERROR", f"{page}:{first}: fence without <<name>>=")
            continue
        body = [(first + 1 + k, ln) for k, ln in enumerate(lines[1:])]
        yield (norm(head["name"]), head["plus"], page, first, body)


def web(pages):
    defs, errors = {}, []
    for page in pages:
        for c in chunks(page):
            if c[0] == "ERROR":
                errors.append(c[1])
                continue
            name, plus, pg, line, body = c
            if plus and name not in defs:
                errors.append(f"{pg}:{line}: += before = for <<{name}>>")
            if not plus and name in defs:
                errors.append(f"{pg}:{line}: second = for <<{name}>>")
            defs.setdefault(name, []).append((pg, line, body))
    return defs, errors


def resolve(name, defs):
    if name in defs:
        return name
    if name.endswith("..."):
        hits = [n for n in defs if n.startswith(name[:-3])]
        if len(hits) == 1:
            return hits[0]
    return None


def expand(name, defs, indent, uses, stack, errors, out):
    if name in stack:
        errors.append(f"cycle through <<{name}>>")
        return
    for pg, _, body in defs[name]:
        for md_line, text in body:
            ref = REF.match(text)
            if ref:
                target = resolve(norm(ref["name"]), defs)
                if target is None:
                    errors.append(
                        f"{pg}:{md_line}: undefined <<{ref['name']}>>"
                    )
                    continue
                uses.setdefault(target, []).append((str(pg), md_line))
                expand(target, defs, indent + ref["indent"], uses,
                       stack | {name}, errors, out)
            else:
                line = indent + text if text else ""
                out.append((line, str(pg), md_line, len(indent)))


def tangle(outdir, pages):
    defs, errors = web(pages)
    uses = {}
    roots = [n for n in defs if ROOT.match(n)]
    for root in roots:
        out = []
        expand(root, defs, "", uses, frozenset(), errors, out)
        rel = defs[root][0][0]
        header = f"# Tangled from {rel}; edit that, not this."
        lines = [header] + [t for t, *_ in out]
        text = "\n".join(lines) + "\n"
        target = Path(outdir) / root
        old = target.read_text(encoding="utf-8") if target.exists() else None
        if CHECK:
            if old != text:
                errors.append(f"lit-stale: {target} differs from {rel}")
            continue
        if old != text:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        sm = [[i + 2, pg, ml, col] for i, (_, pg, ml, col) in enumerate(out)]
        mp = Path(outdir) / ".noslop" / "lit" / (root + ".map.json")
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps(sm), encoding="utf-8")
    for name in defs:
        if ROOT.match(name):
            continue
        n = len(uses.get(name, []))
        if n == 0:
            errors.append(f"unused <<{name}>>")
        elif n > 1:
            errors.append(f"<<{name}>> used {n} times")
    return roots, errors


def selfcheck(outdir, root):
    """Every mapped tangled line equals its Markdown line, modulo indent."""
    target = Path(outdir) / root
    lines = target.read_text(encoding="utf-8").split("\n")
    bad, cache = 0, {}
    mp = Path(outdir) / ".noslop" / "lit" / (root + ".map.json")
    entries = json.loads(mp.read_text(encoding="utf-8"))
    for t_line, pg, ml, _ in entries:
        md = cache.setdefault(
            pg, (Path(outdir) / pg).read_text(encoding="utf-8").split("\n")
        )
        if lines[t_line - 1].strip() != md[ml - 1].strip():
            bad += 1
    return bad


CHECK = False

if __name__ == "__main__":
    argv = sys.argv[1:]
    CHECK = argv[:1] == ["--check"]
    argv = argv[1:] if CHECK else argv
    os.chdir(argv[0])
    root_dir = Path(".")
    roots, errors = tangle(root_dir, [Path(p) for p in argv[1:]])
    for r in roots if not errors and not CHECK else []:
        bad = selfcheck(root_dir, r)
        print(f"lit: {r}: map mismatches {bad}")
        if bad:
            errors.append(f"lit-map: {bad} mismatched lines in {r}")
    for e in errors:
        print("lit:", e, file=sys.stderr)
    sys.exit(1 if errors else 0)

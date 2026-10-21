"""
Prototype of `lit`: noweb chunks in Markdown, tangled to Python.

Throwaway measurement code for the design note (design-noweb-md.md);
not the tool itself. Subcommands: tangle, check, where, weave, fmt.
"""

import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

DEF = re.compile(r"^<<(?P<name>[^<>]+?)>>(?P<op>\+?)=\s*$")
REF = re.compile(r"^(?P<indent>[ \t]*)<<(?P<name>[^<>]+?)>>\s*$")
SPAN = re.compile(r"^<<(?P<name>[^<>]+)>>$")
TOP = re.compile(r"^(@|def |class |async def )")
ROOT = re.compile(r"^[^\s]+\.(py|lark|toml)$")
FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
SOFT, HARD = 25, 40


@dataclass
class Piece:
    name: str
    op: str
    page: str
    line: int  # 1-based md line of the first body line
    body: list[str]
    section: int
    prose: bool


def parse(root: Path, page: Path, errors: list[str]) -> list[Piece]:
    text = page.read_text()
    m = FRONT.match(text)
    if m:  # blank the front matter, keep line numbers
        text = "\n" * m.group(0).count("\n") + text[m.end() :]
    rel = str(page.relative_to(root))
    pieces: list[Piece] = []
    prose = False
    for tok in MarkdownIt("commonmark").parse(text):
        if tok.type == "paragraph_open":
            prose = True
        if tok.type == "inline":
            # `<<Name>>` in prose parses as text "<" then html_inline
            # "<Name>"; a lone `<draft>` is html, not a chunk name.
            before = ""
            for child in tok.children or []:
                bare = (child.type == "text" and "<<" in child.content) or (
                    child.type == "html_inline" and before.endswith("<")
                )
                if bare:
                    errors.append(f"{rel}:{tok.map[0] + 1}: bare << in prose")
                before = child.content
        if tok.type != "fence":
            continue
        lines = tok.content.split("\n")[:-1]
        d = DEF.match(lines[0]) if lines else None
        if not d:
            continue
        start = tok.map[0] + 3  # fence line, def line, then body
        pieces.append(
            Piece(d["name"], d["op"], rel, start, lines[1:],
                  len(pieces) + 1, prose)
        )
        prose = False
    return pieces


def collect(root: Path) -> tuple[dict[str, list[Piece]], list[str]]:
    errors: list[str] = []
    defs: dict[str, list[Piece]] = {}
    for page in sorted(root.rglob("*.md")):
        for p in parse(root, page, errors):
            at = f"{p.page}:{p.line - 1}"
            if p.op == "" and p.name in defs:
                errors.append(f"{at}: <<{p.name}>>= defined twice")
            if p.op == "+" and p.name not in defs:
                errors.append(f"{at}: <<{p.name}>>+= before its =")
            defs.setdefault(p.name, []).append(p)
    return defs, errors


def stubbed(t: str) -> str:
    r = REF.match(t)
    return r["indent"] + "pass" if r else t


def is_def(piece: Piece) -> bool:
    return any(TOP.match(line) for line in piece.body)


Line = tuple[str, tuple[str, int] | None]


def expand(defs, name, indent, out, stack, markers, uses, errors, width):
    if name in stack:
        errors.append(f"cycle: {' -> '.join([*stack, name])}")
        return
    if name not in defs:
        errors.append(f"<<{name}>> used in <<{stack[-1]}>>, never defined")
        return
    for k, piece in enumerate(defs[name]):
        width[id(piece)] = max(width.get(id(piece), 0), len(indent))
        if k and (is_def(piece) or is_def(defs[name][k - 1])):
            out.extend([("", None)] * (2 if indent == "" else 1))
        if markers and stack and indent:  # top level: the def is the anchor
            out.append((f"{indent}# ⟨{name}⟩", None))
        for i, text in enumerate(piece.body):
            r = REF.match(text)
            if r:
                uses.setdefault(r["name"], []).append(piece)
                expand(defs, r["name"], indent + r["indent"], out,
                       [*stack, name], markers, uses, errors, width)
            else:
                out.append(
                    (indent + text if text else "", (piece.page, piece.line + i))
                )


def tangle(root: Path, markers: bool = True):
    defs, errors = collect(root)
    files: dict[str, list[Line]] = {}
    uses: dict[str, list[Piece]] = {}
    width: dict[int, int] = {}
    for name, pieces in defs.items():
        if ROOT.match(name):
            page = pieces[0].page
            out: list[Line] = [
                (f"# Tangled from {page}: edit that page.", None)
            ]
            expand(defs, name, "", out, [], markers, uses, errors, width)
            files[name] = out
    for name, pieces in defs.items():
        if not ROOT.match(name) and name not in uses:
            errors.append(f"{pieces[0].page}:{pieces[0].line - 1}: "
                          f"<<{name}>> defined, never used")
    return defs, files, uses, width, errors


def lint(root: Path, defs, width, errors: list[str]) -> list[str]:
    warn: list[str] = []
    names = set(defs)
    for name, pieces in defs.items():
        for p in pieces:
            at = f"{p.page}:{p.line - 1}"
            if not p.prose:
                errors.append(f"{at}: <<{name}>> has no prose before it")
            n = len(p.body)
            if n > HARD:
                errors.append(f"{at}: <<{name}>> is {n} lines (max {HARD})")
            elif n > SOFT:
                warn.append(f"{at}: <<{name}>> is {n} lines (aim {SOFT})")
            stub = [stubbed(t) for t in p.body]
            try:
                ast.parse("\n".join(stub))
            except SyntaxError as e:
                errors.append(f"{at}: <<{name}>> is not statements: {e.msg}")
            for i, t in enumerate(p.body):
                cols = width.get(id(p), 0) + len(t)
                if not REF.match(t) and cols > 79:
                    errors.append(f"{p.page}:{p.line + i}: {cols} cols "
                                  "once tangled (max 79)")
    for page in sorted(root.rglob("*.md")):
        for tok in MarkdownIt("commonmark").parse(page.read_text()):
            for child in tok.children or []:
                s = SPAN.match(child.content) if child.type == "code_inline" else None
                if s and s["name"] not in names:
                    errors.append(f"{page.relative_to(root)}: prose names "
                                  f"<<{s['name']}>>, which no chunk defines")
    return warn


def text_of(lines: list[Line]) -> str:
    return "\n".join(t for t, _ in lines) + "\n"


def selfcheck(root: Path, files) -> list[str]:
    bad = []
    cache: dict[str, list[str]] = {}
    for out, lines in files.items():
        for n, (t, origin) in enumerate(lines, 1):
            if origin is None:
                continue
            page, line = origin
            src = cache.setdefault(page, (root / page).read_text().split("\n"))
            md = src[line - 1]
            if not (t.endswith(md) and t[: len(t) - len(md)].strip() == ""):
                bad.append(f"{out}:{n} does not match {page}:{line}")
    return bad


def segments(src: str) -> list[str]:
    tree = ast.parse(src)
    segs = []
    for node in tree.body:
        decos = getattr(node, "decorator_list", [])
        segs.append("\n".join([*(ast.get_source_segment(src, d) or "" for d in decos),
                               ast.get_source_segment(src, node) or ""]))
    return sorted(segs)


def fmt(defs, width, ruff: str, config: str) -> list[str]:
    diffs = []
    for name, pieces in defs.items():
        for p in pieces:
            stub = [stubbed(t) for t in p.body]
            src = "\n".join(stub) + "\n"
            w = 79 - width.get(id(p), 0)
            r = subprocess.run(
                [ruff, "format", "--config", config,
                 "--config", f"line-length={w}", "-"],
                input=src, capture_output=True, text=True, check=False,
            )
            if r.returncode or r.stdout != src:
                diffs.append(f"{p.page}:{p.line - 1}: <<{name}>> "
                             f"not ruff-formatted at width {w}")
    return diffs


def main() -> int:
    cmd, root = sys.argv[1], Path(sys.argv[2])
    markers = "--no-markers" not in sys.argv
    defs, files, uses, width, errors = tangle(root, markers)
    if cmd == "tangle":
        warn = lint(root, defs, width, errors)
        for out, lines in files.items():
            (root / out).write_text(text_of(lines))
            maps = [o for _, o in lines]
            mapped = root / ".noslop" / "lit" / (out + ".map.json")
            mapped.parent.mkdir(parents=True, exist_ok=True)
            mapped.write_text(json.dumps(maps))
        print("\n".join(errors + selfcheck(root, files)) or "tangle: ok")
        print("\n".join("warn: " + w for w in warn))
        return 1 if errors else 0
    if cmd == "identity":  # tangled vs seed, as a permutation of statements
        seed = Path(sys.argv[3]).read_text()
        out = text_of(next(iter(files.values())))
        same = segments(seed) == segments(out)
        print("identity:", "same statements" if same else "DIFFERENT")
        return 0 if same else 1
    if cmd == "where":  # lit where fpl/lex.py:123
        out, n = sys.argv[3].rsplit(":", 1)
        t, origin = files[out][int(n) - 1]
        print(f"{out}:{n} <- {origin[0]}:{origin[1]}" if origin else
              f"{out}:{n} is tangler output: {t!r}")
        return 0
    if cmd == "fmt":
        diffs = fmt(defs, width, sys.argv[3], sys.argv[4])
        print("\n".join(diffs) or "fmt: every chunk is ruff-formatted")
        return 1 if diffs else 0
    if cmd == "stats":
        sizes = sorted(len(p.body) for ps in defs.values() for p in ps)
        print("chunks", len(sizes), "median", sizes[len(sizes) // 2],
              "max", sizes[-1], "sizes", sizes)
        return 0
    raise SystemExit(f"unknown {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())

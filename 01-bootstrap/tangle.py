"""
Project the literate pages to a Python package, stage mains, and Quarto
aliases.

The Markdown is the source. This writes 01-bootstrap/python/fpl/, and a
``.qmd`` symlink beside every page that holds a Marimo cell.

    python3 tangle.py             write python/fpl/, the aliases, bin/fpl
    python3 tangle.py --out DIR   write the package to DIR/fpl, nothing else
    python3 tangle.py --check     exit 1, naming each committed file that
                                  differs from what the notes tangle to

Neither ``--out`` nor ``--check`` writes into the repository, so a test
may run them while another process reads python/.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED = ROOT / "fpl"
OUT = ROOT / "python" / "fpl"
FENCE = re.compile(
    r"```python \{\.marimo(?: name=\"([^\"]+)\")?\}\n(.*?)```",
    re.S,
)

SUPPORT = (
    "errors.py",
    "ast_surface.py",
    "ast_core.py",
    "multihash.py",
    "print.py",
    "trivia.py",
    "eval.py",
    "grammar.lark",
)

MODULES = {
    "01.02-pass/01.02.01-lex.md": "lex/__init__.py",
    "01.02-pass/01.02.02-parse.md": "parse/__init__.py",
    "01.02-pass/01.02.05-desugar.md": "desugar/__init__.py",
    "01.02-pass/01.02.06-elaborate.md": "elaborate/__init__.py",
    "01.02-pass/01.02.10-evaluate.md": "evaluate/__init__.py",
    "01.01-boundary/01.01.02-fon.md": "fon/__init__.py",
    "01.01-boundary/01.01.03-pipe.md": "pipe/__init__.py",
    "01.01-boundary/01.01.01-source.md": "source.py",
    "01.01-boundary/01.01.04-render.md": "render.py",
    "01.01-boundary/01.01.05-codec.md": "codec.py",
    "01.01-boundary/01.01.06-cli.md": "cli.py",
    "01.04-compose/01.04.01-pass.md": "arrow.py",
    "01.04-compose/01.04.02-run.md": "run.py",
    "01.04-compose/01.04.05-graph.md": "graph.py",
    "01.06-nagini/01.06.01-advance.md": "advance.py",
}

PACKAGES = ("lex", "parse", "desugar", "elaborate", "evaluate")

INIT = '''\
"""The literate bootstrap, tangled from the Markdown pages."""

import fpl.trivia
from fpl.desugar import desugar
from fpl.elaborate import elaborate
from fpl.evaluate import evaluate
from fpl.lex import lex
from fpl.parse import parse
from fpl.run import run_file

__all__ = ["desugar", "elaborate", "evaluate", "lex", "parse",
"run_file"]
'''

MAIN = '''\
"""`fpl <file>` runs in-process. `fpl <stage>` is one filter."""

import sys

from fpl.cli import dispatch

if __name__ == "__main__":
    sys.exit(dispatch(sys.argv[1:]))
'''

STAGE_MAIN = """\
from fpl.pipe import cli

from . import {name}

cli({name})
"""


FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def quoted(prose: str) -> str:
    """
    A markdown stretch as a string statement. Python does not run it.
    """
    body = prose.strip("\n")
    if not body.strip():
        return ""
    wrapped: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        paragraph = " ".join(part.strip() for part in buf)
        wrapped.extend(
            textwrap.wrap(
                paragraph,
                width=72,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [paragraph]
        )
        buf.clear()

    for line in body.split("\n"):
        if line.strip() == "":
            flush()
            wrapped.append("")
        else:
            buf.append(line)
    flush()
    while wrapped and wrapped[0] == "":
        wrapped.pop(0)
    while wrapped and wrapped[-1] == "":
        wrapped.pop()
    text = "\n".join(wrapped)
    if '"""' in text:
        return "'''\n" + text + "\n'''"
    return '"""\n' + text + '\n"""'


def cell(text: str) -> str:
    """
    Every code cell, in reading order, with the prose between them as
    string statements.

    A cell named setup is the notebook's `import marimo as mo`. A cell
    named play is for running a program in the notebook. Neither belongs
    in the module.
    """
    body = FRONT_MATTER.sub("", text, count=1)
    parts: list[str] = []
    cursor = 0
    saw = False
    for match in FENCE.finditer(body):
        prose = quoted(body[cursor : match.start()])
        if prose:
            parts.append(prose)
        name, source = match.group(1), match.group(2)
        if name not in {"setup", "play"}:
            parts.append(source.rstrip())
            saw = True
        cursor = match.end()
    tail = quoted(body[cursor:])
    if tail:
        parts.append(tail)
    if not saw:
        raise SystemExit("no python cell in a module page")
    return "\n\n".join(_one_docstring(parts)) + "\n"


def _one_docstring(parts: list[str]) -> list[str]:
    """
    Page prose and a cell's opening docstring are one string, then the
    imports.
    """
    if len(parts) < 2 or not parts[0].lstrip().startswith(('"""', "'''")):
        return parts
    code = parts[1].lstrip("\n")
    match = re.match(
        r'(?P<indent>[ \t]*)(?P<q>"""|\'\'\')(?P<body>.*?)(?P=q)\s*',
        code,
        re.S,
    )
    if match is None:
        return parts
    quote = '"""' if parts[0].lstrip().startswith('"""') else "'''"
    prose = parts[0].strip()
    prose = prose[len(quote) : -len(quote)].strip("\n")
    doc = match.group("body").strip("\n")
    merged = f"{quote}\n{prose}\n\n{doc}\n{quote}"
    rest = code[match.end() :].lstrip("\n")
    return [merged, rest, *parts[2:]] if rest else [merged, *parts[2:]]


def aliases() -> None:
    """
    Point ``name.qmd`` at every page Quarto should execute.
    """
    for path in ROOT.rglob("*.md"):
        if (
            ".vendor" in path.parts
            or "site" in path.parts
            or OUT in path.parents
        ):
            continue
        if "{.marimo" not in path.read_text():
            continue
        link = path.with_suffix(".qmd")
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(path.name)


def build(out: Path) -> None:
    """
    Write the package to ``out`` from the pages and the seed's support
    modules. Whatever ``out`` held before is removed.
    """
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in SUPPORT:
        shutil.copy(SEED / name, out / name)
    for page, dest in MODULES.items():
        target = out / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(cell((ROOT / page).read_text()))
    for name in PACKAGES:
        (out / name / "__main__.py").write_text(STAGE_MAIN.format(name=name))
    (out / "__init__.py").write_text(INIT)
    (out / "__main__.py").write_text(MAIN)


def files(tree: Path) -> set[Path]:
    """
    Every file under ``tree``, relative to it; bytecode caches excluded.
    """
    return {
        path.relative_to(tree)
        for path in tree.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def stale() -> list[Path]:
    """
    The files of python/fpl that differ from a fresh tangle, or that
    one of them lacks, as paths relative to 01-bootstrap/.
    """
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "fpl"
        build(fresh)
        return [
            OUT.relative_to(ROOT) / rel
            for rel in sorted(files(fresh) | files(OUT))
            if not (fresh / rel).is_file()
            or not (OUT / rel).is_file()
            or (fresh / rel).read_bytes() != (OUT / rel).read_bytes()
        ]


def tangle() -> None:
    """
    Write python/fpl, the Quarto aliases, and bin/fpl.
    """
    build(OUT)
    aliases()
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "fpl").write_text(
        "#!/bin/sh\n"
        'here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)\n'
        'lit=$(CDPATH= cd -- "$here/.." && pwd)\n'
        "export PYTHONSAFEPATH=1\n"
        "export PYTHONPATH="
        '"$lit/.vendor:$lit/python${PYTHONPATH:+:$PYTHONPATH}"\n'
        'exec "${FPL_PYTHON:-python3}" -m fpl "$@"\n'
    )
    (bin_dir / "fpl").chmod(0o755)


def main(argv: list[str]) -> int:
    """
    Tangle, tangle elsewhere, or check; the exit status says which way
    a check went.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--out", type=Path, metavar="DIR")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.out is not None:
        build(args.out / "fpl")
        return 0
    if not args.check:
        tangle()
        return 0
    behind = stale()
    for path in behind:
        print(f"tangle: stale: {path}", file=sys.stderr)
    if behind:
        print(
            "tangle: python/fpl is not what the notes tangle to; run"
            " python3 tangle.py in 01-bootstrap/ and commit python/"
            " with the notes",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

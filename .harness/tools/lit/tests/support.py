"""Helpers the tests share: fixture pages and the command line.

Fixtures are written to a temporary directory and never committed as
files, so the repository holds no deliberately broken page.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from lit import facts
from lit.__main__ import main

FENCE = "```"

GOOD = """
    ---
    type: Note
    ---
    # Demo

    The file.

    `add' sums.

    ```python
    <<1 Functions
    demo.py>>=
    def add(a: int, b: int) -> int:
        return a + b
    ```
    """


def md(text: str) -> str:
    """Dedent a page and drop its leading newline."""
    return dedent(text).lstrip("\n")


def page(root: Path, name: str, text: str) -> Path:
    """Write a fixture page under ``root``; its absolute path."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md(text), encoding="utf-8")
    return path


def lit(root: Path, *argv: str) -> int:
    """Run the command line on ``root``; its exit status."""
    return main(["--root", str(root), *argv])


# The query cases both readers answer: facts.query in test_hand.py, the
# overlay's block in test_query_js.py. A case may carry rows of its own.
CASES = json.loads((Path(__file__).parent / "query_cases.json").read_text())

# Rows that bear no edge: a relation from a node to itself, one with a
# single target, a set with one member, a set naming one member twice.
EDGELESS: list[facts.Row] = [
    {"id": "x", "item": "p.md", "text": "X"},
    {"id": "c", "labels": ["cites"], "targets": ["x", "x"]},
    {"id": "b", "labels": ["because"], "targets": ["x"]},
    {"id": "k", "labels": ["coref"], "targets": ["x"]},
    {"id": "q", "labels": ["parts"], "targets": ["x", "x"]},
]

# Each bare term beside its one-edge chain: every relation and set for
# ``has``, every relation for ``gives`` (a set member never gives).
PAIRS = [
    (f"{key}:{kind}", f"{key}:{kind}+1")
    for key, kinds in (
        ("has", facts.RELATIONS | facts.SETS),
        ("gives", facts.RELATIONS),
    )
    for kind in sorted(kinds)
]


def chain_rows(n: int) -> list[facts.Row]:
    """Spans ``k0`` to ``kn``, each supporting the next."""
    spans: list[facts.Row] = [
        {"id": f"k{i}", "item": "p.md", "text": str(i)} for i in range(n + 1)
    ]
    links: list[facts.Row] = [
        {
            "id": f"c{i}",
            "labels": ["supports"],
            "targets": [f"k{i}", f"k{i + 1}"],
        }
        for i in range(n)
    ]
    return spans + links

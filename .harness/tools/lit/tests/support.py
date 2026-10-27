"""Helpers the tests share: fixture pages and the command line.

Fixtures are written to a temporary directory and never committed as
files, so the repository holds no deliberately broken page.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from lit.__main__ import main

FENCE = "```"

GOOD = """
    # Demo

    The file.

    ```python
    <<demo.py>>=
    <<Functions>>
    ```

    `add' sums.

    ```python
    <<Functions>>=
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

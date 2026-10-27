"""Tool output read back to the page: a tangled place, a page place.

A traceback's ``File "fpl/lex.py", line 12`` and a linter's
``fpl/lex.py:12:5:`` name a line of a tangled file, which nobody should
edit. `rewrite' turns each into the page line the tangled line came
from, so the place a tool reports is the place to edit. A file is
recognised by its name relative to the root, relative to the working
directory, or as an absolute path; a column is kept as it stands.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from lit.web import Tangled


def table(tangled: list[Tangled], root: Path) -> dict[str, Tangled]:
    """Every spelling of each tangled file's path, to the file."""
    out: dict[str, Tangled] = {}
    for t in tangled:
        full = (root / t.name).resolve()
        for key in (t.name, str(full), os.path.relpath(full)):
            out[key] = t
    return out


def rewrite(text: str, files: dict[str, Tangled], root: Path) -> str:
    """``text`` with each tangled place made a page place."""
    if not files:
        return text
    names = "|".join(
        re.escape(k) for k in sorted(files, key=len, reverse=True)
    )
    trace = re.compile(rf'File "({names})", line (\d+)')
    colon = re.compile(rf"(?<![\w/.])({names}):(\d+)")

    def page(name: str, line: str) -> tuple[str, int] | None:
        t = files[name]
        k = int(line) - 1
        if not 0 <= k < len(t.origin):
            return None
        return os.path.relpath(root / t.page), t.origin[k]

    def by_trace(m: re.Match[str]) -> str:
        hit = page(m[1], m[2])
        return f'File "{hit[0]}", line {hit[1]}' if hit else m[0]

    def by_colon(m: re.Match[str]) -> str:
        hit = page(m[1], m[2])
        return f"{hit[0]}:{hit[1]}" if hit else m[0]

    return colon.sub(by_colon, trace.sub(by_trace, text))

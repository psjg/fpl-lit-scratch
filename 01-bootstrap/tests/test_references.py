"""
Every citation of an example program names one that exists.

The harness cites the maintainer's examples by name: HOLES.md, the docs
and the test docstrings point at a program as a path under
`03-fpl/OLD/03.01-features/`, as `examples/<name>` or, with a line, as
`<name>:<line>`. A rename under `03-fpl/OLD/03.01-features/` leaves
those citations pointing at nothing, and nothing else notices. A bare
name with no line is not taken as a citation: `python -m fpl file.fpl`
and a test's `tmp_path / "p.fpl"` name no example.
"""

import re
from pathlib import Path

from corpus import PROGRAMS, REPO

HERE = Path(
    __file__
).parent.parent  # this project: 01-bootstrap/, or mutmut's copy of it
NAMES = {p.name for p in PROGRAMS}
CITERS = sorted(
    [
        *REPO.glob("*.md"),
        *REPO.glob(".agents/*.md"),
        *REPO.glob("02-docs/**/*.md"),
        *REPO.glob("01-bootstrap/*.md"),
        *HERE.glob("tests/*.py"),
        *HERE.glob("fpl/**/*.py"),
    ]
)

# A full path, `examples/<name>`, or `<name>:<line>`; a glob or a brace
# never matches. A path is taken whole, whatever leads to its
# `features/` (`03-fpl/OLD/03.01-features/`, or a stale
# `fpl/features/`), and is read from the repository root or, as a
# Markdown link is, from the directory of the page that cites it.
PATH = re.compile(r"[\w./-]*\bfeatures/[\w.-]+/examples/[\w.-]+\.fpl\b")
NAME = re.compile(
    r"(?:\bexamples/([\w.-]+\.fpl)\b|(?<![\w./-])([\w.-]+\.fpl):\d)"
)


def dangling(text: str, page: Path = REPO) -> list[str]:
    """
    The citations in `text`, a file in directory `page`, that name no
    example program.
    """
    paths = [
        m
        for m in PATH.findall(text)
        if not (REPO / m).is_file() and not (page / m).is_file()
    ]
    names = [a or b for a, b in NAME.findall(text) if (a or b) not in NAMES]
    return paths + names


def test_a_renamed_program_dangles() -> None:
    name = "gone.fpl"
    path = f"03-fpl/OLD/03.01-features/draft1/examples/{name}"
    assert dangling(f"{path}:3, {name}:3 and draft1.fpl:2") == [
        path,
        name,
        name,
    ]


def test_a_link_is_read_from_the_page_that_holds_it() -> None:
    name = "draft1.fpl"
    link = f"../03-fpl/OLD/03.01-features/draft1/examples/{name}"
    assert dangling(f"[x]({link})", REPO / "02-docs") == []
    assert dangling(f"[x]({link})") == [link]


def test_a_path_from_before_the_move_dangles() -> None:
    name = "draft1.fpl"
    stale = f"fpl/features/draft1/examples/{name}"
    assert dangling(f"see {stale}") == [stale]


def test_every_citation_names_a_program() -> None:
    found = {
        str(p.relative_to(REPO)): dangling(
            p.read_text(encoding="utf-8"), p.parent
        )
        for p in CITERS
    }
    assert {p: d for p, d in found.items() if d} == {}

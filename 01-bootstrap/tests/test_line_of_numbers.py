"""
The note `03-fpl/line-of-numbers.md` is a test suite written in FPL,
and this file runs it: the note is the single source of truth, and
nothing here restates a row.

Every line in an `fpl` fence that holds ` |- ` is a row `L |- R`
(DI-0072). The walker does not read `|-` as a check yet, so a row is
run the long way: `L` goes through :func:`fpl.driver.run` and the
output must be `R`. A row the walker cannot meet today is the target,
named in OPEN with the decision that must land first. Its test is a
strict xfail: when the row starts to pass the suite fails loudly and
the entry goes, so the open list can only shrink.
"""

import re

import pytest
from corpus import REPO

from fpl.driver import run

NOTE = REPO / "03-fpl" / "line-of-numbers.md"
FENCE = re.compile(r"^```fpl\n(.*?)^```$", re.DOTALL | re.MULTILINE)
SEPARATOR = " |- "
ROWS_NOW = 36
"""
How many rows the note holds at least. A row deleted instead of fixed
drops under it; a row added raises it here in the same change.
"""
OPEN = {
    "1 2 3 4 + 1 |- 2 3 4 5": "DI-0072 cluster 2: a scalar maps",
    "1 2 3 4 + 4 3 2 1 |- 5 5 5 5": "DI-0072 cluster 2: strands zip",
    "[ 1 2 3 4 ] + |- 10": "DI-0072 cluster 1: a quotation reduces",
    "1 2 3 4 | + fold |- 10": "DI-0072 cluster 1: bar and fold agree",
    "1 1 + |- [1 1 +]": "DI-0072 cluster 3: |- as a check",
    "[ [ 1 2 + ] 3 times ] ! |- 9": "DI-0073: the postfix lisp reading",
}
"""
The rows that are the target and not the walker, each keyed by its
whole row (the comment cut, as :func:`rows` cuts it) with the cluster
of DI-0072, or the decision DI-0073, that must land first. The whole
row is the key because two rows can share a left side (`1 1 +`).
"""


def split(line: str) -> tuple[str, str] | None:
    """
    The two sides of a row, or None for a line that is not a row.

    The comment is cut first, at the first `;` as the lexer cuts it,
    because a comment may itself hold ` |- `. The rest splits once, at
    the last ` |- `, so the right side is the one that follows it.

    >>> split("1 1 + |- 2")
    ('1 1 +', '2')
    >>> split('1 1 + |- [1 1 +]  ; wanted: |- ! err/<> ""')
    ('1 1 +', '[1 1 +]')
    >>> split("1 2 | 3 4 |- 1 2 | 3 4")
    ('1 2 | 3 4', '1 2 | 3 4')
    >>> split("1 1 +") is None
    True
    """
    code = line.split(";", 1)[0].strip()
    left, found, right = code.rpartition(SEPARATOR)
    return (left, right) if found else None


def rows() -> list[tuple[str, str]]:
    """
    Every row of the note, in the order written.
    """
    fenced = (m.group(1) for m in FENCE.finditer(NOTE.read_text()))
    found = (split(ln) for body in fenced for ln in body.splitlines())
    return [row for row in found if row]


def mark(row: tuple[str, str]) -> pytest.MarkDecorator | None:
    """
    The strict xfail for a row in OPEN, or None for one that must pass.
    """
    text = row[0] + SEPARATOR + row[1]
    if text not in OPEN:
        return None
    return pytest.mark.xfail(strict=True, reason=OPEN[text])


def case(row: tuple[str, str]) -> object:
    """
    A parameter for a row: its whole text as the id, marked if open.
    """
    marks = [m for m in [mark(row)] if m]
    return pytest.param(*row, id=row[0] + SEPARATOR + row[1], marks=marks)


@pytest.mark.parametrize(("left", "right"), [case(r) for r in rows()])
def test_row(left: str, right: str) -> None:
    """
    The output of the left side is the right side. A walker error is a
    failure, not a skip: the row stays red until the walker meets it.
    """
    assert run(left + "\n") == right + "\n"


def test_every_open_row_is_in_the_note() -> None:
    """
    No stale key: an entry of OPEN that names a row the note no longer
    holds (fixed in the note, or renamed) is removed.
    """
    texts = {left + SEPARATOR + right for left, right in rows()}
    assert set(OPEN) <= texts


def test_the_note_keeps_its_rows() -> None:
    """
    A deleted row is noticed: the note holds at least ROWS_NOW rows.
    """
    assert len(rows()) >= ROWS_NOW

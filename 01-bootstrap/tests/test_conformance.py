"""
Every maintainer-written example checks itself (DI-0072): a run line
that prints carries `L |- R`, and a program that fails closes on
`|- ! err/<tag> “message”` (.agents/CONVENTIONS.md). So an example
conforms when the walker runs it to the end: a check that does not
hold, a failure other than the one judged, or a judged failure that
does not come, each raises an FplError. The template is an example too.
"""

from pathlib import Path

import pytest
from corpus import PROGRAMS

from fpl.driver import run


def name(program: Path) -> str:
    """
    The suite and the example, as the test ids name it.
    """
    return f"{program.parts[-3]}/{program.stem}"


@pytest.mark.parametrize("program", PROGRAMS, ids=[name(p) for p in PROGRAMS])
def test_example(program: Path) -> None:
    run(program.read_text())

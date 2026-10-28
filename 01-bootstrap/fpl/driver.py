r"""Run a program from source text to its printed output.

:func:`run` is the whole path: :func:`checked` parses, desugars and type
checks, :func:`stacks` evaluates, and :func:`printed` renders. The
command line and the tests use these steps alone or together.
"""

from collections.abc import Callable

from fpl.ast_core import Run, Statement
from fpl.desugar import desugar, listing
from fpl.eval import Stack, evaluate
from fpl.parse import parse
from fpl.print import render
from fpl.types import Goal, elaborate, reported

#: Each run line's source line number with the stack it leaves.
type Lines = tuple[tuple[int, Stack], ...]

#: Steps each run line may take, in a file run and in each REPL event
#: alike (HOLES.md: fuel-scope). A word that calls itself forever uses
#: about 2.3 s of it, once or twice a body (#144), while the programs
#: the suite runs stay far inside it. Fuel counts steps, not their size:
#: a loop that grows a list or the stack each round can take longer.
FUEL_DEFAULT = 1_000_000


def silent(_line: str) -> None:
    """Discard a reported goal; the default *report* of :func:`run`."""


def checked(source: str) -> tuple[tuple[Statement, ...], tuple[Goal, ...]]:
    r"""Parse, desugar and type check a program.

    Args:
        source: The program text.

    Returns:
        The desugared statements, each body checked against its effect
        line, and the goals met, in the order written.

    Raises:
        :exc:`~fpl.errors.FplError`: *source* does not parse
            (:func:`fpl.parse.parse`) or a body does not match its
            effect line (:func:`fpl.types.elaborate`).

    Examples:
        >>> statements, goals = checked("1 2\n")
        >>> len(statements), goals
        (1, ())
    """
    statements = desugar(parse(source))
    return statements, elaborate(statements)[1]


def stacks(
    statements: tuple[Statement, ...],
    fuel: int | None = None,
    *,
    spent: list[int | None] | None = None,
) -> Lines:
    r"""Evaluate the run lines of a program.

    Args:
        statements: The statements from :func:`checked`.
        fuel: Steps each run line may take; ``None`` is no bound.
        spent: When given, each run line appends the steps it took, in
            order, even when it fails.

    Returns:
        Each run line's line number with the stack it leaves.

    Raises:
        :exc:`~fpl.errors.FplError`: A run line fails, for instance with
            ``out of fuel`` (:func:`fpl.eval.evaluate`).
        ValueError: *fuel* is below zero (:func:`fpl.eval.evaluate`).

    Examples:
        >>> statements, _ = checked("1 2\n3\n")
        >>> stacks(statements)
        ((1, (Strand(items=(1, 2)),)), (2, (3,)))
        >>> stacks(statements, -1)
        Traceback (most recent call last):
        ValueError: fuel below zero: -1
    """
    lines = (s.span.line for s in statements if isinstance(s, Run))
    return tuple(
        zip(lines, evaluate(statements, fuel, spent=spent), strict=True)
    )


def printed(left: Lines) -> str:
    r"""Print the stacks, one line each, as :func:`fpl.print.render`.

    The output format is the hole ``program-output``.

    Args:
        left: The result of :func:`stacks`.

    Returns:
        The text of all lines, each ending in a newline.

    Examples:
        >>> printed(stacks(checked("1 2\n3\n")[0]))
        '1 2\n3\n'
    """
    return render(listing(tuple(stack for _, stack in left)))


def run(source: str, report: Callable[[str], None] = silent) -> str:
    r"""Run a program and return what it prints.

    Definitions print nothing. Each run line gets :data:`FUEL_DEFAULT`
    steps, so a program without end stops with ``out of fuel`` at its
    line.

    Args:
        source: The program text.
        report: Called with each goal met, before any line runs.

    Raises:
        :exc:`~fpl.errors.FplError`: Any failure of :func:`checked` or
            :func:`stacks`.

    Examples:
        >>> run("1 2\n3\n")
        '1 2\n3\n'
        >>> run("$x\n")
        Traceback (most recent call last):
        fpl.errors.FplError: ERROR: 1:1 no evaluator yet
    """
    statements, goals = checked(source)
    for goal in goals:
        report(reported(goal))
    return printed(stacks(statements, FUEL_DEFAULT))

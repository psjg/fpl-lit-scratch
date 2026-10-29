r"""Run a program from source text to its printed output.

:func:`run` is the whole path: :func:`checked` parses, desugars and type
checks, :func:`stacks` evaluates, and :func:`printed` renders. The
command line and the tests use these steps alone or together.
"""

from collections.abc import Callable, Iterable

from fpl.ast_core import Judgment, Run, Statement
from fpl.ast_surface import Program
from fpl.desugar import closing, desugar, listing
from fpl.errors import FplError, NoFailError, UnmatchedFailError
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
    return elaborated(parse(source))


def elaborated(
    program: Program,
) -> tuple[tuple[Statement, ...], tuple[Goal, ...]]:
    r"""Desugar and type check a parsed program, as :func:`checked`.

    Args:
        program: The parsed program.

    Returns:
        The desugared statements and the goals met, as :func:`checked`.

    Raises:
        :exc:`~fpl.errors.FplError`: As :func:`checked`, past parsing.

    Examples:
        >>> statements, goals = elaborated(parse("1 2\n"))
        >>> len(statements), goals
        (1, ())
    """
    statements = desugar(program)
    return statements, elaborate(statements)[1]


def shown(stack: Stack) -> str:
    r"""Print one stack as its line of output, for a failed check.

    The empty stack, which prints as the empty line, is ``nothing``.

    Examples:
        >>> shown((1, "a")), shown(())
        ('1 | “a”', 'nothing')
    """
    return output((stack,)).removesuffix("\n") or "nothing"


def output(left: Iterable[Stack]) -> str:
    r"""Print stacks, one line each, as :func:`fpl.print.render`.

    Args:
        left: The stacks of the run lines, in order.

    Returns:
        The text of all lines, each ending in a newline.

    Examples:
        >>> output([(1, 2), (3,)])
        '1 | 2\n3\n'
    """
    return render(listing(tuple(left)))


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
    left = evaluate(statements, fuel, spent=spent, show=shown)
    return tuple(zip(lines, left, strict=True))


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
    return output(stack for _, stack in left)


def run(source: str, report: Callable[[str], None] = silent) -> str:
    r"""Run a program and return what it prints.

    Definitions print nothing. Each run line gets :data:`FUEL_DEFAULT`
    steps, so a program without end stops with ``out of fuel`` at its
    line. A closing fail judgment ``|- ! err/<tag> “message”``
    (:func:`fpl.desugar.closing`) turns the failure it names into
    output: what the lines before it printed, then its ``ERROR:`` line.

    Args:
        source: The program text.
        report: Called with each goal met, before any line runs.

    Raises:
        :exc:`~fpl.errors.FplError`: Any failure of parsing,
            :func:`checked` or :func:`stacks` that no judgment names.
        :exc:`~fpl.errors.UnmatchedFailError`: The program fails other
            than its judgment says (:func:`judged`).
        :exc:`~fpl.errors.NoFailError`: The program has a judgment and
            passes.

    Examples:
        >>> run("1 2\n3\n")
        '1 2\n3\n'
        >>> run("$x\n")
        Traceback (most recent call last):
        fpl.errors.NoEvaluatorError: ERROR: 1:1 no evaluator yet
        >>> run("1\n$x\n|- ! err/unresolved/no-evaluator\n")
        'ERROR: 1:1 no evaluator yet\n'
        >>> run("1\n|- ! err/no-row\n")  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        fpl.errors.NoFailError: ERROR: 2:1 check failed: expected ...
    """
    program, judgment = closing(parse(source))
    left: list[Stack] = []
    try:
        statements, goals = elaborated(program)
        for goal in goals:
            report(reported(goal))
        evaluate(statements, FUEL_DEFAULT, left=left, show=shown)
    except FplError as error:
        if judgment is None:
            raise
        return judged(judgment, error, left)
    if judgment is not None:
        raise NoFailError(
            judgment.span, f"expected {judgment.tag}, the program passed"
        )
    return output(left)


def judged(judgment: Judgment, error: FplError, left: list[Stack]) -> str:
    r"""Return the output of a program that failed as judged.

    The error matches when its tag is the judgment's, and its message
    too where the judgment gives one.

    Args:
        judgment: The program's closing fail judgment.
        error: The failure of the program.
        left: The stacks of the run lines before the failure.

    Returns:
        Their lines, then the error's ``ERROR:`` line.

    Raises:
        :exc:`~fpl.errors.UnmatchedFailError`: The error does not
            match, at the judgment's line.

    Examples:
        >>> from fpl.errors import FailError, Span
        >>> error = FailError(Span(3, 1), "no row fits")
        >>> judged(Judgment("err/no-row", None), error, [(1,)])
        '1\nERROR: 3:1 no row fits\n'
        >>> judged(  # doctest: +ELLIPSIS
        ...     Judgment("err/check", None), error, []
        ... )
        Traceback (most recent call last):
        fpl.errors.UnmatchedFailError: ERROR: 1:1 check failed: ...
    """
    if error.tag != judgment.tag:
        raise UnmatchedFailError(
            judgment.span, f"expected {judgment.tag}, got {error.tag}"
        ) from error
    if judgment.message not in (None, error.message):
        raise UnmatchedFailError(
            judgment.span,
            f"expected “{judgment.message}”, got “{error.message}”",
        ) from error
    return output(left) + f"{error}\n"

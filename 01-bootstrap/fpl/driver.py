r"""Run a program from source text to its printed output.

:func:`run` is the whole path: :func:`checked` parses, desugars and type
checks, :func:`stacks` evaluates, and :func:`printed` renders. The
command line and the tests use these steps alone or together.
"""

import re
from collections.abc import Callable, Iterable

from fpl.ast_core import Judgment, Run, Statement
from fpl.ast_surface import Program
from fpl.desugar import closing, desugar, listing
from fpl.errors import FplError, NoFailError, UnmatchedFailError
from fpl.eval import Stack, evaluate
from fpl.parse import parse
from fpl.print import render
from fpl.types import Goal, elaborate, reported

OPENS = re.compile(r"\s*\|-\s+!")
"""How a line opens that may close a program that does not read."""

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
    output: what the lines before it printed, then its fail line,
    which pasted back as the closing line is the same judgment. That
    holds for a program that does not even read: its closing line is
    then found in the text (:func:`sealed`).

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
        fpl.errors.NoEvaluatorError: |- ! err/unresolved/no-evaluator...
        >>> run("1\n$x\n|- ! err/unresolved/no-evaluator\n")
        '|- ! err/unresolved/no-evaluator 1:1 “no evaluator yet”\n'
        >>> run("1\n|- ! err/no-row\n")  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        fpl.errors.NoFailError: |- ! err/check/no-fail 2:1 ...
    """
    left: list[Stack] = []
    try:
        program, judgment = closing(parse(source))
    except FplError as error:
        if (judgment := sealed(source)) is None:
            raise
        return judged(judgment, error, left)
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


def sealed(source: str) -> Judgment | None:
    r"""Read the closing fail judgment of a program that does not parse.

    The parsed program is not there to take the judgment off, so it is
    found in the text: a line that opens with ``|- !``, tried from the
    last one back. That line and the lines after it are parsed on their
    own, at their own line numbers, and :func:`fpl.desugar.closing`
    reads the judgment. A tail that does not read is no closing line
    (the ``|- !`` stood inside a string or a comment, or something after
    it is broken) and the search moves back; the read error of the
    lines before the closing line is then the failure it judges.

    Args:
        source: The program text, which did not parse.

    Returns:
        The judgment, or None when no line opens with ``|- !``, no such
        tail reads, or code follows the one that does.

    Raises:
        :exc:`~fpl.errors.FplError`: The judgment is malformed.

    Examples:
        >>> sealed("[ 1\n|- ! err/read/unclosed\n").tag
        'err/read/unclosed'
        >>> boxed = "[\n|- ! err/read/unclosed\n⟦\n|- ! err/no-row\n⟧\n"
        >>> sealed(boxed).tag
        'err/read/unclosed'
        >>> sealed("[ 1\n|- ! err/read/unclosed\n1\n") is None
        True
        >>> sealed("[ 1\n") is None
        True
    """
    lines = source.split("\n")
    for at in reversed(range(len(lines))):
        if not OPENS.match(lines[at]):
            continue
        try:
            tail = parse("\n" * at + "\n".join(lines[at:]))
        except FplError:
            continue
        return closing(tail)[1]
    return None


def judged(judgment: Judgment, error: FplError, left: list[Stack]) -> str:
    r"""Return the output of a program that failed as judged.

    The error matches when its tag is the judgment's, and its message,
    position and step too where the judgment gives them.

    Args:
        judgment: The program's closing fail judgment.
        error: The failure of the program.
        left: The stacks of the run lines before the failure.

    Returns:
        Their lines, then the error's fail line.

    Raises:
        :exc:`~fpl.errors.UnmatchedFailError`: The error does not
            match, at the judgment's line.

    Examples:
        >>> from fpl.errors import FailError, Span
        >>> error = FailError(Span(3, 1), "no row fits")
        >>> judged(Judgment("err/no-row", None), error, [(1,)])
        '1\n|- ! err/no-row 3:1 “no row fits”\n'
        >>> judged(  # doctest: +ELLIPSIS
        ...     Judgment("err/check", None), error, []
        ... )
        Traceback (most recent call last):
        fpl.errors.UnmatchedFailError: |- ! err/check/unmatched-fail ...
    """
    if (wrong := unmatched(judgment, error)) is not None:
        raise UnmatchedFailError(judgment.span, wrong) from error
    return output(left) + f"{error}\n"


def unmatched(judgment: Judgment, error: FplError) -> str | None:
    """Say what of a judgment the error does not match, if anything.

    Returns:
        ``expected <what>, got <what>`` for the first of the tag, the
        message, the position and the step that the judgment gives and
        the error has otherwise; None when all match.

    Examples:
        >>> from fpl.errors import FailError, Span
        >>> error = FailError(Span(3, 1), "no row fits")
        >>> there = Judgment("err/no-row", None, at=Span(4, 1))
        >>> unmatched(there, error)
        'expected 4:1, got 3:1'
    """
    if judgment.tag != error.tag:
        return f"expected {judgment.tag}, got {error.tag}"
    if judgment.message not in (None, error.message):
        return f"expected “{judgment.message}”, got “{error.message}”"
    at, span = judgment.at, error.span
    if at is not None and at != span:
        return f"expected {at.line}:{at.col}, got {span.line}:{span.col}"
    if judgment.step not in (None, error.step):
        got = "no step" if error.step is None else f"step {error.step}"
        return f"expected step {judgment.step}, got {got}"
    return None

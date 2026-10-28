"""A pad: one FPL program written as a column of cells.

The pad is read top to bottom, like a file, and every cell shows the
turns it gave, like a toplevel. A cell holds what one would type at
``fpl repl``: its lines are grouped into inputs by
:func:`fpl.repl.inputs`, and each input is entered by
:func:`fpl.session.enter` after the state the cells above it left. So
the pad and the REPL cannot disagree about a result or a refusal.

History can be edited. :func:`run` sets the text of one cell and
evaluates that cell and every cell below it again, in order, from the
state the cells above it left; the cells above are kept as they are.
The log is held in memory, as ``fpl repl`` holds it without
``--session``, and grows by one event per input, an error included.

A turn is written as the OCaml toplevel writes one, with FPL's effect
line as the type (:func:`fpl.types.shown`):

    - : -- number = 9
    sq : number -- number = <word>
    ERROR: 1:1 unknown word: x

A type the elaborator does not infer is ``...``, as in
:func:`fpl.repl.result_line`. Goals and other notes follow as ``;;``
lines.

The module does no I/O; :mod:`fpl.pad_web` is its shell.
"""

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal

from fpl.ast_core import Define, Run, Statement
from fpl.driver import FUEL_DEFAULT, checked
from fpl.errors import FplError
from fpl.log import Log
from fpl.parse import parse
from fpl.repl import EMPTY, inputs, provenance
from fpl.session import Context, Outcome, enter, evaluator, program
from fpl.types import Arrow, Typing, UntypedError, after, elaborate
from fpl.types import shown as effect

#: What a cell's last evaluation came to: every input ran, one failed,
#: the text goes on after its last line, or the cell holds no input.
type Status = Literal["ok", "error", "pending", "empty"]

#: The type of a run line the elaborator does not infer.
UNTYPED = "..."
#: The value shown for a definition: a word, not a value.
WORD = "<word>"
#: The turn of a cell whose input goes on after its last line.
PENDING = ";; the input goes on"


@dataclass(frozen=True)
class Cell:
    """A cell's text and what its last evaluation showed.

    *log* is the session as the cell leaves it: the log the cell below
    starts from.
    """

    #: The text, as typed; tabs are kept.
    source: str
    #: What the evaluation came to.
    status: Status
    #: The turn lines, in the order the inputs gave them.
    turns: tuple[str, ...]
    #: The cells above, by index, whose output this cell changed.
    changes: tuple[int, ...]
    #: The session after the cell.
    log: Log


def context(env: Mapping[str, str], fuel: int = FUEL_DEFAULT) -> Context:
    """Build the context every input of a pad is entered with.

    It is the REPL's: the evaluator's hash and the provenance in *env*.

    Raises:
        fpl.log.RefusedError: As :func:`fpl.repl.provenance` refuses.
    """
    return Context(evaluator(), *provenance(env), fuel)


def run(
    cells: Sequence[Cell], index: int, source: str, ctx: Context
) -> tuple[Cell, ...]:
    """Set the text of a cell and evaluate it and every cell below.

    Args:
        cells: The pad as it stands.
        index: The cell to set; ``len(cells)`` appends a cell.
        source: Its new text.
        ctx: What each input is entered with.

    Returns:
        The pad after: the cells above *index* as they were, then the
        cells from *index* on, evaluated again.

    Raises:
        IndexError: *index* is beyond the end of the pad.

    Examples:
        >>> pad = run((), 0, "1 | 2 +", context({}))
        >>> pad[0].turns
        ('- : -- number = 3',)
    """
    if not 0 <= index <= len(cells):
        raise IndexError(index)
    sources = [cell.source for cell in cells]
    sources[index : index + 1] = [source]
    return replayed(cells[:index], sources[index:], ctx)


def removed(
    cells: Sequence[Cell], index: int, ctx: Context
) -> tuple[Cell, ...]:
    """Remove a cell and evaluate every cell below it again.

    Raises:
        IndexError: No cell has *index*.
    """
    if not 0 <= index < len(cells):
        raise IndexError(index)
    sources = [cell.source for cell in cells[index + 1 :]]
    return replayed(cells[:index], sources, ctx)


def replayed(
    above: Sequence[Cell], sources: Sequence[str], ctx: Context
) -> tuple[Cell, ...]:
    """Evaluate *sources* in order below the cells *above*."""
    pad = list(above)
    for source in sources:
        pad.append(evaluated(source, pad, ctx))
    return tuple(pad)


def evaluated(source: str, above: Sequence[Cell], ctx: Context) -> Cell:
    """Evaluate one cell after the state the cells *above* left.

    An input that fails does not stop the inputs after it, as in the
    REPL; its event joins the log, but not the program.
    """
    log = above[-1].log if above else EMPTY
    lines = iter(source.splitlines())
    texts = list(inputs(lambda _on: next(lines, None)))
    if not texts:
        return Cell(source, "empty", (), (), log)
    if _open(texts[-1]):
        return Cell(source, "pending", (PENDING,), (), log)
    return _entered(source, texts, above, ctx)


def _entered(
    source: str, texts: Sequence[str], above: Sequence[Cell], ctx: Context
) -> Cell:
    """Enter the inputs *texts* of a cell, one after another."""
    log = above[-1].log if above else EMPTY
    turns: list[str] = []
    changes: list[int] = []
    failed = False
    for text in texts:
        outcome = enter(log, text, ctx, log.head)
        ok = outcome.event.status == "ok"
        failed = failed or not ok
        turns.extend(_turned(log, text, outcome) if ok else _refused(outcome))
        for note in outcome.notes if ok else ():
            changes.extend(_owner(above, note))
            turns.append(_noted(above, note))
        log = log.grown(outcome.event, outcome.bodies, log.size)
    status: Status = "error" if failed else "ok"
    return Cell(source, status, tuple(turns), tuple(sorted(set(changes))), log)


def _open(text: str) -> bool:
    """Tell whether *text* ends inside a pair it has not closed.

    The end of a cell ends its last input, as a blank line does in the
    REPL, so a definition with its body is done; only an open pair
    still waits for its closer (:func:`fpl.repl.pending` says the
    same of it).
    """
    try:
        parse(text)
    except FplError as error:
        return error.message.endswith("never closed")
    return False


def _refused(outcome: Outcome) -> list[str]:
    """Return the turn of an input that failed.

    It is the REPL's ``ERROR`` line, then the caret under the error and
    any goal, as ``;;`` lines.
    """
    notes = "\n".join(outcome.notes).split("\n") if outcome.notes else []
    return [*outcome.out.splitlines(), *(f";; {line}" for line in notes)]


def _turned(log: Log, text: str, outcome: Outcome) -> list[str]:
    """Return the typed turn lines of an input that ran.

    Each statement of the input gives one line: a definition its name
    and inferred effect, a run line ``-`` with the effect it has from
    an empty stack and the stack it printed.
    """
    before = "".join(part.text for part in program(log, log.head))
    entered = text if text.endswith("\n") else text + "\n"
    statements, _goals = checked(before + entered)
    arrows, _ = elaborate(statements)
    first = before.count("\n") + 1
    values = iter(outcome.out.splitlines())
    turns: list[str] = []
    for statement in statements:
        if statement.span.line >= first:
            turns.extend(_typed(statement, arrows, values))
    return [*turns, *(f"- : {UNTYPED} = {value}" for value in values)]


def _typed(
    statement: Statement, arrows: Mapping[str, Arrow], values: Iterator[str]
) -> list[str]:
    """Return the turn line of one statement of an input.

    A clause of a dispatched word shows no line of its own; its
    dispatcher shows the word.
    """
    if isinstance(statement, Define):
        if len(statement.clause) > 1:
            return []
        return [
            f"{statement.name} : {effect(arrows[statement.word])} = {WORD}"
        ]
    return [f"- : {_ran(statement, arrows)} = {next(values, '')}".rstrip()]


def _ran(run_line: Run, arrows: Mapping[str, Arrow]) -> str:
    """Return the effect a run line has from an empty stack.

    Returns:
        ``-- <sorts>``, or :data:`UNTYPED` when the elaborator does not
        infer the line.
    """
    with suppress(UntypedError, FplError):
        end = after(Typing((), {}, {}), run_line.code, arrows)
        return effect(Arrow((), end.stack))
    return UNTYPED


def _owner(above: Sequence[Cell], note: str) -> list[int]:
    """Return the cell that holds the event a ``CHANGED`` note names."""
    match note.split():
        case ["CHANGED", seq, *_]:
            sizes = [len(cell.log.events) for cell in above]
            return [bisect_left(sizes, int(seq))]
        case _:
            return []


def _noted(above: Sequence[Cell], note: str) -> str:
    """Return a note as a turn line, a changed event as its cell."""
    owner = _owner(above, note)
    if owner:
        return f";; CHANGED cell {owner[0] + 1}"
    return ";; " + note.replace("\n", "\n;; ")

"""A pad: one FPL program written as a column of cells, held as text.

The pad is read top to bottom, like a file, and every cell shows the
turns it gave, as ``fpl repl`` shows them at a terminal. The page shows
the pad as one buffer, the :func:`transcript` with the bar of the cell
to come under it (:func:`buffer`), and hands the buffer back after an
edit: :func:`synced` reads it as the REPL reads a paste, keeps the
cells whose text stands, and evaluates the first that differs and every
cell below it. A cell holds
what one would type at the REPL: its lines are grouped into inputs by
:func:`fpl.repl.inputs`, and each input is entered by
:func:`fpl.session.enter` after the state the cells above it left. So
the pad and the REPL cannot disagree about a result or a refusal.

History can be edited. :func:`run` sets the text of one cell and
evaluates that cell and every cell below it again, in order, from the
state the cells above it left; the cells above are kept as they are.
The log is held in memory, as ``fpl repl`` holds it without
``--session``, and grows by one event per input, an error included.

A cell is written as the REPL writes a phrase: the ``;;!`` bar above
it (:func:`fpl.repl.phrase_bar`), which counts the cell, names the
head it starts from and carries the fuel and ms of the cell above;
then a result line per line the input printed
(:func:`fpl.repl.result_line`), with the sorts the elaborator infers
on the stack in the type slot:

    ;;! -( 09:05:03 )-< command 2 >-------------{ head: 1; ms: 1.0 }-
    3 sq
    |- 9 : number

A definition prints nothing, as in the REPL; a type the elaborator
does not infer is ``...``, as in the REPL. A refusal is the REPL's
``ERROR`` line; goals and other notes follow under the bar's mark, as
``;;!`` lines. So everything a cell shows beside its text is what the
loop writes, and :func:`fpl.repl.written` drops it on the way back in:
the :func:`transcript` of a pad, pasted into ``fpl repl`` or seeded
into a pad, is the program the cells hold.

A :func:`preview` evaluates the cell under the cursor before it is
committed, on the cells above it, and keeps nothing. Its
:class:`Ghost` is the line a commit would show (:func:`shaded`), which
the page paints faded after the cell's text. It is bounded twice, as
the server answers one request at a time and a commit waits behind it:

- each run line gets :data:`PREVIEW_FUEL` steps, so a line without end
  shows as ``out of fuel``, as a commit would show it, only sooner;
- the whole preview gets :data:`PREVIEW_SECONDS`, read between inputs
  on the :class:`fpl.repl.Tty` timer, so no number of such lines, nor
  of edited cells above, adds up. Past it, no input is entered and the
  ghost ends in :data:`CUT`; it overruns by one input at most.

Steps alone would not do for the second bound: an input runs the whole
program again (:func:`fpl.session.enter`), and its count of steps
leaves those out. The history runs under the fuel of a line too, so a
committed line heavier than :data:`PREVIEW_FUEL` gives every cell below
it an ``ERROR: @N ... out of fuel`` ghost.

The module does no I/O; :mod:`fpl.pad_web` is its shell. The clocks
come in as the REPL's :class:`fpl.repl.Tty`, so a test can hold them
still.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Literal

from fpl.ast_core import Run
from fpl.driver import FUEL_DEFAULT, checked
from fpl.errors import FplError
from fpl.log import Log
from fpl.parse import parse
from fpl.repl import (
    BAR,
    EMPTY,
    RESULT,
    Tty,
    inputs,
    phrase_bar,
    provenance,
    result_line,
    written,
)
from fpl.session import Context, Outcome, enter, evaluator, program
from fpl.types import Arrow, Typing, UntypedError, after, elaborate
from fpl.types import shown as effect

#: What a cell's last evaluation came to: every input ran, one failed,
#: the text goes on after its last line, or the cell holds no input.
type Status = Literal["ok", "error", "pending", "empty"]

#: The turn of a cell whose input goes on after its last line.
PENDING = f"{BAR} the input goes on"
#: What a phrase bar opens with; a cell of the buffer starts at one.
BAR_HEAD = f"{BAR} -("
#: The steps each run line of a preview may take: an endless loop
#: stops in about 85 ms, at some 2.1 us a step on a laptop.
PREVIEW_FUEL = 40_000
#: The time a whole preview may take before it enters no more inputs:
#: some two such loops, under the page's pause of 300 ms in typing.
PREVIEW_SECONDS = 0.2
#: The last turn of a cell its preview stopped in, or never reached.
CUT = "ERROR: preview out of time"


@dataclass(frozen=True)
class Cell:
    """A cell's text and what its last evaluation showed.

    *log* is the session as the cell leaves it: the log the cell below
    starts from. *spent* and *ms* are what the bar of the cell below
    reports, as the REPL's next bar reports a phrase; both are None for
    a cell that ran nothing, or failed.
    """

    #: The text, as typed; tabs are kept.
    source: str
    #: What the evaluation came to.
    status: Status
    #: The phrase bar above the cell.
    bar: str
    #: The turn lines, in the order the inputs gave them.
    turns: tuple[str, ...]
    #: The cells above, by index, whose output this cell changed.
    changes: tuple[int, ...]
    #: The session after the cell.
    log: Log
    #: The steps the cell's inputs took; None when none ran.
    spent: int | None = None
    #: The wall time of the cell's evaluation; None when none ran.
    ms: float | None = None


@dataclass(frozen=True)
class Ghost:
    """What a cell not yet committed would show, as one faded line.

    The page paints it after the cell's last text line, beside the
    text, so the buffer and its lines stay as typed.
    """

    #: The line of the buffer it follows, counted from 0.
    line: int
    #: A result, a refusal, or a run cut short by the preview's fuel
    #: or its time.
    kind: Literal["ok", "error", "fuel"]
    #: The cell's result and ``ERROR`` lines, parted by two spaces; it
    #: never holds a newline.
    text: str


@dataclass(frozen=True)
class _Part:
    """The lines of one cell of a buffer, as the reader keeps them."""

    #: The offset in the buffer of the part's first line.
    start: int
    #: Each line the loop did not write, by its number counted from 0;
    #: empty lines at both ends are trimmed.
    lines: tuple[tuple[int, str], ...]

    @property
    def text(self) -> str:
        """The cell's text; empty when the part holds none."""
        return "\n".join(line for _, line in self.lines)


def _never() -> bool:
    """Tell a commit it is never late: it enters every input."""
    return False


def context(env: Mapping[str, str], fuel: int = FUEL_DEFAULT) -> Context:
    """Build the context every input of a pad is entered with.

    It is the REPL's: the evaluator's hash and the provenance in *env*.

    Raises:
        fpl.log.RefusedError: As :func:`fpl.repl.provenance` refuses.
    """
    return Context(evaluator(), *provenance(env), fuel)


def run(
    cells: Sequence[Cell], index: int, source: str, ctx: Context, tty: Tty
) -> tuple[Cell, ...]:
    """Set the text of a cell and evaluate it and every cell below.

    Args:
        cells: The pad as it stands.
        index: The cell to set; ``len(cells)`` appends a cell.
        source: Its new text.
        ctx: What each input is entered with.
        tty: The clocks of the bars.

    Returns:
        The pad after: the cells above *index* as they were, then the
        cells from *index* on, evaluated again.

    Raises:
        IndexError: *index* is beyond the end of the pad.

    Examples:
        >>> pad = run((), 0, "1 | 2 +", context({}), Tty())
        >>> pad[0].turns
        ('|- 3 : number',)
    """
    if not 0 <= index <= len(cells):
        raise IndexError(index)
    sources = [cell.source for cell in cells]
    sources[index : index + 1] = [source]
    return replayed(cells[:index], sources[index:], ctx, tty)


def replayed(
    above: Sequence[Cell],
    sources: Sequence[str],
    ctx: Context,
    tty: Tty,
    late: Callable[[], bool] = _never,
) -> tuple[Cell, ...]:
    """Evaluate *sources* in order below the cells *above*.

    Once *late* holds, as it is asked before each input, no input is
    entered any more (:func:`evaluated`).
    """
    pad = list(above)
    for source in sources:
        pad.append(evaluated(source, pad, ctx, tty, late))
    return tuple(pad)


def chunks(text: str) -> list[str]:
    r"""Split a buffer into the texts of its cells.

    A cell starts at a phrase bar; text before the first bar is a cell
    too. In each, the lines the loop wrote drop away
    (:func:`fpl.repl.written`) and blank lines at the edges go. A cell
    left with no text is no cell.

    Examples:
        >>> chunks(";;! -( 9 )-\n1 2 +\n|- 3 : ...\n\n;;! -( 9 )-\n")
        ['1 2 +']
    """
    return [part.text for part in _parts(text) if part.text]


def _parts(text: str) -> list[_Part]:
    r"""Part a buffer at its phrase bars, keeping the program's lines.

    The lines are those of ``text.split("\n")``, numbered as the page
    numbers the lines it paints; a part opens at offset 0 and at every
    bar, and a line the loop wrote (:func:`fpl.repl.written`) is left
    out of it.
    """
    starts: list[int] = [0]
    kept: list[list[tuple[int, str]]] = [[]]
    at = 0
    for number, line in enumerate(text.split("\n")):
        if line.startswith(BAR_HEAD):
            starts.append(at)
            kept.append([])
        elif not written(line):
            kept[-1].append((number, line))
        at += len(line) + 1
    return [_Part(s, _trimmed(k)) for s, k in zip(starts, kept, strict=True)]


def _trimmed(
    lines: list[tuple[int, str]],
) -> tuple[tuple[int, str], ...]:
    """Drop the empty lines at both ends of a part."""
    filled = [i for i, (_, line) in enumerate(lines) if line]
    return tuple(lines[filled[0] : filled[-1] + 1]) if filled else ()


def synced(
    cells: Sequence[Cell], text: str, ctx: Context, tty: Tty
) -> tuple[Cell, ...]:
    """Bring the pad to the buffer *text*.

    A cell whose text stands as it was is kept, with its bar and turns;
    the first cell that differs, and every cell below it, is evaluated
    again, from the state the cells above it left.
    """
    sources = chunks(text)
    kept = _kept(cells, sources)
    return replayed(cells[:kept], sources[kept:], ctx, tty)


def _kept(cells: Sequence[Cell], sources: Sequence[str]) -> int:
    """Count the cells, from the top, whose text *sources* leaves be."""
    kept = 0
    for cell, source in zip(cells, sources, strict=False):
        if cell.source.rstrip("\n") != source:
            break
        kept += 1
    return kept


def buffer(cells: Sequence[Cell], tty: Tty, indent: str = "") -> str:
    """Return the pad as the page edits it.

    It is the :func:`transcript`, then the bar of the cell to come on a
    line of its own, for the text typed under it.
    """
    return transcript(cells, indent) + bar(cells, tty) + "\n"


def caret(
    text: str,
    cursor: int,
    cells: Sequence[Cell],
    tty: Tty,
    indent: str = "",
) -> int:
    """Return where the caret goes once *text* is synced to *cells*.

    *cursor* is an offset into *text*. The caret goes to the start of
    the text of the cell after the one the cursor was in, as the REPL
    reads on under the next bar; past the last cell, to the end of the
    :func:`buffer`, written with *indent*.
    """
    parts = _parts(text)
    here = bisect_right([part.start for part in parts], cursor)
    target = sum(bool(part.text) for part in parts[:here])
    if target < len(cells):
        before = transcript(cells[:target], indent)
        return len(before) + len(cells[target].bar) + 1
    return len(buffer(cells, tty, indent))


def preview(  # noqa: PLR0913 -- the pad's arguments and a budget
    cells: Sequence[Cell],
    text: str,
    cursor: int,
    ctx: Context,
    tty: Tty,
    *,
    fuel: int = PREVIEW_FUEL,
    seconds: float = PREVIEW_SECONDS,
) -> Ghost | None:
    """Return what the cell under the cursor would show; keep nothing.

    The cell is evaluated as :func:`synced` would evaluate it, from the
    state the cells above it leave, but under at most *fuel* steps per
    run line and *seconds* in all, so neither a line that never ends
    nor many of them hold up the typing; the cells stay as they were.

    Args:
        cells: The pad as it stands.
        text: The buffer as typed, not yet committed.
        cursor: An offset into *text*; on a bar or a result line, it is
            in that bar's cell.
        ctx: What each input is entered with.
        tty: The clocks of the bars.
        fuel: The budget of each run line, if below *ctx*'s.
        seconds: The budget of the whole preview, on *tty*'s timer.

    Returns:
        The ghost after the cell's last text line, or None when the
        cell is empty, defines only, waits for a closer, or stands as
        committed, with every cell above it. Past *seconds*, the ghost
        holds the turns of the inputs entered and ends in :data:`CUT`,
        a cell that only defines included.
    """
    found = _under(text, cursor)
    if found is None:
        return None
    index, part = found
    sources = chunks(text)
    kept = _kept(cells, sources)
    if index < kept:
        return None
    small = replace(ctx, fuel=min(ctx.fuel, fuel))
    until = tty.timer() + seconds

    def late() -> bool:
        return tty.timer() > until

    todo = sources[kept : index + 1]
    cell = replayed(cells[:kept], todo, small, tty, late)[-1]
    return shaded(cell, part.lines[-1][0])


def _under(text: str, cursor: int) -> tuple[int, _Part] | None:
    """Return the cell the cursor is in, and how many cells precede it.

    None when the part under the cursor holds no text.
    """
    parts = _parts(text)
    i = bisect_right([part.start for part in parts], cursor) - 1
    if not parts[i].text:
        return None
    return sum(bool(part.text) for part in parts[:i]), parts[i]


def shaded(cell: Cell, line: int) -> Ghost | None:
    """Return a cell's turns as a ghost after the buffer line *line*.

    It keeps the result lines and the ``ERROR`` lines, the turns that
    say what the cell came to; the carets and notes under a bar, the
    blank line of an empty stack and the turn of an open pair go.

    Returns:
        The ghost, of kind ``fuel`` when a run ran out of fuel or the
        preview out of time (:data:`CUT`); None when no turn is kept,
        as for a definition.

    Examples:
        >>> (cell,) = run((), 0, "1 | 2 +", context({}), Tty())
        >>> shaded(cell, 3)
        Ghost(line=3, kind='ok', text='|- 3 : number')
    """
    shown = [t for t in cell.turns if t.startswith((RESULT + " ", "ERROR:"))]
    if not shown:
        return None
    ran_out = any(turn.endswith(("out of fuel", CUT)) for turn in shown)
    kind = "fuel" if ran_out else _kind(cell.status)
    return Ghost(line, kind, "  ".join(shown))


def _kind(status: Status) -> Literal["ok", "error"]:
    """Narrow the status of a cell that kept a turn: ran or failed."""
    return "error" if status == "error" else "ok"


def bar(above: Sequence[Cell], tty: Tty) -> str:
    """Return the phrase bar of the cell that follows *above*.

    It is the REPL's: the cell's number, the head it starts from, the
    time now, and the fuel and ms of the cell above it.

    Examples:
        >>> from datetime import datetime
        >>> at = datetime(2026, 1, 1, 9, 5, 3)
        >>> bar((), Tty(now=lambda: at))  # doctest: +ELLIPSIS
        ';;! -( 09:05:03 )-< command 1 >-...-{ head: 0 }-'
    """
    last = above[-1] if above else None
    return phrase_bar(
        len(above) + 1,
        len(last.log.events) if last else 0,
        tty.now(),
        fuel=last.spent if last else None,
        ms=last.ms if last else None,
    )


def transcript(cells: Sequence[Cell], indent: str = "") -> str:
    """Return the pad as text, as the page shows it.

    Each cell is its bar, its text and its turns, each turn under
    *indent* (a tab sets the results in from the text, as BQNPad does;
    the REPL writes none); a blank line parts the cells. Everything but
    the text is what the loop writes, so the reader of ``fpl repl`` and
    of ``fpl pad FILE`` drops it (:func:`fpl.repl.written`), indented
    or not, and reads the program the cells hold.

    Examples:
        >>> from datetime import datetime
        >>> still = Tty(now=lambda: datetime(2026, 1, 1, 9, 5, 3))
        >>> pad = run((), 0, "1 | 2 +", context({}), still)
        >>> print(transcript(pad))  # doctest: +ELLIPSIS
        ;;! -( 09:05:03 )-< command 1 >-...-{ head: 0 }-
        1 | 2 +
        |- 3 : number
        <BLANKLINE>
    """
    return "".join(
        "\n".join(
            [
                cell.bar,
                cell.source.rstrip("\n"),
                *(indent + turn if turn else turn for turn in cell.turns),
            ]
        )
        + "\n\n"
        for cell in cells
    )


def evaluated(
    source: str,
    above: Sequence[Cell],
    ctx: Context,
    tty: Tty,
    late: Callable[[], bool] = _never,
) -> Cell:
    """Evaluate one cell after the state the cells *above* left.

    An input that fails does not stop the inputs after it, as in the
    REPL; its event joins the log, but not the program. *late* is asked
    before each input: once it holds, the cell enters no more and its
    last turn is :data:`CUT` (a :func:`preview`'s deadline).
    """
    log = above[-1].log if above else EMPTY
    blank = Cell(source, "empty", bar(above, tty), (), (), log)
    lines = iter(source.splitlines())
    texts = list(inputs(lambda _on: next(lines, None)))
    if not texts:
        return blank
    if _open(texts[-1]):
        return replace(blank, status="pending", turns=(PENDING,))
    started = tty.timer()
    cell = _entered(blank, texts, above, ctx, late)
    ms = (tty.timer() - started) * 1000.0
    return cell if cell.status == "error" else replace(cell, ms=ms)


def _entered(
    blank: Cell,
    texts: Sequence[str],
    above: Sequence[Cell],
    ctx: Context,
    late: Callable[[], bool],
) -> Cell:
    """Enter the inputs *texts* of the cell *blank*, in time, in turn.

    *blank* holds the cell's text and bar and the log it starts from.
    """
    log = blank.log
    outcomes: list[Outcome] = []
    turns: list[str] = []
    changes: list[int] = []
    for text in texts:
        if late():
            turns.append(CUT)
            break
        outcome = enter(log, text, ctx, log.head)
        outcomes.append(outcome)
        ok = outcome.event.status == "ok"
        turns.extend(_turned(log, text, outcome) if ok else _refused(outcome))
        for note in outcome.notes if ok else ():
            changes.extend(_owner(above, note))
            turns.append(_noted(above, note))
        log = log.grown(outcome.event, outcome.bodies, log.size)
    status: Status = "ok" if _ran_all(outcomes) else "error"
    changed = tuple(sorted(set(changes)))
    fuel = _spent(outcomes)
    return replace(
        blank,
        status=status,
        turns=tuple(turns),
        changes=changed,
        log=log,
        spent=fuel,
    )


def _ran_all(outcomes: Sequence[Outcome]) -> bool:
    """Tell whether every input of a cell ran."""
    return all(outcome.event.status == "ok" for outcome in outcomes)


def _spent(outcomes: Sequence[Outcome]) -> int | None:
    """Return the steps a cell's inputs took, for the bar below it.

    It is the sum of what the inputs report, as the REPL sums a phrase;
    None when an input failed or none reports steps, as the REPL's bar
    then shows no fuel.
    """
    steps = [o.spent for o in outcomes if o.spent is not None]
    return sum(steps) if steps and _ran_all(outcomes) else None


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
    any goal, as ``;;!`` lines.
    """
    notes = "\n".join(outcome.notes).split("\n") if outcome.notes else []
    return [*outcome.out.splitlines(), *(f"{BAR} {line}" for line in notes)]


def _turned(log: Log, text: str, outcome: Outcome) -> list[str]:
    """Return the result lines of an input that ran.

    Each run line of the input gives the REPL's result line for the
    stack it printed, with the sorts it leaves on the stack from an
    empty one in the type slot; a definition gives no line. A line
    printed beyond the run lines keeps the REPL's ``...``.
    """
    before = "".join(part.text for part in program(log, log.head))
    entered = text if text.endswith("\n") else text + "\n"
    statements, _goals = checked(before + entered)
    arrows, _ = elaborate(statements)
    first = before.count("\n") + 1
    values = iter(outcome.out.splitlines())
    turns: list[str] = []
    for statement in statements:
        if statement.span.line >= first and isinstance(statement, Run):
            turns.append(_resulted(next(values, ""), _ran(statement, arrows)))
    return [*turns, *(_resulted(value) for value in values)]


def _resulted(value: str, typ: str = "...") -> str:
    """Return the result line of *value*; an empty stack, a blank line.

    The REPL leaves the blank line a run with nothing on the stack
    prints as it is (:func:`fpl.repl.transcript`).
    """
    return result_line(value, typ) if value else ""


def _ran(run_line: Run, arrows: Mapping[str, Arrow]) -> str:
    """Return the sorts a run line leaves on the stack, from empty.

    They are the outputs of its effect line, :func:`fpl.types.shown`
    without the ``--`` that parts the inputs, of which there are none.

    Returns:
        The sorts, parted by spaces, or ``...`` when the elaborator does
        not infer the line, as :func:`fpl.repl.result_line` writes one.
    """
    with suppress(UntypedError, FplError):
        end = after(Typing((), {}, {}), run_line.code, arrows)
        return effect(Arrow((), end.stack)).removeprefix("--").strip()
    return "..."


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
        return f"{BAR} CHANGED cell {owner[0] + 1}"
    return f"{BAR} " + note.replace("\n", f"\n{BAR} ")

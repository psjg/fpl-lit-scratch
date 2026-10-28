"""Run an input against the state of a session log.

The state at an event is the accepted inputs its deps lead back through,
joined and run as one file. :func:`enter` prints only the output of the
new input's own lines and names each earlier input whose output the new
input changed; :func:`rewind` makes the event that returns to an earlier
state. Only :func:`evaluator` does I/O: it reads the package's sources.
"""

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import cache, cached_property
from pathlib import Path

from fpl.ast_core import Run, Statement
from fpl.driver import Lines, checked, printed, stacks
from fpl.errors import FplError, Span
from fpl.log import SCHEMA, Event, Log, RefusedError, Status, Who, prefixed
from fpl.multihash import Multihash, content, hashed
from fpl.types import Goal, reported

#: Message of the :exc:`FplError` that :meth:`_Entry.margin` raises.
MARGIN = "an input starts at the left margin"


@dataclass(frozen=True)
class Context:
    """What every event of a call records beside its input.

    HOLES.md (fuel-scope) describes *fuel*.
    """

    #: Hash of the evaluator's sources, from :func:`evaluator`.
    evaluator: Multihash
    #: Who entered the input.
    who: Who
    #: The model that entered it.
    model: str
    #: The session it was entered in.
    session: str
    #: Step budget of each run line.
    fuel: int


@dataclass(frozen=True)
class Part:
    """An accepted input of a program, with its text."""

    #: The input's event.
    event: Event
    #: The decoded body of *event*.
    text: str


@dataclass(frozen=True)
class Outcome:
    """An entered input, not yet appended to a log."""

    #: The new event.
    event: Event
    #: The bytes of the body and output that *event* names.
    bodies: Mapping[Multihash, bytes]
    #: Output for stdout.
    out: str
    #: Notes for stderr: goals met, the caret under an error, inputs
    #: changed.
    notes: tuple[str, ...]
    #: Steps the input's own run lines took in this call; not kept on
    #: the event. ``None`` when no run line of the input reported steps.
    spent: int | None = None


@cache
def evaluator() -> Multihash:
    """Hash the package's sources.

    Each ``*.py`` and ``*.lark`` file next to this module contributes
    its name and its bytes, both length-prefixed, in name order. Cached
    for the life of the process.

    Returns:
        A hash that changes with any edit to those files.
    """
    here = Path(__file__).parent
    sources = sorted([*here.glob("*.py"), *here.glob("*.lark")])
    return hashed(
        b"".join(
            prefixed(f.name.encode()) + prefixed(f.read_bytes())
            for f in sources
        )
    )


def program(log: Log, at: Event | None) -> tuple[Part, ...]:
    """List the accepted inputs of the state at an event, oldest first.

    Follows the first dep of each event back to the origin. An event
    adds a part only if it is an input with status ``ok``, so an error's
    program is its parent's and a rewind's is its target's.

    Args:
        log: The log holding *at* and its ancestors.
        at: The event whose state is wanted; ``None`` is the origin.

    Returns:
        The parts, oldest first; empty at the origin.

    Examples:
        >>> from fpl.log import Log
        >>> program(Log((), {}, 0), None)
        ()
    """
    events = {each.ident: each for each in log.events}
    parts: list[Part] = []
    while at is not None:
        if at.kind == "input" and at.status == "ok":
            parts.append(Part(at, log.bodies[at.body].decode()))
        at = events[at.deps[0]] if at.deps else None
    return tuple(reversed(parts))


def _next(log: Log, context: Context, at: Event | None) -> Event:
    """Build an empty ``ok`` input event extending the state at *at*."""
    empty = content(b"")
    return Event(
        schema=SCHEMA,
        evaluator=context.evaluator,
        kind="input",
        seq=len(log.events) + 1,
        deps=(at.ident,) if at else (),
        links=(),
        body=empty,
        out=empty,
        status="ok",
        who=context.who,
        model=context.model,
        session=context.session,
        fuel=context.fuel,
    )


@dataclass(frozen=True)
class _Entry:
    """An input to run after the program at an event.

    Knows where each part and the input start in the joined source.
    """

    log: Log
    at: Event | None
    context: Context
    parts: tuple[Part, ...]
    text: str

    @cached_property
    def source(self) -> str:
        """The program at the input's state: its parts, joined."""
        return "".join(part.text for part in self.parts)

    @cached_property
    def starts(self) -> tuple[int, ...]:
        """The line each part starts at, then the input's first line."""
        starts = [1]
        for part in self.parts:
            starts.append(starts[-1] + part.text.count("\n"))
        return tuple(starts)

    def owner(self, line: int) -> int:
        """Find the part that holds a line of the joined source.

        Args:
            line: A line number in :attr:`source`, counted from 1.

        Returns:
            The part's index; the input's own index is ``len(parts)``.
        """
        return bisect_right(self.starts, line) - 1

    def local(self, span: Span) -> Span:
        """Convert a span of the joined source to one in its part."""
        return Span(
            span.line - self.starts[self.owner(span.line)] + 1, span.col
        )

    def margin(self) -> None:
        """Refuse an indented input that follows other parts.

        Joined, such an input would become part of the block of the
        input before it. The first input is not checked.

        Raises:
            FplError: The input has earlier parts and its first
                non-blank line starts with whitespace; the span is that
                line, and the message is :data:`MARGIN`.
        """
        lines = self.text.split("\n")
        first = next((line for line in lines if line.strip()), "")
        if self.parts and first[:1].isspace():
            raise FplError(
                Span(self.starts[-1] + lines.index(first), 1), MARGIN
            )

    def noted(self, goals: tuple[Goal, ...]) -> tuple[str, ...]:
        """Report the goals in the input, at their place in it."""
        mine = (g for g in goals if self.owner(g.span.line) == len(self.parts))
        return tuple(
            reported(replace(g, span=self.local(g.span))) for g in mine
        )

    def logged(
        self,
        status: Status,
        out: str,
        notes: tuple[str, ...],
        *,
        spent: int | None = None,
    ) -> Outcome:
        """Make the input's outcome from status, output and notes."""
        body, shown = self.text.encode(), out.encode()
        event = replace(
            _next(self.log, self.context, self.at),
            body=content(body),
            out=content(shown),
            status=status,
        )
        return Outcome(
            event, {event.body: body, event.out: shown}, out, notes, spent
        )


def _failed(
    entry: _Entry,
    error: FplError,
    notes: tuple[str, ...],
    *,
    spent: int | None = None,
) -> Outcome:
    """Make the outcome of an input that failed.

    The output is one ``ERROR:`` line with the error's place in the
    input, or ``@<seq>`` and its place in the earlier input it lies in.
    The caret under the error, drawn in that input, is added to the
    notes.
    """
    owner = entry.owner(error.span.line)
    local = FplError(entry.local(error.span), error.message)
    texts = (*(part.text for part in entry.parts), entry.text)
    where = (
        f"@{entry.parts[owner].event.seq} " if owner < len(entry.parts) else ""
    )
    line = f"ERROR: {where}{local.span.line}:{local.span.col} {local.message}"
    caret = local.render(texts[owner]).partition("\n")[2]
    return entry.logged(
        "error",
        line + "\n",
        (*notes, caret) if caret else notes,
        spent=spent,
    )


def _phrase_spent(
    entry: _Entry,
    statements: tuple[Statement, ...],
    per_run: list[int | None],
) -> int | None:
    """Sum the steps of the input's own run lines, not of history.

    Returns:
        ``None`` if none of those lines reported steps.
    """
    runs = (s for s in statements if isinstance(s, Run))
    total = 0
    any_spent = False
    for run, n in zip(runs, per_run, strict=False):
        if entry.owner(run.span.line) != len(entry.parts) or n is None:
            continue
        total += n
        any_spent = True
    return total if any_spent else None


def _by_part(entry: _Entry, lines: Lines) -> list[Lines]:
    """Group a run's lines by the part they lie in, the input last."""
    groups: list[Lines] = [() for _ in entry.starts]
    for line, stack in lines:
        groups[entry.owner(line)] += ((line, stack),)
    return groups


def _earlier(entry: _Entry, left: Lines) -> Lines:
    """Run the program at the input's state again, as a baseline.

    The fuel is the one its last part was accepted with, whose run
    covered the whole program.

    Args:
        entry: The input; its program is the one run again.
        left: The lines of the new run, returned when the baseline
            fails. Nothing then differs, so the baseline never refuses
            an input whose own run succeeded.
    """
    fuel = entry.parts[-1].event.fuel if entry.parts else entry.context.fuel
    try:
        return stacks(checked(entry.source)[0], fuel)
    except FplError:
        return left


def _changed(
    entry: _Entry, left: Lines, before: Lines, notes: tuple[str, ...]
) -> Outcome:
    """Make the outcome of an input that ran.

    Args:
        entry: The input.
        left: The lines of the run with the input.
        before: The lines of the run of the state the input extends.
        notes: Notes to keep, which come before the changed ones.

    Returns:
        The input's own output, and a ``CHANGED <seq> $<hash>`` note for
        each earlier input whose lines print differently than in
        *before*. A change is named at the input that causes it, not
        again after.
    """
    now, was = _by_part(entry, left), _by_part(entry, before)
    moved = (
        part.event
        for part, new, old in zip(entry.parts, now, was, strict=False)
        if printed(new) != printed(old)
    )
    changed = tuple(f"CHANGED {e.seq} ${e.ident.spelled()}" for e in moved)
    return entry.logged("ok", printed(now[-1]), notes + changed)


def enter(log: Log, text: str, context: Context, at: Event | None) -> Outcome:
    """Run *text* after the program at an event.

    A final newline is added if *text* lacks one. The text is joined
    after the program's parts and run as one file. Goals are noted even
    when the run then fails. An :exc:`FplError` from the margin rule on,
    whether raised while checking or running, becomes an ``error`` event
    whose state is its parent's. The program at *at* is run once more to
    compare lines with; if that run fails, no earlier input is named.

    Args:
        log: The log holding *at* and its ancestors.
        text: The input.
        context: What the new event records beside the input.
        at: The event to extend; ``None`` is the origin.

    Returns:
        The outcome, not yet appended to *log*; its ``spent`` counts the
        input's own run lines only.
    """
    entry = _Entry(
        log,
        at,
        context,
        program(log, at),
        text if text.endswith("\n") else text + "\n",
    )
    notes: tuple[str, ...] = ()
    statements: tuple[Statement, ...] = ()
    per_run: list[int | None] = []
    try:
        entry.margin()
        statements, goals = checked(entry.source + entry.text)
        notes = entry.noted(goals)
        left = stacks(statements, context.fuel, spent=per_run)
    except FplError as error:
        return _failed(
            entry,
            error,
            notes,
            spent=_phrase_spent(entry, statements, per_run),
        )
    cost = _phrase_spent(entry, statements, per_run)
    return replace(
        _changed(entry, left, _earlier(entry, left), notes), spent=cost
    )


def rewind(log: Log, target: Event | None, context: Context) -> Event:
    """Make the event that returns the head to an earlier state.

    The event's state is that of *target*, and it links the head it
    leaves.

    Args:
        log: The log to rewind.
        target: The event to return to; ``None`` is the origin.
        context: What the new event records.

    Raises:
        RefusedError: The log is empty, or *target* is the head.

    Examples:
        >>> from fpl.log import Log
        >>> rewind(Log((), {}, 0), None, None)
        Traceback (most recent call last):
        ...
        fpl.log.RefusedError: nothing to rewind
    """
    head = log.head
    if head is None:
        raise RefusedError("nothing to rewind")
    if target == head:
        raise RefusedError("cannot rewind to the head")
    return replace(
        _next(log, context, target), kind="rewind", links=(head.ident,)
    )

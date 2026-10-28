"""Command line and read-eval loop over a session log.

:func:`main` runs one call of ``argv``, or the loop when ``argv`` names
no action. :func:`once` runs one call without printing, for
:mod:`fpl.kernel`. :func:`inputs` and :func:`pending` group typed lines
into inputs. An append is checked against ``--head`` and durable before
anything is printed.

Exit status is 0 for success, 1 when the input failed, and 2 for bad
argv or a refusal (a path the system refuses included), with nothing
written but a lock.
"""

import importlib
import itertools
import os
import random
import re
import sys
import time
from argparse import ArgumentParser
from bisect import bisect_left
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal, NoReturn, TextIO, override

from fpl.ast_surface import Line, Program
from fpl.desugar import plain
from fpl.driver import FUEL_DEFAULT
from fpl.errors import FplError
from fpl.lex import Lines, prelex
from fpl.log import (
    ASCII,
    U64,
    Event,
    Log,
    RefusedError,
    Who,
    keyed,
    load,
    locked,
    resolve,
    write,
)
from fpl.multihash import Multihash
from fpl.parse import parse
from fpl.print import render
from fpl.session import Context, enter, evaluator, program, rewind
from fpl.trivia import code, head

#: The usage line written for bad argv.
USAGE = (
    "usage: python -m fpl.repl [--session FILE] [--fuel N] "
    "[--canonical] [--at EVENT]"
    " [--head EVENT] [-e SOURCE | --rewind EVENT | --log | --show]"
)
#: Names of the actions a call can carry, in lookup order.
ACTIONS = ("source", "rewind", "log", "show")
#: A decimal numeral without leading zeros.
NUMERAL = re.compile(r"0|[1-9][0-9]*")
#: The empty log, which a call without ``--session`` starts from.
EMPTY = Log((), {}, 0)
#: The mark a phrase bar opens with: a DOC line, so a paste skips it.
BAR = ";;!"
#: The mark a result line opens with: a turnstile.
RESULT = "|-"
#: What the pad ends each line it writes in: the note sign set off by
#: a space on each side, an empty note. The reader takes it off again.
TERMINATOR = " ; "


class UsageError(Exception):
    """Raised for argv that the command line does not take."""


class _Parser(ArgumentParser):
    """An ArgumentParser that raises :exc:`UsageError`, not exits."""

    @override
    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def _fuel(text: str) -> int:
    """Parse a step budget as the log records it.

    The budget is a decimal numeral without leading zeros, below 2^64.

    Raises:
        ValueError: *text* is not such a numeral.

    Examples:
        >>> _fuel("10")
        10
        >>> _fuel("010")
        Traceback (most recent call last):
        ValueError: 010
    """
    if not NUMERAL.fullmatch(text) or int(text) >= U64:
        raise ValueError(text)
    return int(text)


def _sourced(argv: list[str]) -> list[str]:
    """Join a source that opens with ``-`` to its ``-e``.

    argparse would otherwise take the source for an option.

    Returns:
        *argv* with each such pair joined as ``-e<source>``.

    Examples:
        >>> _sourced(["-e", "-1", "--log"])
        ['-e-1', '--log']
    """
    out: list[str] = []
    for arg in argv:
        if out and out[-1] == "-e" and arg.startswith("-"):
            out[-1] += arg
        else:
            out.append(arg)
    return out


@dataclass(frozen=True)
class _Call:
    """The options of a call, and its action with the action's value.

    The value is ``""`` for a flag action.
    """

    session: Path | None
    fuel: int
    canonical: bool
    at: str | None
    head: str | None
    action: str
    value: str


def _call(argv: list[str]) -> _Call:
    """Parse *argv* into a call.

    With no action, the action is ``"loop"``.

    Raises:
        UsageError: argparse refuses *argv* (an unknown option, two
            actions or a bad ``--fuel``), or ``--at`` is beside
            ``--head``, ``--rewind`` or ``--log``, which name no state
            to evaluate at.
    """
    parser = _Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--session", type=Path)
    parser.add_argument("--fuel", type=_fuel, default=FUEL_DEFAULT)
    parser.add_argument("--canonical", action="store_true")
    parser.add_argument("--at")
    parser.add_argument("--head")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("-e", dest="source")
    action.add_argument("--rewind")
    action.add_argument("--log", action="store_const", const="")
    action.add_argument("--show", action="store_const", const="")
    args = vars(parser.parse_args(_sourced(argv)))
    name = next((name for name in ACTIONS if args[name] is not None), "loop")
    if args["at"] is not None and (
        args["head"] is not None or name in ("rewind", "log")
    ):
        raise UsageError("--at goes with -e or --show")
    fields = ("session", "fuel", "canonical", "at", "head")
    value = args.get(name) or ""
    return _Call(
        **{field: args[field] for field in fields}, action=name, value=value
    )


def provenance(env: Mapping[str, str]) -> tuple[Who, str, str]:
    """Tell who enters an input, under which model and session.

    The actor is ``"agent"`` when ``$FPL_MODEL`` or ``$FPL_SESSION_ID``
    is set in *env*, else ``"operator"``.

    Args:
        env: The environment; only the two variables are read.

    Returns:
        The actor, the model and the session id; the last two are ``""``
        when unset.

    Raises:
        RefusedError: Either variable is not printable ASCII of at most
            256 characters.

    Examples:
        >>> provenance({})
        ('operator', '', '')
        >>> provenance({"FPL_MODEL": "m"})
        ('agent', 'm', '')
        >>> provenance({"FPL_MODEL": "é"})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        fpl.log.RefusedError: $FPL_MODEL is not ...
    """
    names = ("FPL_MODEL", "FPL_SESSION_ID")
    for name in names:
        if not ASCII.fullmatch(env.get(name, "")):
            raise RefusedError(
                f"${name} is not printable ASCII of at most 256 characters"
            )
    who: Who = "agent" if any(name in env for name in names) else "operator"
    return who, env.get("FPL_MODEL", ""), env.get("FPL_SESSION_ID", "")


@dataclass(frozen=True)
class Said:
    """What a call prints, and its exit status.

    ``entered`` is set when the call ran :func:`fpl.session.enter`;
    ``spent`` is then the input's own steps.
    """

    #: Text for stdout.
    out: str
    #: Lines for stderr.
    notes: tuple[str, ...]
    #: Exit status.
    code: int
    #: Steps the entered input took; None when nothing was entered.
    spent: int | None = None
    #: Whether the call entered an input.
    entered: bool = False


@dataclass(frozen=True)
class _Change:
    """An event to append, its bodies, and what the call says."""

    event: Event
    bodies: Mapping[Multihash, bytes]
    said: Said


def _parsed(text: str) -> Program | None:
    """Parse *text* alone, or return None when it does not parse."""
    try:
        return parse(text)
    except FplError:
        return None


def _canonical(text: str) -> str:
    """Print *text* as the printer does.

    Returns:
        The printed text, or ``""`` if *text* does not parse.
    """
    program = _parsed(text)
    return "" if program is None else render(program)


def _entered(
    call: _Call, log: Log, context: Context, at: Event | None
) -> _Change:
    """Enter the input after the program at *at*.

    Args:
        call: The call; its value is the input.
        log: The log holding *at* and its ancestors.
        context: What the new event records beside the input.
        at: The event to extend; None is the origin.

    Raises:
        RefusedError: The input is not UTF-8, which argv holds as lone
            surrogates.
    """
    try:
        call.value.encode()
    except UnicodeEncodeError:
        raise RefusedError("the input is not UTF-8") from None
    outcome = enter(log, call.value, context, at)
    shown = _canonical(call.value) if call.canonical else ""
    code = 0 if outcome.event.status == "ok" else 1
    return _Change(
        outcome.event,
        outcome.bodies,
        Said(
            shown + outcome.out,
            outcome.notes,
            code,
            outcome.spent,
            entered=True,
        ),
    )


def _rewound(
    call: _Call, log: Log, context: Context, _at: Event | None
) -> _Change:
    """Rewind the head to the event named by the call's value.

    Raises:
        RefusedError: No event answers to the name, or
            :func:`fpl.session.rewind` refuses the target.
    """
    return _Change(
        rewind(log, resolve(log, call.value), context), {}, Said("", (), 0)
    )


def _seq(
    seqs: Mapping[Multihash, str], ids: tuple[Multihash, ...], none: str
) -> str:
    """Return the seq of the first event in *ids*, else *none*."""
    return seqs[ids[0]] if ids else none


def _listed(log: Log, _at: Event | None) -> Said:
    """List the log, one line per event.

    A line holds seq, kind, status, the seq of its dep or 0, the seq of
    its link or ``-``, and the id.
    """
    seqs = {event.ident: str(event.seq) for event in log.events}
    rows = (
        f"{e.seq} {e.kind} {e.status} "
        f"{_seq(seqs, e.deps, '0')} {_seq(seqs, e.links, '-')}"
        f" ${e.ident.spelled()}\n"
        for e in log.events
    )
    return Said("".join(rows), (), 0)


def _shown(log: Log, at: Event | None) -> Said:
    """Show the program at *at*: its accepted inputs, joined."""
    return Said("".join(part.text for part in program(log, at)), (), 0)


#: The actions that only read a log, by name.
READERS: dict[str, Callable[[Log, Event | None], Said]] = {
    "log": _listed,
    "show": _shown,
}
#: The actions that append an event, by name.
WRITERS: dict[str, Callable[[_Call, Log, Context, Event | None], _Change]] = {
    "source": _entered,
    "rewind": _rewound,
}


def _changed(
    call: _Call, log: Log, env: Mapping[str, str], at: Event | None
) -> _Change:
    """Build the event the call would append at the head.

    Raises:
        RefusedError: ``--head`` names an event other than the head, or
            the action refuses.
    """
    if call.head is not None and resolve(log, call.head) is not log.head:
        raise RefusedError(f"head moved: the head is {len(log.events)}")
    context = Context(evaluator(), *provenance(env), call.fuel)
    return WRITERS[call.action](call, log, context, at)


def _read(call: _Call, log: Log, env: Mapping[str, str]) -> Said:
    """Carry out a call that appends nothing to *log*.

    The call is a reader, or an input evaluated as of ``--at``; the
    event the input would make is dropped.

    Raises:
        RefusedError: ``--at`` names no event, or the action refuses.
    """
    at = log.head if call.at is None else resolve(log, call.at)
    if call.action in READERS:
        return READERS[call.action](log, at)
    return _changed(call, log, env, at).said


def _reads(call: _Call) -> bool:
    """Tell whether the call appends nothing.

    That holds for a reader, and when ``--at`` is set.
    """
    return call.action in READERS or call.at is not None


def _kept(
    call: _Call, env: Mapping[str, str], memory: Log
) -> tuple[Said, Log]:
    """Carry out the call on a log held in memory.

    An append returns the log grown by the new event.

    Raises:
        RefusedError: The call is refused.
    """
    if _reads(call):
        return _read(call, memory, env), memory
    change = _changed(call, memory, env, memory.head)
    return change.said, memory.grown(change.event, change.bodies, memory.size)


def _said(
    call: _Call, env: Mapping[str, str], memory: Log
) -> tuple[Said, Log]:
    """Carry out the call and return what it says and the log after it.

    An append loads, checks and writes under the session's lock, and
    puts a ``HEAD <seq> $<id>`` note last.

    Raises:
        RefusedError: The log does not load, the call is refused, or the
            write is refused.
        OSError: The lock or a file of the session cannot be used.
    """
    if call.session is None:
        return _kept(call, env, memory)
    key = keyed(env)
    if _reads(call):
        log = load(call.session, key)
        return _read(call, log, env), log
    with locked(call.session):
        log = load(call.session, key)
        change = _changed(call, log, env, log.head)
        log = write(call.session, key, log, change.event, change.bodies)
    head = f"HEAD {change.event.seq} ${change.event.ident.spelled()}"
    return replace(change.said, notes=(*change.said.notes, head)), log


def once(argv: list[str], env: Mapping[str, str]) -> Said:
    """Carry out one call of *argv* without printing.

    *argv* must name an action: ``-e``, ``--rewind``, ``--log`` or
    ``--show``. The call runs on an empty log unless ``--session`` is
    given.

    Returns:
        What :func:`main` would print, as a :class:`Said`. A refusal
        comes back as the ``ERROR`` line that :func:`main` writes, with
        code 2, and bad argv as :data:`USAGE` in ``notes``.

    Raises:
        KeyError: *argv* names no action; the loop has no :class:`Said`.

    Examples:
        >>> once(["--show"], {}).code
        0
        >>> once(["--bogus"], {}).notes == (USAGE,)
        True
    """
    try:
        return _said(_call(argv), env, EMPTY)[0]
    except UsageError:
        return Said("", (USAGE,), 2)
    except (RefusedError, OSError) as error:
        return Said(f"ERROR: {error}\n", (), 2)


def pending(text: str) -> bool:
    """Tell whether the input goes on after its last line.

    It does when a pair is left open, a definition head or a line with a
    block is last, or the text ends in ``/`` (a directory head).

    Examples:
        >>> pending("f x [")
        True
        >>> pending("a = 1")
        False
    """
    try:
        last = parse(text).lines[-1]
    except FplError as error:
        return error.message.endswith("never closed")
    return head(last) or bool(last.block) or text.rstrip().endswith("/")


def _body(text: str) -> str:
    """Return the tabs the body of a definition takes, or ``""``.

    The result is one tab more than the head's own depth when *text*
    so far ends in a definition head, else ``""``. The head is the
    deepest last line of the parse of *text*. A head after the closer
    of a block comment on its line counts; a head whose body has begun
    does not. When *text* does not parse, it is inside an open pair
    (any other error has ended the input, see :func:`inputs`), where a
    line that reads as a head is only text, such as a line of a string.
    The depth is the count of leading tabs that :func:`fpl.lex.prelex`
    gives the line of code the head stands on, block comments removed.
    A head under a directory is one deeper, also with a block comment
    between the head and its body or before the head on its own line.
    """
    program = _parsed(text)
    if program is None:
        return ""
    line = program.lines[-1]
    while line.block:
        line = line.block[-1]
    if not head(line):
        return ""
    lexed = prelex(text)
    at = bisect_left(
        lexed.origin,
        Lines(text).starts[line.span.line - 1] + line.span.col - 1,
    )
    code_line = lexed.code[lexed.code.rfind("\n", 0, at) + 1 :]
    return "\t" * (len(code_line) - len(code_line.lstrip("\t")) + 1)


def _taken(text: str, line: str) -> str:
    """Return *line* as the input *text* so far takes it.

    A line at the margin right after a definition head is the body's
    first, one tab deeper. Any other line is returned as written.
    """
    return line if line[:1] in ("", " ", "\t") else _body(text) + line


#: What the loop writes at the margin beside the program: a result
#: line, a phrase bar (the pad and the kernel write their notes under
#: the same mark) and an ``ERROR`` line. :func:`written` knows them.
WRITTEN = (RESULT, BAR, "ERROR:")


def written(line: str) -> bool:
    r"""Tell whether *line* is the loop's, not the program's.

    The reader drops such a line, so a transcript pasted back is the
    program it came from: read(print(session)) = session. A line is the
    loop's when, after any tabs and spaces (the pad may indent what it
    writes) and before the pad's :data:`TERMINATOR`, it is one of
    :data:`WRITTEN` or starts with one and a space.

    Examples:
        >>> [written(l) for l in ("|- 2 : ...", "\t;;! -( 9 )-", "|-x")]
        [True, True, False]
    """
    bare = line.lstrip("\t ").removesuffix(TERMINATOR)
    return any(bare == mark or bare.startswith(mark + " ") for mark in WRITTEN)


def inputs(read: Callable[[bool], str | None]) -> Iterator[str]:
    r"""Group physical lines into inputs.

    An input ends at a blank line or at a line after which
    :func:`pending` is false; blank lines between inputs are skipped. A
    line the loop wrote (:func:`written`) counts as a blank line: it is
    dropped and ends the input; the pad's :data:`TERMINATOR` at the end
    of a line comes off. A line at the margin right after a
    definition head is taken as the body's first, as if it were written
    one tab deeper. A line that starts with a space or a tab is left as
    written.

    Args:
        read: Called with whether an input is in progress; returns the
            next line without its newline, or None at the end.

    Yields:
        The lines of one input, each ending in a newline.

    Examples:
        >>> lines = iter(["a = 1", "", "b = 2"])
        >>> list(inputs(lambda on: next(lines, None)))
        ['a = 1\n', 'b = 2\n']
    """
    text = ""
    while (line := read(bool(text))) is not None:
        line = "" if written(line) else line.removesuffix(TERMINATOR)
        line = _taken(text, line)
        blank = not line.strip()
        if not blank:
            text += line + "\n"
        if text and (blank or not pending(text)):
            yield text
            text = ""
    if text:
        yield text


def _plain(stdin: TextIO) -> Callable[[bool], str | None]:
    """Return a line reader over a stream that is not a terminal.

    It writes no prompts.
    """

    def read(_on: bool) -> str | None:
        line = stdin.readline()
        return line.removesuffix("\n") if line else None

    return read


def _typed(_on: bool) -> str | None:
    """Read a line from the terminal; None at end of input.

    The terminal is read under readline.

    No prompt is printed, so a session reads like a utop transcript.
    """
    try:
        return input("")
    except EOFError:
        return None


def _reader(stdin: TextIO) -> Callable[[bool], str | None]:
    """Return a line reader over *stdin*.

    At a terminal it goes through readline, where a tab inserts itself
    (an indent).
    """
    if not stdin.isatty():
        return _plain(stdin)
    readline = importlib.import_module("readline")
    readline.parse_and_bind("tab: self-insert")
    return _typed


#: Width in columns of a phrase bar, when its fields leave room.
BAR_WIDTH = 72

# Kakoune assistant_clippy; smoke / jonko tweak eyes and prop. Meatdog
# stays plain ASCII.
#: Face of the default assistant, in box-drawing characters.
CLIPPER_FACE: tuple[str, ...] = (
    " ╭──╮",
    " │  │",
    " @  @  ╭",
    " ││ ││ │",
    " ││ ││ ╯",
    " │╰─╯│",
    " ╰───╯",
)
#: Face of the smoking variant of the clipper.
CLIPPER_SMOKE_FACE: tuple[str, ...] = (
    " ╭──╮",
    " │  │",
    " @  @  ╭~~o",
    " ││ ││ │",
    " ││ ││ ╯",
    " │╰─╯│",
    " ╰───╯",
)
#: Face of the red-eyed variant of the clipper.
CLIPPER_JONKO_FACE: tuple[str, ...] = (
    " ╭──╮",
    " │  │",
    " O  O  ╭~",
    " ││ ││ │",
    " ││ ││ ╯",
    " │╰─╯│",
    " ╰───╯",
)
#: ASCII face of the dog assistant, in plain ASCII.
MEATDOG_FACE: tuple[str, ...] = (
    " /\\_/\\",
    "( o.o )",
    " > ^ <",
)

_HELLO_CLIPPER: tuple[str, ...] = (
    "FPL - Favourite Programming Language",
    "FPL - Final Programming Language",
    "Clipper: it looks like you're writing FPL.",
    "Don't get eaten by a grue.",
    "You are standing west of a white house.",
    "Dunnet awaits. Type carefully.",
)
_BYE_CLIPPER: tuple[str, ...] = (
    "Clipper: it looks like you're leaving FPL.",
    "Save your ice cream for Immortal Joe.",
    "See you west of the white house.",
)
_HELLO_SMOKE: tuple[str, ...] = (
    "Clipper on a break. Meter still runs.",
    "Talk to the Mayor; you are the Overseer.",
    "Chuck Norris compiles without a meter.",
)
_BYE_SMOKE: tuple[str, ...] = (
    "Stub it out. Come back with fuel.",
    "The Overseer will want a report.",
)
_HELLO_JONKO: tuple[str, ...] = (
    "Peut-etre francais?",
    "Don't get lost in the wasteland.",
    "Big red eyes. Small step budget.",
    "Immortal Joe wants your ice cream, Jack.",
)
_BYE_JONKO: tuple[str, ...] = (
    "Peut-etre a la prochaine.",
    "Don't get lost in the wasteland.",
    "Eyes still O. Fuel still finite.",
)
_HELLO_MEATDOG: tuple[str, ...] = (
    "Meatdog: kut, here is the news.",
    "Low on gas? Meatdog can give you a lift.",
    "Woof. The meter lies; Meatdog does not.",
)
_BYE_MEATDOG: tuple[str, ...] = (
    "Meatdog out. Sync your ice later.",
    "Woof. Don't get lost in the wasteland.",
    "Kut. Same time tomorrow?",
)
_HELLO_NONE: tuple[str, ...] = (
    "FPL - Favourite Programming Language",
    "Don't get eaten by a grue.",
    "Don't get lost in the wasteland.",
)
_BYE_NONE: tuple[str, ...] = (
    "Bye.",
    "Don't get lost in the wasteland.",
)


@dataclass(frozen=True)
class Assistant:
    """A TTY mascot for a session: an optional face and its lines.

    ``hello`` and ``bye`` are the lines it speaks. It is display only.
    """

    #: Name of the assistant.
    id: str
    #: Lines of the face; empty for none.
    face: tuple[str, ...]
    #: Lines it may greet with.
    hello: tuple[str, ...]
    #: Lines it may part with.
    bye: tuple[str, ...]


#: The assistants :func:`pick_assistant` chooses from.
ASSISTANTS: tuple[Assistant, ...] = (
    Assistant("clipper", CLIPPER_FACE, _HELLO_CLIPPER, _BYE_CLIPPER),
    Assistant("clipper-smoke", CLIPPER_SMOKE_FACE, _HELLO_SMOKE, _BYE_SMOKE),
    Assistant("clipper-jonko", CLIPPER_JONKO_FACE, _HELLO_JONKO, _BYE_JONKO),
    Assistant("meatdog", MEATDOG_FACE, _HELLO_MEATDOG, _BYE_MEATDOG),
    Assistant("none", (), _HELLO_NONE, _BYE_NONE),
)
# smoke + jonko ~14%; meatdog / none uncommon; clipper the rest
_ASSISTANT_WEIGHTS: tuple[int, ...] = (70, 7, 7, 10, 6)

#: The hello lines of all :data:`ASSISTANTS`, for :func:`splash_line`.
SPLASHES: tuple[str, ...] = tuple(line for a in ASSISTANTS for line in a.hello)


def pick_assistant(rng: random.Random | None = None) -> Assistant:
    """Pick the assistant for a session, weighted.

    The smoke and jonko variants are rare.

    Args:
        rng: The generator to choose with; the one in :mod:`random` when
            None.
    """
    choice = rng.choices if rng is not None else random.choices
    return choice(ASSISTANTS, weights=_ASSISTANT_WEIGHTS, k=1)[0]


def speak(
    assistant: Assistant,
    kind: Literal["hello", "bye"],
    *,
    pick: Callable[[Sequence[str]], str] | None = None,
) -> str:
    """Return the face (if any) plus one hello or bye line.

    Args:
        assistant: The assistant whose face and lines to use.
        kind: Which of the assistant's lines to choose from.
        pick: Chooses the line; :func:`random.choice` when None.

    Returns:
        The face lines, then the chosen line, each ending in a newline.

    Examples:
        >>> first = lambda lines: lines[0]
        >>> print(speak(ASSISTANTS[-1], "bye", pick=first), end="")
        Bye.
    """
    lines = assistant.hello if kind == "hello" else assistant.bye
    choose = pick if pick is not None else random.choice
    text = choose(lines)
    if not assistant.face:
        return text + "\n"
    return "\n".join(assistant.face) + "\n" + text + "\n"


def splash_line(
    pick: Callable[[Sequence[str]], str] | None = None,
) -> str:
    """Return one Minecraft-style MOTD line in ASCII.

    Prefer :func:`speak`, which also gives a face.

    Args:
        pick: Chooses the line; :func:`random.choice` when None.
    """
    choose = pick if pick is not None else random.choice
    return choose(SPLASHES)


@dataclass(frozen=True)
class Tty:
    """Clocks and chrome for a TTY transcript.

    With a :class:`Tty` the loop writes bars and typed result lines.
    """

    #: Wall clock for the time on a phrase bar.
    now: Callable[[], datetime] = datetime.now
    #: Monotonic timer for the ms of a phrase.
    timer: Callable[[], float] = time.perf_counter
    #: Gives the fingerprint shown as ``&`` on a bar; None shows none.
    state_id: Callable[[], int] | None = None
    #: Whether the loop greets, and says goodbye, with an assistant.
    splash: bool = False
    #: The session's assistant; None lets :func:`pick_assistant` pick.
    assistant: Assistant | None = None


def phrase_bar(  # noqa: PLR0913 -- bar fields are the chrome, not a bag type
    n: int,
    head: int,
    when: datetime,
    *,
    fuel: int | None = None,
    ms: float | None = None,
    state_id: int | None = None,
) -> str:
    """Build the DOC line between TTY phrases: a command bar.

    The line opens with ``;;!``, which makes a paste a DOC, and shows
    the local time, the phrase number and the head.

    Args:
        n: The phrase number.
        head: The sequence number of the log's head.
        when: The local time to show.
        fuel: The previous phrase's steps; None shows none.
        ms: The previous phrase's wall time in milliseconds; None shows
            none.
        state_id: A turn fingerprint, shown as ``&<decimal>``.

    Examples:
        >>> from datetime import datetime
        >>> at = datetime(2026, 1, 1, 9, 5, 3)
        >>> phrase_bar(1, 0, at)  # doctest: +ELLIPSIS
        ';;! -( 09:05:03 )-< command 1 >-...-{ head: 0 }-'
    """
    left = f"{BAR} -( {when.strftime('%H:%M:%S')} )-< command {n} >-"
    fields = [f"head: {head}"]
    if state_id is not None:
        fields.append(f"&{state_id}")
    if fuel is not None:
        fields.append(f"fuel: {fuel}")
    if ms is not None:
        fields.append(f"ms: {ms:.1f}")
    right = "{ " + "; ".join(fields) + " }-"
    pad = max(0, BAR_WIDTH - len(left) - len(right))
    return left + ("-" * pad) + right


def result_line(value: str, typ: str = "...") -> str:
    """Build one TTY result line.

    The line is a turnstile, *value*, and a type slot *typ*.

    The slot is ``...`` until the walker exposes a type; it is not FPL's
    ``?`` goal or ``_`` hole.

    Examples:
        >>> result_line("3")
        '|- 3 : ...'
    """
    return f"{RESULT} {value} : {typ}"


def _commanded(call: _Call, text: str) -> _Call:
    """Turn a ``:`` command in *text* into the call it makes.

    ``:log`` and ``:rewind`` name no state to evaluate at, so they clear
    ``at``.

    Raises:
        RefusedError: The command is not known.
    """
    match text.split():
        case [":show"]:
            return replace(call, action="show")
        case [":log"]:
            return replace(call, action="log", at=None)
        case [":rewind", event]:
            return replace(call, action="rewind", value=event, at=None)
        case [":canonical"]:
            return replace(
                call, action="canonical", canonical=not call.canonical
            )
        case _:
            raise RefusedError("unknown command")


def _told(said: Said, stdout: TextIO, stderr: TextIO) -> None:
    """Write the output to *stdout* and the notes to *stderr*.

    *stdout* is flushed for whoever drives the loop.
    """
    stdout.write(said.out)
    stdout.flush()
    stderr.write("".join(note + "\n" for note in said.notes))


def transcript(out: str) -> str:
    r"""Turn the lines of a successful TTY eval into result lines.

    Each line becomes a :func:`result_line`; blank lines stay blank. The
    form is a shell convention, not grammar.

    Examples:
        >>> transcript("1\n\n2\n")
        '|- 1 : ...\n\n|- 2 : ...\n'
    """
    parts: list[str] = []
    for line in out.splitlines(keepends=True):
        body = line.removesuffix("\n")
        parts.append(result_line(body) + line[len(body) :] if body else line)
    return "".join(parts)


def _seen(call: _Call, log: Log) -> _Call:
    """Check the call against the head of *log*.

    A call that evaluates as of ``--at`` is returned as it is.
    """
    return (
        call
        if call.at is not None
        else replace(call, head=str(len(log.events)))
    )


def _bare(lines: tuple[Line, ...]) -> Iterator[str]:
    """Yield a NOTE for each definition in *lines* that has no body.

    The definitions in the blocks under *lines* are included. An empty
    line where the body was meant would otherwise pass without a word.
    The note says only that the written body is empty; what the word
    then does belongs to the desugaring (a head group makes it a match),
    which this parse does not see.
    """
    for line in lines:
        name = plain(line.frames[0].cells[0].items[0]) if head(line) else None
        if name is not None and not any(map(code, line.block)):
            at = f"{line.span.line}:{line.span.col}"
            yield f"NOTE {at} {name} has an empty body"
        yield from _bare(line.block)


def _flagged(text: str, said: Said) -> Said:
    """Put a NOTE first in *said* for each bodiless definition."""
    program = _parsed(text)
    return (
        said
        if program is None
        else replace(said, notes=(*_bare(program.lines), *said.notes))
    )


def _turn(  # noqa: PLR0913 -- call/env/log/streams plus optional Tty
    call: _Call,
    text: str,
    env: Mapping[str, str],
    log: Log,
    streams: tuple[TextIO, TextIO],
    *,
    tty: Tty | None = None,
) -> tuple[_Call, Log, int | None, float | None]:
    """Carry out one input or one command, and tell the result.

    An input is entered as ``-e`` enters it. On a TTY, a successful
    source eval writes its stdout lines as ``|- value : ...``. A refusal
    is told, and the head as it now stands is adopted.

    Args:
        call: The call this turn starts from.
        text: An input, or a command that starts with ``:``.
        env: The environment, for provenance and the key.
        log: The log held in memory when the call has no session.
        streams: The stdout and stderr to write to.
        tty: Set on a TTY, which timestamps the turn and prints results.

    Returns:
        The call and log the next turn starts from; on a TTY, the steps
        and the wall ms of an entered source, else None for both.

    Raises:
        OSError: The session file cannot be used.
    """
    stdout, stderr = streams
    started = tty.timer() if tty is not None else 0.0
    try:
        this = (
            _commanded(call, text)
            if text.startswith(":")
            else replace(call, action="source", value=text)
        )
        if this.action == "canonical":
            return this, log, None, None
        said, log = _said(this, env, log)
    except RefusedError as error:
        _told(Said(f"ERROR: {error}\n", (), 2), stdout, stderr)
        log = _loaded(call, env, log)
        return _seen(call, log), log, None, None
    said = _transcribed(this, _flagged(text, said), tty)
    _told(said, stdout, stderr)
    if tty is not None and said.entered:
        return (
            _seen(call, log),
            log,
            said.spent,
            (tty.timer() - started) * 1000.0,
        )
    return _seen(call, log), log, None, None


def _transcribed(this: _Call, said: Said, tty: Tty | None) -> Said:
    """Return what a turn tells.

    On a TTY, a source that ran shows its stdout lines as ``|- value :
    ...``; anything else is told as it was said.
    """
    if tty is None or this.action != "source" or said.code != 0:
        return said
    return replace(said, out=transcript(said.out))


def _loaded(call: _Call, env: Mapping[str, str], memory: Log) -> Log:
    """Return the session's log as it stands, else the one in *memory*.

    Raises:
        RefusedError: The session's log does not load.
        OSError: The session file cannot be read.
    """
    return memory if call.session is None else load(call.session, keyed(env))


def _looped(
    call: _Call,
    read: Callable[[bool], str | None],
    streams: tuple[TextIO, TextIO],
    env: Mapping[str, str],
    *,
    tty: Tty | None = None,
) -> int:
    """Run inputs and commands until the end or ``:quit``; return 0.

    Each is checked against the head last seen: ``--head`` at first,
    else the head at start. A TTY writes ``;;!`` phrase bars and ``|-
    value : ...`` result lines, and a bar may name the previous phrase's
    fuel and wall ms.

    Args:
        call: The call whose options the loop runs under.
        read: The line reader given to :func:`inputs`.
        streams: The stdout and stderr to write to.
        env: The environment, for provenance and the key.
        tty: Set on a TTY, which gets bars, results and an assistant.

    Raises:
        RefusedError: The log does not load at start.
        OSError: The session file cannot be used.
    """
    log = _loaded(call, env, EMPTY)
    if call.head is None:
        call = _seen(call, log)
    stdout, _stderr = streams
    session: Assistant | None = None
    if tty is not None and tty.splash:
        session = (
            tty.assistant if tty.assistant is not None else pick_assistant()
        )
        stdout.write(speak(session, "hello"))
        stdout.flush()
    phrase = 0
    need_bar = True
    last_fuel: int | None = None
    last_ms: float | None = None

    def framed(on: bool) -> str | None:
        nonlocal phrase, need_bar, last_fuel, last_ms
        if tty is not None and not on and need_bar:
            phrase += 1
            identity = None if tty.state_id is None else tty.state_id()
            bar = phrase_bar(
                phrase,
                len(log.events),
                tty.now(),
                fuel=last_fuel,
                ms=last_ms,
                state_id=identity,
            )
            stdout.write(bar + "\n")
            stdout.flush()
            need_bar = False
            last_fuel, last_ms = None, None
        return read(on)

    for text in itertools.takewhile(
        lambda t: t.split() != [":quit"], inputs(framed)
    ):
        call, log, last_fuel, last_ms = _turn(
            call, text, env, log, streams, tty=tty
        )
        need_bar = True
    if session is not None:
        stdout.write(speak(session, "bye"))
        stdout.flush()
    return 0


def main(  # noqa: PLR0913 -- argv and stdio/env plus optional Tty
    argv: list[str],
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    env: Mapping[str, str] = os.environ,
    *,
    tty: Tty | None = None,
) -> int:
    """Carry out *argv* and return the exit status.

    The output, or one ``ERROR`` line, goes to *stdout*; goals, the
    caret under an error, inputs changed and the new head go to
    *stderr*, all after any append is durable. An :exc:`OSError` is a
    refusal: its line names the path the system refused. Bad argv writes
    :data:`USAGE` to *stderr* and returns 2.

    Args:
        argv: The command line without the program name; with no action
            it starts the read-eval loop.
        stdin: Read by the loop only.
        stdout: Receives the output.
        stderr: Receives the notes.
        env: Where the model, session id and key location come from.
        tty: Clocks and chrome for the loop, for a driven transcript
            (tests); when None and *stdin* is a terminal, one is built.

    Returns:
        The exit status described in the module docstring; 0 for the
        loop.
    """
    try:
        call = _call(argv)
        if call.action == "loop":
            display = tty
            if display is None and stdin.isatty():
                display = Tty(
                    state_id=lambda: random.getrandbits(64),
                    splash=True,
                )
            return _looped(
                call,
                _reader(stdin),
                (stdout, stderr),
                env,
                tty=display,
            )
        said = _said(call, env, EMPTY)[0]
    except UsageError:
        stderr.write(USAGE + "\n")
        return 2
    except (RefusedError, OSError) as error:
        stdout.write(f"ERROR: {error}\n")
        return 2
    _told(said, stdout, stderr)
    return said.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

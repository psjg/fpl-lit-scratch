"""
`python -m fpl.repl`: one input entered at a session's head or evaluated
as of an event, a rewind, the log listed, or the program at an event
shown; with none of these, inputs read one after another, each as its
own -e. Without --session the log is empty and held in memory, so one
input runs as its file does. An append is checked against --head and
made durable under the session's lock before anything is printed. Exit 0
ok, 1 the input failed, 2 argv not taken or a refusal, a path the system
refuses included, with nothing written but a lock.
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

USAGE = (
    "usage: python -m fpl.repl [--session FILE] [--fuel N] "
    "[--canonical] [--at EVENT]"
    " [--head EVENT] [-e SOURCE | --rewind EVENT | --log | --show]"
)
ACTIONS = ("source", "rewind", "log", "show")
NUMERAL = re.compile(r"0|[1-9][0-9]*")
EMPTY = Log((), {}, 0)


class UsageError(Exception):
    """
    argv the command line does not take.
    """


class _Parser(ArgumentParser):
    """
    An ArgumentParser that raises where it would print and exit.
    """

    @override
    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def _fuel(text: str) -> int:
    """
    A step budget: a decimal numeral below 2^64, as the log records it.
    """
    if not NUMERAL.fullmatch(text) or int(text) >= U64:
        raise ValueError(text)
    return int(text)


def _sourced(argv: list[str]) -> list[str]:
    """
    argv with a source that opens with - joined to its -e, as
    -e<source>, which argparse would otherwise take for an option.
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
    """
    argv taken: the options, and the one action with its value ("" for a
    flag).
    """

    session: Path | None
    fuel: int
    canonical: bool
    at: str | None
    head: str | None
    action: str
    value: str


def _call(argv: list[str]) -> _Call:
    """
    argv as a call; with no action, the loop. Refused (UsageError):
    anything argparse refuses, two actions, and --at beside --head,
    --rewind or --log, which name no state to evaluate at.
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
    """
    Who enters an input, under which model and session: an agent when
    $FPL_MODEL or $FPL_SESSION_ID is set, else an operator. Refused
    (RefusedError): either not printable ASCII of at most 256
    characters.
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
class _Said:
    """
    What a call prints, and its exit status. `entered` is set when the
    call ran `enter`; `spent` is the input's own steps when it did.
    """

    out: str
    notes: tuple[str, ...]
    code: int
    spent: int | None = None
    entered: bool = False


@dataclass(frozen=True)
class _Change:
    """
    An event to append, the bodies it names, and what the call prints
    once it is.
    """

    event: Event
    bodies: Mapping[Multihash, bytes]
    said: _Said


def _parsed(text: str) -> Program | None:
    """
    The input as a program, or None when it does not parse alone.
    """
    try:
        return parse(text)
    except FplError:
        return None


def _canonical(text: str) -> str:
    """
    The input as the printer writes it, or nothing when it does not
    parse alone.
    """
    program = _parsed(text)
    return "" if program is None else render(program)


def _entered(
    call: _Call, log: Log, context: Context, at: Event | None
) -> _Change:
    """
    The input after the program at `at`. Refused: text that is not
    UTF-8, which argv holds as lone surrogates.
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
        _Said(
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
    """
    A rewind of the head to the event named.
    """
    return _Change(
        rewind(log, resolve(log, call.value), context), {}, _Said("", (), 0)
    )


def _seq(
    seqs: Mapping[Multihash, str], ids: tuple[Multihash, ...], none: str
) -> str:
    """
    The seq of the first event named, or `none`.
    """
    return seqs[ids[0]] if ids else none


def _listed(log: Log, _at: Event | None) -> _Said:
    """
    A line an event: seq, kind, status, the seq of its dep or 0, of its
    link or -, id.
    """
    seqs = {event.ident: str(event.seq) for event in log.events}
    rows = (
        f"{e.seq} {e.kind} {e.status} "
        f"{_seq(seqs, e.deps, '0')} {_seq(seqs, e.links, '-')}"
        f" ${e.ident.spelled()}\n"
        for e in log.events
    )
    return _Said("".join(rows), (), 0)


def _shown(log: Log, at: Event | None) -> _Said:
    """
    The program at `at`: its accepted inputs, joined.
    """
    return _Said("".join(part.text for part in program(log, at)), (), 0)


READERS: dict[str, Callable[[Log, Event | None], _Said]] = {
    "log": _listed,
    "show": _shown,
}
WRITERS: dict[str, Callable[[_Call, Log, Context, Event | None], _Change]] = {
    "source": _entered,
    "rewind": _rewound,
}


def _changed(
    call: _Call, log: Log, env: Mapping[str, str], at: Event | None
) -> _Change:
    """
    The event the call would append at the head. Refused: a --head that
    is not it.
    """
    if call.head is not None and resolve(log, call.head) is not log.head:
        raise RefusedError(f"head moved: the head is {len(log.events)}")
    context = Context(evaluator(), *provenance(env), call.fuel)
    return WRITERS[call.action](call, log, context, at)


def _read(call: _Call, log: Log, env: Mapping[str, str]) -> _Said:
    """
    A call that appends nothing: a reader, or an input evaluated as of
    --at, or at the head of a log held in memory.
    """
    at = log.head if call.at is None else resolve(log, call.at)
    if call.action in READERS:
        return READERS[call.action](log, at)
    return _changed(call, log, env, at).said


def _reads(call: _Call) -> bool:
    """
    The call appends nothing: a reader, or an input evaluated as of
    --at.
    """
    return call.action in READERS or call.at is not None


def _kept(
    call: _Call, env: Mapping[str, str], memory: Log
) -> tuple[_Said, Log]:
    """
    The call on a log held in memory; an append grows it and names no
    head.
    """
    if _reads(call):
        return _read(call, memory, env), memory
    change = _changed(call, memory, env, memory.head)
    return change.said, memory.grown(change.event, change.bodies, memory.size)


def _said(
    call: _Call, env: Mapping[str, str], memory: Log
) -> tuple[_Said, Log]:
    """
    The call carried out, and the log as it stands after it. An append
    loads, checks and writes under the lock, and names the new head
    last.
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


def pending(text: str) -> bool:
    """
    The input goes on: a pair left open, a definition head or a line
    with a block last, or a trailing / (a directory head).
    """
    try:
        last = parse(text).lines[-1]
    except FplError as error:
        return error.message.endswith("never closed")
    return head(last) or bool(last.block) or text.rstrip().endswith("/")


def _body(text: str) -> str:
    """
    The tabs the body of a definition takes if the input so far ends in
    its head, else nothing: one more than the head has. The head is
    judged in the parse of the whole input, down the last line's block
    to the deepest line last written: so a head after the closer of a
    block comment on its line counts, a head whose body has begun does
    not, and an input that does not parse so far is inside a pair left
    open (any other error has ended it, see `inputs`), where a line that
    reads as a head is only text, such as a line of a string. The tabs
    are the depth the pre-lexer gives the head's line, the tabs that
    lead the line of code it stands on once the block comments are gone:
    so a head under a directory is one deeper still, also when a block
    comment stands between the head and its body, or before the head on
    its own line.
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
    """
    A line as the input so far takes it: a line at the margin right
    after a definition head is the body's first, one tab deeper; any
    other line, as it was written.
    """
    return line if line[:1] in ("", " ", "\t") else _body(text) + line


def inputs(read: Callable[[bool], str | None]) -> Iterator[str]:
    """
    Physical lines, read until None, grouped into inputs: an input ends
    at a blank line or at a line after which it is not pending, and
    blank lines between inputs are skipped. A line at the margin right
    after a definition head is taken as the body's first, as if it were
    written one tab deeper; one that starts with a space or a tab is
    left as written, so the tabs-only rule of a file holds. Each input
    is its lines, each ending in a newline; `read` is told whether one
    goes on.
    """
    text = ""
    while (line := read(bool(text))) is not None:
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
    """
    Lines from a stream that is not a terminal, without prompts.
    """

    def read(_on: bool) -> str | None:
        line = stdin.readline()
        return line.removesuffix("\n") if line else None

    return read


def _typed(_on: bool) -> str | None:
    """
    A line from the terminal under readline, with no prompt text so the
    session reads as a utop-style transcript.
    """
    try:
        return input("")
    except EOFError:
        return None


def _reader(stdin: TextIO) -> Callable[[bool], str | None]:
    """
    The terminal through readline, where a tab inserts itself (an
    indent), or the stream.
    """
    if not stdin.isatty():
        return _plain(stdin)
    readline = importlib.import_module("readline")
    readline.parse_and_bind("tab: self-insert")
    return _typed


BAR_WIDTH = 72

# Kakoune assistant_clippy; smoke / jonko tweak eyes and prop. Meatdog
# stays plain ASCII.
CLIPPER_FACE: tuple[str, ...] = (
    " ╭──╮",
    " │  │",
    " @  @  ╭",
    " ││ ││ │",
    " ││ ││ ╯",
    " │╰─╯│",
    " ╰───╯",
)
CLIPPER_SMOKE_FACE: tuple[str, ...] = (
    " ╭──╮",
    " │  │",
    " @  @  ╭~~o",
    " ││ ││ │",
    " ││ ││ ╯",
    " │╰─╯│",
    " ╰───╯",
)
CLIPPER_JONKO_FACE: tuple[str, ...] = (
    " ╭──╮",
    " │  │",
    " O  O  ╭~",
    " ││ ││ │",
    " ││ ││ ╯",
    " │╰─╯│",
    " ╰───╯",
)
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
    """
    One TTY mascot for a REPL session: optional ASCII face and the
    hello / bye line pools it speaks (chrome only, offline for now).
    """

    id: str
    face: tuple[str, ...]
    hello: tuple[str, ...]
    bye: tuple[str, ...]


ASSISTANTS: tuple[Assistant, ...] = (
    Assistant("clipper", CLIPPER_FACE, _HELLO_CLIPPER, _BYE_CLIPPER),
    Assistant("clipper-smoke", CLIPPER_SMOKE_FACE, _HELLO_SMOKE, _BYE_SMOKE),
    Assistant("clipper-jonko", CLIPPER_JONKO_FACE, _HELLO_JONKO, _BYE_JONKO),
    Assistant("meatdog", MEATDOG_FACE, _HELLO_MEATDOG, _BYE_MEATDOG),
    Assistant("none", (), _HELLO_NONE, _BYE_NONE),
)
# smoke + jonko ~14%; meatdog / none uncommon; clipper the rest
_ASSISTANT_WEIGHTS: tuple[int, ...] = (70, 7, 7, 10, 6)

SPLASHES: tuple[str, ...] = tuple(line for a in ASSISTANTS for line in a.hello)


def pick_assistant(rng: random.Random | None = None) -> Assistant:
    """
    One assistant for a session, weighted (smoke / jonko rare).
    """
    choice = rng.choices if rng is not None else random.choices
    return choice(ASSISTANTS, weights=_ASSISTANT_WEIGHTS, k=1)[0]


def speak(
    assistant: Assistant,
    kind: Literal["hello", "bye"],
    *,
    pick: Callable[[Sequence[str]], str] | None = None,
) -> str:
    """
    Face (if any) plus one line from the hello or bye pool.
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
    """
    One Minecraft-style MOTD line (ASCII); prefer `speak` for faces.
    """
    choose = pick if pick is not None else random.choice
    return choose(SPLASHES)


@dataclass(frozen=True)
class Tty:
    """
    Clocks for a TTY transcript: wall date for phrase bars, and a
    monotonic timer for per-phrase ms. Presence of a `Tty` means the
    loop writes bars and typed result lines. Optional `state_id` fills
    `&` on each bar; `splash` greets (and later byes) with one
    session `assistant`, picked if none is injected.
    """

    now: Callable[[], datetime] = datetime.now
    timer: Callable[[], float] = time.perf_counter
    state_id: Callable[[], int] | None = None
    splash: bool = False
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
    """
    ASCII DOC line between TTY phrases: `;;!` so paste is a DOC, then a
    utop-shaped command bar with local time, phrase number, and head.
    Optional `fuel` and `ms` are the previous phrase's steps and wall
    time; optional `state_id` is a turn fingerprint as `&<decimal>`.
    """
    left = f";;! -( {when.strftime('%H:%M:%S')} )-< command {n} >-"
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
    """
    One TTY result line: turnstile, value, and a type slot (`...` until
    the walker exposes a type; not FPL's `?` goal or `_` hole).
    """
    return f"|- {value} : {typ}"


def _commanded(call: _Call, text: str) -> _Call:
    """
    A : command as the call it makes; :log and :rewind name no state to
    evaluate at. Refused: a command not known.
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


def _told(said: _Said, stdout: TextIO, stderr: TextIO) -> None:
    """
    The output to stdout, flushed for whoever drives the loop, the notes
    to stderr.
    """
    stdout.write(said.out)
    stdout.flush()
    stderr.write("".join(note + "\n" for note in said.notes))


def transcript(out: str) -> str:
    """
    Each non-empty line of a successful TTY eval as `|- value : ...`
    (shell convention, not grammar). Blank lines stay blank.
    """
    if not out:
        return out
    parts: list[str] = []
    for line in out.splitlines(keepends=True):
        if line.endswith("\n"):
            body, nl = line[:-1], "\n"
        else:
            body, nl = line, ""
        parts.append(result_line(body) + nl if body else line)
    return "".join(parts)


def _seen(call: _Call, log: Log) -> _Call:
    """
    The call checked against the head of `log`, unless it evaluates as
    of --at.
    """
    return (
        call
        if call.at is not None
        else replace(call, head=str(len(log.events)))
    )


def _bare(lines: tuple[Line, ...]) -> Iterator[str]:
    """
    A NOTE for each definition among the lines, and the blocks under
    them, whose head has no code under it, which an empty line where the
    body was meant would otherwise leave without a word. It says only
    that the written body is empty: what the word then does is the
    desugaring's (a head group makes it a match), which this parse does
    not see.
    """
    for line in lines:
        name = plain(line.frames[0].cells[0].items[0]) if head(line) else None
        if name is not None and not any(map(code, line.block)):
            at = f"{line.span.line}:{line.span.col}"
            yield f"NOTE {at} {name} has an empty body"
        yield from _bare(line.block)


def _flagged(text: str, said: _Said) -> _Said:
    """
    What an input said, with a NOTE first for each definition in it that
    has no body.
    """
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
    """
    One input, entered as -e enters it, or one command, carried out and
    told; the call and log the next one starts from, and on a TTY the
    steps and wall ms of an entered source (else None). A refusal is
    told, and the head as it now stands adopted. On a TTY loop, a
    successful source eval's stdout lines are written as
    `|- value : ...`.
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
        _told(_Said(f"ERROR: {error}\n", (), 2), stdout, stderr)
        log = _loaded(call, env, log)
        return _seen(call, log), log, None, None
    said = _flagged(text, said)
    if (
        tty is not None
        and this.action == "source"
        and said.code == 0
        and said.out
    ):
        said = replace(said, out=transcript(said.out))
    _told(said, stdout, stderr)
    if tty is not None and said.entered:
        return (
            _seen(call, log),
            log,
            said.spent,
            (tty.timer() - started) * 1000.0,
        )
    return _seen(call, log), log, None, None


def _loaded(call: _Call, env: Mapping[str, str], memory: Log) -> Log:
    """
    The session's log as it stands, or the log held in memory.
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
    """
    Inputs and commands until the end or :quit, each checked against the
    head last seen: --head at first, else the head at start. Refused: a
    log that does not load at start. A TTY writes `;;!` phrase bars and
    `|- value : ...` result lines; a bar may name the previous phrase's
    fuel and wall ms.
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
    """
    Carry out argv; the output, or one ERROR line, to stdout; goals, the
    caret under an error, inputs changed and the new head to stderr, all
    after any append is durable. An OSError is a refusal: its line names
    the path the system refused. `tty` supplies clocks when the loop is
    driven as a transcript (tests); at a real terminal it is built from
    `stdin.isatty()`.
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

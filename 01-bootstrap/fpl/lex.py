# Tangled from 01.02-pass/01.02.01-lex.md; edit that, not this.
"""The pre-lexer: what the grammar cannot count, counted first."""

import re
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fpl.ast_surface import Kind
from fpl.errors import FplError, Span

PAIRS = {"“": "”", "「": "」", "⟦": "⟧"}
BRACKETS = {"[": "]", "(": ")", "⟨": "⟩", "{": "}"}
CLOSERS = {close: opener for opener, close in (PAIRS | BRACKETS).items()}
PLACEHOLDER = "¶"
SPECIAL = re.compile(r"[“「⟦”」⟧;⍝]")
LINE_COMMENT = re.compile(r"(;+|⍝)[^\n]*")
MODS = "\u00b4`\u00a8\u02dc\u207c\u02d9"
SHAPE = re.compile(rf"(->|→|\$|#|&|\.\./|\.\.)?([^{MODS}]*?)([{MODS}]*)")
NUMBER = re.compile(r"-?(\d+(\.\d+)?|∞|π)")


class Lines:
    """Offsets into a source as an editor's 1-based line and column."""

    def __init__(self, source: str) -> None:
        self.starts = [0] + [
            n + 1 for n, char in enumerate(source) if char == "\n"
        ]

    def span(self, offset: int) -> Span:
        """The line and column of a source offset."""
        line = bisect_right(self.starts, offset)
        return Span(line, offset - self.starts[line - 1] + 1)


@dataclass(frozen=True)
class Stashed:
    """A string's interior, [start, end) in the source."""

    kind: Literal["str", "raw"]
    start: int
    end: int
    depth: int


@dataclass(frozen=True)
class Prelexed:
    """Code for the grammar, each character's origin, and the stash."""

    code: str
    origin: tuple[int, ...]
    stash: dict[int, Stashed]


def counted(text: str, at: int, close: str, end: int) -> int | None:
    """The offset past the closer balancing text[at], or None."""
    opener, depth, j = text[at], 1, at + 1
    while j < end and depth:
        depth += (text[j] == opener) - (text[j] == close)
        j += 1
    return None if depth else j


class _Code:
    """The code being written, each character with its source offset."""

    def __init__(self) -> None:
        self.chars: list[str] = []
        self.origin: list[int] = []
        self.stash: dict[int, Stashed] = {}

    def put(self, text: str, at: int, verbatim: bool = True) -> None:
        """Append text from source offset `at`."""
        self.chars.extend(text)
        self.origin.extend(
            at + k if verbatim else at for k in range(len(text))
        )

    def at_line_start(self) -> bool:
        """Nothing but tabs written since the last newline."""
        for char in reversed(self.chars):
            if char != "\t":
                return char == "\n"
        return True


def _pair(source: str, at: int, end: int, code: _Code) -> int:
    """Write the pair opening at `at`; return the offset after it."""
    opener = source[at]
    after = counted(source, at, PAIRS[opener], end)
    if after is None:
        raise FplError(Lines(source).span(at), f"{opener} never closed")
    if opener == "⟦":
        if code.at_line_start():
            return (
                len(source[after:end])
                - len(source[after:end].lstrip(" "))
                + after
            )
        code.put(" ", at)
        return after
    if code.chars and code.chars[-1] not in " \t\n":
        code.put(" ", at)
    line = source.rfind("\n", 0, at) + 1
    depth = len(source[line:at]) - len(source[line:at].lstrip("\t"))
    code.stash[len(code.chars)] = Stashed(
        "str" if opener == "“" else "raw", at + 1, after - 1, depth
    )
    code.put(PLACEHOLDER + " ", at, verbatim=False)
    return after


def _special(source: str, at: int, end: int, code: _Code) -> int:
    """Write what source[at] starts; return where copying resumes."""
    char = source[at]
    if char in PAIRS:
        return _pair(source, at, end, code)
    if char in CLOSERS:
        raise FplError(Lines(source).span(at), f"{char} closes nothing")
    newline = source.find("\n", at, end)
    after = end if newline < 0 else newline
    code.put(source[at:after], at)
    return after


def pairs(
    source: str,
    start: int = 0,
    end: int | None = None,
    special: re.Pattern[str] = SPECIAL,
) -> Prelexed:
    """Stash strings and drop block comments of source[start:end]."""
    stop = len(source) if end is None else end
    code, at = _Code(), start
    while at < stop:
        found = special.search(source, at, stop)
        upto = found.start() if found else stop
        code.put(source[at:upto], at)
        at = _special(source, upto, stop, code) if found else stop
    code.put("\n", stop)
    return Prelexed("".join(code.chars), (*code.origin, stop), code.stash)


def prelex(source: str, start: int = 0, end: int | None = None) -> Prelexed:
    """Pre-lex source[start:end] to code the grammar reads."""
    lexed = pairs(source, start, end)
    strict(source, lexed.code, lexed.origin)
    return lexed


class _RefusalError(Exception):
    """A refusal at a code offset, before it is placed in the source."""

    def __init__(self, offset: int, message: str) -> None:
        super().__init__(message)
        self.offset = offset
        self.message = message


def _brackets(
    line: str, base: int, depth: int, open_: list[tuple[str, int, int]]
) -> None:
    """Track one line's brackets on the stack of open ones."""
    body = LINE_COMMENT.split(line, maxsplit=1)[0]
    for n, char in enumerate(body):
        if char in BRACKETS:
            open_.append((char, base + n, depth))
        elif char in CLOSERS and not open_:
            raise _RefusalError(base + n, f"{char} closes nothing")
        elif char in CLOSERS and open_[-1][0] != CLOSERS[char]:
            raise _RefusalError(
                base + n, f"{char} does not close {open_[-1][0]}"
            )
        elif char in CLOSERS:
            open_.pop()


def _lines(code: str, line_of: Callable[[int], int]) -> None:
    """Refuse spaces that indent, and a dedent past an open bracket."""
    open_: list[tuple[str, int, int]] = []
    base = 0
    for line in code.split("\n"):
        depth = len(line) - len(line.lstrip("\t"))
        if not open_ and line[depth : depth + 1] == " ":
            raise _RefusalError(base + depth, "indentation must be tabs")
        if open_ and line.strip() and depth < open_[-1][2]:
            opener, opened, _ = open_[-1]
            message = (
                f"dedent below line {line_of(opened)}, "
                f"but its {opener} is still open"
            )
            raise _RefusalError(base + depth, message)
        _brackets(line, base, depth, open_)
        base += len(line) + 1
    if open_:
        raise _RefusalError(open_[-1][1], f"{open_[-1][0]} never closed")


def strict(source: str, code: str, origin: tuple[int, ...]) -> None:
    """Hold the code to strict indentation, refusing in the source."""
    lines = Lines(source)
    try:
        _lines(code, lambda offset: lines.span(origin[offset]).line)
    except _RefusalError as refusal:
        raise FplError(
            lines.span(origin[refusal.offset]), refusal.message
        ) from None


def shape(token: str) -> tuple[str, Kind, tuple[str, ...], str] | None:
    """A token's prefix, kind, body and modifiers, or None."""
    match = SHAPE.fullmatch(token)
    if match is None:
        return None
    prefix, body, mods = match.group(1) or "", match.group(2), match.group(3)
    kind: Kind = (
        "modifier"
        if not body
        else "number"
        if NUMBER.fullmatch(body)
        else "path"
        if "/" in body
        else "name"
    )
    return (
        prefix,
        kind,
        tuple(body.split("/")) if kind == "path" else (body,),
        mods,
    )

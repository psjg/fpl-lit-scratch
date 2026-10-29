"""Count what the grammar cannot, before Lark reads the text.

:func:`prelex` counts each pair (strings “ ” and 「 」, block comments
⟦ ⟧) by its own pair only. A string becomes one placeholder with its
interior left in the source, and a block comment becomes a space or
nothing. It then refuses indentation with spaces and a dedent below the
line of a bracket still open. Every character of the :class:`Prelexed`
code keeps its source offset. After lexing, :func:`shape` reads a
token's sigil, kind and modifiers.
"""

import re
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fpl.ast_surface import Kind
from fpl.errors import (
    FplError,
    MismatchedError,
    Span,
    StrayDedentError,
    TabsError,
    UnclosedError,
    UnopenedError,
)

from pathlib import Path

from lark import Lark

from fpl.arrow import Pass

#: Opener to closer of each pair: string, raw string and block comment.
PAIRS = {"“": "”", "「": "」", "⟦": "⟧"}
#: Opener to closer of each bracket.
BRACKETS = {"[": "]", "(": ")", "⟨": "⟩", "{": "}"}
#: Closer to opener, for the pairs of :data:`PAIRS` and the brackets of
#: :data:`BRACKETS`.
CLOSERS = {close: opener for opener, close in (PAIRS | BRACKETS).items()}
#: Stands for a whole string in the code the grammar reads.
PLACEHOLDER = "¶"
#: The characters :func:`pairs` stops at: the openers and closers of the
#: pairs, and the marks ``;`` and ``⍝`` of a line comment.
SPECIAL = re.compile(r"[“「⟦”」⟧;⍝]")
#: A line comment: a run of ``;`` or one ``⍝``, up to the end of the
#: line.
LINE_COMMENT = re.compile(r"(;+|⍝)[^\n]*")
#: The modifier characters that may end a token.
MODS = "\u00b4`\u00a8\u02dc\u207c\u02d9"
#: A token as sigil, body and trailing :data:`MODS`, the groups
#: :func:`shape` reads.
SHAPE = re.compile(rf"(->|→|\$|#|&|\.\./|\.\.)?([^{MODS}]*?)([{MODS}]*)")
#: A number body: an optional minus, then digits with an optional
#: fraction, ``∞`` or ``π``.
NUMBER = re.compile(r"-?(\d+(\.\d+)?|∞|π)")


class Lines:
    """Turn offsets into a source into lines and columns."""

    def __init__(self, source: str) -> None:
        """Index the lines of *source*."""
        #: Offset at which each line starts, the first line included.
        self.starts = [0] + [
            n + 1 for n, char in enumerate(source) if char == "\n"
        ]

    def span(self, offset: int) -> Span:
        r"""Return the 1-based line and column of a source offset.

        Args:
            offset: Position in the source; the end of the source is
                just past its last line.

        Examples:
            >>> Lines("ab\ncd").span(3)
            Span(line=2, col=1)
        """
        line = bisect_right(self.starts, offset)
        return Span(line, offset - self.starts[line - 1] + 1)


@dataclass(frozen=True)
class Stashed:
    """A string's interior in the source, the range ``[start, end)``."""

    #: ``str`` for “ ”, which interpolates ⟨ ⟩; ``raw`` for 「 」, which
    #: does not.
    kind: Literal["str", "raw"]
    #: Source offset of the first interior character.
    start: int
    #: Source offset just past the last interior character.
    end: int
    #: Tabs before the line the string opens on; its continuation lines
    #: drop that many (S26).
    depth: int


@dataclass(frozen=True)
class Prelexed:
    """The output of :func:`prelex`: grammar code with its origins."""

    #: The code the grammar reads; it ends in a newline.
    code: str
    #: Source offset of each character of *code*, then of the end.
    origin: tuple[int, ...]
    #: The string each placeholder stands for, by the placeholder's
    #: offset in *code*.
    stash: dict[int, Stashed]


def counted(text: str, at: int, close: str, end: int) -> int | None:
    """Return the offset just past the closer that balances an opener.

    Only the opener's own pair is counted, so a nested opener of the
    same pair needs a closer of its own and other brackets are ignored.

    Args:
        text: Source holding the opener.
        at: Offset of the opener.
        close: Closer of that opener.
        end: Offset where counting stops; the closer lies before it.

    Returns:
        The offset after the balancing closer, or ``None`` if none
        occurs before *end*.

    Examples:
        >>> counted("“a”", 0, "”", 3)
        3
        >>> counted("“a“b”", 0, "”", 5) is None
        True
    """
    opener, depth, j = text[at], 1, at + 1
    while j < end and depth:
        depth += (text[j] == opener) - (text[j] == close)
        j += 1
    return None if depth else j


class _Code:
    """Collect the code being written, with each character's origin."""

    def __init__(self) -> None:
        self.chars: list[str] = []
        self.origin: list[int] = []
        self.stash: dict[int, Stashed] = {}

    def put(self, text: str, at: int, verbatim: bool = True) -> None:
        """Append *text* to the code.

        Args:
            text: Characters to append.
            at: Source offset the text comes from.
            verbatim: If true, character *k* of *text* has origin
                ``at + k``; if false, as for a pad or placeholder, every
                character has origin *at*.
        """
        self.chars.extend(text)
        self.origin.extend(
            at + k if verbatim else at for k in range(len(text))
        )

    def at_line_start(self) -> bool:
        """Tell whether only tabs came since the last newline."""
        for char in reversed(self.chars):
            if char != "\t":
                return char == "\n"
        return True


def _pair(source: str, at: int, end: int, code: _Code) -> int:
    """Write the string or block comment that opens at *at*.

    A string becomes a placeholder, preceded by a space unless the code
    ends in whitespace, and is stashed. A block comment becomes a space,
    or nothing at the start of a line.

    Args:
        source: Text being read.
        at: Offset of the opener.
        end: Offset where reading stops.
        code: The code being written.

    Returns:
        The offset where the next write starts: after the closer or, for
        a block comment at the start of a line, after the spaces that
        follow it.

    Raises:
        FplError: The pair is never closed.
    """
    opener = source[at]
    after = counted(source, at, PAIRS[opener], end)
    if after is None:
        raise UnclosedError(Lines(source).span(at), f"{opener} never closed")
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
    """Write what starts with a special character.

    A pair goes to :func:`_pair`, a closer with no opener is refused,
    and anything else is a line comment, copied up to its newline.

    Args:
        source: Text being read.
        at: Offset of the special character.
        end: Offset where reading stops.
        code: The code being written.

    Returns:
        The offset where the next write starts.

    Raises:
        FplError: The character is a closer with no opener, or opens a
            pair that is never closed.
    """
    char = source[at]
    if char in PAIRS:
        return _pair(source, at, end, code)
    if char in CLOSERS:
        raise UnopenedError(Lines(source).span(at), f"{char} closes nothing")
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
    """Stash the strings and drop the block comments of a source range.

    Indentation and brackets are not checked here; :func:`strict` does
    that.

    Args:
        source: Text to read.
        start: Offset where reading starts.
        end: Offset where reading stops; the end of *source* by default.
        special: The characters that open or close a pair or start a
            line comment.

    Returns:
        The code, ending in a newline, with the source offset of each of
        its characters and the strings it stashed.

    Raises:
        FplError: A pair is never closed, or a closer has no opener.
    """
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
    r"""Pre-lex ``source[start:end]`` into code the grammar reads.

    Args:
        source: Text to read.
        start: Offset where reading starts.
        end: Offset where reading stops; the end of *source* by default.

    Returns:
        The code, ending in a newline, with the source offset of each of
        its characters and the strings it stashed.

    Raises:
        FplError: A pair is never closed, a closer has no opener, a line
            is indented with spaces outside brackets, a dedent goes
            below the line of a bracket still open, or a bracket closes
            nothing, closes the wrong opener or is never closed. The
            error is placed at the offending line and column of
            *source*.

    Examples:
        >>> prelex("a “b” c\n").code
        'a ¶  c\n\n'
        >>> prelex("x “ab\n")  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        fpl.errors.UnclosedError: |- ! err/read/unclosed 1:3 ...
    """
    lexed = pairs(source, start, end)
    strict(source, lexed.code, lexed.origin)
    return lexed


class _RefusalError(Exception):
    """A strictness refusal at a code offset, not yet placed."""

    def __init__(
        self, offset: int, message: str, kind: type[FplError]
    ) -> None:
        super().__init__(message)
        self.offset = offset
        self.message = message
        #: The error the refusal becomes once it is placed.
        self.kind = kind


def _brackets(
    line: str, base: int, depth: int, open_: list[tuple[str, int, int]]
) -> None:
    """Track the brackets of one code line, ignoring its line comment.

    Args:
        line: The line, without its newline.
        base: Offset in the code of the line's first character.
        depth: Tabs at the start of the line.
        open_: Stack of the open brackets as (bracket, offset in the
            code, depth), updated in place.

    Raises:
        _RefusalError: A closer closes nothing, or does not close the
            latest opener.
    """
    body = LINE_COMMENT.split(line, maxsplit=1)[0]
    for n, char in enumerate(body):
        if char in BRACKETS:
            open_.append((char, base + n, depth))
        elif char in CLOSERS and not open_:
            raise _RefusalError(
                base + n, f"{char} closes nothing", UnopenedError
            )
        elif char in CLOSERS and open_[-1][0] != CLOSERS[char]:
            raise _RefusalError(
                base + n,
                f"{char} does not close {open_[-1][0]}",
                MismatchedError,
            )
        elif char in CLOSERS:
            open_.pop()


def _lines(code: str, line_of: Callable[[int], int]) -> None:
    """Refuse loose indentation, line by line.

    A dedent below the line of a bracket still open is reported at the
    dedenting line and names the opener's line.

    Args:
        code: The code to check.
        line_of: Maps an offset in *code* to its source line number.

    Raises:
        _RefusalError: A line is indented with spaces outside brackets,
            a dedent goes below the line of a bracket still open, or a
            bracket is never closed. A bracket error of
            :func:`_brackets` passes through.
    """
    open_: list[tuple[str, int, int]] = []
    base = 0
    for line in code.split("\n"):
        depth = len(line) - len(line.lstrip("\t"))
        if not open_ and line[depth : depth + 1] == " ":
            raise _RefusalError(
                base + depth, "indentation must be tabs", TabsError
            )
        if open_ and line.strip() and depth < open_[-1][2]:
            opener, opened, _ = open_[-1]
            message = (
                f"dedent below line {line_of(opened)}, "
                f"but its {opener} is still open"
            )
            raise _RefusalError(base + depth, message, StrayDedentError)
        _brackets(line, base, depth, open_)
        base += len(line) + 1
    if open_:
        raise _RefusalError(
            open_[-1][1], f"{open_[-1][0]} never closed", UnclosedError
        )


def strict(source: str, code: str, origin: tuple[int, ...]) -> None:
    """Refuse loose indentation in code, at its place in the source.

    Args:
        source: Text the code was lexed from.
        code: The code from :func:`pairs`.
        origin: Source offset of each character of *code*, then of the
            end.

    Raises:
        FplError: A line is indented with spaces outside brackets, a
            dedent goes below the line of a bracket still open, or a
            bracket closes nothing, closes the wrong opener or is never
            closed.
    """
    lines = Lines(source)
    try:
        _lines(code, lambda offset: lines.span(origin[offset]).line)
    except _RefusalError as refusal:
        raise refusal.kind(
            lines.span(origin[refusal.offset]), refusal.message
        ) from None


def shape(token: str) -> tuple[str, Kind, tuple[str, ...], str] | None:
    """Split a token into prefix sigil, kind, body and suffix modifiers.

    Args:
        token: One token of lexed code.

    Returns:
        A tuple of the prefix sigil (``""`` for none), the kind, the
        body (the segments of a path, else the one-element name) and the
        modifiers of :data:`MODS`; ``None`` when a modifier stands
        anywhere but at the end.

    Examples:
        >>> shape("->x´")
        ('->', 'name', ('x',), '´')
        >>> shape("a/b")
        ('', 'path', ('a', 'b'), '')
        >>> shape("a´b") is None
        True
    """
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


GRAMMAR = Path(__file__).resolve().parents[1] / "grammar.lark"


@dataclass(frozen=True)
class Tokens:
    """
    The lexer's output: the pre-lexed text and the tokens the second
    Lark will read.
    """

    source: str
    lexed: Prelexed
    raw: tuple[tuple[str, str, int, int], ...]


_LEXER: Lark | None = None


def token_lark() -> Lark:
    """
    The lexer Lark. It does not parse.
    """
    global _LEXER
    if _LEXER is None:
        _LEXER = Lark(
            GRAMMAR.read_text(),
            parser="lalr",
            propagate_positions=True,
            maybe_placeholders=False,
        )
    return _LEXER


def code_tokens(code: str) -> list:
    """
    Tokens for code the pre-lexer already produced.
    """
    return list(token_lark().lex(code))


def _pack(got: list) -> tuple[tuple[str, str, int, int], ...]:
    return tuple(
        (token.type, str(token), token.start_pos or 0, token.end_pos or 0)
        for token in got
    )


def _lex(source: str) -> Tokens:
    lexed = prelex(source)
    return Tokens(source, lexed, _pack(code_tokens(lexed.code)))


lex = Pass("lex", _lex, source="Source", target="Tokens")

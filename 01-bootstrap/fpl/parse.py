"""Parse source text to the surface AST.

:func:`parse` runs :func:`fpl.lex.prelex`, the tab indenter
:class:`FplIndenter`, an LALR parser over ``fpl/grammar.lark`` and the
affix pass :func:`fpl.lex.shape` on every token. Every refusal is an
:exc:`fpl.errors.FplError` with a position. The module assigns no
meaning to the tree (``.agents/CONVENTIONS.md``).
"""

# pyright: reportIncompatibleMethodOverride=false, reportAssignmentType=false
# ruff: noqa: RUF012 -- Lark reads a class attribute

from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path
from typing import override

import icontract
from lark import Lark, Token, Tree, UnexpectedInput, UnexpectedToken
from lark.indenter import DedentError, Indenter

from fpl.ast_surface import (
    Cell,
    Comment,
    Enclosure,
    Frame,
    Item,
    Line,
    Pair,
    Program,
    Text,
    Word,
)
from fpl.errors import (
    CommentError,
    ModifierError,
    Span,
    StrayDedentError,
    TooDeepError,
    UnclosedError,
    UnexpectedError,
)
from fpl.lex import BRACKETS, Lines, Prelexed, Stashed, counted, prelex, shape

#: The Lark grammar file, next to this module.
GRAMMAR = Path(__file__).with_name("grammar.lark")
#: Enclosure pair of each grammar rule that is an enclosure.
PAIRS: dict[str, Pair] = {
    "quotation": "quotation",
    "prefix": "prefix",
    "group": "group",
    "dict": "dict",
}


class MisindentedError(Exception):
    """Raised by the indenter on a dedent to a level no line opened.

    Attributes:
        token: The newline token at which the dedent went wrong.
    """

    def __init__(self, token: Token) -> None:
        """Keep the newline *token* of the bad dedent."""
        super().__init__(token)
        self.token = token


class FplIndenter(Indenter):
    """Lark indenter with one tab per level.

    A newline inside ``[ ]``, ``( )``, ``⟨ ⟩`` or ``{ }`` is not block
    structure.
    """

    # Lark declares these as abstract properties and then reads them as
    # class attributes. The two lists are class variables.
    #: Token type of a newline.
    NL_type = "_NL"
    #: Token types that open an enclosure.
    OPEN_PAREN_types = ["LSQB", "LPAR", "_LANGLE", "_LBRACE"]
    #: Token types that close an enclosure.
    CLOSE_PAREN_types = ["RSQB", "RPAR", "_RANGLE", "_RBRACE"]
    #: Token type emitted when a block opens.
    INDENT_type = "_INDENT"
    #: Token type emitted when a block closes.
    DEDENT_type = "_DEDENT"
    #: Columns one tab counts for.
    tab_len = 1

    @override
    def handle_NL(self, token: Token) -> Iterator[Token]:
        """Indent as Lark does, but keep the newline of a bad dedent.

        Raises:
            MisindentedError: The dedent returns to a level no line
                opened.
        """
        try:
            yield from super().handle_NL(token)
        except DedentError as failure:
            raise MisindentedError(token) from failure


@cache
def parser() -> Lark:
    """Return the LALR parser for ``GRAMMAR``, built once."""
    return Lark(
        GRAMMAR.read_text(),
        parser="lalr",
        postlex=FplIndenter(),
        propagate_positions=True,
        maybe_placeholders=False,
    )


def parse(source: str) -> Program:
    r"""Parse source text to the surface AST.

    Args:
        source: The whole program text.

    Returns:
        The program, every node placed in *source*.

    Raises:
        FplError: The pre-lexer, the indenter, the grammar or the affix
            pass refuses the text, at a position inside *source*.
            Nesting deeper than the build can recurse to is refused at
            ``1:1``.

    Examples:
        >>> len(parse("a b\n").lines)
        1
        >>> parse("(x\n")  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        fpl.errors.UnclosedError: |- ! err/read/unclosed 1:1 ...
    """
    try:
        return read(source, Lines(source), 0, len(source))
    except RecursionError:
        raise TooDeepError(Span(1, 1), "nesting too deep to read") from None


def read(source: str, lines: Lines, start: int, end: int) -> Program:
    """Parse ``source[start:end]``, placing nodes in the whole source.

    Args:
        source: The whole text, which positions refer to.
        lines: The line index of *source*.
        start: Offset of the first character to parse.
        end: Offset just past the last character to parse.

    Raises:
        FplError: As :func:`parse`, except that nesting is not caught
            here.
    """
    lexed = prelex(source, start, end)
    tree = _tree(source, lexed)
    return _Build(source, lines, lexed).program(tree, lines.span(start))


def _tree(source: str, lexed: Prelexed) -> Tree[Token]:
    """Return Lark's tree for the pre-lexed code.

    Raises:
        FplError: Lark or the indenter refuses the code; the position is
            placed in *source*.
    """
    try:
        return parser().parse(lexed.code)  # pyright: ignore[reportUnknownMemberType] -- lark types its text argument loosely
    except UnexpectedToken as failure:
        comment = isinstance(failure.token, Token) and failure.token.type in {
            "NOTE",
            "DOC",
        }
        if comment:
            raise CommentError(
                placed(source, lexed, failure.pos_in_stream),
                "a comment cannot stand inside an enclosure",
            ) from None
        raise UnexpectedError(
            placed(source, lexed, failure.pos_in_stream), "unexpected input"
        ) from None
    except UnexpectedInput as failure:
        raise UnexpectedError(
            placed(source, lexed, failure.pos_in_stream), "unexpected input"
        ) from None
    except MisindentedError as failure:
        where_ = placed(source, lexed, failure.token.end_pos)
        raise StrayDedentError(
            where_, "dedent to a level never opened"
        ) from None


def placed(source: str, lexed: Prelexed, offset: int | None) -> Span:
    """Place an offset of the pre-lexed code in the source.

    Args:
        source: The whole text.
        lexed: The pre-lexed code that *offset* points into.
        offset: Offset in ``lexed.code``; ``None`` or negative, which is
            how Lark reports an unknown or end position, places it at
            the end of *source*.

    Returns:
        The position in *source*.
    """
    if offset is None or offset < 0:
        return where(source, -1, -1)
    at = Lines(source).span(lexed.origin[offset])
    return where(source, at.line, at.col)


class _Build:
    """Build the surface AST from Lark's tree.

    Every node is placed in the source through ``lexed.origin``.
    """

    def __init__(self, source: str, lines: Lines, lexed: Prelexed) -> None:
        self.source, self.lines, self.lexed = source, lines, lexed

    def at(self, tree: Tree[Token], outer: Span) -> Span:
        """Return where a subtree starts, or *outer* if it is empty."""
        if tree.meta.empty:
            return outer
        return self.lines.span(self.lexed.origin[tree.meta.start_pos])

    def program(self, tree: Tree[Token], outer: Span) -> Program:
        """Build the start rule, the program's lines."""
        return Program(self.subtrees(tree, outer, self.line), outer)

    def subtrees[T](
        self,
        tree: Tree[Token],
        outer: Span,
        build: Callable[[Tree[Token], Span], T],
    ) -> tuple[T, ...]:
        """Return each child subtree built with *build*."""
        return tuple(
            build(child, outer)
            for child in tree.children
            if isinstance(child, Tree)
        )

    def line(self, tree: Tree[Token], outer: Span) -> Line:
        """Build ``frames check? (NOTE | DOC)? _NL block?``.

        A ``;;`` line holds its comment and no frames. The frames of a
        ``check`` are the right side of ``L |- R``.

        Raises:
            FplError: :meth:`comment` refuses the line's comment.
        """
        span = self.at(tree, outer)
        frames, *rest = tree.children
        assert isinstance(frames, Tree)
        parts = {str(c.data): c for c in rest if isinstance(c, Tree)}
        checked = "check" in parts
        comment = next(
            (
                self.comment(c, frames, checked)
                for c in rest
                if isinstance(c, Token)
            ),
            None,
        )
        return Line(
            self.held(frames, span, comment),
            self.part(parts.get("block"), span, self.line),
            span,
            comment,
            next(iter(self.part(parts.get("check"), span, self.frames)), None),
        )

    def part[T](
        self,
        tree: Tree[Token] | None,
        outer: Span,
        build: Callable[[Tree[Token], Span], T],
    ) -> tuple[T, ...]:
        """Return :meth:`subtrees` of an optional part, or none.

        Args:
            tree: The part, None where the line has none.
            outer: The span of the line.
            build: Builds one subtree of the part.

        Returns:
            What *build* makes of each subtree, in order.
        """
        return () if tree is None else self.subtrees(tree, outer, build)

    def held(
        self, frames: Tree[Token], span: Span, comment: Comment | None
    ) -> tuple[Frame, ...]:
        """Return a line's frames; a ``;;`` line holds none."""
        if comment is not None and comment.level > 1:
            return ()
        return self.subtrees(frames, span, self.frame)

    def comment(
        self, token: Token, frames: Tree[Token], checked: bool
    ) -> Comment:
        """Build a note with its continuation lines, or a ``;;`` one.

        Args:
            token: The comment's token.
            frames: The line's frames.
            checked: Whether the line has a check.

        Raises:
            FplError: A ``;;`` comment follows code or a check on its
                line.
        """
        span = self.lines.span(self.lexed.origin[token.start_pos or 0])
        level = (
            1 if token.type == "NOTE" else len(token) - len(token.lstrip(";"))
        )
        if level > 1 and (checked or _code(frames)):
            raise CommentError(
                span, f"a {';' * level} comment stands on a line of its own"
            )
        return Comment(
            level, tuple(part.lstrip("\t") for part in token.split("\n")), span
        )

    def frames(self, tree: Tree[Token], outer: Span) -> tuple[Frame, ...]:
        """Build ``frame (_BAR frame)*``."""
        return self.subtrees(tree, outer, self.frame)

    def frame(self, tree: Tree[Token], outer: Span) -> Frame:
        """Build ``_TABS? (cell (_TABS cell)* _TABS?)?``.

        An empty frame starts where its enclosing node does.
        """
        span = self.at(tree, outer)
        return Frame(self.subtrees(tree, span, self.cell), span)

    def cell(self, tree: Tree[Token], outer: Span) -> Cell:
        """Build ``item+``."""
        span = self.at(tree, outer)
        return Cell(
            tuple(self.item(child, span) for child in tree.children), span
        )

    def item(self, child: Tree[Token] | Token, outer: Span) -> Item:
        """Build a token, a string placeholder or an enclosure.

        Raises:
            FplError: :meth:`word` or :meth:`text` refuses it.
        """
        if isinstance(child, Tree):
            span = self.at(child, outer)
            (frames,) = self.subtrees(child, span, self.frames)
            return Enclosure(PAIRS[str(child.data)], frames, span)
        start = child.start_pos or 0
        span = self.lines.span(self.lexed.origin[start])
        stashed = self.lexed.stash.get(start)
        if stashed is not None:
            return self.text(stashed, span)
        return self.word(str(child), span)

    def word(self, token: str, span: Span) -> Word:
        """Run the affix pass on one token.

        Raises:
            FplError: The token ends in a modifier, so
                :func:`fpl.lex.shape` reads nothing.
        """
        read_ = shape(token)
        if read_ is None:
            raise ModifierError(span, f"a modifier ends its word: {token}")
        prefix, kind, body, mods = read_
        return Word(prefix, kind, body, mods, span)

    def text(self, stashed: Stashed, span: Span) -> Text:
        """Build a string's interior.

        A raw string is kept whole. An interpolating one is split into
        text and ``⟨ ⟩`` islands; the incidental indentation of its
        continuation lines is dropped (S26).

        Raises:
            FplError: :meth:`island` finds an island that never closes.
        """
        if stashed.kind == "raw":
            return Text(
                "raw", (self.source[stashed.start : stashed.end],), span
            )
        parts: list[str | Program] = []
        at = stashed.start
        while at < stashed.end:
            island = self.source.find("⟨", at, stashed.end)
            upto = stashed.end if island < 0 else island
            if upto > at:
                parts.append(
                    self.source[at:upto].replace(
                        "\n" + "\t" * stashed.depth, "\n"
                    )
                )
            at = (
                upto if island < 0 else self.island(island, stashed.end, parts)
            )
        return Text("str", tuple(parts), span)

    def island(self, at: int, end: int, parts: list[str | Program]) -> int:
        """Read the ``⟨ ⟩`` island at *at* and append it to *parts*.

        Returns:
            The offset after the island.

        Raises:
            FplError: The island never closes before *end*, or its
                content is refused as in :func:`read`.
        """
        after = counted(self.source, at, BRACKETS["⟨"], end)
        if after is None:
            raise UnclosedError(self.lines.span(at), "⟨ never closed")
        parts.append(read(self.source, self.lines, at + 1, after - 1))
        return after


def _code(frames: Tree[Token]) -> bool:
    """Return whether a line's frames hold code (a bar or a cell)."""
    return len(frames.children) > 1 or any(
        isinstance(frame, Tree) and frame.children for frame in frames.children
    )


def within(source: str, line: int, col: int) -> bool:
    r"""Return whether line and column name a character or a line end.

    Args:
        source: The text.
        line: 1-based line number.
        col: 1-based column; one past the line's length is allowed.

    Examples:
        >>> within("ab\ncd", 1, 3)
        True
        >>> within("ab", 1, 4)
        False
    """
    lines = source.split("\n")
    return 1 <= line <= len(lines) and 1 <= col <= len(lines[line - 1]) + 1


def reported(source: str, line: int, column: int) -> bool:
    """Return whether Lark's failure position is usable.

    That is a position within *source*, or line ``-1`` for its end.
    """
    return line == -1 or within(source, line, column)


def inside(result: Span, source: str) -> bool:
    """Tell whether *result* lies in *source*.

    The postcondition of :func:`where`.
    """
    return within(source, result.line, result.col)


@icontract.require(reported)
@icontract.ensure(inside)
def where(source: str, line: int, column: int) -> Span:
    r"""Return the position of a parse failure.

    Args:
        source: The text.
        line: Lark's line; ``-1`` means the end of the input.
        column: Lark's column.

    Returns:
        The position, which for line ``-1`` is just after the last
        character.

    Raises:
        icontract.ViolationError: The position is neither within
            *source* nor the end (``reported``), or the result is not
            within it (``inside``).

    Examples:
        >>> where("ab\ncd", -1, -1)
        Span(line=2, col=3)
        >>> where("x", 1, 1)
        Span(line=1, col=1)
    """
    if line >= 1:
        return Span(line, column)
    lines = source.split("\n")
    return Span(len(lines), len(lines[-1]) + 1)

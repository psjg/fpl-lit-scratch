"""Print a surface tree as canonical source.

:func:`render` is the entry point; it is the only place source text is
normalised. Items are joined by a space, cells by a tab, frames by `` |
`` (an empty frame adds only its bar). An enclosure prints as ``o body
c``, or ``oc`` when it holds one empty frame. A block line carries one
tab per level. A note after code stands in a cell of its own, and its
continuation lines carry as many tabs as stand before it. A note on a
line of its own right after a line that ends in a note gets a blank line
before it, which ends the earlier note. No code line ends in a space; a
program ends in a newline, and one empty line is the empty text.
"""

from typing import assert_never

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
from fpl.errors import FplError, Span

#: Opening and closing delimiter that :meth:`_Out.enclosure` prints for
#: each enclosure pair.
DELIMITERS: dict[Pair, tuple[str, str]] = {
    "quotation": ("[", "]"),
    "prefix": ("(", ")"),
    "group": ("⟨", "⟩"),
    "dict": ("{", "}"),
}


def render(program: Program) -> str:
    r"""Print *program* as canonical source.

    ``parse(render(p)) == p`` holds for every tree the parser can give,
    and ``render(parse(s))`` is idempotent. The result ends in a
    newline; the empty program prints as the empty string.

    Args:
        program: A tree as the parser builds it: cells hold items, an
            enclosure holds frames, and only the first line may be
            empty.

    Returns:
        The source text.

    Raises:
        FplError: The tree is nested deeper than the interpreter can
            recurse to, as the parser refuses such source (issue #95).

    Examples:
        >>> from fpl.parse import parse
        >>> render(parse("[ a   b ]  | c"))
        '[ a b ] | c\n'
        >>> render(parse(""))
        ''
    """
    out = _Out()
    try:
        out.lines(program.lines, 0)
    except RecursionError:
        raise FplError(Span(1, 1), "nesting too deep to print") from None
    text = "".join(out.chunks)
    return text + "\n" if text else ""


class _Out:
    """Accumulate source text while :func:`render` walks the tree.

    Besides the chunks, it tracks the tabs that open the current
    physical line (an interpolating string's continuation lines repeat
    them, since the parser drops them, S26), the column in tabs, and
    whether the last line written ends in a note.
    """

    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.tabs = 0
        self.leading = True
        self.column = 0
        self.noted = False

    def put(self, text: str) -> None:
        """Append *text*; update the tab counts of its last line."""
        self.chunks.append(text)
        newline = text.rfind("\n")
        if newline >= 0:
            self.tabs, self.leading, self.column, text = (
                0,
                True,
                0,
                text[newline + 1 :],
            )
        self.column += text.count("\t")
        if self.leading:
            rest = text.lstrip("\t")
            self.tabs += len(text) - len(rest)
            self.leading = not rest

    def lines(self, lines: tuple[Line, ...], depth: int) -> None:
        """Write *lines* at *depth* tabs, each followed by its block."""
        for n, line in enumerate(lines):
            if n:
                self.put("\n")
            self.line(line, depth)

    def line(self, line: Line, depth: int) -> None:
        """Write one line and its block, one level deeper.

        A note on a line of its own right after a line that ends in a
        note would read back as that note's continuation, so a blank
        line, which ends a note, is written between them.
        """
        code = _code(line.frames)
        note = line.comment is not None and line.comment.level == 1
        if self.noted and note and not code:
            self.put("\n")
        self.put("\t" * depth)
        self.frames(line.frames)
        if line.comment is not None:
            self.comment(line.comment, code)
        self.noted = note
        for inner in line.block:
            self.put("\n")
            self.line(inner, depth + 1)

    def comment(self, comment: Comment, code: bool) -> None:
        """Write *comment* as written.

        Args:
            comment: The comment to write.
            code: Whether code precedes it on the line; a note after
                code goes in a cell of its own, and its continuation
                lines are indented by the column it starts in.
        """
        first, *rest = comment.lines
        self.put("\t" if code else "")
        column = self.column
        self.put(first)
        for more in rest:
            self.put("\n" + "\t" * column + more)

    def frames(self, frames: tuple[Frame, ...]) -> None:
        """Write *frames* between bars; an empty frame adds its bar."""
        written = False
        for n, frame in enumerate(frames):
            if n:
                self.put(" |" if written else "|")
                written = True
            if frame.cells:
                self.put(" " if written else "")
                self.cells(frame.cells)
                written = True

    def cells(self, cells: tuple[Cell, ...]) -> None:
        """Write *cells* separated by tabs, and items by spaces."""
        for n, cell in enumerate(cells):
            self.put("\t" if n else "")
            for k, item in enumerate(cell.items):
                self.put(" " if k else "")
                self.item(item)

    def item(self, item: Item) -> None:
        """Write a word as written, a string, or an enclosure."""
        match item:
            case Word():
                self.put(item.prefix + "/".join(item.body) + item.mods)
            case Text():
                self.text(item)
            case Enclosure():
                self.enclosure(item)
            case _:
                assert_never(item)

    def enclosure(self, enclosure: Enclosure) -> None:
        """Write ``o body c``, or ``oc`` for one empty frame inside."""
        opener, closer = DELIMITERS[enclosure.pair]
        if not _code(enclosure.frames):
            self.put(opener + closer)
            return
        self.put(opener + " ")
        self.frames(enclosure.frames)
        self.put(" " + closer)

    def text(self, text: Text) -> None:
        """Write a raw string verbatim, or an interpolating one.

        An interpolating string has its continuation lines indented as
        the line it opens on, and its islands written as programs.
        """
        if text.kind == "raw":
            self.put(f"「{''.join(str(part) for part in text.parts)}」")
            return
        indent = "\n" + "\t" * self.tabs
        self.put("“")
        for part in text.parts:
            if isinstance(part, str):
                self.put(part.replace("\n", indent))
            else:
                self.put("⟨")
                self.lines(part.lines, 0)
                self.put("⟩")
        self.put("”")


def _code(frames: tuple[Frame, ...]) -> bool:
    """Tell whether *frames* hold code: a bar, or a frame with cells.

    A line without code is empty or a comment of its own; an enclosure
    without code holds one empty frame.
    """
    return len(frames) > 1 or any(frame.cells for frame in frames)

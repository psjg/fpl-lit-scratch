"""Classify the comments of a parsed program by their level.

A comment's attachment follows from its level and its position, not from
its text: :func:`comments` returns every comment as an
:class:`Attached`, and :func:`docstrings` collects the ones that
document a definition head. :func:`head` and :func:`code` are the line
tests it uses; :mod:`fpl.desugar` and :mod:`fpl.repl` call them too.

====================  ==========================================
Comment               Attaches to
====================  ==========================================
``;`` after code      its own line (``"trailing"``)
``;;`` on its own     the next code line (``"before"``); a
                      ``"doc"`` of that line when it is a
                      definition head, or when the ``;;`` opens
                      the body of a head
``;;;`` on its own    the section of the file (``"section"``)
``;;;;`` on its own   the file (``"file"``)
====================  ==========================================

``⍝`` counts as ``;``.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from fpl.ast_surface import Line, Program, Word

#: What a comment attaches to; see :data:`KINDS` and :class:`Attached`.
type Attachment = Literal["trailing", "before", "doc", "section", "file"]
#: Attachment by comment level minus one; a level above 4 counts as 4.
#: Level 2 starts as ``"before"`` and :func:`comments` may turn it into
#: ``"doc"``.
KINDS: tuple[Attachment, ...] = ("trailing", "before", "section", "file")


@dataclass(frozen=True)
class Attached:
    """A comment with its level and what it attaches to."""

    #: Source line of the comment.
    line: int
    #: Number of ``;`` marks (``⍝`` counts as one).
    level: int
    #: How the comment attaches. ``"before"`` is a ``;;`` that is not a
    #: doc.
    kind: Attachment
    #: Source line the comment attaches to; ``None`` for ``"section"``
    #: and ``"file"``, and for a ``"before"`` comment with no code after
    #: it.
    target: int | None
    #: Comment text with the marks and surrounding blanks removed.
    text: str


def head(line: Line) -> bool:
    r"""Tell whether *line* is a definition head.

    A head is a line whose first cell's second item is the plain word
    ``:``.

    Examples:
        >>> from fpl.parse import parse
        >>> [head(line) for line in parse("f : x -- y\na b").lines]
        [True, False]
    """
    cells = line.frames[0].cells if line.frames else ()
    second = [item for cell in cells[:1] for item in cell.items[1:2]]
    return (
        second == [Word("", "name", (":",), "", second[0].span)]
        if second
        else False
    )


def code(line: Line) -> bool:
    r"""Tell whether *line* holds code: a bar, an item or a check.

    Examples:
        >>> from fpl.parse import parse
        >>> [code(line) for line in parse(";; note\na b\n|- 1").lines]
        [False, True, True]
    """
    return (
        line.check is not None
        or len(line.frames) > 1
        or any(frame.cells for frame in line.frames)
    )


def _order(
    lines: tuple[Line, ...], parent: Line | None
) -> Iterator[tuple[Line, Line | None]]:
    """Yield each line in order with the line whose block holds it.

    The parent is ``None`` for a top-level line.
    """
    for line in lines:
        yield line, parent
        yield from _order(line.block, line)


type Order = tuple[tuple[Line, Line | None], ...]


def _aimed(order: Order, n: int) -> tuple[Attachment, int | None]:
    """Return the attachment and target of the ``;;`` at index *n*.

    The target is the next code line, as a ``"doc"`` when that line is a
    head. Failing that, when the ``;;`` opens a head's body, it is a
    ``"doc"`` of that head. Otherwise it is ``"before"`` the next code
    line, or ``None`` when no code follows.
    """
    after = next((line for line, _ in order[n + 1 :] if code(line)), None)
    if after is not None and head(after):
        return "doc", after.span.line
    opened = _opens(order, n)
    if opened is not None:
        return "doc", opened.span.line
    return "before", None if after is None else after.span.line


def _opens(order: Order, n: int) -> Line | None:
    """Return the head whose body line *n* opens, or ``None``.

    The line opens a body when it sits in the block of a head and no
    code line lies between that head and it.
    """
    before = next(
        (line for line, _ in reversed(order[:n]) if code(line)), None
    )
    parent = order[n][1]
    return (
        parent
        if parent is not None and before is parent and head(parent)
        else None
    )


def comments(program: Program) -> tuple[Attached, ...]:
    r"""Classify every comment of *program* by its level.

    A comment mark inside a string is not a comment and is not returned.

    Returns:
        The comments in written order.

    Examples:
        >>> from fpl.parse import parse
        >>> comments(parse(";; adds\nf : x -- y\na b ; t"))
        ... # doctest: +NORMALIZE_WHITESPACE
        (Attached(line=1, level=2, kind='doc', target=2, text='adds'),
         Attached(line=3, level=1, kind='trailing', target=3, text='t'))
    """
    order = tuple(_order(program.lines, None))
    found: list[Attached] = []
    for n, (line, _) in enumerate(order):
        if line.comment is None:
            continue
        kind = KINDS[min(line.comment.level, len(KINDS)) - 1]
        target = line.span.line if kind == "trailing" else None
        if kind == "before":
            kind, target = _aimed(order, n)
        text = " ".join(
            part.lstrip(";⍝").strip() for part in line.comment.lines
        )
        found.append(
            Attached(
                line.comment.span.line, line.comment.level, kind, target, text
            )
        )
    return tuple(found)


def docstrings(program: Program) -> dict[int, str]:
    r"""Collect the ``"doc"`` comments of *program* by head.

    Returns:
        Maps the source line of each documented head to its docs in
        written order, one per line.

    Examples:
        >>> from fpl.parse import parse
        >>> docstrings(parse(";; adds\nf : x -- y"))
        {2: 'adds'}
    """
    docs: dict[int, list[str]] = {}
    for comment in comments(program):
        if comment.kind == "doc" and comment.target is not None:
            docs.setdefault(comment.target, []).append(comment.text)
    return {line: "\n".join(texts) for line, texts in docs.items()}

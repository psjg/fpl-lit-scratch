"""Define the frozen nodes of the surface syntax tree.

The tree mirrors the source text. :class:`Program` is the root and holds
:class:`Line` nodes; a line holds :class:`Frame` nodes, a frame holds
:class:`Cell` nodes, and a cell holds items (:data:`Item`). Each node
records the :class:`~fpl.errors.Span` where it starts; spans are left
out of equality, so :mod:`fpl.parse` output compares by content.
"""

from dataclasses import dataclass, field
from typing import Literal

from fpl.errors import Span

#: How the affix pass classified a :class:`Word`.
type Kind = Literal["name", "number", "path", "modifier"]
#: The bracket pair of an :class:`Enclosure`: ``[ ]``, ``( )``, ``⟨ ⟩``,
#: ``{ }``.
type Pair = Literal["quotation", "prefix", "group", "dict"]


@dataclass(frozen=True)
class Word:
    """A token read by the affix pass.

    Examples:
        Equality ignores the span:

        >>> a = Word("", "name", ("x",), "", Span(1, 1))
        >>> a == Word("", "name", ("x",), "", Span(9, 9))
        True
    """

    #: The prefix sigil.
    prefix: str
    #: The class the affix pass gave the token.
    kind: Kind
    #: The segments of a path, otherwise a single element.
    body: tuple[str, ...]
    #: The suffix modifiers.
    mods: str
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Text:
    """A string literal.

    A ``"str"`` text holds literal text and the programs of its ``⟨ ⟩``
    islands. A ``"raw"`` text holds a single literal text.
    """

    #: ``"str"`` for an interpolating string, ``"raw"`` for a raw one.
    kind: Literal["str", "raw"]
    #: Literal text and island programs, in source order.
    parts: tuple["str | Program", ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Enclosure:
    """Frames in brackets: ``[ ]``, ``( )``, ``⟨ ⟩`` or ``{ }``."""

    #: Which bracket pair encloses the frames.
    pair: Pair
    #: The frames between the brackets.
    frames: tuple["Frame", ...]
    span: Span = field(compare=False)


#: One element of a :class:`Cell`.
type Item = Word | Text | Enclosure


@dataclass(frozen=True)
class Cell:
    """The items between two tabs."""

    #: The items in source order.
    items: tuple[Item, ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Frame:
    """The cells between two bars.

    An empty frame has the span of the node that encloses it.
    """

    #: The cells in source order.
    cells: tuple[Cell, ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Comment:
    """A line comment; *lines* holds each line from the mark on.

    Level 1 is a note: ``;`` (``⍝`` counts as ``;``) after the code of
    its line, plus the ``;`` lines directly below that continue it.
    Levels 2 and up (``;;``, ``;;;``, ``;;;;`` ...) are comments on a
    line of their own.
    """

    #: The number of semicolons in the mark.
    level: int
    #: The text of each comment line, from the mark on.
    lines: tuple[str, ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Line:
    """The frames on one line, its comment and the block under it.

    A ``;;`` comment line has no frames. An empty line has one empty
    frame.
    """

    #: The frames of the line, empty for a ``;;`` comment line.
    frames: tuple[Frame, ...]
    #: The lines indented under this one.
    block: tuple["Line", ...]
    span: Span = field(compare=False)
    #: The comment that starts or continues on this line, if any.
    comment: Comment | None = None


@dataclass(frozen=True)
class Program:
    """The lines of a source, or of a string's ``⟨ ⟩`` island."""

    #: The top-level lines; indented lines hang off :attr:`Line.block`.
    lines: tuple[Line, ...]
    span: Span = field(compare=False)

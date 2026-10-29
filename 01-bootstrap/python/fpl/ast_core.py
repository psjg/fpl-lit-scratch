"""Define the AST that desugaring produces and evaluation reads.

A program is a sequence of :data:`Statement` values, each a
:class:`Define` or a :class:`Run`. Code is a tuple of :data:`Node`
values and data is a :data:`Value`; a section is a :class:`Quotation`.
:data:`EFFECTS` declares the :class:`Effect` of each builtin word, in
the same form as an effect line on a defined word. A word that runs a
quotation declares a fixed effect whatever the quotation does (hole
control-effects); ``?`` and ``_`` declare none, and the elaborator finds
what fills them (hole goal-placeholder).
"""

from dataclasses import KW_ONLY, dataclass, field
from decimal import Decimal
from typing import Literal

from fpl.errors import Span

#: A numeral's value: an integer, or a decimal when it has a point.
type Number = int | Decimal
#: A literal that is a single item of a :class:`Strand`.
type Atom = Number | str
#: How a word takes an input: ``"value"`` is run at once, ``"thunk"`` is
#: run when and if the word chooses, ``"code"`` is inspected and never
#: run.
type Slot = Literal["value", "thunk", "code"]

#: Most digits a numeral may have, not counting its sign and point, and
#: most a computed number may have before its point (hole number-bound).
#: It is below Python's 4300-digit limit on converting between ``int``
#: and ``str``.
DIGITS = 4096


@dataclass(frozen=True)
class Strand:
    """Literals written side by side in one cell, taken as one value."""

    items: tuple[Atom, ...]


@dataclass(frozen=True)
class Listed:
    """A ``⟨ ⟩`` list, with *items* in written order."""

    items: tuple["Value", ...]


@dataclass(frozen=True)
class Quotation:
    """Code as a value."""

    code: tuple["Node", ...]


@dataclass(frozen=True)
class Symbol:
    """A name as a value, written ``#name``."""

    name: str


@dataclass(frozen=True)
class Dict:
    """A built ``{ }``: each key with its value, in written order."""

    entries: tuple[tuple[str, "Value"], ...]


#: Data on the stack: an :data:`Atom` or one of the classes above.
type Value = Atom | Strand | Listed | Quotation | Symbol | Dict


@dataclass(frozen=True)
class Push:
    """Push a value."""

    value: Value


@dataclass(frozen=True)
class Call:
    """Run a word; *span* is where it was written."""

    name: str
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Bind:
    """Take the top value and run *body* with *name* bound to it.

    Written ``→name``. The scope is the rest of the line, the body or
    the quotation the binder is written in (decision f).
    """

    name: str
    body: tuple["Node", ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Keyed:
    """Run each entry's node on a fresh stack; build one :class:`Dict`.

    Written ``{ key value ... }``.
    """

    entries: tuple[tuple[str, "Node"], ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Wild:
    """The pattern ``_``: matches anything and binds nothing."""


@dataclass(frozen=True)
class Var:
    """A name in a pattern: matches anything, bound in the row body."""

    name: str


@dataclass(frozen=True)
class Equal:
    """A literal or ``$x`` in a pattern.

    Matches a value equal to the one *node* pushes once ``x`` is bound.
    """

    node: "Node"


@dataclass(frozen=True)
class Inverse:
    """The pattern ``( name args )``: constructor *name* run backwards.

    Each of *args* matches the corresponding value the constructor took.
    """

    name: str
    args: tuple["Pattern", ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Guarded:
    """The pattern ``p ∈ test``: *pattern* matches, *test* leaves 1.

    The word *test* is run on the value.
    """

    pattern: "Pattern"
    test: str
    span: Span = field(compare=False)


#: A pattern in a :class:`Row`.
type Pattern = Wild | Var | Equal | Inverse | Guarded


@dataclass(frozen=True)
class Row:
    """One pattern per value a match takes; the body runs on a match."""

    patterns: tuple[Pattern, ...]
    body: tuple["Node", ...]


@dataclass(frozen=True)
class Match:
    """Take one value per pattern; run the first row that matches.

    When no row matches, the match fails with ``+fail`` at *span*.
    """

    rows: tuple[Row, ...]
    span: Span = field(compare=False)


@dataclass(frozen=True)
class Refuse:
    """An error raised where it runs, never ``+fail``.

    The desugarer puts it where a call fits two crossing clauses (design
    09 §3.4).
    """

    message: str
    span: Span = field(compare=False)


#: One step of code.
type Node = Push | Call | Bind | Keyed | Match | Refuse


@dataclass(frozen=True)
class Effect:
    """An effect line: what a word takes and leaves, and if it fails.

    Each input has a :data:`Slot` (S49 rule 5) and a type, which is a
    type word's name or ``None`` when untyped. Empty *slots* make every
    input a ``"value"`` and empty *types* make every input untyped.

    Args:
        ins: Names of the inputs, deepest first.
        outs: Names of the outputs.
        fails: Whether the word may fail with ``+fail``.
        slots: One per input, or empty.
        types: One per input, or empty.

    Raises:
        ValueError: *slots* or *types* is non-empty and its length
            differs from that of *ins* (raised in
            :meth:`__post_init__`).

    Examples:
        >>> Effect(("x", "y"), ("z",)).slots
        ('value', 'value')
        >>> Effect(("x",), (), slots=("value", "thunk"))
        Traceback (most recent call last):
        ValueError: one slot per input
    """

    ins: tuple[str, ...]
    outs: tuple[str, ...]
    fails: bool = False
    _: KW_ONLY
    slots: tuple[Slot, ...] = ()
    types: tuple[str | None, ...] = ()

    def __post_init__(self) -> None:
        """Fill the default slots and types.

        Raises:
            ValueError: *slots* or *types* is non-empty and not one per
                input.
        """
        slots = self.slots or ("value",) * len(self.ins)
        types = self.types or (None,) * len(self.ins)
        if len(slots) != len(self.ins):
            raise ValueError("one slot per input")
        if len(types) != len(self.ins):
            raise ValueError("one type per input")
        object.__setattr__(
            self, "slots", slots
        )  # frozen: the default is filled once, here
        object.__setattr__(self, "types", types)


@dataclass(frozen=True)
class Define:
    """A definition ``name : ins -- outs`` with its block's code.

    Args:
        doc: Its docstring, ``""`` for none.
        span: Where its effect line is.
        clause: Which clause of a dispatched word this is: ``()`` for a
            word not dispatched, ``(n,)`` for the dispatcher of its
            arity-n clauses, and ``(n, i)`` for its i-th clause of arity
            n.
        clauses: The words of a dispatcher's clauses, in written order.
    """

    name: str
    effect: Effect
    code: tuple[Node, ...]
    doc: str = ""
    span: Span = field(compare=False, default=Span(1, 1))
    clause: tuple[int, ...] = ()
    clauses: tuple[str, ...] = ()

    @property
    def word(self) -> str:
        """The name followed by the clause, joined with ``/``.

        Examples:
            >>> Define("f", Effect((), ()), (), clause=(2, 1)).word
            'f/2/1'
        """
        return "/".join((self.name, *map(str, self.clause)))

    @property
    def paths(self) -> tuple[str, ...]:
        """The name, then each longer prefix of :attr:`word` to its end.

        Examples:
            >>> Define("f", Effect((), ()), (), clause=(2, 1)).paths
            ('f', 'f/2', 'f/2/1')
        """
        return tuple(
            "/".join((self.name, *map(str, self.clause[:end])))
            for end in range(len(self.clause) + 1)
        )


@dataclass(frozen=True)
class Judgment:
    """The closing line ``|- ! err/<tag>``: the program fails so.

    It is no statement: the driver takes it from the last line of a
    file before the rest is desugared, which may itself be the failure.
    """

    #: The error's path under ``err/``, as written.
    tag: str
    #: The message the error must have, or None for any.
    message: str | None
    span: Span = field(compare=False, default=Span(1, 1))


@dataclass(frozen=True)
class Run:
    """A line's code, run on a fresh stack; what it leaves prints."""

    code: tuple[Node, ...]
    span: Span = field(compare=False, default=Span(1, 1))
    #: The code right of ``|-``, whose stack must equal :attr:`code`'s.
    check: tuple[Node, ...] | None = None


#: One top-level item of a program.
type Statement = Define | Run

_BINARY = Effect(("x", "y"), ("z",))
#: The binary arithmetic words, each with the name of its one-value
#: form: the word called where exactly one value is on the stack, which
#: reduces a strand (``1 2 3 4 +`` is 10).
ONE_VALUE: dict[str, str] = {word: f"{word}/1" for word in ("+", "-", "times")}
#: The :class:`Effect` of each builtin word, by name.
EFFECTS: dict[str, Effect] = {
    "+": _BINARY,
    "-": _BINARY,
    "times": _BINARY,
    **dict.fromkeys(ONE_VALUE.values(), Effect(("xs",), ("x",))),
    "swap": Effect(("x", "y"), ("y", "x")),
    "dup": Effect(("x",), ("x", "x")),
    "drop": Effect(("x",), ()),
    "enclose": Effect(("x",), ("q",)),
    ",": Effect(("a", "b"), ("ab",), slots=("code", "code")),
    "pair": Effect(("a", "b"), ("p",)),
    "cons": Effect(("x", "xs"), ("ys",)),
    "!": Effect(("q",), ("x",), slots=("thunk",)),
    "if": Effect(("c", "t", "e"), (), slots=("value", "thunk", "thunk")),
    "swap-args": Effect(
        ("x", "y", "q"), ("z",), slots=("value", "value", "thunk")
    ),
    "repeat": Effect(("q", "n"), (), slots=("thunk", "value")),
    "each": Effect(("xs", "q"), ("ys",), slots=("value", "thunk")),
    "scan": Effect(("xs", "q"), ("ys",), slots=("value", "thunk")),
    **dict.fromkeys(
        ("fold", "foldl", "foldr"),
        Effect(("xs", "q"), ("x",), slots=("value", "thunk")),
    ),
    **dict.fromkeys(
        ("Int", "Decimal", "Text", "Symbol"), Effect(("x",), ("b",))
    ),
    "?": Effect((), ()),
    "_": Effect((), ()),
}

#: Words the language's own examples call and nothing here runs, so a
#: call of one that no definition names is ``no evaluator yet``, not an
#: unknown word. Each is called in a maintainer's example where nothing
#: defines it: ``newline`` (draft1), ``debug`` (draft2/03), ``select``
#: (draft2/05), ``unpair`` (draft2/06), ``dict`` (draft2/08), ``curry``
#: (draft2/11), ``shape`` (draft3/paths), ``pos``, ``true`` and
#: ``false`` (match/01, match/04), and ``bind`` (draft3/paths), which
#: runs only as ``#name bind`` in a directory. A program's own
#: definition wins: draft2/02 defines ``curry``. The set is a sample:
#: ``first`` and ``divide`` are called in the examples too and are
#: unknown here. A word that runs moves to :data:`EFFECTS` (hole
#: unimplemented-words).
PLANNED = frozenset(
    {
        "newline",
        "debug",
        "select",
        "unpair",
        "dict",
        "curry",
        "shape",
        "pos",
        "true",
        "false",
        "bind",
    }
)

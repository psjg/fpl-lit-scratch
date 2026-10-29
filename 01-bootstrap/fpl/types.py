"""Infer each word's effect and check it against its effect line.

:func:`elaborate` walks the core AST before any line runs and returns
the :class:`Arrow` of every word and the :class:`Goal` of each ``?`` in
typed code. A body that leaves another count of values than its effect
line promises, or takes a sort a word cannot take, is refused with
:exc:`FplError`. Code that elaboration does not infer keeps its effect
line.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum, IntEnum
from typing import assert_never

from fpl.ast_core import (
    EFFECTS,
    Bind,
    Call,
    Define,
    Equal,
    Guarded,
    Inverse,
    Keyed,
    Match,
    Node,
    Pattern,
    Push,
    Refuse,
    Row,
    Run,
    Statement,
    Strand,
    Symbol,
    Value,
    Var,
    Wild,
)
from fpl.errors import FplError, Span
from fpl.eval import CONTROLS


@dataclass(frozen=True)
class Input:
    """The *index*-th value a word takes, its sort not known yet."""

    #: Position among the word's inputs, counted from the deepest.
    index: int


class Verdict(IntEnum):
    """How surely values of known sorts fit a pattern.

    A conjunction of verdicts is the least of them, so the members are
    ordered.
    """

    #: The values surely do not fit.
    NO = 0
    #: The values may fit; only a run can tell.
    MAYBE = 1
    #: The values surely fit.
    YES = 2


class Kind(Enum):
    """A sort of value that elaboration tracks.

    The literals of the integers partition into ``NAT1`` (1 2 …),
    ``ZERO`` (0) and ``NEG1`` (-1 -2 …). Above them sit the covers
    ``NAT0`` (``NAT1`` and ``ZERO``) and ``NEG0`` (``NEG1`` and
    ``ZERO``), then ``INT``, then ``NUMBER``, which also holds the
    decimals (:data:`RISES`). A sort rises one way, never falls: a word
    takes any sort that rises to the one it asks (:func:`taken`). A
    literal gets the smallest sort that holds it (:func:`sort`). ``RAT``
    is reserved for the rationals: no literal and no arrow has it yet
    (DI-0070).

    ``VALUE`` stands for a value of no tracked sort: a list, a
    quotation, a dict, or what a control word leaves.
    """

    #: A positive integer, the literals ``1 2 3 …``.
    NAT1 = "Nat1"
    #: Zero, the literal ``0`` alone.
    ZERO = "Zero"
    #: A negative integer, the literals ``-1 -2 …``.
    NEG1 = "Neg1"
    #: A natural number with zero: ``NAT1`` or ``ZERO``.
    NAT0 = "Nat0"
    #: A non-positive integer: ``NEG1`` or ``ZERO``.
    NEG0 = "Neg0"
    #: An integer: ``NAT0`` or ``NEG0``; no literal of its own.
    INT = "Int"
    #: A rational; reserved, no literal yet.
    RAT = "Rat"
    #: A number: an integer or a decimal.
    NUMBER = "Number"
    #: A text.
    TEXT = "Text"
    #: A symbol.
    SYMBOL = "Symbol"
    #: A value of no tracked sort.
    VALUE = "Value"


#: What elaboration knows of a value: a kind, or an input not yet
#: resolved.
type Sort = Kind | Input


#: The sorts each number sort rises to, one step up the lattice.
RISES: dict[Kind, tuple[Kind, ...]] = {
    Kind.NAT1: (Kind.NAT0,),
    Kind.NEG1: (Kind.NEG0,),
    Kind.ZERO: (Kind.NAT0, Kind.NEG0),
    Kind.NAT0: (Kind.INT,),
    Kind.NEG0: (Kind.INT,),
    Kind.INT: (Kind.NUMBER,),
}


def rises(have: Kind, need: Kind) -> bool:
    """Return whether a value of sort *have* is taken where *need* is.

    A sort is taken where itself is asked, and where any sort it rises
    to is; never the other way.

    Examples:
        >>> rises(Kind.NAT1, Kind.NUMBER), rises(Kind.NUMBER, Kind.NAT1)
        (True, False)
        >>> rises(Kind.ZERO, Kind.NEG0), rises(Kind.NAT1, Kind.ZERO)
        (True, False)
    """
    return have is need or any(
        rises(above, need) for above in RISES.get(have, ())
    )


def joined(sorts: set[Sort]) -> Sort:
    """Return the least sort every one of *sorts* rises to.

    Values of one sort have it. Values of several number sorts have the
    lowest sort of the lattice above them all; any other mix is of no
    known sort.

    Examples:
        >>> joined({Kind.ZERO, Kind.NAT1}) is Kind.NAT0
        True
        >>> joined({Kind.NAT1, Kind.NEG1}) is Kind.INT
        True
        >>> joined({Kind.NAT0, Kind.NEG0}) is Kind.INT
        True
        >>> joined({Kind.NAT1, Kind.TEXT}) is Kind.VALUE
        True
    """
    if len(sorts) < 2:
        return next(iter(sorts), Kind.VALUE)
    for above in Kind:
        if all(isinstance(s, Kind) and rises(s, above) for s in sorts):
            return above
    return Kind.VALUE


@dataclass(frozen=True)
class Arrow:
    """A word's inferred effect: the sorts it takes and leaves.

    An :class:`Input` in *outs* is the value taken at that index.
    """

    #: The sorts taken, deepest first.
    ins: tuple[Sort, ...]
    #: The sorts left, top last.
    outs: tuple[Sort, ...]


@dataclass(frozen=True)
class Dispatch(Arrow):
    """A dispatcher's arrow, with the rows it tries (design 09 §3.6)."""

    #: The rows in the order they are tried.
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Cases(Arrow):
    """A word whose result sort depends on the sort of its input.

    The arrow itself is the general case, taken for an input of unknown
    sort. :func:`chosen` resolves a call to the first of *cases* that
    takes the sort of its input.
    """

    #: The arrows of the same count of ins, most specific first.
    cases: tuple[Arrow, ...]


@dataclass(frozen=True)
class Goal:
    """A ``?`` met in typed code."""

    #: Where the ``?`` is.
    span: Span
    #: The arrow that would fill it.
    arrow: Arrow


@dataclass(frozen=True)
class Typing:
    """What elaboration knows at one point in the code."""

    #: The sorts on the stack, top last.
    stack: tuple[Sort, ...]
    #: The sort each bound name stands for.
    env: Mapping[str, Sort]
    #: The sort found for each input of the body, by index.
    known: Mapping[int, Sort]
    #: The goals met so far.
    goals: tuple[Goal, ...] = ()
    #: Whether the code gets here; a refusal never passes.
    reached: bool = True


class UntypedError(Exception):
    """Code that elaboration does not infer.

    Raised for a control word, whose effect is the code it runs, for a
    match whose rows leave different counts, and for a call to a name
    with no arrow. The word's effect line is trusted instead.
    """


class UnderflowError(FplError):
    """Fewer values than a word, a binder or a match takes."""

    def __init__(self, span: Span) -> None:
        """Build the error with the message ``stack underflow``.

        Args:
            span: The word, binder or match that took too many values.
        """
        super().__init__(span, "stack underflow")


#: The hole words: ``?`` is a goal, ``_`` is inferred as nothing.
HOLES = ("?", "_")
#: The arrow of binary arithmetic: two numbers in, one out.
NUMBERS = Arrow((Kind.NUMBER, Kind.NUMBER), (Kind.NUMBER,))
#: The sort ``succ`` leaves for each sort it takes, most specific first.
SUCC: tuple[tuple[Kind, Kind], ...] = (
    (Kind.NAT1, Kind.NAT1),
    (Kind.ZERO, Kind.NAT1),
    (Kind.NAT0, Kind.NAT1),
    (Kind.NEG1, Kind.NEG0),
    (Kind.NEG0, Kind.INT),
    (Kind.INT, Kind.INT),
)
#: The sort ``pred`` leaves for each sort it takes, most specific first.
PRED: tuple[tuple[Kind, Kind], ...] = (
    (Kind.NEG1, Kind.NEG1),
    (Kind.ZERO, Kind.NEG1),
    (Kind.NEG0, Kind.NEG1),
    (Kind.NAT1, Kind.NAT0),
    (Kind.NAT0, Kind.INT),
    (Kind.INT, Kind.INT),
)


def stepping(table: tuple[tuple[Kind, Kind], ...]) -> Cases:
    """Return the arrow of a unary step word from its table.

    Any other number, a ``Number``, leaves a ``Number``.
    """
    return Cases(
        NUMBERS.ins[:1],
        NUMBERS.outs,
        tuple(Arrow((have,), (left,)) for have, left in table),
    )


type Rows = tuple[tuple[Kind, Kind, Kind], ...]

#: A ``Zero`` divisor sticks the six division words: the term stays as
#: a value of no number sort (:class:`~fpl.ast_core.Stuck`). The row
#: comes first, before a row whose divisor a ``Zero`` rises to.
STUCK: Rows = ((Kind.INT, Kind.ZERO, Kind.VALUE),)
#: The sort of the quotient of ``kdiv``, ``bdiv`` and ``tdiv`` alike, as
#: (dividend, divisor, result), most specific first. Any other pair
#: leaves an ``Int``. A floored, Euclidean or truncated quotient has
#: the sign of ``a`` times that of ``d``, or is 0 (a floored one of a
#: negative ``a`` by a positive ``d`` is below 0, never above).
QUOTIENT: Rows = (
    (Kind.ZERO, Kind.NAT1, Kind.ZERO),
    (Kind.NAT0, Kind.NAT1, Kind.NAT0),
    (Kind.NEG0, Kind.NAT1, Kind.NEG0),
    (Kind.NAT0, Kind.NEG1, Kind.NEG0),
    (Kind.NEG0, Kind.NEG1, Kind.NAT0),
)
#: The sort of the remainder of ``kmod``: the sign of the divisor.
KMOD: Rows = (
    (Kind.INT, Kind.NAT1, Kind.NAT0),
    (Kind.INT, Kind.NEG1, Kind.NEG0),
)
#: The sort of the remainder of ``bmod``: never negative.
BMOD: Rows = (
    (Kind.INT, Kind.NAT1, Kind.NAT0),
    (Kind.INT, Kind.NEG1, Kind.NAT0),
)
#: The sort of the remainder of ``tmod``: the sign of the dividend.
TMOD: Rows = (
    (Kind.ZERO, Kind.INT, Kind.ZERO),
    (Kind.NAT0, Kind.INT, Kind.NAT0),
    (Kind.NEG0, Kind.INT, Kind.NEG0),
)
#: The sort of ``pdiv``: a quotient by 0 is 0, else as ``bdiv``.
PDIV: Rows = ((Kind.INT, Kind.ZERO, Kind.ZERO), *QUOTIENT)
#: The sort of ``pmod``: a remainder by 0 is the dividend, of its own
#: sort; else as ``bmod``.
PMOD: Rows = (
    *(
        (have, Kind.ZERO, have)
        for have in (
            Kind.ZERO,
            Kind.NAT1,
            Kind.NEG1,
            Kind.NAT0,
            Kind.NEG0,
            Kind.INT,
        )
    ),
    *BMOD,
)


def dividing(table: Rows) -> Cases:
    """Return the arrow of a division word from its table.

    The general arrow takes two integers and leaves one. It is taken
    for a divisor that may be 0 but is not known to be, so a stuck term
    can stand where it said ``Int`` (an open question).
    """
    return Cases(
        (Kind.INT, Kind.INT),
        (Kind.INT,),
        tuple(Arrow((a, d), (left,)) for a, d, left in table),
    )


#: The arrow of each builtin word, without control words and holes.
ARROWS: dict[str, Arrow] = {
    **{
        name: Arrow(
            tuple(map(Input, range(len(e.ins)))), (Kind.VALUE,) * len(e.outs)
        )
        for name, e in EFFECTS.items()
        if name not in CONTROLS and name not in HOLES
    },
    "+": NUMBERS,
    "-": NUMBERS,
    "times": NUMBERS,
    "succ": stepping(SUCC),
    "pred": stepping(PRED),
    "kdiv": dividing(STUCK + QUOTIENT),
    "kmod": dividing(STUCK + KMOD),
    "bdiv": dividing(STUCK + QUOTIENT),
    "bmod": dividing(STUCK + BMOD),
    "tdiv": dividing(STUCK + QUOTIENT),
    "tmod": dividing(STUCK + TMOD),
    "pdiv": dividing(PDIV),
    "pmod": dividing(PMOD),
    "swap": Arrow((Input(0), Input(1)), (Input(1), Input(0))),
    "dup": Arrow((Input(0),), (Input(0), Input(0))),
    "drop": Arrow((Input(0),), ()),
}
#: The query suffixes every definition gets, as in ``word/doc``.
QUERIES = ("history", "doc", "effect")
#: The kind each builtin type word tests for.
TESTED = {
    "Int": Kind.INT,
    "Decimal": Kind.NUMBER,
    "Text": Kind.TEXT,
    "Symbol": Kind.SYMBOL,
}


def elaborate(
    statements: tuple[Statement, ...],
) -> tuple[dict[str, Arrow], tuple[Goal, ...]]:
    """Infer the arrow of every word and collect the goals met.

    The result holds the builtins and the ``/history``, ``/doc`` and
    ``/effect`` queries of each definition. A word called before its
    last definition has been inferred meets that definition's effect
    line. A goal in code that is not typed is not met.

    Args:
        statements: The program's top-level statements, in order
            written.

    Returns:
        The arrow of each word by name, and the goals met in the order
            written.

    Raises:
        FplError: A body leaves another count of values than its effect
            line promises, a word takes a sort it cannot take, a ``_``
            cannot be inferred, or a word takes more values than exist
            (the subclass :exc:`UnderflowError`).
    """
    arrows = dict(ARROWS)
    defines = [s for s in statements if isinstance(s, Define)]
    for d in defines:
        arrows[d.word] = dispatching(d, declared(d))
        arrows.update(
            {
                f"{d.word}/{query}": Arrow((), (Kind.VALUE,))
                for query in QUERIES
            }
        )
    last = {d.word: d for d in defines}
    goals: list[Goal] = []
    for s in statements:
        with suppress(UntypedError):
            goals.extend(checked(s, last, arrows))
    return arrows, tuple(goals)


def checked(
    statement: Statement, last: Mapping[str, Define], arrows: dict[str, Arrow]
) -> tuple[Goal, ...]:
    """Return the goals one statement meets.

    The last definition of a word also sets the word's arrow in
    *arrows*.

    Args:
        statement: A definition or a run of code.
        last: The last definition of each word.
        arrows: The arrow of each word so far; updated in place.

    Raises:
        FplError: As for :func:`elaborate`.
        UntypedError: A ``Run`` holds code that is not typed.
    """
    if isinstance(statement, Run):
        return after(Typing((), {}, {}), statement.code, arrows).goals
    arrow, goals = inferred(statement, arrows)
    if last[statement.word] is statement:
        arrows[statement.word] = dispatching(statement, arrow)
    return goals


def dispatching(define: Define, arrow: Arrow) -> Arrow:
    """Return a dispatcher's arrow with its rows, any other as is.

    A dispatcher is a definition with one clause number whose code is a
    single match.
    """
    match define.code:
        case (Match(rows=rows),) if len(define.clause) == 1:
            return Dispatch(arrow.ins, arrow.outs, rows)
        case _:
            return arrow


def declared(define: Define) -> Arrow:
    """Return the effect line of *define* as an arrow.

    Every input is general and every output is ``Kind.VALUE``.
    """
    ins = tuple(map(Input, range(len(define.effect.ins))))
    return Arrow(ins, (Kind.VALUE,) * len(define.effect.outs))


def inferred(
    define: Define, arrows: Mapping[str, Arrow]
) -> tuple[Arrow, tuple[Goal, ...]]:
    """Infer the arrow of a body and the goals it meets.

    Inputs are as general as the body lets them be. A body that is not
    typed gets its effect line as arrow and no goals.

    Raises:
        FplError: The body leaves another count of values than its
            effect line promises, or :func:`after` refuses it.
    """
    start = Typing(tuple(map(Input, range(len(define.effect.ins)))), {}, {})
    promised = len(define.effect.outs)
    try:
        end = after(start, define.code, arrows, promised)
    except UntypedError:
        return declared(define), ()
    if len(end.stack) != promised:
        message = f"leaves {len(end.stack)} values, its effect line {promised}"
        raise FplError(define.span, f"{define.word} {message}")
    return Arrow(
        resolved(start.stack, end), resolved(end.stack, end)
    ), end.goals


def resolved(sorts: tuple[Sort, ...], typing: Typing) -> tuple[Sort, ...]:
    """Replace each input found to be of a sort by that sort."""
    return tuple(known(s, typing) for s in sorts)


def known(s: Sort, typing: Typing) -> Sort:
    """Return the sort found for an input, else *s* itself."""
    return typing.known.get(s.index, s) if isinstance(s, Input) else s


def after(
    typing: Typing,
    code: tuple[Node, ...],
    arrows: Mapping[str, Arrow],
    need: int | None = None,
) -> Typing:
    """Return what is known once *code* has run.

    Args:
        typing: What is known before the code.
        code: The nodes to run, in order.
        arrows: The arrow of each word.
        need: The count of values the code must end at, when known.

    Raises:
        FplError: A node cannot run; the error points at its span. This
            includes the subclass :exc:`UnderflowError`.
        UntypedError: The code is not typed.
    """
    for index, node in enumerate(code):
        rest = code[index + 1 :]
        if (
            isinstance(node, Call)
            and node.name in HOLES
            and node.name not in typing.env
        ):
            typing = filled(typing, node, rest, arrows, need)
        else:
            typing = through(typing, node, arrows, None if rest else need)
    return typing


def filled(
    typing: Typing,
    node: Call,
    rest: tuple[Node, ...],
    arrows: Mapping[str, Arrow],
    need: int | None,
) -> Typing:
    """Elaborate a hole, ``?`` or ``_``.

    A ``?`` takes the stack under it, leaves values of no known sort as
    many as the rest takes, and records a goal with those sorts. A ``_``
    is nothing when the rest takes the stack as it is.

    Args:
        typing: What is known before the hole.
        node: The hole.
        rest: The nodes after the hole.
        arrows: The arrow of each word.
        need: The count of values the code must end at, when known.

    Raises:
        FplError: A ``_`` would leave another count than it takes, or
            :func:`wanted` finds no count for the hole.
        UntypedError: The rest is not typed.
    """
    arrow = Arrow(
        resolved(typing.stack, typing),
        wanted(typing, node, rest, arrows, need),
    )
    if node.name == "?":
        stack = (Kind.VALUE,) * len(arrow.outs)
        return replace(
            typing, stack=stack, goals=(*typing.goals, Goal(node.span, arrow))
        )
    if len(arrow.outs) != len(arrow.ins):
        raise FplError(node.span, f"cannot infer _ : {shown(arrow)}")
    return typing


def wanted(
    typing: Typing,
    hole: Call,
    rest: tuple[Node, ...],
    arrows: Mapping[str, Arrow],
    need: int | None,
) -> tuple[Sort, ...]:
    """Return the sorts of the fewest values the rest runs on.

    The rest ends at *need* values when that is known. A value the rest
    puts no sort on is ``Kind.VALUE``.

    Past ``reach(rest)`` values nothing underflows, and each value more
    is either left on top or cleared by a hole in the rest. So
    ``reach(rest) + need`` values end at *need* when any count does.

    Args:
        typing: What is known before the hole.
        hole: The hole whose values are wanted.
        rest: The nodes after the hole.
        arrows: The arrow of each word.
        need: The count of values the code must end at, when known.

    Raises:
        FplError: No count of values lets the rest run or end at *need*.
        UntypedError: The rest is not typed.
    """
    for count in range(reach(rest, arrows) + (need or 0) + 1):
        start = Typing(tuple(map(Input, range(count))), typing.env, {})
        with suppress(UnderflowError):
            end = after(start, rest, arrows, need)
            if need is None or len(end.stack) >= need:
                found = resolved(start.stack, end)
                return tuple(
                    Kind.VALUE if isinstance(s, Input) else s for s in found
                )
    ending = "runs" if need is None else f"ends at {need}"
    raise FplError(
        hole.span, f"cannot infer {hole.name} : no count it leaves {ending}"
    )


def reach(code: tuple[Node, ...], arrows: Mapping[str, Arrow]) -> int:
    """Return the most values *code* can take from under it.

    Sums what each node takes. For a match the first row's patterns
    count, and the body that takes most. A hole takes none, since it
    takes only what is there.
    """
    total = 0
    for node in code:
        match node:
            case Call():
                total += (
                    len(arrows[node.name].ins) if node.name in arrows else 0
                )
            case Bind():
                total += 1 + reach(node.body, arrows)
            case Match():
                total += len(node.rows[0].patterns)
                total += max(reach(row.body, arrows) for row in node.rows)
            case Push() | Keyed() | Refuse():
                pass
            case _:
                assert_never(node)
    return total


def shown(arrow: Arrow) -> str:
    """Format an arrow as an effect line.

    An input is written ``t`` and its index.

    Examples:
        >>> shown(Arrow((Input(0), Kind.NUMBER), (Input(0),)))
        't0 Number -- t0'
    """
    names = [
        f"t{s.index}" if isinstance(s, Input) else s.value
        for s in (*arrow.ins, *arrow.outs)
    ]
    return " ".join([*names[: len(arrow.ins)], "--", *names[len(arrow.ins) :]])


def reported(goal: Goal) -> str:
    """Format a goal as the line :mod:`fpl.driver` reports.

    Examples:
        >>> reported(Goal(Span(3, 4), Arrow((Kind.NUMBER,), ())))
        'GOAL 3:4 ? : Number --'
    """
    return f"GOAL {goal.span.line}:{goal.span.col} ? : {shown(goal.arrow)}"


def through(
    typing: Typing,
    node: Node,
    arrows: Mapping[str, Arrow],
    need: int | None = None,
) -> Typing:
    """Return what is known once one node has run.

    Raises:
        FplError: The node cannot run, as for :func:`after`.
        UntypedError: The node is not typed.
    """
    match node:
        case Push():
            return replace(typing, stack=(*typing.stack, sort(node.value)))
        case Keyed():
            return replace(typing, stack=(*typing.stack, Kind.VALUE))
        case Bind():
            return bound(typing, node, arrows, need)
        case Call():
            return called(typing, node, arrows)
        case Match():
            return matched(typing, node, arrows, need)
        case Refuse():
            return replace(typing, reached=False)
        case _:
            assert_never(node)


def bound(
    typing: Typing, node: Bind, arrows: Mapping[str, Arrow], need: int | None
) -> Typing:
    """Elaborate a binder: name the top for its scope and run the scope.

    The name ends with the scope.

    Raises:
        UnderflowError: The stack is empty.
        FplError: The scope cannot run, as for :func:`after`.
        UntypedError: The scope is not typed.
    """
    if not typing.stack:
        raise UnderflowError(node.span)
    env = {**typing.env, node.name: typing.stack[-1]}
    end = after(
        replace(typing, stack=typing.stack[:-1], env=env),
        node.body,
        arrows,
        need,
    )
    return replace(end, env=typing.env)


def matched(
    typing: Typing, node: Match, arrows: Mapping[str, Arrow], need: int | None
) -> Typing:
    """Elaborate a match: run each row on the values under its patterns.

    A row's pattern names stand for values of no known sort. The result
    leaves the sorts the rows agree on, where they leave as many values.

    Every row counts, one after a sure fit included. A sort a row finds
    for an input holds for the rows after it and for the word, whichever
    row runs, and what a row that never runs leaves joins the agreement.
    So no pruning of rows lets the word leave a sort it does not promise
    (hole ``typed-fragment``). Pruning serves only :func:`chosen`.

    Raises:
        UnderflowError: The stack holds fewer values than the match
            takes.
        FplError: A row cannot run, as for :func:`after`.
        UntypedError: The rows leave different counts, or a row is not
            typed.
    """
    cut = len(typing.stack) - len(node.rows[0].patterns)
    if cut < 0:
        raise UnderflowError(node.span)
    ends: list[Typing] = []
    for row in node.rows:
        names = dict.fromkeys(bindings(row.patterns), Kind.VALUE)
        begun = replace(
            typing, stack=typing.stack[:cut], env={**typing.env, **names}
        )
        ends.append(after(begun, row.body, arrows, need))
        typing = replace(typing, known=ends[-1].known, goals=ends[-1].goals)
    return replace(typing, stack=agreed(ends))


def agreed(ends: list[Typing]) -> tuple[Sort, ...]:
    """Return the sorts the rows leave.

    Inputs are resolved by what every row found. Each position keeps the
    sort the rows agree on, the least every row's rises to
    (:func:`joined`), and is ``Kind.VALUE`` elsewhere. A row
    that refuses leaves nothing and does not count.

    Raises:
        UntypedError: The rows leave different counts.
    """
    stacks = {resolved(end.stack, ends[-1]) for end in ends if end.reached}
    if len({len(stack) for stack in stacks}) != 1:
        raise UntypedError
    return tuple(map(joined, map(set, zip(*stacks, strict=True))))


def bindings(patterns: tuple[Pattern, ...]) -> tuple[str, ...]:
    """Return the names the patterns bind, in the order written."""
    return tuple(name for pattern in patterns for name in bound_by(pattern))


def bound_by(pattern: Pattern) -> tuple[str, ...]:
    """Return the names one pattern binds."""
    match pattern:
        case Var():
            return (pattern.name,)
        case Guarded():
            return bound_by(pattern.pattern)
        case Inverse():
            return bindings(pattern.args)
        case Wild() | Equal():
            return ()
        case _:
            assert_never(pattern)


def called(typing: Typing, node: Call, arrows: Mapping[str, Arrow]) -> Typing:
    """Elaborate a call.

    A bound name pushes the sort it stands for. A word takes and leaves
    its arrow's sorts.

    Raises:
        UntypedError: The name is neither bound nor a word with an
            arrow.
        FplError: The word cannot take the sorts, as for
            :func:`applied`.
    """
    if node.name in typing.env:
        return replace(typing, stack=(*typing.stack, typing.env[node.name]))
    if node.name not in arrows:
        raise UntypedError
    return applied(
        typing, chosen(typing, arrows[node.name], arrows), node.span
    )


def chosen(typing: Typing, arrow: Arrow, arrows: Mapping[str, Arrow]) -> Arrow:
    """Return the arrow a call applies.

    A dispatcher's arrow is resolved to its clause's when exactly one
    row survives and the call is certain to reach that clause: the row
    surely fits, or the clause takes the sorts of the values. Where the
    row only may fit, the run would miss by refusing, so the clause must
    take them. A sort-indexed arrow is resolved by :func:`cased`. Any
    other arrow, and a dispatcher whose call cannot be resolved, is
    returned as it is.
    """
    cut = len(typing.stack) - len(arrow.ins)
    if cut < 0:
        return arrow
    sorts = resolved(typing.stack[cut:], typing)
    if isinstance(arrow, Cases):
        return cased(arrow, sorts)
    if isinstance(arrow, Dispatch):
        return dispatched(arrow, sorts, arrows)
    return arrow


def dispatched(
    arrow: Dispatch, sorts: tuple[Sort, ...], arrows: Mapping[str, Arrow]
) -> Arrow:
    """Return a dispatcher's clause arrow where the call must reach it.

    See :func:`chosen`; the arrow itself where it cannot be resolved.
    """
    if any(isinstance(s, Input) for s in sorts):
        return arrow
    match surviving(arrow.rows, sorts, arrows):
        case (Row(body=(*_, Call(name=clause))) as row,):
            found = arrows[clause]
            if verdict(row, sorts, arrows) is Verdict.YES or taken(
                found, sorts
            ):
                return found
            return arrow
        case _:
            return arrow


def cased(arrow: Cases, sorts: tuple[Sort, ...]) -> Arrow:
    """Return the first case that takes the sorts, else the arrow.

    An input of unknown sort, a ``Value`` and a sort no case takes keep
    the general arrow.

    Examples:
        >>> cased(ARROWS["succ"], (Kind.NEG1,)).outs == (Kind.NEG0,)
        True
        >>> cased(ARROWS["succ"], (Kind.VALUE,)) is ARROWS["succ"]
        True
    """
    if any(isinstance(s, Input) or s is Kind.VALUE for s in sorts):
        return arrow
    return next((c for c in arrow.cases if taken(c, sorts)), arrow)


def surviving(
    rows: tuple[Row, ...], sorts: tuple[Sort, ...], arrows: Mapping[str, Arrow]
) -> tuple[Row, ...]:
    """Return the rows values of the sorts may take, in order.

    A row that surely misses is dropped, and none is kept after the
    first that surely fits.
    """
    kept: list[Row] = []
    for row in rows:
        fit = verdict(row, sorts, arrows)
        if fit is not Verdict.NO:
            kept.append(row)
        if fit is Verdict.YES:
            break
    return tuple(kept)


def verdict(
    row: Row, sorts: tuple[Sort, ...], arrows: Mapping[str, Arrow]
) -> Verdict:
    """Return how surely values of the sorts fit the row's patterns."""
    fits = (
        fitted(have, p, arrows)
        for have, p in zip(sorts, row.patterns, strict=True)
    )
    return min(fits, default=Verdict.YES)


def fitted(
    have: Sort, pattern: Pattern, arrows: Mapping[str, Arrow]
) -> Verdict:
    """Return how surely a value of the sort fits the pattern.

    A name or ``_`` surely does. A guarded pattern, an ascription ``x:
    w`` included, at most may, and surely not where its pattern or its
    test surely misses. A literal or a constructor may.
    """
    match pattern:
        case Var() | Wild():
            return Verdict.YES
        case Guarded():
            return min(
                fitted(have, pattern.pattern, arrows),
                tested(have, pattern.test, arrows),
            )
        case Equal() | Inverse():
            return Verdict.MAYBE
        case _:
            assert_never(pattern)


def tested(have: Sort, test: str, arrows: Mapping[str, Arrow]) -> Verdict:
    """Return how surely a test leaves 1 on a value of the sort.

    Never ``Verdict.YES``: the test word runs on the value only at run
    time, so a guarded row is never a sure fit and pruning never stops
    at it. A builtin type word surely does not on a known sort that
    neither rises to its own nor is risen to by it (a ``Number`` may be
    an ``Int``). On a related sort, on an input or on a value of no
    known sort it may, as any other test may, a type word the program
    redefines included.
    """
    want = TESTED.get(test)
    if want is None or arrows.get(test) is not ARROWS[test]:
        return Verdict.MAYBE
    if isinstance(have, Input) or have is Kind.VALUE:
        return Verdict.MAYBE
    related = rises(have, want) or rises(want, have)
    return Verdict.MAYBE if related else Verdict.NO


def taken(arrow: Arrow, sorts: tuple[Sort, ...]) -> bool:
    """Return whether the arrow takes values of the sorts.

    A general input takes any sort. A sort taken takes ``Kind.VALUE``
    and any sort that rises to it (:func:`rises`).

    Examples:
        >>> taken(NUMBERS, (Kind.NAT1, Kind.VALUE))
        True
        >>> taken(Arrow((Kind.NAT0,), ()), (Kind.INT,))
        False
        >>> taken(NUMBERS, (Kind.TEXT, Kind.NUMBER))
        False
    """
    pairs = zip(arrow.ins, sorts, strict=True)
    return all(fits(need, have) for need, have in pairs)


def fits(need: Sort, have: Sort) -> bool:
    """Return whether a value of sort *have* meets the input *need*."""
    if isinstance(need, Input) or have is Kind.VALUE:
        return True
    return isinstance(have, Kind) and rises(have, need)


def applied(typing: Typing, arrow: Arrow, span: Span) -> Typing:
    """Return *typing* with the arrow's inputs met and outputs placed.

    The inputs are met by the values under the top.

    Args:
        typing: What is known before the call.
        arrow: The arrow to apply.
        span: Where the call is.

    Raises:
        UnderflowError: The stack holds fewer values than the arrow
            takes.
        FplError: An input is met by a sort it cannot take.
    """
    cut = len(typing.stack) - len(arrow.ins)
    if cut < 0:
        raise UnderflowError(span)
    local: dict[int, Sort] = {}
    found = dict(typing.known)
    for need, have in zip(arrow.ins, typing.stack[cut:], strict=True):
        met(need, known(have, typing), local, found, span)
    outs = tuple(
        local[s.index] if isinstance(s, Input) else s for s in arrow.outs
    )
    return replace(typing, stack=(*typing.stack[:cut], *outs), known=found)


def met(
    need: Sort,
    have: Sort,
    local: dict[int, Sort],
    found: dict[int, Sort],
    span: Span,
) -> None:
    """Meet one input of an arrow with the sort of a value.

    A general input takes the value's sort, recorded in *local*. A
    number wants a number or a sort that rises to one: an input of the
    body met by one is found to be one, recorded in *found*.

    Args:
        need: The sort the arrow takes.
        have: The sort of the value.
        local: The sort each general input of the arrow took; updated.
        found: The sort found for each input of the body; updated.
        span: Where the call is.

    Raises:
        FplError: *have* is a known sort that is not ``Kind.VALUE`` and
            does not rise to *need*.

    Examples:
        >>> met(Kind.NUMBER, Kind.TEXT, {}, {}, Span(3, 4))
        Traceback (most recent call last):
            ...
        fpl.errors.FplError: ERROR: 3:4 arithmetic on a non-number
    """
    match need:
        case Input():
            local[need.index] = have
        case _ if isinstance(have, Input):
            found[have.index] = need
        case _ if not fits(need, have):
            raise FplError(span, "arithmetic on a non-number")
        case _:
            pass


def integral(value: int) -> Kind:
    """Return the smallest sort that holds an integer.

    Examples:
        >>> integral(2) is Kind.NAT1, integral(0) is Kind.ZERO
        (True, True)
        >>> integral(-1) is Kind.NEG1
        True
    """
    if value > 0:
        return Kind.NAT1
    return Kind.ZERO if value == 0 else Kind.NEG1


def sort(value: Value) -> Sort:
    """Return the sort of a value.

    A literal gets the smallest sort that holds it (:func:`integral`).
    A strand has the least sort all its items rise to (:func:`joined`).

    Examples:
        >>> sort(2) is Kind.NAT1, sort(0) is Kind.ZERO
        (True, True)
        >>> sort(-2) is Kind.NEG1
        True
        >>> sort(Decimal("1.5")) is Kind.NUMBER
        True
        >>> sort(Strand((0, 2))) is Kind.NAT0
        True
        >>> sort(Strand((1, "a"))) is Kind.VALUE
        True
    """
    match value:
        case int():
            return integral(value)
        case Decimal():
            return Kind.NUMBER
        case str():
            return Kind.TEXT
        case Symbol():
            return Kind.SYMBOL
        case Strand():
            return joined(set(map(sort, value.items)))
        case _:
            return Kind.VALUE

"""Run core programs as a step machine.

A :class:`State` holds the stack, the code still to run and the
definitions. :func:`step` runs one node of it, :func:`final` runs a
state to the end, and :func:`evaluate` runs the run lines of a whole
program. Works over the core AST of :mod:`fpl.ast_core` only.
"""

from collections import deque
from collections.abc import Callable, Iterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
from functools import partial
from typing import assert_never

import icontract

from fpl.ast_core import (
    DIGITS,
    EFFECTS,
    Bind,
    Call,
    Define,
    Dict,
    Equal,
    Guarded,
    Inverse,
    Keyed,
    Listed,
    Match,
    Node,
    Number,
    Pattern,
    Push,
    Quotation,
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
from fpl.errors import FailError, FplError, Span

#: A builtin word: called with the word's span and its arguments, it
#: returns the values it leaves.
type Builtin = Callable[..., tuple[Value, ...]]
#: The definitions in force, by word name.
type Words = Mapping[str, tuple[Node, ...]]
#: A control word: called with the word's span, the definitions and its
#: arguments, it returns the code to run in its place.
type Control = Callable[..., tuple[Node, ...]]
#: The values a pattern bound, by name.
type Bound = dict[str, Value]
#: The values on the stack, top last.
type Stack = tuple[Value, ...]

#: The least magnitude a number cannot have: ``10**DIGITS``.
LIMIT = 10**DIGITS


@dataclass(frozen=True)
class State:
    """The stack, the code still to run and the definitions by name."""

    #: The stack, top last.
    stack: tuple[Value, ...]
    #: The nodes still to run, next first.
    code: tuple[Node, ...]
    #: The definitions by word name.
    words: Words


def evaluate(
    statements: tuple[Statement, ...],
    fuel: int | None = None,
    *,
    spent: list[int | None] | None = None,
) -> tuple[tuple[Value, ...], ...]:
    """Run each run line of a program on a fresh stack.

    Args:
        statements: The definitions and run lines of the program.
        fuel: Steps each run line may take; ``None`` is no bound.
        spent: When given, each run line appends the steps it took, in
            order, even when it fails (``None`` for a line without a
            bound).

    Returns:
        The stack each run line leaves, in order.

    Raises:
        ValueError: *fuel* is below zero (from :func:`budget`), before
            the first step.
        :exc:`FplError`: A run line fails (from :func:`metered`), for
            instance with ``out of fuel``; :exc:`FailError` where a
            match finds no row.

    Note:
        A later definition of a word shadows an earlier one, for every
        line. For each defined word *w* there are three more:
        ``w/history`` pushes the definitions it shadows, oldest first,
        each as a quotation; ``w/doc`` pushes the docstring of the one
        in force; ``w/effect`` pushes its effect line
        (:func:`effect_line`).
    """
    budget(fuel)
    logged: dict[str, list[Define]] = {}
    for s in statements:
        if isinstance(s, Define):
            logged.setdefault(s.word, []).append(s)
    words = {word: log[-1].code for word, log in logged.items()}
    for word, log in logged.items():
        words[f"{word}/history"] = (
            Push(Listed(tuple(Quotation(d.code) for d in log[:-1]))),
        )
        words[f"{word}/doc"] = (Push(log[-1].doc),)
        words[f"{word}/effect"] = (Push(effect_line(log[-1])),)
    return tuple(
        metered(s, words, fuel, spent)
        for s in statements
        if isinstance(s, Run)
    )


def budget(fuel: int | None) -> None:
    """Refuse a fuel below zero.

    A negative fuel would be counted down by :class:`Meter` past zero
    and never stop the run.

    Raises:
        ValueError: *fuel* is below zero.

    Examples:
        >>> budget(None)
        >>> budget(-1)
        Traceback (most recent call last):
            ...
        ValueError: fuel below zero: -1
    """
    if fuel is not None and fuel < 0:
        raise ValueError(f"fuel below zero: {fuel}")


@dataclass
class Meter:
    """The steps left to a run line, and the line charged for them.

    :attr:`budget` is the bound at the start; the steps spent are
    ``budget - left`` when there is a bound.
    """

    #: Steps still allowed; ``None`` is no bound.
    left: int | None
    #: The run line the steps are charged to, for errors.
    span: Span
    #: The bound at the start, set from *left* after init.
    budget: int | None = field(init=False)

    def __post_init__(self) -> None:
        """Keep the starting bound; :attr:`left` counts down from it."""
        self.budget = self.left

    def spent(self) -> int | None:
        """Return the steps taken, or ``None`` without a bound."""
        if self.budget is None or self.left is None:
            return None
        return self.budget - self.left

    def spend(self) -> None:
        """Take one step.

        Raises:
            :exc:`FplError`: No step is left (``out of fuel``), reported
                at the line.
        """
        if self.left == 0:
            raise FplError(self.span, "out of fuel")
        if self.left is not None:
            self.left -= 1


#: The meter of the run line being evaluated.
FUEL: ContextVar[Meter] = ContextVar("fuel")
#: The meter used when no run line has set :data:`FUEL`: no bound.
UNMETERED = Meter(None, Span(1, 1))


def metered(
    run: Run,
    words: Words,
    fuel: int | None,
    spent: list[int | None] | None = None,
) -> tuple[Value, ...]:
    """Run one run line on a meter of its own.

    The steps of every run nested in the line are charged to the same
    meter.

    Args:
        run: The run line.
        words: The definitions in force.
        fuel: Steps the line may take; ``None`` is no bound.
        spent: When given, the steps taken are appended, even if the run
            then fails.

    Returns:
        The stack the run line leaves.

    Raises:
        :exc:`FplError`: The run fails (from :func:`final`), or recurses
            deeper than the Python stack allows (``recursion too deep``,
            at the line).
    """
    meter = Meter(fuel, run.span)
    token = FUEL.set(meter)
    try:
        return final(State((), run.code, words))
    except RecursionError:
        raise FplError(run.span, "recursion too deep") from None
    finally:
        if spent is not None:
            spent.append(meter.spent())
        FUEL.reset(token)


def effect_line(define: Define) -> Listed:
    """Write a word's effect line as a list of strings.

    The line reads ``ins -- outs``, a typed input as its two strings
    ``x:`` and its type, then ``+fail`` if the word may fail (hole
    effect-query).
    """
    effect = define.effect
    fails = ("+fail",) if effect.fails else ()
    typed = zip(effect.ins, effect.types, strict=True)
    ins = (text for name, part in typed for text in slotted(name, part))
    return Listed((*ins, "--", *effect.outs, *fails))


def slotted(name: str, part: str | None) -> tuple[str, ...]:
    """Write one input as an effect line spells it.

    That is ``name``, or ``name:`` and its type.

    Examples:
        >>> slotted("x", None)
        ('x',)
        >>> slotted("x", "Int")
        ('x:', 'Int')
    """
    return (name,) if part is None else (name + ":", part)


def final(state: State) -> tuple[Value, ...]:
    """Run a state until no code is left.

    A step reads only the first node and leaves the rest of the code
    behind what it puts in place. So each step is taken on its node
    alone, and the code still waiting is held here, next node last: a
    step costs the code it puts in place, not the code waiting. Stepping
    the whole state would copy the waiting code each step, which is
    quadratic in the steps of a recursion that leaves a call waiting
    each time (``f f``, #144). The stack and the values a step builds
    are still copied whole, so a loop that grows either each round stays
    quadratic in its steps.

    Each step is spent from the meter in :data:`FUEL`, if any.

    Returns:
        The stack once no code is left.

    Raises:
        :exc:`FplError`: The meter has no step left
            (:meth:`Meter.spend`), or a step fails (:func:`step`).
    """
    meter = FUEL.get(UNMETERED)
    stack, waiting = state.stack, list(reversed(state.code))
    while waiting:
        meter.spend()
        after = step(State(stack, (waiting.pop(),), state.words))
        stack = after.stack
        waiting.extend(reversed(after.code))
    return stack


def running(state: State) -> bool:
    """Return whether some code is left to run."""
    return bool(state.code)


@icontract.require(running)
def step(state: State) -> State:
    """Run the first node of a state.

    A push pushes its value. A call of a defined word puts that word's
    code in its place; a call of any other word is a builtin or control
    word (:func:`builtin`). A binder puts its scope in its place with
    the top standing for its name (:func:`binding`), a dict pushes the
    dict its values build (:func:`gathered`), and a match puts the body
    of the row it chose in its place (:func:`matching`).

    Raises:
        icontract.ViolationError: *state* has no code left.
        :exc:`FplError`: The node is a refusal, which raises its own
            error, or a callee fails; :exc:`FailError` where a match
            finds no row.
    """
    node, rest = state.code[0], state.code[1:]
    match node:
        case Push():
            return State((*state.stack, node.value), rest, state.words)
        case Bind():
            return binding(node, state, rest)
        case Keyed():
            return State(
                (*state.stack, gathered(node, state.words)), rest, state.words
            )
        case Call() if node.name in state.words:
            return State(
                state.stack, state.words[node.name] + rest, state.words
            )
        case Call():
            return builtin(node, state, rest)
        case Match():
            return matching(node, state, rest)
        case Refuse():
            raise FplError(node.span, node.message)
        case _:
            assert_never(node)


def binding(node: Bind, state: State, rest: tuple[Node, ...]) -> State:
    """Put a binder's scope in its place, the top standing for its name.

    Args:
        node: The binder.
        state: The state to step.
        rest: The nodes after the binder.

    Raises:
        :exc:`FplError`: The stack is empty (``stack underflow``).
    """
    if not state.stack:
        raise FplError(node.span, "stack underflow")
    scope = substitute(node.body, node.name, state.stack[-1])
    return State(state.stack[:-1], scope + rest, state.words)


def substitute(
    code: tuple[Node, ...], name: str, value: Value
) -> tuple[Node, ...]:
    """Replace each call of *name* in *code* by a push of *value*.

    Quotations are included. A binder of the same name shadows it for
    its scope.
    """
    return tuple(replaced(node, name, value) for node in code)


def replaced(node: Node, name: str, value: Value) -> Node:
    """Replace each call of *name* in one node by a push of *value*."""
    match node:
        case Call():
            return Push(value) if node.name == name else node
        case Push():
            return Push(held(node.value, name, value))
        case Bind():
            return rebinder(node, name, value)
        case Keyed():
            return rekeyed(node, name, value)
        case Match():
            return rematched(node, name, value)
        case Refuse():  # pragma: no cover -- a refusing row binds nothing
            return node
        case _:
            assert_never(node)


def rebinder(node: Bind, name: str, value: Value) -> Bind:
    """Substitute in a binder's body, unless it binds *name* anew."""
    body = (
        node.body if node.name == name else substitute(node.body, name, value)
    )
    return Bind(node.name, body, node.span)


def rekeyed(node: Keyed, name: str, value: Value) -> Keyed:
    """Substitute in each value of a dict."""
    return Keyed(
        tuple((key, replaced(n, name, value)) for key, n in node.entries),
        node.span,
    )


def rematched(node: Match, name: str, value: Value) -> Match:
    """Substitute in each row of a match."""
    return Match(
        tuple(rebound(row, name, value) for row in node.rows), node.span
    )


def rebound(row: Row, name: str, value: Value) -> Row:
    """Substitute in a row, up to the pattern that binds *name* anew.

    The patterns after that one, and the body, are left as they are.
    """
    patterns: list[Pattern] = []
    shadowed = False
    for pattern in row.patterns:
        patterns.append(pattern if shadowed else pinned(pattern, name, value))
        shadowed = shadowed or name in names(pattern)
    body = row.body if shadowed else substitute(row.body, name, value)
    return Row(tuple(patterns), body)


def pinned(pattern: Pattern, name: str, value: Value) -> Pattern:
    """Substitute in the nodes a pattern pins (``$name``)."""
    match pattern:
        case Equal():
            return Equal(replaced(pattern.node, name, value))
        case Inverse():
            args = tuple(pinned(p, name, value) for p in pattern.args)
            return Inverse(pattern.name, args, pattern.span)
        case Guarded():
            return Guarded(
                pinned(pattern.pattern, name, value),
                pattern.test,
                pattern.span,
            )
        case Wild() | Var():
            return pattern
        case _:
            assert_never(pattern)


def names(pattern: Pattern) -> frozenset[str]:
    """Return the names a pattern binds.

    Examples:
        >>> names(Var("x")) == {"x"}
        True
        >>> names(Wild())
        frozenset()
    """
    match pattern:
        case Var():
            return frozenset((pattern.name,))
        case Inverse():
            return frozenset[str]().union(*map(names, pattern.args))
        case Guarded():
            return names(pattern.pattern)
        case Wild() | Equal():
            return frozenset()
        case _:
            assert_never(pattern)


def matching(node: Match, state: State, rest: tuple[Node, ...]) -> State:
    """Replace a match by the body of the first row that fits.

    Each name a pattern bound stands for its value in the body.

    Args:
        node: The match.
        state: The state to step.
        rest: The nodes after the match.

    Raises:
        :exc:`FplError`: Fewer values than a row takes (``stack
            underflow``), or a pattern names a word that cannot run
            backwards (from :func:`matches`).
        :exc:`FailError`: No row fits (``+fail``).
    """
    cut = len(state.stack) - len(node.rows[0].patterns)
    if cut < 0:
        raise FplError(node.span, "stack underflow")
    for row in node.rows:
        bound = matches(row.patterns, state.stack[cut:], state.words)
        if bound is not None:
            code = row.body
            for name, value in bound.items():
                code = substitute(code, name, value)
            return State(state.stack[:cut], code + rest, state.words)
    raise FailError(node.span, "no row matches")


def matches(
    patterns: tuple[Pattern, ...], values: Stack, words: Words
) -> Bound | None:
    """Match each pattern against its value, left to right.

    A name bound by one pattern is pinned in those after it.

    Returns:
        The names bound, or ``None`` if one pattern does not fit.

    Raises:
        :exc:`FplError`: A pattern names a word that cannot run
            backwards (from :func:`matched`).
    """
    bound: Bound = {}
    for pattern, value in zip(patterns, values, strict=True):
        for name, earlier in bound.items():
            pattern = pinned(pattern, name, earlier)  # noqa: PLW2901 -- pinned in turn
        got = matched(pattern, value, words)
        if got is None:
            return None
        bound |= got
    return bound


def matched(pattern: Pattern, value: Value, words: Words) -> Bound | None:
    """Return what one pattern binds on a value, or ``None``.

    A guard fits when its pattern matches and its word then leaves ``1``
    on the value (hole guard-test).

    Raises:
        :exc:`FplError`: A guard word or a constructor fails (from
            :func:`guarded` and :func:`unbuilt`).
    """
    match pattern:
        case Wild():
            return {}
        case Var():
            return {pattern.name: value}
        case Equal():
            return {} if pattern.node == Push(value) else None
        case Guarded():
            return guarded(pattern, value, words)
        case Inverse():
            return unbuilt(pattern, value, words)
        case _:
            assert_never(pattern)


def guarded(guard: Guarded, value: Value, words: Words) -> Bound | None:
    """Return what the inner pattern binds, if the guard leaves ``1``.

    The word runs only on a value the inner pattern matched, so a row
    whose pattern refuses the value falls through even where the word
    would raise on it.

    Raises:
        :exc:`FplError`: The word fails other than by ``+fail`` (from
            :func:`tested`).
    """
    bound = matched(guard.pattern, value, words)
    return bound if bound is not None and tested(guard, value, words) else None


def tested(guard: Guarded, value: Value, words: Words) -> bool:
    """Return whether the guard word leaves ``1`` on the value.

    A ``+fail`` (:exc:`FailError`) is a miss and any other error in the
    word propagates as that error (design 09 §3.9).

    Raises:
        :exc:`FplError`: The word fails other than by ``+fail`` (from
            :func:`final`).
    """
    try:
        left = final(State((value,), (Call(guard.test, guard.span),), words))
    except FailError:
        return False
    return left == (1,)


def unbuilt(pattern: Inverse, value: Value, words: Words) -> Bound | None:
    """Return what the arguments bind on what the constructor gives.

    The constructor is run backwards on *value*.

    Raises:
        :exc:`FplError`: The constructor cannot run backwards (from
            :func:`undone`).
    """
    given = undone(pattern.name, (value,), words, pattern.span)
    if given is None or len(given) != len(pattern.args):
        return None
    return matches(pattern.args, given, words)


def undone(
    name: str,
    stack: Stack,
    words: Words,
    span: Span,
    trail: frozenset[str] = frozenset(),
) -> Stack | None:
    """Run a word backwards on the top of a stack.

    A defined word runs its body backwards, a primitive its entry in
    :data:`INVERSES`.

    Args:
        name: The word to run backwards.
        stack: The stack whose top the word builds.
        words: The definitions in force.
        span: The position of the pattern naming the word, for errors.
        trail: The words being run backwards already, to refuse a word
            inside its own body.

    Returns:
        The stack below the word's results, or ``None`` where the top is
        not a value the word builds.

    Raises:
        :exc:`FplError`: *name* is neither defined nor in
            :data:`INVERSES`, or is defined and inside its own body
            (``is not invertible``), or a node of its body cannot run
            backwards (from :func:`unrun`).
    """
    if name in words and name not in trail:
        state: Stack | None = stack
        for node in reversed(words[name]):
            if state is None:
                return None
            state = unrun(node, state, words, span, trail | {name})
        return state
    if name in words or name not in INVERSES:
        raise FplError(span, f"{name} is not invertible")
    return INVERSES[name](stack)


def unrun(
    node: Node, stack: Stack, words: Words, span: Span, trail: frozenset[str]
) -> Stack | None:
    """Run one node of a constructor's body backwards.

    A push takes its value back off the stack, a call runs the word
    backwards (:func:`undone`).

    Raises:
        :exc:`FplError`: The node is neither a push nor a call, or the
            call cannot run backwards (from :func:`undone`).
    """
    match node:
        case Push():
            return unpush(node.value, stack)
        case Call():
            return undone(node.name, stack, words, span, trail)
        case _:
            raise FplError(
                span, "a constructor is words and literals: not invertible"
            )


def unpush(value: Value, stack: Stack) -> Stack | None:
    """Return the stack below its top, when the top is *value*.

    Examples:
        >>> unpush(2, (1, 2))
        (1,)
        >>> unpush(3, (1, 2)) is None
        True
    """
    match stack:
        case (*below, top) if top == value:
            return tuple(below)
        case _:
            return None


def unswap(stack: Stack) -> Stack | None:
    """Run ``swap`` backwards, which swaps again.

    Examples:
        >>> unswap((1, 2, 3))
        (1, 3, 2)
        >>> unswap((1,)) is None
        True
    """
    match stack:
        case (*below, x, y):
            return (*below, y, x)
        case _:
            return None


def unpair(stack: Stack) -> Stack | None:
    """Run ``pair`` backwards: a two-item list becomes its two items.

    Examples:
        >>> unpair((0, Listed((1, 2))))
        (0, 1, 2)
        >>> unpair((0, Listed((1,)))) is None
        True
    """
    match stack:
        case (*below, Listed(items=(a, b))):
            return (*below, a, b)
        case _:
            return None


def uncons(stack: Stack) -> Stack | None:
    """Run ``cons`` backwards: split a list into first item and rest.

    Examples:
        >>> uncons((Listed((1, 2, 3)),))
        (1, Listed(items=(2, 3)))
        >>> uncons((Listed(()),)) is None
        True
    """
    match stack:
        case (*below, Listed(items=(x, *xs))):
            return (*below, x, Listed(tuple(xs)))
        case _:
            return None


#: Primitive words that can run backwards in a pattern, by word name.
INVERSES: dict[str, Callable[[Stack], Stack | None]] = {
    "swap": unswap,
    "pair": unpair,
    "cons": uncons,
}


def held(inner: Value, name: str, value: Value) -> Value:
    """Substitute in the code a pushed value holds."""
    match inner:
        case Quotation():
            return Quotation(substitute(inner.code, name, value))
        case Listed():
            return Listed(
                tuple(held(item, name, value) for item in inner.items)
            )
        case _:
            return inner


def gathered(node: Keyed, words: Words) -> Dict:
    """Build a dict by running each value on a fresh stack.

    Raises:
        :exc:`FplError`: A value leaves other than one value, or fails
            (from :func:`final`).
    """
    entries: list[tuple[str, Value]] = []
    for key, code in node.entries:
        stack = final(State((), (code,), words))
        if len(stack) != 1:
            raise FplError(node.span, "a dict value is one value")
        entries.append((key, stack[0]))
    return Dict(tuple(entries))


def builtin(call: Call, state: State, rest: tuple[Node, ...]) -> State:
    """Apply a builtin or control word to the values it takes.

    A builtin's results take the place of its arguments; a control
    word's code goes before the rest.

    Args:
        call: The call of the word.
        state: The state to step.
        rest: The nodes after the call.

    Raises:
        :exc:`FplError`: Fewer values than the word takes (``stack
            underflow``): an effect line promised more than its body
            left. Also whatever the word itself raises
            (:data:`BUILTINS`, :data:`CONTROLS`).
    """
    cut = len(state.stack) - len(EFFECTS[call.name].ins)
    if cut < 0:
        raise FplError(call.span, "stack underflow")
    below, taken = state.stack[:cut], state.stack[cut:]
    if call.name in CONTROLS:
        code = CONTROLS[call.name](call.span, state.words, *taken)
        return State(below, code + rest, state.words)
    return State(
        (*below, *BUILTINS[call.name](call.span, *taken)), rest, state.words
    )


def stepped(delta: int, span: Span, a: Value) -> tuple[Value, ...]:
    """Add *delta* to a number, or to each item of a strand.

    ``succ`` is ``stepped(1, ...)`` and ``pred`` ``stepped(-1, ...)``.

    Raises:
        :exc:`FplError`: As :func:`arithmetic`.

    Examples:
        >>> stepped(1, Span(1, 1), 2), stepped(-1, Span(1, 1), 0)
        ((3,), (-1,))
    """
    return arithmetic(lambda x, y: x + y, span, a, delta)


def floored(a: int, d: int) -> tuple[int, int]:
    """Divide with a floored quotient; the remainder takes d's sign.

    Examples:
        >>> floored(-7, 2), floored(7, -2), floored(-7, -2)
        ((-4, 1), (-4, -1), (3, -1))
    """
    return a // d, a % d


def euclidean(a: int, d: int) -> tuple[int, int]:
    """Divide with a remainder in ``0 <= r < |d|`` (Boute 1992).

    Examples:
        >>> euclidean(-7, 2), euclidean(7, -2), euclidean(-7, -2)
        ((-4, 1), (-3, 1), (4, 1))
    """
    r = a % abs(d)
    return (a - r) // d, r


def truncated(a: int, d: int) -> tuple[int, int]:
    """Divide with a quotient cut toward zero; r takes a's sign.

    The quotient is built from magnitudes, so a big integer never
    passes through a float.

    Examples:
        >>> truncated(-7, 2), truncated(7, -2), truncated(-7, -2)
        ((-3, -1), (-3, 1), (3, -1))
    """
    q = abs(a) // abs(d)
    q = -q if (a < 0) != (d < 0) else q
    return q, a - d * q


def divided(
    rule: Callable[[int, int], tuple[int, int]],
    part: int,
    span: Span,
    a: Value,
    d: Value,
) -> tuple[Value, ...]:
    """Leave the quotient (*part* 0) or remainder (1) of integers.

    ``a d kdiv`` leaves the quotient of *a* by *d*, ``a d kmod`` the
    remainder; strands map item by item as in :func:`arithmetic`.

    Args:
        rule: How the pair divides: :func:`floored`, :func:`euclidean`
            or :func:`truncated`.
        part: 0 for the quotient, 1 for the remainder.
        span: The word's position, for errors.
        a: The dividend.
        d: The divisor.

    Raises:
        :exc:`FplError`: An operand is not an integer (``arithmetic on a
            non-number``, the text of :func:`operands`), or a divisor
            is 0 (``division by zero``).

    Examples:
        >>> divided(floored, 1, Span(1, 1), Strand((7, 8)), 2)
        (Strand(items=(1, 0)),)
    """

    def op(x: Number, y: Number) -> Number:
        if isinstance(x, Decimal) or isinstance(y, Decimal):
            raise FplError(span, "arithmetic on a non-number")
        if y == 0:
            raise FplError(span, "division by zero")
        return rule(x, y)[part]

    return arithmetic(op, span, a, d)


def operands(value: Value, span: Span) -> tuple[Number, ...]:
    """Return a number as one operand, or a strand as its items.

    Raises:
        :exc:`FplError`: Anything else (``arithmetic on a non-number``).

    Examples:
        >>> operands(Strand((1, 2)), Span(1, 1))
        (1, 2)
        >>> operands(3, Span(1, 1))
        (3,)
    """
    items = value.items if isinstance(value, Strand) else (value,)
    numbers = tuple(item for item in items if isinstance(item, int | Decimal))
    if len(numbers) < len(items):
        raise FplError(span, "arithmetic on a non-number")
    return numbers


def arithmetic(
    op: Callable[[Number, Number], Number], span: Span, a: Value, b: Value
) -> tuple[Value, ...]:
    """Apply a pervasive operator to two values.

    A number meets a number, or each item of a strand; two strands meet
    item by item and must be as long.

    Args:
        op: The operator on two numbers.
        span: The word's position, for errors.
        a: The left operand.
        b: The right operand.

    Returns:
        The result, a strand if either operand was one.

    Raises:
        :exc:`FplError`: An operand is not a number or a strand of
            numbers (from :func:`operands`), two strands differ in
            length, or a result has :data:`DIGITS <fpl.ast_core.DIGITS>`
            digits or more before its point (``number too large``).

    Examples:
        >>> arithmetic(int.__add__, Span(1, 1), Strand((1, 2)), 10)
        (Strand(items=(11, 12)),)
    """
    xs, ys = operands(a, span), operands(b, span)
    if len(xs) != len(ys) and 1 not in (len(xs), len(ys)):
        raise FplError(span, "strands of unequal length")
    zs = tuple(
        op(xs[i % len(xs)], ys[i % len(ys)])
        for i in range(max(len(xs), len(ys)))
    )
    if any(abs(z) >= LIMIT for z in zs):
        raise FplError(span, "number too large")
    return (
        Strand(zs)
        if isinstance(a, Strand) or isinstance(b, Strand)
        else zs[0],
    )


def swap(_span: Span, a: Value, b: Value) -> tuple[Value, ...]:
    """Swap the top two values (``x y -- y x``)."""
    return b, a


def dup(_span: Span, a: Value) -> tuple[Value, ...]:
    """Duplicate the top value (``x -- x x``)."""
    return a, a


def drop(_span: Span, _a: Value) -> tuple[Value, ...]:
    """Drop the top value (``x --``)."""
    return ()


def enclose(_span: Span, a: Value) -> tuple[Value, ...]:
    """Quote the top value (``x -- [x]``)."""
    return (Quotation((Push(a),)),)


def join(span: Span, a: Value, b: Value) -> tuple[Value, ...]:
    """Join two quotations into one, or two lists into one.

    Raises:
        :exc:`FplError`: The values are not two quotations or two lists.

    Examples:
        >>> join(Span(1, 1), Listed((1,)), Listed((2,)))
        (Listed(items=(1, 2)),)
    """
    match a, b:
        case Quotation(), Quotation():
            return (Quotation(a.code + b.code),)
        case Listed(), Listed():
            return (Listed(a.items + b.items),)
        case _:
            raise FplError(span, ", joins two quotations or two lists")


def pair(_span: Span, a: Value, b: Value) -> tuple[Value, ...]:
    """Make a two-item list of the top two values (``a b -- p``).

    See hole pair-shape.
    """
    return (Listed((a, b)),)


def cons(span: Span, x: Value, xs: Value) -> tuple[Value, ...]:
    """Put a value before the items of a list (``x xs -- ys``).

    Raises:
        :exc:`FplError`: *xs* is not a list.

    Examples:
        >>> cons(Span(1, 1), 0, Listed((1,)))
        (Listed(items=(0, 1)),)
    """
    if not isinstance(xs, Listed):
        raise FplError(span, "cons takes a list")
    return (Listed((x, *xs.items)),)


def typed(kind: type[object], _span: Span, value: Value) -> tuple[Value, ...]:
    """Test a value's type (``x -- b``).

    Args:
        kind: The type a value, or each item of a strand, must be an
            instance of.
        value: The value to test.

    Returns:
        ``1`` when the value is of the type, or is a strand whose items
        all are; ``0`` on any other value, an empty strand included.

    Examples:
        >>> typed(int, Span(1, 1), Strand((1, 2)))
        (1,)
        >>> typed(int, Span(1, 1), Strand(()))
        (0,)
    """
    items = value.items if isinstance(value, Strand) else (value,)
    return (
        int(bool(items) and all(isinstance(item, kind) for item in items)),
    )


def unfilled(span: Span) -> tuple[Value, ...]:
    """Refuse a goal left in the code, where it runs.

    See hole goal-placeholder.

    Raises:
        :exc:`FplError`: Always (``unfilled goal``).
    """
    raise FplError(span, "unfilled goal")


def nothing(_span: Span) -> tuple[Value, ...]:
    """Leave nothing, for a ``_`` the elaborator inferred as nothing.

    See hole infer-hole.
    """
    return ()


#: Builtin words by name, each called as ``fn(span, *args)``.
BUILTINS: dict[str, Builtin] = {
    "+": partial(arithmetic, lambda x, y: x + y),
    "-": partial(arithmetic, lambda x, y: x - y),
    "times": partial(arithmetic, lambda x, y: x * y),
    "succ": partial(stepped, 1),
    "pred": partial(stepped, -1),
    "kdiv": partial(divided, floored, 0),
    "kmod": partial(divided, floored, 1),
    "bdiv": partial(divided, euclidean, 0),
    "bmod": partial(divided, euclidean, 1),
    "tdiv": partial(divided, truncated, 0),
    "tmod": partial(divided, truncated, 1),
    "swap": swap,
    "dup": dup,
    "?": unfilled,
    "_": nothing,
    "drop": drop,
    "enclose": enclose,
    ",": join,
    "pair": pair,
    "cons": cons,
    "Int": partial(typed, int),
    "Decimal": partial(typed, Decimal),
    "Text": partial(typed, str),
    "Symbol": partial(typed, Symbol),
}


def quoted(value: Value, span: Span) -> Quotation:
    """Return *value* as a quotation.

    Raises:
        :exc:`FplError`: *value* is not a quotation.
    """
    if not isinstance(value, Quotation):
        raise FplError(span, "a quotation is expected")
    return value


def force(span: Span, _words: Words, q: Value) -> tuple[Node, ...]:
    """Run a quotation in place (``q --``).

    A quotation fills a thunk slot, as every control word's quotation
    does.

    Raises:
        :exc:`FplError`: *q* is not a quotation (from :func:`quoted`).
    """
    return quoted(q, span).code


def choose(
    span: Span, _words: Words, c: Value, t: Value, e: Value
) -> tuple[Node, ...]:
    """Run *t* in place on ``1``, *e* on ``0`` (``c t e --``).

    See hole truth-values.

    Raises:
        :exc:`FplError`: *c* is not ``0`` or ``1``, or *t* or *e* is not
            a quotation (from :func:`quoted`).
    """
    branches = quoted(e, span), quoted(t, span)
    if not isinstance(c, int) or c not in (0, 1):
        raise FplError(span, "if takes 0 or 1")
    return branches[c].code


def commute(
    span: Span, _words: Words, x: Value, y: Value, q: Value
) -> tuple[Node, ...]:
    """Run a quotation in place on the two values below it, swapped.

    The stack effect is ``x y q --``.

    Raises:
        :exc:`FplError`: *q* is not a quotation (from :func:`quoted`).
    """
    return (Push(y), Push(x), *quoted(q, span).code)


def repeat(span: Span, _words: Words, q: Value, n: Value) -> tuple[Node, ...]:
    """Run a quotation in place *n* times (``q n --``).

    Each round puts back one *q* and the rest of the count, so the code
    grows by one *q*, not *n*.

    Raises:
        :exc:`FplError`: *q* is not a quotation (from :func:`quoted`),
            or *n* is not a count (a non-negative int).
    """
    code = quoted(q, span).code
    if not isinstance(n, int) or n < 0:
        raise FplError(span, "repeat takes a count")
    if n == 0:
        return ()
    return (*code, Push(q), Push(n - 1), Call("repeat", span))


def items(xs: Value, span: Span) -> tuple[Value, ...]:
    """Return the items of a strand or a list.

    Raises:
        :exc:`FplError`: *xs* is neither.
    """
    if not isinstance(xs, Strand | Listed):
        raise FplError(span, "a strand or a list is expected")
    return xs.items


def single(state: State, span: Span) -> Value:
    """Run a state and return the one value it leaves (hole step-stack).

    Raises:
        :exc:`FplError`: The run leaves other than one value, or fails
            (from :func:`final`).
    """
    stack = final(state)
    if len(stack) != 1:
        raise FplError(span, "each step leaves one value")
    return stack[0]


def rebuilt(xs: Value, values: list[Value]) -> Push:
    """Push the results as a strand or as a list (hole sequence-shape).

    A strand is made when *xs* was one and every result is a number or a
    string, a list otherwise.
    """
    atoms = tuple(v for v in values if isinstance(v, int | Decimal | str))
    if isinstance(xs, Strand) and len(atoms) == len(values):
        return Push(Strand(atoms))
    return Push(Listed(tuple(values)))


def running_results(
    span: Span, words: Words, xs: Value, q: Value
) -> Iterator[Value]:
    """Yield each result of a fold over the items.

    The first item, then *q* run on the result so far and the next item.
    One at a time, so a fold need not hold the ones it has passed.

    Yields:
        Each result of the fold, nothing for no items.

    Raises:
        :exc:`FplError`: *q* is not a quotation (from :func:`quoted`),
            *xs* is not a strand or a list (from :func:`items`), or a
            step does not leave one value (from :func:`single`).
    """
    code = quoted(q, span).code
    values = items(xs, span)
    if not values:
        return
    result = values[0]
    yield result
    for x in values[1:]:
        result = single(State((result, x), code, words), span)
        yield result


def each(span: Span, words: Words, xs: Value, q: Value) -> tuple[Node, ...]:
    """Run a quotation on each item alone (``xs q -- ys``).

    Raises:
        :exc:`FplError`: As :func:`quoted`, :func:`items` and
            :func:`single`.
    """
    code = quoted(q, span).code
    return (
        rebuilt(
            xs,
            [single(State((x,), code, words), span) for x in items(xs, span)],
        ),
    )


def scan(span: Span, words: Words, xs: Value, q: Value) -> tuple[Node, ...]:
    """Collect every result a fold passes through (``xs q -- ys``).

    Raises:
        :exc:`FplError`: As :func:`running_results`.
    """
    return (rebuilt(xs, list(running_results(span, words, xs, q))),)


def fold(span: Span, words: Words, xs: Value, q: Value) -> tuple[Node, ...]:
    """Reduce the items to the last result of the scan (``xs q -- x``).

    Raises:
        :exc:`FplError`: There is no item to start from (``fold over
            nothing``), or as :func:`running_results`.
    """
    last = deque(running_results(span, words, xs, q), maxlen=1)
    if not last:
        raise FplError(span, "fold over nothing")
    return (Push(last[0]),)


#: Control words by name, each called as ``fn(span, words, *args)``.
CONTROLS: dict[str, Control] = {
    "!": force,
    "if": choose,
    "swap-args": commute,
    "repeat": repeat,
    "each": each,
    "scan": scan,
    "fold": fold,
}

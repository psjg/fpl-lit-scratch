"""
Every error is a subclass at its place in the tree under err/: its tag
is its parent's and one more segment, each leaf is what its raise site
raises, and no module raises or builds the bare FplError.
"""

import ast
from pathlib import Path

import pytest
from test_session import CONTEXT, entered

import fpl.fon
import fpl.session
from fpl.driver import checked, run, stacks
from fpl.errors import (
    AmbiguousCallError,
    AmbiguousClauseError,
    AmbiguousQueryError,
    CheckFormError,
    ClauseError,
    CommentError,
    DictError,
    EachError,
    EffectError,
    EmptyFoldError,
    FailError,
    FplError,
    GoalError,
    MatchError,
    MismatchedError,
    ModifierError,
    NoEvaluatorError,
    NoFailError,
    NotInvertibleError,
    NotListError,
    NotNumberError,
    NotQuotationError,
    OutOfGasError,
    PatternError,
    PrintError,
    RecursionDepthError,
    RowError,
    SessionError,
    StrayDedentError,
    TabsError,
    TooDeepError,
    TooLargeError,
    TooLongError,
    UnclosedError,
    UnderflowError,
    UnequalError,
    UnequalStrandsError,
    UnexpectedError,
    UnknownWordError,
    UnmatchedFailError,
    UnopenedError,
)

#: The package whose modules may raise only subclasses.
PACKAGE = Path(fpl.fon.__file__).parent

P3 = (
    "g : x: Int  y -- z\n\tdrop drop #left\n"
    "g : x  y: Int -- z\n\tdrop drop #right\n"
)
P4 = "f : x y -- z\n\t+\nf : x -- y\n\t1 +\n"
H = (
    "Text : x -- b\n\tdrop 1\n"
    "h : x: Int  y: Int  z -- o\n\tdrop drop drop 1\n"
    "h : x: Text  y  z: Int -- o\n\tdrop drop drop 1\n"
)
TWICE = (
    "twice : x -- y\n\tdup +\n"
    "f : a b -- c\n\tmatch\n\t\ty\t( twice x )\tx\n1 | 2 f\n"
)
MATCH = "f : x -- y\n\tmatch\n"

#: For each leaf that :func:`fpl.driver.run` reaches, a program that
#: raises it, and the error line it prints.
RAISED: dict[type[FplError], tuple[str, str]] = {
    UnclosedError: ("[ 1 2\n", "1:1 [ never closed"),
    UnopenedError: ("a ]\n", "1:3 ] closes nothing"),
    MismatchedError: ("[ a )\n", "1:5 ) does not close ["),
    TabsError: ("a\n  b\n", "2:1 indentation must be tabs"),
    StrayDedentError: (
        "a\n\t\tb\n\tc\n",
        "3:2 dedent to a level never opened",
    ),
    TooDeepError: (
        "[" * 1000 + "]" * 1000 + "\n",
        "1:1 nesting too deep to read",
    ),
    ModifierError: ("a´b\n", "1:1 a modifier ends its word: a´b"),
    CommentError: ("a ;; d\n", "1:3 a ;; comment stands on a line of its own"),
    UnexpectedError: ("a\x0b\n", "1:2 unexpected input"),
    TooLongError: ("9" * 4097 + "\n", "1:1 number too long"),
    RowError: (MATCH + "\t\t_\t_\t1\n", "3:3 a row is 1 patterns and a body"),
    MatchError: (MATCH + "\t\t; a comment\n1 f\n", "2:2 a match has no rows"),
    PatternError: (MATCH + "\t\t( cons )\t1\n", "3:5 cons takes 2 patterns"),
    DictError: ("{ a 1 a 2 }\n", "1:7 repeated key a"),
    EffectError: (
        "f : x -- y\n\tdrop\n",
        "1:1 f leaves 0 values, its effect line 1",
    ),
    ClauseError: (
        "f : x -- y\n\t1\nf : t: [ ] -- y\n\t2\n",
        "3:1 f/1/2 takes a thunk at 1, f/1/1 a value",
    ),
    CheckFormError: (
        "1 |- ! err/no-row\n",
        "1:1 a fail judgment closes the program",
    ),
    AmbiguousClauseError: (
        P3 + "1 | 2 g\n",
        "3:1 g/2/2 is ambiguous with g/2/1 at x: Int  y: Int",
    ),
    AmbiguousCallError: (
        H + "1 | 2 | 3 h\n",
        "3:1 ambiguous call to h: h/3/1 and h/3/2 both fit",
    ),
    AmbiguousQueryError: (
        P4 + "f/effect\n",
        "5:1 f/effect names more than one group: f/1 f/2",
    ),
    NotNumberError: ("[ ] 1 +\n", "1:7 arithmetic on a non-number"),
    NotQuotationError: ("1 !\n", "1:3 a quotation is expected"),
    NotListError: ("3 [+] foldr\n", "1:7 a strand or a list is expected"),
    NotInvertibleError: (TWICE, "5:7 + is not invertible"),
    UnequalStrandsError: ("1 2 | 1 2 3 +\n", "1:13 strands of unequal length"),
    EmptyFoldError: ("⟨⟩ [+] fold\n", "1:8 fold over nothing"),
    EachError: ("1 2 [drop drop] foldr\n", "1:17 each step leaves one value"),
    GoalError: ("f : x -- y\n\t?\n1 f\n", "2:2 unfilled goal"),
    NoEvaluatorError: ("3 debug\n", "1:3 no evaluator yet: debug"),
    UnknownWordError: ("3 gone\n", "1:3 unknown word: gone"),
    UnderflowError: ("g : -- y\n\t[ ] !\ng →x\n", "3:3 stack underflow"),
    FailError: (MATCH + "\t\t0\t1\n5 f\n", "2:2 no row matches"),
    TooLargeError: ("9" * 4096 + " | 1 +\n", "1:4102 number too large"),
    RecursionDepthError: (
        "f : x -- y\n\t1 2 [f] each\n1 f\n",
        "3:1 recursion too deep",
    ),
    PrintError: (
        "1" + " enclose" * 3000 + "\n",
        "1:1 nesting too deep to print",
    ),
    UnequalError: ("1 |- 2\n", "1:1 check failed: 1 is not 2"),
    UnmatchedFailError: (
        "3 gone\n|- ! err/no-row\n",
        "2:1 check failed: expected err/no-row,"
        " got err/unresolved/unknown-word",
    ),
    NoFailError: (
        "1\n|- ! err/no-row\n",
        "2:1 check failed: expected err/no-row, the program passed",
    ),
}
#: The leaves that :func:`fpl.driver.run` does not reach, each tested
#: on its own below: a document refusal, the fuel (which ``run`` fixes
#: at a million steps) and the margin of a session input.
ELSEWHERE = {fpl.fon.FonError, OutOfGasError, SessionError}


def tree(root: type[FplError]) -> list[type[FplError]]:
    """Return *root* and every subclass below it, loaded now.

    Args:
        root: The class to start from.

    Returns:
        The classes, *root* first, each before its subclasses.

    Examples:
        >>> [kind.__name__ for kind in tree(UnequalError.__base__)][:2]
        ['CheckError', 'UnequalError']
    """
    found = [root]
    for kind in root.__subclasses__():
        found.extend(tree(kind))
    return found


SUBCLASSES = tree(FplError)[1:]


@pytest.mark.parametrize("error", SUBCLASSES, ids=lambda e: e.__name__)
def test_a_tag_is_its_parents_and_one_segment(error: type[FplError]) -> None:
    (parent,) = error.__bases__
    assert issubclass(parent, FplError)
    head, segment = error.tag.rsplit("/", 1)
    assert head == parent.tag
    assert segment


def test_each_tag_names_one_class() -> None:
    tags = [error.tag for error in SUBCLASSES]
    assert len(set(tags)) == len(tags)


def test_every_leaf_is_raised_by_a_program_or_tested_elsewhere() -> None:
    leaves = {error for error in SUBCLASSES if not error.__subclasses__()}
    assert leaves == set(RAISED) | ELSEWHERE


@pytest.mark.parametrize("error", RAISED, ids=lambda e: e.__name__)
def test_a_raise_site_raises_its_leaf(error: type[FplError]) -> None:
    source, line = RAISED[error]
    with pytest.raises(FplError) as caught:
        run(source)
    assert type(caught.value) is error
    assert str(caught.value) == f"ERROR: {line}"


def test_a_run_past_its_fuel_is_out_of_gas() -> None:
    with pytest.raises(FplError) as caught:
        stacks(checked("1 2 +\n")[0], 0)
    assert type(caught.value) is OutOfGasError


def test_an_indented_session_input_is_a_session_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reraise(
        _entry: object, error: FplError, *_: object, **__: object
    ) -> None:
        raise error

    log, _ = entered(["1\n"])
    monkeypatch.setattr(fpl.session, "_failed", reraise)
    with pytest.raises(SessionError, match=r"^ERROR: 2:1 an input starts"):
        fpl.session.enter(log, "\t3\n", CONTEXT, log.head)


def test_a_refused_document_is_a_fon_error() -> None:
    with pytest.raises(fpl.fon.FonError) as caught:
        fpl.fon.read("[")
    assert caught.value.tag == "err/fon"


def bare(source: str) -> list[int]:
    r"""Return the lines of *source* that raise or build the bare base.

    Args:
        source: The text of a Python module.

    Returns:
        The line of each ``raise FplError`` and each ``FplError(...)``,
        raised or not: the base is only ever a base.

    Examples:
        >>> bare("raise FplError(s, m)\nraise X(s)\nraise FplError\n")
        [1, 3]
        >>> bare("e = FplError(s, m)\nclass E(FplError): pass\n")
        [1]
    """
    lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        named: ast.expr | None
        if isinstance(node, ast.Call):
            named = node.func
        elif isinstance(node, ast.Raise):
            named = node.exc
        else:
            continue
        if isinstance(named, ast.Name) and named.id == "FplError":
            lines.add(node.lineno)
    return sorted(lines)


@pytest.mark.parametrize(
    "module", sorted(PACKAGE.glob("*.py")), ids=lambda p: p.name
)
def test_no_module_raises_or_builds_the_bare_base(module: Path) -> None:
    assert bare(module.read_text()) == []

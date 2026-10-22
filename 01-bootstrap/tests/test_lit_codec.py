"""
The codecs of 01.01.05-codec carry every stage's value as FON and back
unchanged.

The checks run in a child interpreter over the tangled tree
(tests/lit.py). They compare values and bytes, never FON text, so they
hold whatever syntax `fon.write` chooses: a value read back equals the
value, and a second trip writes the same bytes as the first.
"""

import ast
import json

from corpus import PROGRAMS
from lit import PYTHON, lit

PRELUDE = """
import dataclasses, json, sys
from decimal import Decimal
from fpl.codec import (
    CODECS, CORE, ERROR, SOURCE, STACKS, SYNTAX, TOKENS, from_fon,
    read_repr, to_fon,
)
from fpl.errors import FplError, Span


def spans(x):
    if isinstance(x, Span):
        return [x]
    if isinstance(x, (tuple, list)):
        return [s for item in x for s in spans(item)]
    if isinstance(x, dict):
        return [s for item in x.values() for s in spans(item)]
    if dataclasses.is_dataclass(x):
        return [
            s for f in dataclasses.fields(x) for s in spans(getattr(x, f.name))
        ]
    return []


def same(x):
    if isinstance(x, FplError):
        return type(x), x.span, x.message
    return x


def trip(codec, x):
    once = codec.fonify(x)
    back = codec.defonify(once)
    problems = []
    if same(back) != same(x):
        problems.append("value")
    if spans(back) != spans(x):
        problems.append("spans")
    if codec.fonify(back) != once:
        problems.append("bytes")
    if read_repr(once) != codec.repr:
        problems.append("repr")
    return back, problems
"""

CORPUS = """
from fpl.desugar import desugar
from fpl.elaborate import elaborate
from fpl.evaluate import evaluate
from fpl.lex import lex
from fpl.parse import parse
from fpl.print import render

checked, failed = 0, []
for path in json.loads(sys.argv[1]):
    text = open(path, encoding="utf-8").read()
    value, stages = text, (
        (SOURCE, None), (TOKENS, lex), (SYNTAX, parse), (CORE, desugar),
        (CORE, elaborate), (STACKS, evaluate),
    )
    for codec, stage in stages:
        try:
            value = value if stage is None else stage(value)
        except FplError as error:
            back, problems = trip(ERROR, error)
            if (type(back), str(back)) != (type(error), str(error)):
                problems.append("error")
            checked += 1
            failed += [f"{path} Error {p}" for p in problems]
            break
        back, problems = trip(codec, value)
        if codec is SYNTAX and render(back) != render(value):
            problems.append("render")
        checked += 1
        failed += [f"{path} {codec.repr} {p}" for p in problems]
print(json.dumps({"checked": checked, "failed": failed}))
"""


def child(code: str, *args: str) -> str:
    """
    Run the prelude and `code` against the tangled tree; its stdout.
    """
    result = lit(
        "import sys; sys.argv[1:] = "
        + json.dumps(list(args))
        + "\n"
        + PRELUDE
        + code
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout.decode()


def test_every_stage_value_of_every_example_round_trips() -> None:
    """
    Over the maintainer's examples, each stage's value, or the error a
    stage raised, comes back equal, spans included, and rewrites to the
    same bytes.
    """
    report = json.loads(child(CORPUS, json.dumps([str(p) for p in PROGRAMS])))
    assert report["failed"] == []
    assert report["checked"] >= 3 * len(PROGRAMS)


def test_numbers_text_symbols_and_absence_stay_apart() -> None:
    """
    2, 2.0 and 2.50 are three values, text and a symbol two, and each
    comes back as the kind it went in as.
    """
    code = """
from fpl.ast_core import Symbol
values = (
    2, -7, Decimal("2.0"), Decimal("2.50"), Decimal("-0.0"), "x",
    Symbol("x"), True, False, None, (), {}, "“ 「 ⟨ ⟩",
)
out = []
for v in values:
    back = from_fon(to_fon(v))
    out.append([type(back).__name__, str(back), back == v])
print(json.dumps(out))
"""
    got = json.loads(child(code))
    assert got == [
        ["int", "2", True],
        ["int", "-7", True],
        ["Decimal", "2.0", True],
        ["Decimal", "2.50", True],
        ["Decimal", "-0.0", True],
        ["str", "x", True],
        ["Symbol", "Symbol(name='x')", True],
        ["bool", "True", True],
        ["bool", "False", True],
        ["NoneType", "None", True],
        ["tuple", "()", True],
        ["dict", "{}", True],
        ["str", "“ 「 ⟨ ⟩", True],
    ]


def test_the_corners_of_the_trees_round_trip() -> None:
    """
    A string's island program, a level-3 comment, an effect with slots
    and types, a dispatched word's clause, and a match with every
    pattern kind come back equal, spans and keyword fields included.
    """
    code = """
from fpl.ast_core import (
    Call, Define, Effect, Equal, Guarded, Inverse, Match, Push, Row, Run,
    Var, Wild,
)
from fpl.ast_surface import (
    Cell, Comment, Frame, Line, Program, Text, Word,
)

one = Word("", "number", ("1",), "", Span(1, 5))
inner = Program((Line((Frame((Cell((one,), Span(1, 5)),), Span(1, 5)),), (),
                      Span(1, 5)),), Span(1, 5))
text = Text("str", ("a ", inner, " b"), Span(1, 1))
island = Program(
    (
        Line((Frame((Cell((text,), Span(1, 1)),), Span(1, 1)),), (),
             Span(1, 1)),
        Line((), (), Span(2, 1), Comment(3, (";;; three",), Span(2, 1))),
    ),
    Span(1, 1),
)
effect = Effect(
    ("q", "n"), ("x",), True, slots=("thunk", "value"), types=("Int", None)
)
match = Match(
    (
        Row(
            (
                Guarded(Var("x"), "Int", Span(2, 3)),
                Inverse(
                    "pair", (Wild(), Equal(Push(Decimal("1.5")))), Span(4, 5)
                ),
            ),
            (Call("+", Span(6, 7)),),
        ),
    ),
    Span(1, 1),
)
core = (
    Define("f", effect, (match,), "doc", Span(3, 4), (2,), ("f/2/1", "f/2/2")),
    Define("f", effect, (Push(1),), "", Span(5, 1), (2, 1)),
    Run((Push(()),), Span(9, 2)),
)
print(json.dumps([trip(SYNTAX, island)[1], trip(CORE, core)[1]]))
"""
    assert json.loads(child(code)) == [[], []]


def test_errors_keep_their_class_span_and_message() -> None:
    """
    An UnresolvedError and an UnderflowError, whose constructor takes
    only a span, come back as themselves.
    """
    code = """
from fpl.elaborate import UnderflowError
from fpl.errors import UnresolvedError
out = []
for error in (UnresolvedError(Span(3, 4), "unknown word x"),
              UnderflowError(Span(1, 2)), FplError(Span(5, 6), "plain")):
    back, problems = trip(ERROR, error)
    out.append([type(back).__name__, str(back), problems])
print(json.dumps(out))
"""
    assert json.loads(child(code)) == [
        ["UnresolvedError", "ERROR: 3:4 unknown word x", []],
        ["UnderflowError", "ERROR: 1:2 stack underflow", []],
        ["FplError", "ERROR: 5:6 plain", []],
    ]


def test_a_document_names_its_representation() -> None:
    """
    Each codec is keyed by the representation it carries, and decoding
    a document of another one is refused, naming both.
    """
    code = """
from fpl.lex import lex
tokens = TOKENS.fonify(lex("1 2 +\\n"))
try:
    CODECS["Syntax"].defonify(tokens)
except ValueError as refusal:
    message = str(refusal)
print(json.dumps([sorted(CODECS), read_repr(tokens), message]))
"""
    assert json.loads(child(code)) == [
        ["Core", "Error", "Source", "Stacks", "Syntax", "Tokens"],
        "Tokens",
        "expected Syntax, got Tokens",
    ]


def test_a_numeral_at_the_digit_limit_round_trips_with_its_sign() -> None:
    """
    The longest numeral the language admits, minus sign included, is a
    longer FON word than the reader's default allows; the document
    reader accepts it.
    """
    code = """
from fpl.desugar import desugar
from fpl.lex import lex
from fpl.parse import parse
out = []
for sign in ("", "-"):
    core = desugar(parse(lex(sign + "9" * 4096 + "\\n")))
    out.append(CORE.defonify(CORE.fonify(core)) == core)
print(json.dumps(out))
"""
    assert json.loads(child(code)) == [True, True]


def test_the_codec_imports_only_data() -> None:
    """
    FON only materialises data: the codec imports the value modules and
    the FON module, never a pass, the printer or the command line.
    """
    tree = ast.parse((PYTHON / "fpl" / "codec.py").read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    allowed = {
        "fpl",
        "fpl.ast_core",
        "fpl.ast_surface",
        "fpl.errors",
        "fpl.fon",
        "fpl.lex",
    }
    assert {name for name in imported if name.startswith("fpl")} <= allowed
    assert {name.split(".")[0] for name in imported} <= {
        "fpl",
        "dataclasses",
        "decimal",
        "typing",
    }

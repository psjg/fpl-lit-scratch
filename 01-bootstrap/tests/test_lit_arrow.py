"""
A composition of passes is data: `PassCompose`, from 01.04.01-pass.

`>>` builds a flat tuple of passes that can be listed, printed, checked
for matching representations and run by `direct`. Every assertion runs
in one child interpreter against the tangled tree (see lit.py).
"""

from lit import BOOTSTRAP, lit

CHECKS = r"""
from fpl.arrow import Pass, PassCompose, direct, pass_compose
from fpl.desugar import desugar
from fpl.lex import lex
from fpl.parse import parse
from fpl.run import COMPOSITIONS, run_now

front = lex >> parse
assert isinstance(front, PassCompose), type(front)
assert tuple(p.name for p in front.stages) == ("lex", "parse")
assert front.name == "lex>>parse", front.name

left = (lex >> parse) >> desugar
right = lex >> (parse >> desugar)
assert left == right == pass_compose(lex, parse, desugar)
assert left == pass_compose(front, desugar)
assert left.stages == (lex, parse, desugar)
assert (left.source, left.target) == ("Source", "Core")

assert str(front) == repr(front) == "pass_compose(lex, parse)"
assert str(run_now) == (
    "pass_compose(lex, parse, desugar, elaborate, eval)"
), str(run_now)
assert COMPOSITIONS == {"run": run_now}

refused = (
    (lambda: parse >> lex, "parse writes Syntax, lex reads Source"),
    (lambda: pass_compose(desugar, front), "desugar writes Core, lex reads"),
)
for bad, said in refused:
    try:
        bad()
    except TypeError as error:
        assert said in str(error), error
    else:
        raise AssertionError("a mismatched >> composed")
try:
    pass_compose()
except ValueError:
    pass
else:
    raise AssertionError("an empty composition was built")

for direct_build in (
    lambda: PassCompose(()),
    lambda: PassCompose((parse, lex)),
):
    try:
        direct_build()
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError("the constructor took an invalid stage chain")

upper = Pass("upper", str.upper)
strip = Pass("strip", str.strip)
assert (upper.source, upper.target) == ("", "")
loose = upper >> strip >> lex
assert loose(" a ") == lex("A")
assert (loose.source, loose.target) == ("", "Tokens")

text = "1 | 1 2 3 +\n"
assert direct(run_now, text) == run_now(text)
assert direct(lex, text) == lex(text)
print("ok")
"""


def test_a_composition_is_flat_typed_and_runs() -> None:
    """
    Stages, names, associativity, repr, the type check at `>>`, the
    empty composition, untyped passes, and `direct` against a call.
    """
    result = lit(CHECKS)
    assert (result.returncode, result.stdout) == (0, b"ok\n"), result.stderr


def test_composition_keeps_no_closure() -> None:
    """
    TD-0008: the structure is the tuple of stages, so arrow.py builds no
    anonymous function.
    """
    arrow = BOOTSTRAP / "python" / "fpl" / "arrow.py"
    assert "lambda" not in arrow.read_text(encoding="utf-8")


def test_the_website_entry_still_renders() -> None:
    """
    `fpl.run.default.src` is what the Pyodide page calls.
    """
    code = "import fpl.run; print(fpl.run.default.src('1 | 1 2 3 +\\n'))"
    result = lit(code)
    assert (result.returncode, result.stdout) == (0, b"2 3 4\n\n")

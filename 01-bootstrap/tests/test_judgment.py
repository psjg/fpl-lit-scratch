"""
The judgment lines (DI-0072): a failure prints as `|- ! <tag>
<line>:<col> “<message>” @ <n>`, `n` the step of the evaluation it
failed at, and a result as `|- <value> : <sort> within <n>`. Each is
left out where it is not known, and a printed failure pasted back as
the closing line of its program is the same check.
"""

from dataclasses import replace
from datetime import datetime
from io import StringIO

import pytest
from lit import BOOTSTRAP, lit
from test_session import CONTEXT, entered

from fpl.driver import run
from fpl.errors import (
    FplError,
    OutOfGasError,
    Span,
    UnmatchedFailError,
    fail_line,
)
from fpl.kernel import Turn, split, swallowed
from fpl.log import Log
from fpl.pad import CUT, context, shaded
from fpl.pad import run as pad_run
from fpl.repl import Tty, main, once, result_line, transcript
from fpl.session import enter

EMPTY = Log((), {}, 0)
LOOP = "f : -- x\n\tf\n"
STILL = Tty(now=lambda: datetime(2026, 1, 1, 9, 5, 3), timer=lambda: 0.0)


def failure(source: str) -> FplError:
    """
    The error a source fails with.
    """
    with pytest.raises(FplError) as caught:
        run(source)
    return caught.value


def test_a_fail_line_is_the_tag_the_position_and_the_message() -> None:
    assert fail_line("err/no-row", "none fits", Span(2, 3)) == (
        "|- ! err/no-row 2:3 “none fits”"
    )


def test_a_fail_line_ends_in_the_step_when_there_is_one() -> None:
    assert fail_line("err/no-row", "m", Span(2, 3), step=0) == (
        "|- ! err/no-row 2:3 “m” @ 0"
    )


def test_a_fail_line_names_the_input_before_the_position() -> None:
    line = fail_line("err/no-row", "m", Span(2, 3), input_number=4, step=7)
    assert line == "|- ! err/no-row #4 2:3 “m” @ 7"


def test_a_failure_without_a_place_prints_without_one() -> None:
    assert fail_line("err/session", "gone") == "|- ! err/session “gone”"


def test_an_error_prints_as_its_fail_line() -> None:
    assert str(FplError(Span(2, 3), "bad")) == "|- ! err 2:3 “bad”"
    error = FplError(Span(2, 3), "bad")
    error.step = 5
    assert str(error) == "|- ! err 2:3 “bad” @ 5"


def test_the_caret_block_stays_under_the_fail_line() -> None:
    error = FplError(Span(2, 3), "bad")
    assert error.render("a\nbcd\n") == "|- ! err 2:3 “bad”\nbcd\n  ^"


def test_a_failed_run_line_knows_its_step() -> None:
    assert failure("1 [+] !\n").step == 4
    assert failure("1\n2 |- 3\n").step == 2


def test_out_of_fuel_is_at_the_whole_budget() -> None:
    error = OutOfGasError(Span(1, 1), "out of fuel")
    assert str(error) == "|- ! err/out-of-gas 1:1 “out of fuel”"
    result = enter(EMPTY, LOOP + "f\n", replace(CONTEXT, fuel=3), None)
    assert result.out == ("|- ! err/out-of-gas 3:1 “out of fuel” @ 3\n")


def test_a_failure_before_evaluation_has_no_step() -> None:
    assert failure("frob\n").step is None
    assert failure("[\n").step is None
    assert str(failure("frob\n")) == (
        "|- ! err/unresolved/unknown-word 1:1 “unknown word: frob”"
    )


def test_a_failed_input_names_an_earlier_input_by_its_number() -> None:
    log, _ = entered(["g : x -- y\n\t?\n"])
    out = enter(log, "1 g\n", CONTEXT, log.head).out
    assert out == "|- ! err/unresolved/goal #1 2:2 “unfilled goal” @ 3\n"


def test_the_repl_prints_the_fail_line_and_exits_one() -> None:
    out, err = StringIO(), StringIO()
    code = main(["-e", "frob"], StringIO(), out, err, {})
    assert code == 1
    assert out.getvalue() == (
        "|- ! err/unresolved/unknown-word 1:1 “unknown word: frob”\n"
    )
    assert err.getvalue() == "frob\n^\n"


def test_the_repl_loop_prints_the_fail_line_of_a_failed_input() -> None:
    out = StringIO()
    code = main(["--fuel", "3"], StringIO(LOOP + "\nf\n"), out, StringIO(), {})
    assert code == 0
    assert out.getvalue() == ("|- ! err/out-of-gas 1:1 “out of fuel” @ 3\n")


def test_a_refusal_is_a_fail_line_without_a_place() -> None:
    assert once(["--rewind", "0"], {}).out == (
        "|- ! err/session “nothing to rewind”\n"
    )


def test_a_result_line_ends_in_the_steps_it_spent() -> None:
    assert result_line("3", "number", within=7) == "|- 3 : number within 7"
    assert result_line("3") == "|- 3 : ..."
    assert result_line("3", within=0) == "|- 3 : ... within 0"


def test_a_transcript_gives_each_line_its_own_steps() -> None:
    assert transcript("1\n\n2\n3\n", (4, 9, 5, None)) == (
        "|- 1 : ... within 4\n\n|- 2 : ... within 5\n|- 3 : ...\n"
    )
    assert transcript("x\n1\n", (4,)) == "|- x : ...\n|- 1 : ... within 4\n"
    assert transcript("1\n2\n") == "|- 1 : ...\n|- 2 : ...\n"


def test_an_input_reports_the_steps_of_each_run_line() -> None:
    outcome = enter(EMPTY, "1 1 +\n2\n", CONTEXT, None)
    assert outcome.steps == (2, 1)
    assert outcome.spent == 3
    assert enter(EMPTY, "f : -- x\n\t1\n", CONTEXT, None).steps == ()


def test_a_pad_cell_shows_within_on_its_result_line() -> None:
    (cell,) = pad_run((), 0, "1 | 2 +", context({}), STILL)
    assert cell.turns == ("|- 3 : number within 3",)
    ghost = shaded(cell, 3)
    assert ghost is not None
    assert ghost.text == "|- 3 : number within 3"


def test_a_pad_cell_shows_the_fail_line() -> None:
    (cell,) = pad_run((), 0, "x", context({}), STILL)
    assert cell.turns[0] == (
        "|- ! err/unresolved/unknown-word 1:1 “unknown word: x”"
    )
    ghost = shaded(cell, 0)
    assert ghost is not None
    assert (ghost.kind, ghost.text) == (
        "error",
        "|- ! err/unresolved/unknown-word 1:1 “unknown word: x”",
    )


def test_the_ghost_of_a_run_out_of_fuel_is_of_kind_fuel() -> None:
    (cell,) = pad_run((), 0, LOOP + "f", context({}), STILL)
    ghost = shaded(cell, 3)
    assert ghost is not None
    assert ghost.kind == "fuel"
    assert ghost.text.startswith("|- ! err/out-of-gas 3:1 ")


def test_the_cut_preview_is_a_fail_line_of_the_same_kind() -> None:
    assert CUT == "|- ! err/out-of-gas “preview out of time”"


def test_a_kernel_error_turn_is_the_fail_line_itself() -> None:
    fail = "|- ! err/no-row 1:1 “no row matches”\n"
    assert Turn("f", fail, ("f", "^"), 1, None, 0.0).block() == (
        f"f\n{fail};; f\n;; ^\n"
    )
    assert Turn("1", "1\n", (), 0, None, 0.0).block() == "1\n|= 1\n"


def test_a_transcript_with_a_fail_line_feeds_back_as_its_inputs() -> None:
    text = "(a)\n|- ! err/no-row 1:1 “no row matches”\n(b)\n|= 3\n"
    assert split(text) == ["(a)\n", "(b)\n"]
    assert swallowed(text) == "(a)\n(b)\n"


@pytest.mark.parametrize(
    "source",
    ["frob\n", "1\n1 [+] !\n", "1 1 + |- 3\n", LOOP + "f\n", "1\n2 |- 3\n4\n"],
)
def test_a_printed_fail_line_is_the_closing_judgment_of_its_program(
    source: str,
) -> None:
    error = failure(source)
    printed = run(source + str(error) + "\n")
    assert printed.endswith(str(error) + "\n")
    bare = fail_line(error.tag, error.message)
    assert run(source + bare + "\n") == printed


@pytest.mark.parametrize(
    ("line", "said"),
    [
        ("|- ! err/stack/underflow 9:9", "expected 9:9, got 1:4"),
        ("|- ! err/stack/underflow @ 99", "expected step 99, got step 4"),
    ],
)
def test_a_position_or_step_that_differs_fails_the_check(
    line: str, said: str
) -> None:
    with pytest.raises(UnmatchedFailError) as caught:
        run(f"1 [+] !\n{line}\n")
    assert caught.value.message.endswith(said)


@pytest.mark.parametrize(
    "judgment",
    [
        "|- ! err/no-row 0:1",
        "|- ! err/no-row 01:1",
        "|- ! err/no-row 1:1:1",
        "|- ! err/no-row 1:1 @",
        "|- ! err/no-row 1:1 @ 07",
        "|- ! err/no-row 1:1 @ -1",
        "|- ! err/no-row @ 3 1:1",
        "|- ! err/no-row 1:1 @ 3 4",
        "|- ! err/no-row “m” 1:1",
    ],
)
def test_a_judgment_that_is_not_a_printed_form_is_refused(
    judgment: str,
) -> None:
    assert failure(f"$x\n{judgment}\n").message == (
        "a fail judgment is ! err/<tag> “message”"
    )


def test_prove_still_takes_the_printed_judgment_off() -> None:
    code = f"""
import importlib.util, sys, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    "prove", {str(BOOTSTRAP / "prove.py")!r})
prove = importlib.util.module_from_spec(spec)
sys.modules["prove"] = prove
spec.loader.exec_module(prove)
text = (
    "1\\n$x\\n"
    "|- ! err/unresolved/no-evaluator 2:1 “no evaluator yet” @ 1\\n"
)
path = Path(tempfile.mkdtemp(), "x.fpl")
path.write_text(text, encoding="utf-8")
with prove.judged(path) as program:
    print(repr(program.read_text(encoding="utf-8")))
"""
    result = lit(code)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode().strip() == repr("1\n$x\n")

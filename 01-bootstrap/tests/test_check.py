"""
A line L |- R checks that L and R leave equal stacks, and a closing
line |- ! err/<tag> judges how the program fails; every error carries
its tag under err/.
"""

import pytest
from test_session import CONTEXT

from fpl.desugar import desugar, resugar
from fpl.driver import run
from fpl.errors import (
    CheckError,
    FailError,
    FplError,
    NoEvaluatorError,
    NoFailError,
    OutOfGasError,
    StackError,
    UnderflowError,
    UnequalError,
    UnknownWordError,
    UnmatchedFailError,
    UnresolvedError,
)
from fpl.log import Log
from fpl.parse import parse
from fpl.print import render
from fpl.session import enter

UNRESOLVED = "$x\n"


def refusal(source: str) -> str:
    """
    The error line run gives for a source it refuses.
    """
    with pytest.raises(FplError) as caught:
        run(source)
    return str(caught.value)


def test_a_check_that_holds_prints_what_its_left_side_leaves() -> None:
    assert run("1 | 1 + |- 2\n") == "2\n"


def test_a_check_compares_whole_strands() -> None:
    assert run("1 2 3 4 | 1 + |- 2 3 4 5\n") == "2 3 4 5\n"


def test_a_check_that_fails_names_both_stacks() -> None:
    with pytest.raises(UnequalError) as caught:
        run("1 | 1 + |- 3\n")
    assert str(caught.value) == (
        "|- ! err/check/unequal 1:1 “check failed: 2 is not 3” @ 4"
    )


def test_a_failed_check_is_told_at_its_own_line() -> None:
    assert (
        refusal("1\n2 |- 3\n")
        == "|- ! err/check/unequal 2:1 “check failed: 2 is not 3” @ 2"
    )


def test_an_empty_stack_is_told_as_nothing() -> None:
    assert (
        refusal("1 |-\n")
        == "|- ! err/check/unequal 1:1 “check failed: 1 is not nothing” @ 1"
    )
    assert run("1 drop |-\n") == ""


def test_a_note_may_follow_a_check() -> None:
    assert run("1 | 1 + |- 2\t; note\n") == "2\n"


def test_a_doc_comment_may_not_follow_a_check() -> None:
    message = (
        "|- ! err/read/comment 1:8 “a ;; comment stands on a line of its own”"
    )
    assert refusal("1 |- 1 ;; doc\n") == message


@pytest.mark.parametrize("source", ["[ 1 |- 1 ]\n", "( 1 |- 1 )\n"])
def test_no_enclosure_holds_a_check(source: str) -> None:
    assert refusal(source) == "|- ! err/read/unexpected 1:5 “unexpected input”"


def test_a_bar_glued_to_a_word_is_no_check() -> None:
    assert parse("1 |-1\n").lines[0].check is None


def test_a_check_heads_no_block() -> None:
    assert (
        refusal("1 |- 1\n\t2\n")
        == "|- ! err/read/unexpected 1:7 “unexpected input”"
    )


@pytest.mark.parametrize(
    "source",
    [
        "f : -- x |- 1\n",
        "f : -- x\n\t1 |- 1\n",
        "d/\n\tf : -- x\n\t\t1 |- 1\n",
    ],
)
def test_a_check_is_a_run_line(source: str) -> None:
    assert refusal(source).endswith("“a check is a run line”")


def test_the_goals_of_both_sides_are_reported() -> None:
    goals: list[str] = []
    with pytest.raises(FplError):
        run("? |- ?\n", report=goals.append)
    assert goals == ["GOAL 1:1 ? : --", "GOAL 1:6 ? : --"]


def test_a_check_resugars_as_written() -> None:
    assert render(resugar(desugar(parse("1 |- 1\n")))) == "1 |- 1\n"


@pytest.mark.parametrize(
    "source", ["1 1 + |- 2\t; note\n", "|- ! err/no-row “why”\n", "| |- |\n"]
)
def test_a_check_prints_as_it_reads(source: str) -> None:
    assert render(parse(source)) == source


def test_a_closing_judgment_prints_the_failure_it_names() -> None:
    judged = UNRESOLVED + "|- ! err/unresolved/no-evaluator\n"
    assert (
        run(judged)
        == "|- ! err/unresolved/no-evaluator 1:1 “no evaluator yet”\n"
    )


def test_a_judgment_may_name_the_message_too() -> None:
    said = UNRESOLVED + "|- ! err/unresolved/no-evaluator “no evaluator yet”\n"
    assert (
        run(said)
        == "|- ! err/unresolved/no-evaluator 1:1 “no evaluator yet”\n"
    )


def test_a_judgment_with_another_message_fails() -> None:
    said = UNRESOLVED + "|- ! err/unresolved/no-evaluator “other”\n"
    with pytest.raises(UnmatchedFailError) as caught:
        run(said)
    assert str(caught.value) == (
        "|- ! err/check/unmatched-fail 2:1 “check failed:"
        " expected “other”, got “no evaluator yet””"
    )


def test_a_judgment_with_another_tag_fails() -> None:
    with pytest.raises(UnmatchedFailError) as caught:
        run(UNRESOLVED + "|- ! err/no-row\n")
    assert str(caught.value) == (
        "|- ! err/check/unmatched-fail 2:1 “check failed: expected"
        " err/no-row, got err/unresolved/no-evaluator”"
    )


def test_a_judgment_on_a_program_that_passes_fails() -> None:
    with pytest.raises(NoFailError) as caught:
        run("1\n|- ! err/no-row\n")
    assert str(caught.value) == (
        "|- ! err/check/no-fail 2:1 “check failed: expected err/no-row,"
        " the program passed”"
    )


def test_the_lines_before_a_judged_failure_still_print() -> None:
    source = "1\n2 |- 3\n4\n;; done\n|- ! err/check/unequal\n;; after\n"
    assert (
        run(source)
        == "1\n|- ! err/check/unequal 2:1 “check failed: 2 is not 3” @ 2\n"
    )


@pytest.mark.parametrize(
    "source", ["|- ! err/no-row\n1\n", "1 |- ! err/no-row\n"]
)
def test_a_fail_judgment_closes_the_program(source: str) -> None:
    assert refusal(source).endswith("“a fail judgment closes the program”")


@pytest.mark.parametrize(
    "judgment",
    [
        "|- ! no-row",
        "|- ! err/no-row 7",
        "|- ! err/no-row | “m”",
        "|- ! #err/no-row",
        "|- ! err/no-row “⟨1⟩”",
        "|- ! err/",
        "|- ! err//no-row",
    ],
)
def test_a_judgment_is_a_tag_and_a_string(judgment: str) -> None:
    message = (
        "|- ! err/form/check 2:1 “a fail judgment is ! err/<tag> “message””"
    )
    assert refusal(f"{UNRESOLVED}{judgment}\n") == message


def test_an_unjudged_program_fails_as_before() -> None:
    with pytest.raises(NoEvaluatorError):
        run(UNRESOLVED)


@pytest.mark.parametrize(
    ("error", "tag"),
    [
        (FailError, "err/no-row"),
        (UnresolvedError, "err/unresolved"),
        (NoEvaluatorError, "err/unresolved/no-evaluator"),
        (UnknownWordError, "err/unresolved/unknown-word"),
        (OutOfGasError, "err/out-of-gas"),
        (StackError, "err/stack"),
        (UnderflowError, "err/stack/underflow"),
        (CheckError, "err/check"),
        (UnequalError, "err/check/unequal"),
        (UnmatchedFailError, "err/check/unmatched-fail"),
        (NoFailError, "err/check/no-fail"),
    ],
)
def test_each_tag_is_a_path_below_its_parent_tag(
    error: type[FplError], tag: str
) -> None:
    (parent,) = error.__bases__
    assert FplError.tag == "err"
    assert issubclass(parent, FplError)
    assert error.tag == tag
    assert tag.startswith(parent.tag + "/")


def test_an_unknown_word_is_not_a_planned_one() -> None:
    with pytest.raises(UnknownWordError):
        run("frob\n")


def test_a_failed_check_in_the_repl_is_an_error_line() -> None:
    outcome = enter(Log((), {}, 0), "1 | 1 + |- 3", CONTEXT, None)
    assert outcome.out == (
        "|- ! err/check/unequal 1:1 “check failed: 2 is not 3” @ 4\n"
    )
    assert outcome.event.status == "error"

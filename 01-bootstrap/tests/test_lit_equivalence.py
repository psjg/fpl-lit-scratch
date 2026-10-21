"""
The executors of a composition agree: prove.py, run by make check.

`direct` runs the passes of a composition in one interpreter; the shell
route runs each as a filter on FON, in real processes or folded in one.
prove.py holds them against each other and against the seed walker on
every example, per pass, per slice and for the whole chain, and checks
that no filter lexes or parses a second time. Here it runs in process
on the whole suite and in real processes on three examples; the tests
below also show that its poison check catches a filter that re-parses,
and pin the depth the shell route falls short of `direct` by.
"""

import sys

import pytest
from corpus import PROGRAMS
from lit import BOOTSTRAP, lit, run

PROVE = BOOTSTRAP / "prove.py"
LOAD = f"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("prove", {str(PROVE)!r})
prove = importlib.util.module_from_spec(spec)
sys.modules["prove"] = prove
spec.loader.exec_module(prove)
"""

AGAIN = """
from fpl.codec import SYNTAX
from fpl.lex import lex
from fpl.parse import parse
from fpl.pipe import run_filter
from fpl.print import render

def again(stage, data):
    if stage.source == "Syntax":
        text = render(SYNTAX.defonify(data))
        data = SYNTAX.fonify(parse(lex(text)))
    return run_filter(stage, data)

def folded_again(c, data):
    for stage in c.stages:
        data = again(stage, data)
    return data
"""


def test_every_executor_agrees_on_every_example_in_process() -> None:
    """
    The seed, `fpl run`, the folded pipe and every slice agree on all
    examples, and the poisoned filters still do.
    """
    result = run([sys.executable, str(PROVE), "--in-process"])
    out = result.stdout.decode()
    assert result.returncode == 0, out + result.stderr.decode()
    assert f"{len(PROGRAMS)}/{len(PROGRAMS)} examples" in out, out


def test_real_processes_agree_on_three_examples() -> None:
    """
    The same checks with bash and `run_shell`: one OS process per stage.
    """
    three = (PROGRAMS[0], PROGRAMS[len(PROGRAMS) // 2], PROGRAMS[-1])
    result = run([sys.executable, str(PROVE), *map(str, three)])
    out = result.stdout.decode()
    assert result.returncode == 0, out + result.stderr.decode()
    assert "3/3 examples: every executor agrees (in real" in out, out


def test_the_poison_catches_a_filter_that_parses_again() -> None:
    """
    A filter that renders its Syntax and lexes and parses the text again
    (the hack TD-0006 removed) fails the poison check. The slices catch
    it here too, because the spans move, but the poison does not rely
    on the bytes differing. The real filter passes both.
    """
    frames = next(p for p in PROGRAMS if p.name == "01-frames.fpl")
    result = lit(
        LOAD + AGAIN + f"text = open({str(frames)!r}, encoding='utf-8')\n"
        "xs = prove.joints(text.read())\n"
        "assert prove.slices(xs, prove.folded)[1] == []\n"
        "assert prove.unlexed(xs) == []\n"
        "assert 'desugar' in prove.slices(xs, folded_again)[1]\n"
        "said = prove.unlexed(xs, again)\n"
        "assert said == ['desugar lexed or parsed again'], said\n"
    )
    assert result.returncode == 0, result.stderr.decode()


@pytest.mark.xfail(
    strict=True,
    reason="measured: direct carries 88 levels of nesting, the shell route "
    "about 53: the Syntax codec writer recurses (not fixed here)",
)
def test_the_shell_route_carries_what_direct_carries() -> None:
    """
    However deeply a program nests, the pipe runs it if direct does.
    """
    result = lit(
        LOAD + "direct, shell = prove.depths(False)\n"
        "assert direct == shell, (direct, shell)\n"
    )
    assert result.returncode == 0, result.stderr.decode()

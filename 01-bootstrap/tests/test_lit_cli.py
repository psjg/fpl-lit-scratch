"""
The `fpl` command line of 01.01.06-cli, run as a real process.

Bare `fpl` opens the interactive interface; `fpl <stage>` is one
filter; `fpl run <file>` runs the whole chain; `fpl graph` and
`fpl shell` show a composition. The command names come from the
registries (`fpl.pipe.PASSES`, `fpl.pipe.ENDS`, `fpl.run.COMPOSITIONS`),
so no stage name is spelled out in the CLI or in the tangler.
"""

import re
import subprocess
import sys

from lit import BOOTSTRAP, PYTHON, TANGLE, env, fpl, lit

FRAMES = (
    BOOTSTRAP.parent
    / "03-fpl/OLD/03.01-features/draft2/examples/01-frames.fpl"
)
STAGE = re.compile(r'"(lex|parse|desugar|elaborate)"')


def out(code: str) -> str:
    """
    Run `code` in the tangled tree; its stdout, the exit status checked.
    """
    done = lit(code)
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode()


def test_help_lists_every_command() -> None:
    shown = fpl("--help")
    assert shown.returncode == 0, shown.stderr.decode()
    commands = shown.stdout.decode().partition("Commands:")[2]
    listed = re.findall(r"^  (\w+)", commands, re.M)
    assert listed == [
        "desugar",
        "elaborate",
        "eval",
        "graph",
        "lex",
        "parse",
        "render",
        "run",
        "shell",
        "source",
    ]


def test_no_stage_name_is_spelled_out() -> None:
    for path in (PYTHON / "fpl" / "cli.py", TANGLE):
        assert not STAGE.findall(path.read_text()), path


def test_graph_prints_the_explanation() -> None:
    explain = out(
        "from fpl.graph import explain\n"
        "from fpl.run import run_now\n"
        "print(explain(run_now))\n"
    )
    shown = fpl("graph", "run")
    assert (shown.returncode, shown.stdout.decode()) == (0, explain)


def test_graph_formats() -> None:
    dot = fpl("graph", "run", "--format", "dot").stdout.decode()
    mermaid = fpl("graph", "run", "--format", "mermaid").stdout.decode()
    assert dot.startswith("digraph")
    assert mermaid.startswith("flowchart LR")


def test_an_unknown_composition_is_refused() -> None:
    assert fpl("graph", "nosuch").returncode == 2


def test_the_printed_shell_script_runs_like_fpl_run() -> None:
    """
    `fpl shell run` prints a pipe; bash with pipefail runs it on the
    frames example to the stdout and status of `fpl run`.
    """
    script = fpl("shell", "run").stdout.decode()
    fpl_sh = f'fpl() {{ "{sys.executable}" -m fpl "$@"; }}\n'
    piped = subprocess.run(
        ["bash", "-o", "pipefail", "-c", fpl_sh + script],
        input=FRAMES.read_bytes(),
        capture_output=True,
        env=env(),
        timeout=60,
        check=False,
    )
    ran = fpl("run", str(FRAMES))
    assert ran.returncode == 0, ran.stderr.decode()
    assert (piped.returncode, piped.stdout) == (ran.returncode, ran.stdout)


def test_bare_fpl_opens_the_repl() -> None:
    """
    With no arguments `fpl` hands stdin to the REPL, which evaluates
    each input and prints the stack.
    """
    opened = fpl(stdin=b"1 2 +\n")
    assert opened.returncode == 0, opened.stderr.decode()
    assert opened.stdout == b"[ 1 2 + ]\n"


def test_a_stage_main_exits_with_the_filter_status() -> None:
    """
    `python -m fpl.lex` handed no FON fails: exit 1, a stderr line.
    """
    done = subprocess.run(
        [sys.executable, "-m", "fpl.lex"],
        input=b"x",
        capture_output=True,
        env=env(),
        timeout=60,
        check=False,
    )
    assert done.returncode == 1
    assert done.stderr

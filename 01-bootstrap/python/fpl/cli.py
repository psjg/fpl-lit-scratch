"""
# 01.01.06 CLI

`python -m fpl` and the installed `fpl` script (`entry`, declared in
`pyproject.toml`) land here
([ADR-0006](../../02-docs/02.05-project/adr/ADR-0006-one-fpl-executable.md)).
The commands are read off the registries, so a new pass or composition
needs no line here.

`fpl repl` opens the interactive interface, and `fpl` alone is short for
it. For now that is the seed walker's REPL, `python -m fpl.repl` run
from [the seed](../fpl/repl.py) in a child process: the tangled tree has
no REPL of its own yet, and the seed cannot be imported beside it, since
both packages are named `fpl`. The wheel carries the seed as
`fpl/_seed/fpl` (`pyproject.toml`), so an installed `fpl` finds it
there; a checkout finds it in `01-bootstrap/` (TD-0014). The child's
path is the seed's root ahead of this process's own, so the seed wins
the name `fpl` and the dependencies stay in reach wherever they are
installed.

`fpl <stage>` is one filter across the pipe of
[01.01.03-pipe](01.01.03-pipe.md): a pass of `PASSES`, or one of the two
`ENDS`, `source` and `render`. `fpl run <file>` runs the whole chain
in-process; `fpl <file>` is short for it, unless the file is named like
a command.

`fpl graph <composition>` prints a composition as data
([01.04.05-graph](../01.04-compose/01.04.05-graph.md)): as text,
Graphviz or Mermaid. `fpl shell <composition>` prints the shell pipe
that runs it. The compositions are `COMPOSITIONS` of
[01.04.02-run](../01.04-compose/01.04.02-run.md).

Click stays in this module: `import fpl` does not reach it, so the
website, which has no Click, still imports the library.

`fpl repl`, or `fpl`, opens the REPL. `fpl <stage>` is one filter.
"""

import os
import subprocess
import sys
from pathlib import Path

import click

from fpl.graph import dot, explain, mermaid
from fpl.pipe import ENDS, PASSES, cli, shell_script
from fpl.run import COMPOSITIONS, run_file

HERE = Path(__file__).resolve().parent
SEEDS = (HERE / "_seed", HERE.parents[1])
"""
Where the seed walker's root may be, in order: beside this module, as
the wheel installs it, or the checkout's 01-bootstrap/. Its `fpl.repl`
is the REPL.
"""

FORMATS = {"text": explain, "dot": dot, "mermaid": mermaid}
"""
The ways `fpl graph` writes a composition down.
"""


def repl() -> int:
    """
    Run the seed REPL on this terminal; its exit status.

    The child's path is the seed's root, then this process's own, so
    `fpl` is the seed and lark and the rest are found where they were;
    PYTHONSAFEPATH keeps the working directory off the path.
    """
    found = [root for root in SEEDS if (root / "fpl" / "repl.py").is_file()]
    if not found:
        places = " or ".join(str(root / "fpl") for root in SEEDS)
        print(f"fpl: no REPL: no seed in {places}", file=sys.stderr)
        return 2
    path = os.pathsep.join([str(found[0]), *filter(None, sys.path)])
    env = os.environ | {"PYTHONPATH": path, "PYTHONSAFEPATH": "1"}
    child = [sys.executable, "-m", "fpl.repl"]
    return subprocess.run(child, env=env, check=False).returncode


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Open the REPL, run a file, or run one pass across a pipe."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl_command)


@main.command("repl")
def repl_command() -> None:
    """Open the REPL. Bare `fpl` does the same."""
    sys.exit(repl())


@main.command("run")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
def run_command(file: str) -> None:
    """Run a file in-process. ABTs stay in this process."""
    sys.exit(run_file(file))


COMPOSITION = click.argument("composition", type=click.Choice(COMPOSITIONS))


@main.command("graph")
@COMPOSITION
@click.option(
    "--format", "form", type=click.Choice(FORMATS), default="text"
)
def graph_command(composition: str, form: str) -> None:
    """Print a composition as a graph. Nothing runs."""
    click.echo(FORMATS[form](COMPOSITIONS[composition]).rstrip("\n"))


@main.command("shell")
@COMPOSITION
def shell_command(composition: str) -> None:
    """Print the shell pipe that runs a composition."""
    click.echo(shell_script(COMPOSITIONS[composition]))


def _filter(name: str, summary: str) -> click.Command:
    """
    The filter command `name`: one stage from stdin to stdout.
    """

    def command() -> None:
        sys.exit(cli(name))

    return click.command(name, help=summary)(command)


for _name, _end in ENDS.items():
    main.add_command(_filter(_name, (_end.__doc__ or "").strip()))
for _name, _pass in PASSES.items():
    main.add_command(
        _filter(_name, f"FON<{_pass.source}> in, FON<{_pass.target}> out.")
    )


def dispatch(argv: list[str]) -> int:
    """
    `fpl <file>` is `fpl run <file>`; anything else is Click.

    A command name wins over a file of the same name.
    """
    if len(argv) == 1 and argv[0] not in main.commands:
        if Path(argv[0]).is_file():
            argv = ["run", *argv]
    try:
        main(args=argv, standalone_mode=False)
    except SystemExit as stop:
        return int(stop.code or 0)
    except click.ClickException as refused:
        refused.show()
        return refused.exit_code
    return 0


def entry() -> None:
    """The `fpl` console script: exit with the dispatch status."""
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    entry()

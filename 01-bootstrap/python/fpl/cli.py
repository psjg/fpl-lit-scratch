"""
# 01.01.06 CLI

`python -m fpl` and the installed `fpl` script (`entry`, declared in
`pyproject.toml`) land here
([ADR-0006](../../02-docs/02.05-project/adr/ADR-0006-one-fpl-executable.md)).
The commands are read off the registries, so a new pass or composition
needs no line here.

`fpl` alone opens the interactive interface. For now that is the seed
walker's REPL, `python -m fpl.repl` run from [the seed](../fpl/repl.py)
in a child process: the tangled tree has no REPL of its own yet, and the
seed cannot be imported beside it, since both packages are named `fpl`.

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

`fpl` opens the REPL. `fpl <stage>` is one filter.
"""

import os
import subprocess
import sys
from pathlib import Path

import click

from fpl.graph import dot, explain, mermaid
from fpl.pipe import ENDS, PASSES, cli, shell_script
from fpl.run import COMPOSITIONS, run_file

SEED = Path(__file__).resolve().parents[2]
"""
The seed walker's root, 01-bootstrap/; its `fpl.repl` is the REPL.
"""

FORMATS = {"text": explain, "dot": dot, "mermaid": mermaid}
"""
The ways `fpl graph` writes a composition down.
"""


def repl() -> int:
    """
    Run the seed REPL on this terminal; its exit status.

    The child sees the seed and nothing else: PYTHONPATH is replaced,
    and PYTHONSAFEPATH keeps the working directory off the path.
    """
    if not (SEED / "fpl" / "repl.py").is_file():
        print(f"fpl: no REPL: {SEED / 'fpl'} is missing", file=sys.stderr)
        return 2
    env = os.environ | {"PYTHONPATH": str(SEED), "PYTHONSAFEPATH": "1"}
    child = [sys.executable, "-m", "fpl.repl"]
    return subprocess.run(child, env=env, check=False).returncode


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Open the REPL, run a file, or run one pass across a pipe."""
    if ctx.invoked_subcommand is None:
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

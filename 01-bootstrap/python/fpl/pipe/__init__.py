"""
# 01.01.03 Pipe

A pass run as a filter reads the [FON](01.01.02-fon.md) document of the
representation it reads and writes the document of the one it writes
([ADR-0002](../../02-docs/02.05-project/adr/ADR-0002-fon-is-the-stage-protocol.md)).
Nothing in between is text: the [codec](01.01.05-codec.md) of the pass's
`source` decodes the value, the pass runs on it, and the codec of its
`target` encodes the result, `defonify >> stage >> fonify`
([ADR-0005](../../02-docs/02.05-project/adr/ADR-0005-fonify-defonify.md)).
One formula serves every pass, so the pipe never names a stage and never
lexes or parses twice
([TD-0006](../../02-docs/02.05-project/techdebt/TD-0006-pipe-reparses-rendered-text.md)).

The passes are the stages of the compositions
[01.04.02-run](../01.04-compose/01.04.02-run.md) names, keyed by the
name each pass carries: a pass added to a composition is a filter with
no line here.

Every pass as a filter, and the shell route that chains them.
"""

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from fpl.arrow import PassCompose, Stage
from fpl.codec import CODECS, ERROR, SOURCE, read_repr
from fpl.desugar import listing, resugar
from fpl.errors import FplError
from fpl.print import render
from fpl.run import COMPOSITIONS

PASSES: dict[str, Stage] = {
    stage.name: stage
    for composition in COMPOSITIONS.values()
    for stage in composition.stages
}
"""
The passes a filter can run, by name.
"""

"""
## A diagnostic is data

A pass that raises an `FplError` writes the error as an `Error` document
and exits 1. A pass handed an `Error` document passes it on unchanged
and exits 1 too, so under `pipefail` the pipe fails with the stage that
failed first, and the error reaches `render`, which prints it the way
`fpl run` does. Input that is no document of the expected representation
is another matter: the pipe itself is miswired, so the filter says what
it expected on stderr, writes nothing and exits 1.
"""

def run_filter(stage: Stage, data: bytes) -> bytes:
    """
    FON<source> → FON<target>: the document of what `stage` makes of
    the value `data` carries, or of the error it raises. An Error
    document comes back as it went in; any other document of the wrong
    representation is refused with a ValueError.
    """
    return _filter(stage, data)[0]


def _filter(stage: Stage, data: bytes) -> tuple[bytes, int]:
    """
    run_filter's document and the exit status it stands for.
    """
    try:
        value = CODECS[stage.source].defonify(data)
    except ValueError:
        if read_repr(data) != ERROR.repr:
            raise
        return data, 1
    try:
        return CODECS[stage.target].fonify(stage(value)), 0
    except FplError as error:
        return ERROR.fonify(error), 1

"""
## The two ends

The pipe does not start on FON, and a person does not read it. `ingress`
turns the text of a program into a `Source` document. `egress` turns any
document back into text for a person: source as itself, tokens as the
source they cover, a program, core or stacks rendered as FPL, and an
error as the line `fpl run` prints.
"""

def ingress(text: str) -> bytes:
    """
    Text → FON<Source>.
    """
    return SOURCE.fonify(text)


def egress(data: bytes) -> str:
    """
    FON<any> → the text a person reads.
    """
    return _egress(data)[0]


def _egress(data: bytes) -> tuple[str, int]:
    """
    egress's text and the exit status it stands for.
    """
    name = read_repr(data)
    if name not in CODECS:
        raise ValueError(f"unknown representation {name}")
    value: Any = CODECS[name].defonify(data)
    match name:
        case "Source":
            return value, 0
        case "Tokens":
            return value.source, 0
        case "Syntax":
            return render(value), 0
        case "Core":
            return render(resugar(value)), 0
        case "Stacks":
            return render(listing(value)), 0
        case _:
            return f"{value}\n", 1

"""
## The filter

`cli` is the imperative shell around those functions: it reads stdin
once, writes stdout once, and returns the exit status. `ENDS` holds the
two ends by name; every other name is a pass.
"""

def _source(data: bytes) -> tuple[bytes, int]:
    """
    The `source` filter: raw bytes in, FON<Source> out.
    """
    return ingress(data.decode()), 0


def _render(data: bytes) -> tuple[bytes, int]:
    """
    The `render` filter: FON in, text out.
    """
    text, status = _egress(data)
    return text.encode(), status


ENDS: dict[str, Callable[[bytes], tuple[bytes, int]]] = {
    "source": _source,
    "render": _render,
}
"""
The filters that are not passes, by name.
"""


def cli(stage: Stage | str) -> int:
    """
    Run one stage on stdin, a Pass or its name, and write stdout.

    A name is looked up among the ends and the registered passes; a Pass
    runs as itself.
    """
    if isinstance(stage, str):
        run = ENDS.get(stage) or partial(_filter, PASSES[stage])
    else:
        run = partial(_filter, stage)
    try:
        out, status = run(sys.stdin.buffer.read())
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    sys.stdout.buffer.write(out)
    return status

"""
## The shell route

A composition run through the shell is one process per pass joined by OS
pipes, the linear projection of the composition
([ADR-0012](../../02-docs/02.05-project/adr/ADR-0012-pipeline-is-a-computation-graph.md)).
`shell_script` writes it down for a person to paste; `run_shell` runs
it, so its result can be held against `direct`. Each child runs this
same package: its directory leads the children's path, and the working
directory is kept off it.
"""

def _stages(c: Stage | PassCompose[Any, Any]) -> tuple[Stage, ...]:
    """
    The passes of a composition, or the pass alone.
    """
    return c.stages if isinstance(c, PassCompose) else (c,)


def shell_script(c: Stage | PassCompose[Any, Any]) -> str:
    """
    `fpl source | fpl lex | … | fpl render`: c between the two ends.
    """
    names = ["source", *(stage.name for stage in _stages(c)), "render"]
    return " | ".join(f"fpl {name}" for name in names)


def run_shell(
    c: Stage | PassCompose[Any, Any],
    data: bytes,
    python: str = sys.executable,
) -> bytes:
    """
    FON<c.source> → FON<c.target>, one `python -m fpl <pass>` process per
    stage. A stage that fails other than with an Error document raises
    a RuntimeError.
    """
    root = str(Path(__file__).resolve().parents[2])
    path = os.pathsep.join(filter(None, (root, os.environ.get("PYTHONPATH"))))
    env = os.environ | {"PYTHONPATH": path, "PYTHONSAFEPATH": "1"}
    with tempfile.TemporaryFile() as given:
        given.write(data)
        given.seek(0)
        procs: list[subprocess.Popen[bytes]] = []
        for stage in _stages(c):
            given_to = procs[-1].stdout if procs else given
            procs.append(
                subprocess.Popen(
                    [python, "-m", "fpl", stage.name],
                    stdin=given_to,
                    stdout=subprocess.PIPE,
                    env=env,
                )
            )
            if given_to is not given and given_to is not None:
                given_to.close()
        last = procs[-1].stdout
        out = last.read() if last is not None else b""
    codes = [proc.wait() for proc in procs]
    if any(codes) and not _is_error(out):
        raise RuntimeError(f"{shell_script(c)} exited {codes}")
    return out


def _is_error(data: bytes) -> bool:
    """
    Whether `data` is an Error document.
    """
    try:
        return read_repr(data) == ERROR.repr
    except ValueError:
        return False

"""
Hold every executor of the literate tree against every other.

A composition means one thing however it runs: how it runs is the
executor's business, not the program's (handoff section 14, ADR-0012).
So for every example program this script runs each executor the tree
has and fails on the first byte two of them disagree on, each given
the program without its closing fail judgment (`judged`):

(a) seed    `fpl run`, which runs `run_now` with `direct`, prints what
            the seed walker prints and ends in the same status.
(b) shell   `fpl source | fpl lex | ... | fpl render`, one process per
            stage under `bash -o pipefail`, prints the same and ends in
            the same status.
(c) slices  for every contiguous run P of the passes of `run_now` and
            the value x it starts from, the shell route turns
            fonify(x) into the very bytes of fonify(direct(P, x)), and
            they decode to a value equal to direct's. The five single
            passes are the slices of length one, the whole chain the
            longest.
(d) poison  with every function of the lexer and the parser made to
            raise, desugar, elaborate and eval still turn the Syntax and
            Core documents of the example into the same documents: no
            filter lexes or parses a second time (TD-0006).

Then it measures how deeply nested a program `direct` and the shell
route each carry: a known limit, reported and not judged.

    prove.py [--in-process] [EXAMPLE ...]

By default every executor runs in real processes: (b) through bash,
(c) through `run_shell`. `--in-process` runs (b) and (c) by folding
`run_filter` over the stages in one interpreter instead: the same
filters without the OS pipes, fast enough for `make check`
(tests/test_lit_equivalence.py). The seed always runs as a process,
and (d) always in process, where the poison can reach the filter. With
no EXAMPLE it proves the whole conformance suite, one worker process
per example. Exit 0 when every check holds on every example, else 1.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile
import types
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TANGLED = ROOT / "python"
# The seed package `fpl/` sits beside this file and the tangled one is
# named `fpl` too: put the tangled tree first, the seed off the path.
sys.path[:] = [
    str(TANGLED),
    *(p for p in sys.path if p and Path(p).resolve() != ROOT),
]

import lark  # noqa: E402
from fpl.arrow import PassCompose, direct, pass_compose  # noqa: E402
from fpl.codec import CODECS, ERROR, read_repr  # noqa: E402
from fpl.pipe import (  # noqa: E402
    egress,
    ingress,
    run_filter,
    run_shell,
    shell_script,
)
from fpl.run import run_file, run_now  # noqa: E402

from fpl.errors import FplError  # noqa: E402

SUITE = ROOT.parent / "03-fpl" / "OLD" / "03.01-features"
PYTHON = os.environ.get("FPL_PYTHON", sys.executable)
TIMEOUT = 120
DEEPEST = 512

type Composition = PassCompose[Any, Any]
type Executor = Callable[[Composition, bytes], bytes]
type Filter = Callable[[Any, bytes], bytes]
type Ran = tuple[bytes, int]


"""
## The executors

`direct` runs a composition in this interpreter; `run_shell` runs it as
one `python -m fpl <pass>` process per stage joined by OS pipes;
`folded` is the shell route without the processes. The two shell
executors read and write documents; `document` is what direct's result
must look like on the wire.
"""


def folded(c: Composition, data: bytes) -> bytes:
    """
    FON<c.source> -> FON<c.target>: each stage's filter in turn, here.
    """
    for stage in c.stages:
        data = run_filter(stage, data)
    return data


def document(c: Composition, value: Any) -> bytes:
    """
    The document of what `direct` makes of `value`, or of its error.
    """
    try:
        return CODECS[c.target].fonify(direct(c, value))
    except FplError as error:
        return ERROR.fonify(error)


def _process(args: list[str], path: Path, stdin: bytes = b"") -> Ran:
    """
    Run `args` with `path` the only package path: stdout and status.
    """
    env = os.environ | {"PYTHONSAFEPATH": "1", "PYTHONPATH": str(path)}
    done = subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        env=env,
        timeout=TIMEOUT,
        check=False,
    )
    return done.stdout, done.returncode


"""
## The checks

Each check takes one example and returns what went wrong, an empty list
when it holds.
"""


def seed(example: Path, real: bool) -> list[str]:
    """
    (a) `fpl run` against the seed walker, stdout and status.
    """
    want = _process([PYTHON, "-m", "fpl", str(example)], ROOT)
    return [] if ran(example, real) == want else ["fpl run != seed"]


def ran(example: Path, real: bool) -> Ran:
    """
    `fpl run example`: as a process, or `run_file` in this one.
    """
    if real:
        return _process([PYTHON, "-m", "fpl", "run", str(example)], TANGLED)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = run_file(str(example))
    return out.getvalue().encode(), status


def shell(example: Path, real: bool) -> list[str]:
    """
    (b) The seven-stage pipe against `fpl run`, stdout and status.
    """
    if real:
        script = f'fpl() {{ "{PYTHON}" -m fpl "$@"; }}\n'
        args = ["bash", "-o", "pipefail", "-c", script + shell_script(run_now)]
        got = _process(args, TANGLED, example.read_bytes())
    else:
        data = folded(run_now, ingress(example.read_text(encoding="utf-8")))
        got = egress(data).encode(), int(read_repr(data) == ERROR.repr)
    return [] if got == ran(example, real) else ["pipe != fpl run"]


def joints(text: str) -> list[Any]:
    """
    The value at each joint of `run_now` on `text`, up to the first
    stage that fails: the source, then each stage's result.
    """
    got: list[Any] = [text]
    for stage in run_now.stages:
        try:
            got.append(stage(got[-1]))
        except FplError:
            break
    return got


def slices(xs: list[Any], executor: Executor) -> tuple[int, list[str]]:
    """
    (c) Every contiguous slice of `run_now` from a joint `xs` reaches,
    run by `executor` and by `direct`: how many ran, and which differ.
    """
    stages = run_now.stages
    wrong: list[str] = []
    count = 0
    for i, x in enumerate(xs[: len(stages)]):
        for j in range(i + 1, len(stages) + 1):
            c = pass_compose(*stages[i:j])
            count += 1
            want = document(c, x)
            try:
                got = executor(c, CODECS[c.source].fonify(x))
            except RuntimeError as error:
                wrong.append(f"{c.name}: {error}")
                continue
            if got != want or not _decodes(c, got, x):
                wrong.append(c.name)
    return count, wrong


def _decodes(c: Composition, data: bytes, x: Any) -> bool:
    """
    Whether `data`, unless an error, decodes to what `direct` makes of
    `x`.
    """
    if read_repr(data) == ERROR.repr:
        return True
    return CODECS[c.target].defonify(data) == direct(c, x)


POISON = "the lexer or the parser ran"


def _poison(*_: object, **__: object) -> None:
    # Runs under the victim's globals, so it names nothing but builtins.
    raise AssertionError("the lexer or the parser ran")


def _unbitten[T](run: Callable[..., T], *args: Any) -> T | None:
    """
    `run(*args)`, or None when it calls a poisoned function.
    """
    try:
        return run(*args)
    except AssertionError as error:
        if str(error) != POISON:
            raise
        return None


def _victims() -> list[types.FunctionType]:
    """
    Every function of the lexer and parser modules, and Lark's own entry
    points: whatever a filter would call to lex or parse again. The
    modules come from sys.modules: `fpl.lex` as an attribute is the
    pass, which the package re-exports under the module's name.
    """
    found = [
        f
        for name in ("fpl.lex", "fpl.parse")
        for f in vars(importlib.import_module(name)).values()
        if isinstance(f, types.FunctionType) and f.__module__ == name
    ]
    found += [lark.Lark.parse, lark.Lark.lex, lark.Lark.__init__]
    return [f for f in found if not f.__code__.co_freevars]


@contextlib.contextmanager
def poisoned() -> Iterator[None]:
    """
    Within the block every victim raises the POISON error, however it
    was imported: its code object is swapped, not a module's name.
    """
    victims = _victims()
    saved = [f.__code__ for f in victims]
    try:
        for f in victims:
            f.__code__ = _poison.__code__
        yield
    finally:
        for f, code in zip(victims, saved, strict=True):
            f.__code__ = code


def unlexed(xs: list[Any], run: Filter = run_filter) -> list[str]:
    """
    (d) With the lexer and the parser poisoned, `run` takes each stage
    after parse from the document of its input to the document `direct`
    makes. Fails too when the poison does not bite.
    """
    stages = run_now.stages
    cases = [
        (stage, CODECS[stage.source].fonify(x), document(stage, x))
        for stage, x in zip(stages[2:], xs[2:], strict=False)
    ]
    wrong: list[str] = []
    with poisoned():
        if _unbitten(run_now.stages[0], xs[0]) is not None:
            wrong.append("the poison does not bite")
        for stage, given, want in cases:
            got = _unbitten(run, stage, given)
            if got is None:
                wrong.append(f"{stage.name} lexed or parsed again")
            elif got != want:
                wrong.append(f"{stage.name} differs from direct")
    return wrong


"""
## One example, every example

`prove` runs every check on one example; `main` runs it on each example
in a worker process of its own, so the poison, the redirected stdout and
the recursion depth of one never reach another.
"""


@dataclass(frozen=True)
class Row:
    """
    What became of one example.
    """

    name: str
    seed: list[str]
    shell: list[str]
    count: int
    slices: list[str]
    poison: list[str]

    def ok(self) -> bool:
        """
        Whether every check held.
        """
        return not (self.seed or self.shell or self.slices or self.poison)


#: How the closing fail judgment of an example starts (DI-0072).
JUDGMENT = "|- ! "


@contextlib.contextmanager
def judged(example: Path) -> Iterator[Path]:
    """
    The program `example` holds, without its closing fail judgment.

    The judgment `|- ! err/<tag> “message”` is the suite's assertion
    about the program, which only the seed reads (the tangled tree reads
    no check or judgment): every executor is held to the seed on the program it
    judges. An example whose last line that is not blank starts so is
    copied without that line into a directory of its own, removed when
    the block ends; any other is yielded as it is. Textual, so a
    judgment line the converter did not write, or one followed by a
    comment line, is not taken off and the seed check says so.
    """
    lines = example.read_text(encoding="utf-8").splitlines(keepends=True)
    last = max((n for n, s in enumerate(lines) if s.strip()), default=-1)
    if last < 0 or not lines[last].startswith(JUDGMENT):
        yield example
        return
    with tempfile.TemporaryDirectory() as tmp:
        program = Path(tmp) / example.name
        program.write_text("".join(lines[:last]), encoding="utf-8")
        yield program


def prove(example: Path, real: bool) -> Row:
    """
    Every check on `example`, on the program its judgment judges.
    """
    with judged(example) as program:
        xs = joints(program.read_text(encoding="utf-8"))
        count, wrong = slices(xs, run_shell if real else folded)
        return Row(
            name=f"{example.parent.parent.name}/{example.name}",
            seed=seed(program, real),
            shell=shell(program, real),
            count=count,
            slices=wrong,
            poison=unlexed(xs),
        )


def _nested(n: int) -> str:
    return "[ " * n + "1" + " ]" * n + "\n"


def _carries(executor: Executor, n: int) -> bool:
    """
    Whether `executor` takes a program nested `n` deep from source to
    stacks the way `direct` does.
    """
    text = _nested(n)
    try:
        want = document(run_now, text)
    except RecursionError:
        return False
    try:
        with _quiet():
            return executor(run_now, CODECS["Source"].fonify(text)) == want
    except (RecursionError, RuntimeError):
        return False


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """
    Within the block, file descriptor 2 is /dev/null, for this process
    and the children it starts: a child that overflows its stack prints
    the whole traceback.
    """
    saved = os.dup(2)
    try:
        with open(os.devnull, "wb") as null:
            os.dup2(null.fileno(), 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


def deepest(executor: Executor) -> int:
    """
    The deepest nesting `executor` carries, by bisection up to DEEPEST.
    """
    low, high = 0, DEEPEST + 1
    while high - low > 1:
        mid = (low + high) // 2
        low, high = (mid, high) if _carries(executor, mid) else (low, mid)
    return low


def _direct(c: Composition, data: bytes) -> bytes:
    """
    `direct` as an executor on documents.
    """
    return document(c, CODECS[c.source].defonify(data))


def depths(real: bool) -> tuple[int, int]:
    """
    How deep `direct` and the shell route each carry a program.
    """
    return deepest(_direct), deepest(run_shell if real else folded)


def _cell(wrong: list[str]) -> str:
    return "ok" if not wrong else "FAIL"


def main(argv: list[str]) -> int:
    """
    Prove the examples named in `argv`, or all; print one row each.
    """
    real = "--in-process" not in argv
    named = [Path(a).resolve() for a in argv if a != "--in-process"]
    examples = named or sorted(SUITE.glob("*/examples/*.fpl"))
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(prove, examples, [real] * len(examples)))
        far = pool.submit(depths, real).result()
    width = max(len(r.name) for r in rows)
    print(f"{'example':<{width}}  seed  shell  slices  poison")
    for r in rows:
        done = f"{r.count - len(r.slices)}/{r.count}"
        print(
            f"{r.name:<{width}}  {_cell(r.seed):<4}  {_cell(r.shell):<5}"
            f"  {done:<6}  {_cell(r.poison)}"
        )
    for r in rows:
        for wrong in (*r.seed, *r.shell, *r.slices, *r.poison):
            print(f"{r.name}: {wrong}")
    held = sum(r.ok() for r in rows)
    how = "in real processes" if real else "in process"
    print(f"{held}/{len(rows)} examples: every executor agrees ({how})")
    print(
        f"depth: direct carries {far[0]} levels, the shell route {far[1]}"
        f" (measured {how}; a known limit, not judged)"
    )
    return 0 if held == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

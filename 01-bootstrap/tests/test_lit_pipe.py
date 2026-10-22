"""
The pipe of 01.01.03-pipe runs a pass as a filter on real FON.

A filter decodes the document of the pass's source representation, runs
the pass on that value and writes the document of its target; it never
renders a program to text and reads it back (TD-0006). A diagnostic is
a document too: it travels to the end of the pipe, where `render`
prints it the way `fpl run` does. The matrix over every example runs in
one child interpreter; real processes run on three examples only.
"""

import json
import subprocess
import sys

from corpus import PROGRAMS
from lit import PYTHON, env, fpl, lit

MATRIX = r"""
import contextlib, io, json, sys
from fpl.codec import CODECS, ERROR, read_repr
from fpl.errors import FplError
from fpl.pipe import PASSES, egress, ingress, run_filter
from fpl.run import run_file, run_now

assert set(PASSES) == {s.name for s in run_now.stages}, set(PASSES)
failed = []
for path in json.loads(sys.argv[1]):
    seen = io.StringIO()
    with contextlib.redirect_stdout(seen):
        status = run_file(path)
    value = open(path, encoding="utf-8").read()
    data = ingress(value)
    for stage in run_now.stages:
        data = run_filter(stage, data)
    got = (egress(data), int(read_repr(data) == ERROR.repr))
    if got != (seen.getvalue(), status):
        failed.append(f"{path} pipe")
    for stage in run_now.stages:
        given = CODECS[stage.source].fonify(value)
        try:
            value = stage(value)
        except FplError as error:
            if run_filter(stage, given) != ERROR.fonify(error):
                failed.append(f"{path} {stage.name} error")
            break
        if run_filter(stage, given) != CODECS[stage.target].fonify(value):
            failed.append(f"{path} {stage.name}")
print(json.dumps(failed))
"""


def test_the_pipe_in_process_is_fpl_run_on_every_example() -> None:
    """
    source, the five passes and render, chained in one process, print
    what `fpl run` prints and end in the same status; each pass alone
    writes exactly the document of its own result.
    """
    paths = json.dumps([str(p) for p in PROGRAMS])
    result = lit("import sys; sys.argv[1:] = [" + repr(paths) + "]" + MATRIX)
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout) == []


def test_no_stage_is_named_and_no_text_is_reparsed() -> None:
    """
    The filter is one formula over the pass registry: no if-chain on
    stage names, no second lexer or parser, no rendered text on the
    wire.
    """
    pipe = (PYTHON / "fpl" / "pipe" / "__init__.py").read_text()
    for banned in ('name == "', "lex_pass", "parse_pass", "fonify_text"):
        assert banned not in pipe, banned


def bash(script: str, stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    """
    Run `script` under `bash -o pipefail` with `fpl` the tangled tree.
    """
    fpl_sh = f'fpl() {{ "{sys.executable}" -m fpl "$@"; }}\n'
    return subprocess.run(
        ["bash", "-o", "pipefail", "-c", fpl_sh + script],
        input=stdin,
        capture_output=True,
        env=env(),
        timeout=60,
        check=False,
    )


def test_the_shell_pipe_is_fpl_run_on_three_examples() -> None:
    """
    `shell_script(run_now)` run by bash with pipefail prints what
    `fpl run` prints, with the same exit status, on real processes.
    """
    script = lit(
        "from fpl.pipe import shell_script\n"
        "from fpl.run import run_now\n"
        "print(shell_script(run_now))"
    )
    assert script.stdout.decode().strip() == (
        "fpl source | fpl lex | fpl parse | fpl desugar | fpl elaborate"
        " | fpl eval | fpl render"
    )
    for path in (PROGRAMS[0], PROGRAMS[len(PROGRAMS) // 2], PROGRAMS[-1]):
        piped = bash(script.stdout.decode(), path.read_bytes())
        ran = fpl("run", str(path))
        assert (piped.returncode, piped.stdout) == (
            ran.returncode,
            ran.stdout,
        ), path


def test_run_shell_is_direct_on_the_frames_example() -> None:
    """
    run_shell chains one `python -m fpl <pass>` process per stage with
    OS pipes; its bytes are the document of the in-process result.
    """
    frames = next(p for p in PROGRAMS if p.name == "01-frames.fpl")
    result = lit(
        "import sys\n"
        "from fpl.arrow import direct\n"
        "from fpl.codec import SOURCE, STACKS\n"
        "from fpl.pipe import run_shell\n"
        "from fpl.run import run_now\n"
        f"text = open({str(frames)!r}, encoding='utf-8').read()\n"
        "got = run_shell(run_now, SOURCE.fonify(text))\n"
        "assert got == STACKS.fonify(direct(run_now, text)), got\n"
    )
    assert result.returncode == 0, result.stderr.decode()


def test_a_pass_fed_another_representation_says_what_it_expected() -> None:
    """
    `fpl parse` given Syntax refuses on stderr and exits 1.
    """
    syntax = fpl("lex", stdin=fpl("source", stdin=b"1 2 +\n").stdout)
    syntax = fpl("parse", stdin=syntax.stdout)
    assert syntax.returncode == 0, syntax.stderr
    again = fpl("parse", stdin=syntax.stdout)
    assert again.returncode == 1
    assert again.stdout == b""
    assert b"expected Tokens, got Syntax" in again.stderr


def test_a_diagnostic_crosses_the_pipe_as_data() -> None:
    """
    The pass that fails writes an Error document and exits 1, a later
    pass passes it on unchanged and exits 1, and render prints the
    message `fpl run` prints, exiting 1.
    """
    source = fpl("source", stdin=b"nosuchword\n")
    tokens = fpl("lex", stdin=source.stdout)
    syntax = fpl("parse", stdin=tokens.stdout)
    failed = fpl("desugar", stdin=syntax.stdout)
    assert failed.returncode == 1, failed.stderr
    passed = fpl("elaborate", stdin=failed.stdout)
    assert (passed.returncode, passed.stdout) == (1, failed.stdout)
    shown = fpl("render", stdin=failed.stdout)
    said = lit(
        "from fpl.run import default\n"
        "try:\n"
        "    default.src('nosuchword\\n')\n"
        "except Exception as error:\n"
        "    print(error)\n"
    )
    assert said.stdout
    assert (shown.returncode, shown.stdout) == (1, said.stdout)


def test_a_deeply_nested_program_crosses_every_codec() -> None:
    """
    Forty levels of nesting is far past the depth FON's reader allows by
    default; the pipe reads deeper, so the chain still matches direct.
    """
    result = lit(
        "from fpl.arrow import direct\n"
        "from fpl.pipe import egress, ingress, run_filter\n"
        "from fpl.print import render\n"
        "from fpl.desugar import listing\n"
        "from fpl.run import run_now\n"
        "text = '[ ' * 40 + '1' + ' ]' * 40 + '\\n'\n"
        "data = ingress(text)\n"
        "for stage in run_now.stages:\n"
        "    data = run_filter(stage, data)\n"
        "want = render(listing(direct(run_now, text)))\n"
        "assert egress(data) == want, egress(data)\n"
    )
    assert result.returncode == 0, result.stderr.decode()


def test_a_pass_that_is_handed_to_cli_is_the_one_that_runs() -> None:
    """
    `cli` takes a Pass or its name; a Pass, registered or not, runs as
    itself, and one named like a registered pass does not become it.
    """
    code = (
        "from fpl.arrow import Pass\n"
        "from fpl.pipe import cli\n"
        "shout = Pass('lex', str.upper, 'Source', 'Source')\n"
        "raise SystemExit(cli(shout))\n"
    )
    document = fpl("source", stdin=b"abc\n").stdout
    got = lit(code, stdin=document)
    assert got.returncode == 0, got.stderr
    assert got.stdout == fpl("source", stdin=b"ABC\n").stdout


def test_a_document_of_an_unknown_representation_is_refused() -> None:
    """
    `fpl render` given a representation nobody defines says so on stderr
    and exits 1, with no traceback.
    """
    got = fpl("render", stdin=b"1 Unknown/1\n")
    assert (got.returncode, got.stdout) == (1, b"")
    assert b"Unknown" in got.stderr
    assert b"Traceback" not in got.stderr

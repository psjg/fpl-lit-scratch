"""run: a tool's tangled places turned into page places."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from support import GOOD, lit, md, page

from lit import run, web


def py(code: str) -> list[str]:
    """The argv that runs ``code`` in this interpreter."""
    return [sys.executable, "-c", code]


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A root holding the demo page, as the working directory."""
    page(tmp_path, "demo.md", GOOD)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_colon_form(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``file:line:col`` becomes ``page:line:col``."""
    code = "print('demo.py:2:5: E1 oops')"
    assert lit(root, "run", "--", *py(code)) == 0
    assert capsys.readouterr().out == "demo.md:13:5: E1 oops\n"


def test_traceback_form_and_exit_status(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A traceback line is rewritten on stderr; the status is kept."""
    code = "import sys; print('File \"demo.py\", line 1', file=sys.stderr);"
    code += " sys.exit(3)"
    assert lit(root, "run", "--page", str(root / "demo.md"), *py(code)) == 3
    assert capsys.readouterr().err == 'File "demo.md", line 12\n'


def test_absolute_path_and_out_of_range_line(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An absolute spelling is found; a line past the file is kept."""
    here = (root / "demo.py").resolve()
    code = f"print('{here}:1 {here}:99 demo.py:0 File \"demo.py\", line 9')"
    assert lit(root, "run", "--", *py(code)) == 0
    got = capsys.readouterr().out
    assert got.startswith("demo.md:12 ")
    assert f'{here}:99 demo.py:0 File "demo.py", line 9' in got


def test_no_pages_leaves_output_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With an empty table the text is written back as it came."""
    assert lit(tmp_path, "run", *py("print('demo.py:2')")) == 0
    assert capsys.readouterr().out == "demo.py:2\n"


def test_rewrite_with_an_empty_table() -> None:
    """`rewrite' returns its text when no file is known."""
    assert run.rewrite("a.py:1", {}, Path()) == "a.py:1"


def test_table_spellings(tmp_path: Path) -> None:
    """A file is known by name, absolute path and relative path."""
    t = web.Tangled("m.py", "p.md", ("x",), (4,))
    keys = set(run.table([t], tmp_path))
    assert {"m.py", str((tmp_path / "m.py").resolve())} <= keys


def test_a_longer_name_ending_in_a_file_is_left_alone(tmp_path: Path) -> None:
    """``other-demo.py`` is not ``demo.py``."""
    files, _ = web.tangle(web.read("p.md", md(GOOD)))
    table = run.table(files, tmp_path)
    assert run.rewrite("other-demo.py:1: x", table, tmp_path) == (
        "other-demo.py:1: x"
    )

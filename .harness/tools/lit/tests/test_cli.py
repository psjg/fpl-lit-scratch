"""The command line: tangle, check and the drift of written files."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from support import GOOD, lit, page


def mode(path: Path) -> int:
    """The permission bits of a file."""
    return stat.S_IMODE(path.stat().st_mode)


def test_tangle_writes_read_only_and_is_idempotent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tangled file is 0o444; a second tangle writes nothing."""
    page(tmp_path, "demo.md", GOOD)
    assert lit(tmp_path, "tangle") == 0
    target = tmp_path / "demo.py"
    want = "def add(a: int, b: int) -> int:\n    return a + b\n"
    assert target.read_bytes() == want.encode()
    assert mode(target) == 0o444
    assert "1 written" in capsys.readouterr().out
    assert lit(tmp_path, "tangle") == 0
    assert "0 written" in capsys.readouterr().out


def test_tangle_restores_a_chmodded_file(tmp_path: Path) -> None:
    """Identical bytes under a writable mode are made read-only."""
    page(tmp_path, "demo.md", GOOD)
    lit(tmp_path, "tangle")
    (tmp_path / "demo.py").chmod(0o644)
    assert lit(tmp_path, "tangle") == 0
    assert mode(tmp_path / "demo.py") == 0o444


def test_tangle_rewrites_a_read_only_file(tmp_path: Path) -> None:
    """A page edit replaces the read-only file it tangled before."""
    path = page(tmp_path, "demo.md", GOOD)
    lit(tmp_path, "tangle")
    path.write_text(path.read_text().replace("a + b", "b + a"))
    assert lit(tmp_path, "tangle") == 0
    assert "return b + a" in (tmp_path / "demo.py").read_text()
    assert mode(tmp_path / "demo.py") == 0o444


def test_tangle_with_default_root_and_relative_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --root the working directory is the root."""
    page(tmp_path, "demo.md", GOOD)
    monkeypatch.chdir(tmp_path)
    from lit.__main__ import main  # noqa: PLC0415 -- after chdir

    assert main(["tangle", "demo.md"]) == 0
    assert (tmp_path / "demo.py").is_file()


def test_check_clean_after_tangle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tangled page checks clean."""
    page(tmp_path, "demo.md", GOOD)
    lit(tmp_path, "tangle")
    capsys.readouterr()
    assert lit(tmp_path, "check") == 0
    assert capsys.readouterr().out == "lit check: 1 page(s), 0 finding(s)\n"


def test_check_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file not yet tangled is missing, at its first page line."""
    page(tmp_path, "demo.md", GOOD)
    assert lit(tmp_path, "check") == 1
    out = capsys.readouterr().out
    assert "demo.md:13: lit-drift: demo.py is missing" in out


def test_check_missing_empty_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file with no lines is missing at page line 1."""
    page(tmp_path, "e.md", "```python\n<<1 E\ne.py>>=\n```\n")
    assert lit(tmp_path, "check") == 1
    assert "e.md:1: lit-drift: e.py is missing" in capsys.readouterr().out


def test_check_differing_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A changed line is named by file:k and the page line."""
    page(tmp_path, "demo.md", GOOD)
    lit(tmp_path, "tangle")
    target = tmp_path / "demo.py"
    target.chmod(0o644)
    target.write_text("def add(a: int, b: int) -> int:\n    return 0\n")
    capsys.readouterr()
    assert lit(tmp_path, "check") == 1
    out = capsys.readouterr().out
    assert "demo.md:14: lit-drift: demo.py:2 differs from the page" in out


def test_check_extra_trailing_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lines added after the last tangled line are drift too."""
    page(tmp_path, "demo.md", GOOD)
    lit(tmp_path, "tangle")
    target = tmp_path / "demo.py"
    target.chmod(0o644)
    target.write_text(target.read_text() + "\n")
    capsys.readouterr()
    assert lit(tmp_path, "check") == 1
    out = capsys.readouterr().out
    assert "demo.md:14: lit-drift: demo.py:3 differs" in out


def test_check_file_emptied_from_the_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file on disk against a page that tangles nothing."""
    page(tmp_path, "e.md", "```python\n<<1 E\ne.py>>=\n```\n")
    (tmp_path / "e.py").write_text("x = 1\n")
    assert lit(tmp_path, "check") == 1
    assert "e.md:1: lit-drift: e.py:1 differs" in capsys.readouterr().out


STYLED = """
    # Demo

    ```python
    <<1 Functions
    demo.py>>=
    import os
    def add(a: int, b: int) -> int:
        return a+b
    ```
    """


def test_check_holds_the_tangle_to_ruff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unformatted code and a missing blank line, each at its line."""
    page(tmp_path, "demo.md", STYLED)
    lit(tmp_path, "tangle")
    capsys.readouterr()
    assert lit(tmp_path, "check") == 1
    remedy = " -- edit the page, then run lit tangle"
    assert capsys.readouterr().out.splitlines() == [
        "demo.md:7: lit-tangle-ruff: demo.py:2 is not as ruff format writes"
        " it" + remedy,
        "demo.md:7: lit-tangle-ruff: demo.py:2: E302 Expected 2 blank lines,"
        " found 0" + remedy,
        "lit check: 1 page(s), 2 finding(s)",
    ]


def test_check_reports_a_tangle_ruff_cannot_parse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ruff's own word, once, at the file's first page line."""
    page(tmp_path, "demo.md", STYLED.replace("int) -> int:", "int ->"))
    lit(tmp_path, "tangle")
    capsys.readouterr()
    assert lit(tmp_path, "check") == 1
    out = capsys.readouterr().out
    assert "demo.md:6: lit-tangle-ruff: error: Failed to parse demo.py" in out
    assert out.count("lit-tangle-ruff") == 1


def test_check_without_ruff_says_so(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ruff beside the interpreter or on PATH is a finding."""
    page(tmp_path, "demo.md", GOOD)
    lit(tmp_path, "tangle")
    capsys.readouterr()
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    assert lit(tmp_path, "check") == 1
    out = capsys.readouterr().out
    assert "demo.md:1: lit-tangle-ruff: ruff is neither beside" in out


def test_check_needs_no_ruff_without_python(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page that tangles no Python file is not held to ruff."""
    page(tmp_path, "n.md", "```text\n<<1 N\nn.txt>>=\nx=1\n```\n")
    lit(tmp_path, "tangle")
    capsys.readouterr()
    monkeypatch.delenv("PATH")
    assert lit(tmp_path, "check") == 0


def test_usage_error_exits_two() -> None:
    """No subcommand is a usage error, exit 2."""
    from lit.__main__ import main  # noqa: PLC0415 -- the one call

    with pytest.raises(SystemExit) as stop:
        main([])
    assert stop.value.code == 2


def test_check_sees_a_carriage_return(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Drift is judged on bytes: CRLF is not the page's LF."""
    page(tmp_path, "p.md", GOOD)
    assert lit(tmp_path, "tangle") == 0
    target = tmp_path / "demo.py"
    target.chmod(0o644)
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    capsys.readouterr()
    assert lit(tmp_path, "check") == 1
    assert "lit-drift" in capsys.readouterr().out

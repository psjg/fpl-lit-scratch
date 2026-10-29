"""lint: prose and code agree, and a page's examples pass."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from support import FENCE, GOOD, lit, md, page

from lit import lint, web


def run_lint(root: Path, text: str, capsys: pytest.CaptureFixture[str]) -> str:
    """Lint a page written to ``root``; what it printed."""
    page(root, "p.md", text)
    code = lit(root, "lint")
    out = capsys.readouterr().out
    assert code == (
        1 if "finding(s)" in out and " 0 finding" not in out else 0
    )
    return out


def test_clean_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A page whose prose names its code and whose examples pass."""
    out = run_lint(tmp_path, GOOD, capsys)
    assert out == "lit lint: 1 page(s), 0 finding(s)\n"


def test_unknown_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reference to nothing bound is lit-unknown at its line."""
    out = run_lint(
        tmp_path, md(GOOD) + "\nSee `ghost' and `add.nope'.\n", capsys
    )
    assert "p.md:17: lit-unknown: `ghost' names nothing the code" in out
    assert "`add.nope'" in out


def test_reference_inside_a_fence_is_not_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fenced `name' may quote anything."""
    text = md(GOOD) + f"\n{FENCE}text\n`ghost'\n{FENCE}\n"
    assert "0 finding(s)" in run_lint(tmp_path, text, capsys)


MODULE = """
    ---
    type: Note
    ---
    # Demo

    `Box.size' and `LIMIT' are described; `_hidden' is private.

    ```python
    <<1 Define the module
    m.py>>=
    import os.path as osp
    from typing import Any

    LIMIT: int = 3
    _PRIV = 2
    _skip = 1
    a, b = 1, 2


    class Box:
        count: int = 0

        def size(self) -> int:
            self.n = 1
            return 1

        def other(self) -> int:
            return 2

        def _private(self) -> int:
            return 3

    def free(x: Any) -> Any:
        return osp.join(x)
    ```

    ```text
    <<notes.txt>>=
    plain
    ```
    """


def test_unmentioned_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Public names the section's prose never names are findings."""
    out = run_lint(tmp_path, MODULE, capsys)
    assert "lit-unmentioned: `_PRIV'" in out
    assert "`count'" in out
    assert "`other'" in out
    assert "`free'" in out
    assert "`Box'" in out
    assert "`size'" not in out
    assert "`LIMIT'" not in out
    assert "`_skip'" not in out
    assert "`a'" in out
    assert "`b'" in out
    assert "`_private'" not in out


def test_qualified_reference_and_allow_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Cls.meth' satisfies meth; lit-allow waives a name."""
    allow = "lit-allow: [other, free, _PRIV, a, b]"
    text = md(MODULE).replace("type: Note", f"type: Note\n{allow}")
    text = text.replace("`LIMIT' are", "`LIMIT' `Box' `count' are")
    text = text.replace("`_hidden'", "`_skip'")
    out = run_lint(tmp_path, text, capsys)
    assert "0 finding(s)" in out


def test_two_files_from_one_chunk_owe_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One chunk placed in two files reports its name once."""
    text = """
        # Two

        ```python
        <<1 Shared
        a.py b.py>>=
        def twice() -> int:
            return 2
        ```
        """
    out = run_lint(tmp_path, text, capsys)
    assert out.count("lit-unmentioned") == 1


EX = """
    ---
    type: Note
    ---
    # Ex

    The `add' sums.

    {prose}

    ```python
    <<1 Add
    m.py>>=
    def add(a: int, b: int) -> int:
        return a + b
    ```

    ```pycon
    {example}
    ```
    """


@pytest.mark.parametrize(
    ("example", "message"),
    [
        (">>> add(1, 2)\n3", None),
        (">>> add(1, 2)\n4", "p.md:18: lit-example: expected '4', got '3'"),
        (">>> add(1, None)", "lit-example: raised TypeError"),
    ],
)
def test_examples(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    example: str,
    message: str | None,
) -> None:
    """A pycon fence passes, fails on a value, or on an exception."""
    body = md(EX).format(prose="Adds: `add'.", example=example)
    out = run_lint(tmp_path, body, capsys)
    if message is None:
        assert "0 finding(s)" in out
    else:
        assert message in out


def test_example_without_python_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An example with no Python file to run in is a finding."""
    text = f"""
        {FENCE}text
        <<1 Say hi
        n.txt>>=
        hi
        {FENCE}

        {FENCE}pycon
        >>> 1
        1
        {FENCE}
        """
    out = run_lint(tmp_path, text.replace("text\n", "python\n", 1), capsys)
    assert "lit-example: an example, and no Python file to run it in" in out


def test_module_that_fails_to_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A module that raises on load is one finding at line 1."""
    text = """
        # Boom

        `x' is bound.

        ```python
        <<1 Bind x and fail
        boom_mod.py>>=
        x = 1
        raise RuntimeError("no")
        ```

        ```pycon
        >>> x
        1
        ```
        """
    out = run_lint(tmp_path, text, capsys)
    assert "p.md:1: lit-example: boom_mod.py does not load" in out
    assert "boom_mod" not in sys.modules


def test_load_restores_the_module_it_replaced(tmp_path: Path) -> None:
    """A tangle named like a live module leaves that module in place."""
    import textwrap  # noqa: PLC0415 -- the module whose entry is saved

    t = web.Tangled("textwrap.py", "p.md", ("y = 1",), (1,))
    space = lint.load(t, tmp_path)
    assert space["y"] == 1
    assert sys.modules["textwrap"] is textwrap


def test_dotted() -> None:
    """A path becomes its module name, a package's init its package."""
    assert lint.dotted("fpl/lex.py") == "fpl.lex"
    assert lint.dotted("fpl/__init__.py") == "fpl"


def test_qualified_reference_must_name_a_member(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Cls.member' must be a member of that class.

    A reference into an import is not checked past the module.
    """
    text = md(MODULE) + "\nSee `Box.free', `Box.size' and `osp.join'.\n"
    out = run_lint(tmp_path, text, capsys)
    assert "`Box.free' names nothing" in out
    assert "`Box.size' names nothing" not in out
    assert "`osp.join' names nothing" not in out


def test_load_restores_a_none_entry(tmp_path: Path) -> None:
    """An entry of None in sys.modules is put back, not deleted."""
    files, _ = web.tangle(web.read("p.md", md(GOOD)))
    sys.modules["demo"] = cast("ModuleType", None)  # the case under test
    try:
        lint.load(files[0], tmp_path)
        assert "demo" in sys.modules
        assert sys.modules["demo"] is None
    finally:
        del sys.modules["demo"]


PACKAGE = """
    # Pkg

    `VALUE' is the helper's.

    ```python
    <<1 Import the value
    pkg/__init__.py>>=
    from .helper import VALUE
    ```

    ```pycon
    >>> VALUE
    7
    ```
    """


def test_a_package_root_runs_relative_imports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An __init__.py file is a package; relative imports resolve."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "helper.py").write_text("VALUE = 7\n")
    out = run_lint(tmp_path, PACKAGE, capsys)
    assert "0 finding(s)" in out, out

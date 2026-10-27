"""The web: how a page is read, and every finding the reader makes."""

from __future__ import annotations

from pathlib import Path

import pytest
from lit import web
from support import GOOD, lit, md, page


def read(text: str) -> web.Page:
    """A page read from dedented text, named ``p.md``."""
    return web.read("p.md", md(text))


def rules(text: str) -> list[str]:
    """The web's findings of a page, as printed."""
    found = web.tangle(read(text))[1]
    return [str(f) for f in found]


def test_tangle_indents_uses_and_keeps_blank_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A use is indented as it stands; a blank line stays empty."""
    page(
        tmp_path,
        "p.md",
        """
        ```python
        <<out/m.py>>=
        class A:
            <<Body>>
        ```

        ```python
        <<Body>>=
        x = 1

        <<Inner>>
        ```

        ```python
        <<Inner>>=
        y = 2
        ```
        """,
    )
    assert lit(tmp_path, "tangle") == 0
    got = (tmp_path / "out" / "m.py").read_text()
    assert got == "class A:\n    x = 1\n\n    y = 2\n"
    assert "1 file(s), 1 written" in capsys.readouterr().out


def test_plus_equals_continues_a_chunk(tmp_path: Path) -> None:
    """A ``+=`` chunk adds its lines after the ``=`` chunk's."""
    page(
        tmp_path,
        "p.md",
        """
        ```python
        <<m.py>>=
        <<Body>>
        ```

        ```python
        <<Body>>=
        a = 1
        ```

        ```python
        <<Body>>+=
        b = 2
        ```
        """,
    )
    assert lit(tmp_path, "tangle") == 0
    assert (tmp_path / "m.py").read_text() == "a = 1\nb = 2\n"


def test_python_fence_without_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A python fence that names no chunk is a lit-header finding."""
    text = "```python\nx = 1\n```\n\n```python\n```\n"
    found = [str(f) for f in web.read("p.md", text).findings]
    assert found[0].startswith("p.md:1: lit-header: a python fence opens")
    assert found[1].startswith("p.md:5: lit-header")
    assert capsys.readouterr().out == ""


def test_plus_before_equals() -> None:
    """A ``+=`` that no ``=`` precedes is a finding at its line."""
    got = rules("""
        ```python
        <<m.py>>+=
        x = 1
        ```
        """)
    assert got == ["p.md:2: lit-web: += before = of m.py"]


def test_second_equals() -> None:
    """A second ``=`` of one name is a finding at its line."""
    got = rules("""
        ```python
        <<m.py>>=
        x = 1
        ```

        ```python
        <<m.py>>=
        y = 1
        ```
        """)
    assert got == ["p.md:7: lit-web: a second = of m.py"]


def test_undefined_use() -> None:
    """A use of a chunk never defined names its page line."""
    got = rules("""
        ```python
        <<m.py>>=
        x = 1
          <<Nope>>
        ```
        """)
    assert got == ["p.md:4: lit-web: <<Nope>> undefined"]


def test_unused_chunk() -> None:
    """A chunk no file reaches is a finding at its first line."""
    got = rules("""
        ```python
        <<m.py>>=
        x = 1
        ```

        ```python
        <<Lost>>=
        y = 1
        ```
        """)
    assert got == ["p.md:7: lit-web: <<Lost>> is never used by a file"]


def test_cycle() -> None:
    """A chunk that uses itself, through another, is a cycle."""
    got = rules("""
        ```python
        <<m.py>>=
        <<A>>
        ```

        ```python
        <<A>>=
        <<B>>
        ```

        ```python
        <<B>>=
        <<A>>
        ```
        """)
    assert got == ["p.md:7: lit-web: cycle: m.py -> A -> B -> A"]


def test_unclosed_fence() -> None:
    """A fence that never closes is a finding, and reading stops."""
    got = read("""
        text

        ```python
        <<m.py>>=
        x = 1
        """).findings
    assert [str(f) for f in got] == ["p.md:3: lit-fence: a fence never closes"]


def test_cli_prints_findings_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """tangle prints a web's finding, writes nothing, and exits 1."""
    page(tmp_path, "p.md", "```python\n<<m.py>>+=\nx\n```\n")
    assert lit(tmp_path, "tangle") == 1
    out = capsys.readouterr().out
    assert "p.md:2: lit-web: += before = of m.py" in out
    assert "lit tangle: 1 page(s), 1 finding(s)" in out
    assert not (tmp_path / "m.py").exists()


def test_two_pages_own_one_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The second page naming a file is told who owns it."""
    page(tmp_path, "a.md", GOOD)
    page(tmp_path, "b.md", GOOD)
    assert (
        lit(tmp_path, "check", str(tmp_path / "a.md"), str(tmp_path / "b.md"))
        == 1
    )
    out = capsys.readouterr().out
    assert "b.md:1: lit-web: demo.py is also a file of a.md" in out


def test_section_of_outside_any_chunk() -> None:
    """A page line in no chunk belongs to no section."""
    assert read(GOOD).section_of(1) == 0


def test_discover_skips_hidden_and_plain_notes(tmp_path: Path) -> None:
    """Only Markdown with a chunk header, outside dot-folders."""
    page(tmp_path, "a/real.md", GOOD)
    page(tmp_path, ".hid/real.md", GOOD)
    page(tmp_path, "plain.md", "# Just prose\n")
    assert web.discover(tmp_path) == [tmp_path / "a" / "real.md"]


def test_front_matter_allowlist() -> None:
    """lit-allow names come from front matter; other lines are free."""
    got = read("""
        ---
        type: Note
        lit-allow: [a, b ,, c]
        ---
        text
        """)
    assert got.allow == {"a", "b", "c"}


def test_unclosed_front_matter_is_prose() -> None:
    """Front matter that never closes is read as ordinary prose."""
    got = read("---\nlit-allow: [a]\ntext\n")
    assert got.allow == frozenset()
    assert len(got.sections) == 1


def test_non_python_fence_is_prose_and_blank_tail_is_dropped() -> None:
    """A text fence stays prose; blank prose after the last chunk is not
    a section."""
    got = read("""
        ```text
        <<m.py>>=
        ```

        ```python
        <<m.py>>=
        x = 1
        ```

        """)
    assert [s.number for s in got.sections] == [1]
    assert got.sections[0].chunk is not None
    assert got.sections[0].prose[0].text == "```text"

"""The web: how a page is read, and every finding the reader makes."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import GOOD, lit, md, page

from lit import web


def read(text: str) -> web.Page:
    """A page read from dedented text, named ``p.md``."""
    return web.read("p.md", md(text))


def rules(text: str) -> list[str]:
    """The web's findings of a page, as printed."""
    found = web.tangle(read(text))[1]
    return [str(f) for f in found]


def files(text: str) -> dict[str, str]:
    """Each file a page tangles to, by name, with its text."""
    return {t.name: t.text for t in web.tangle(read(text))[0]}


def test_tangle_indents_uses_and_keeps_blank_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A use is indented as it stands; a blank line stays empty."""
    page(
        tmp_path,
        "p.md",
        """
        ---
        tangle: out/m.py
        ---
        ```python
        <<Define A>>=
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
        ---
        tangle: m.py
        ---
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


def test_parts_are_the_unused_chunks_in_page_order() -> None:
    """A chunk no other uses is a part; a used one goes where used."""
    got = files("""
        ---
        tangle: m.py
        ---
        ```python
        <<First>>=
        a = 1
        <<Used>>
        ```

        ```python
        <<Used>>=
        b = 2
        ```

        ```python
        <<Second>>=
        c = 3
        ```
        """)
    assert got == {"m.py": "a = 1\nb = 2\n\nc = 3\n"}


def test_imports_follow_the_docstring() -> None:
    """Parts of imports alone move up behind the docstring, in order."""
    got = files("""
        ---
        tangle: m.py
        ---
        ```python
        <<Say what it is>>=
        \"\"\"Doc.\"\"\"
        ```

        ```python
        <<Use them>>=
        x = re.compile(path.sep)
        ```

        ```python
        <<Import re>>=
        import re
        ```

        ```python
        <<Import a path>>=
        # the separator
        from os import path
        ```
        """)
    want = '"""Doc."""\n\nimport re\n\n# the separator\nfrom os import path'
    assert got == {"m.py": want + "\n\nx = re.compile(path.sep)\n"}


def test_imports_come_first_without_a_docstring() -> None:
    """Without a docstring, the imports open the file."""
    got = files("""
        ---
        tangle: m.py
        ---
        ```python
        <<Use it>>=
        x = os.sep
        ```

        ```python
        <<Import it>>=
        import os
        ```
        """)
    assert got == {"m.py": "import os\n\nx = os.sep\n"}


def test_two_blank_lines_stand_around_a_def_or_a_class() -> None:
    """PEP 8's gaps: two around a top def or class, one otherwise."""
    got = files("""
        ---
        tangle: m.py
        ---
        ```python
        <<A constant>>=
        X = 1
        ```

        ```python
        <<A function>>=
        def f() -> int:
            return X
        ```

        ```python
        <<A use>>=
        Y = f()
        ```

        ```python
        <<A class>>=
        @final
        class C:
            pass
        ```
        """)
    want = "X = 1\n\n\ndef f() -> int:\n    return X\n\n\nY = f()\n\n\n"
    assert got == {"m.py": want + "@final\nclass C:\n    pass\n"}


def test_parts_that_are_not_python_stand_one_line_apart() -> None:
    """A part Python cannot read is neither imports nor a def."""
    got = files("""
        ---
        tangle: notes.txt
        ---
        ```python
        <<One>>=
        one two
        ```

        ```python
        <<Two>>=
        three four
        ```
        """)
    assert got == {"notes.txt": "one two\n\nthree four\n"}


SECOND = """
    ---
    tangle: m.py
    ---
    ```python
    <<Say what it is
    lib.py 1>>=
    \"\"\"Doc.\"\"\"
    ```

    ```python
    <<Set x
    lib.py 2>>=
    x = 1
    ```

    ```python
    <<Show x>>=
    print(x)
    ```
    """


def test_a_header_places_its_chunk_in_a_second_file() -> None:
    """A file line adds a file; the chunk stays in the page's own."""
    tangled, findings = web.tangle(read(SECOND))
    assert findings == []
    assert [t.name for t in tangled] == ["lib.py", "m.py"]
    lib, m = (t.text for t in tangled)
    assert lib == '"""Doc."""\n\nx = 1\n'
    assert m == '"""Doc."""\n\nx = 1\n\nprint(x)\n'


def test_a_two_line_header_keeps_the_page_lines() -> None:
    """The body follows the header's last line; a gap, the part's."""
    got = read(SECOND)
    [doc, x, show] = got.chunks()
    assert (doc.name, doc.line, doc.head, doc.places) == (
        "Say what it is",
        6,
        2,
        (("lib.py", 1),),
    )
    lib = web.tangle(got)[0][0]
    assert lib.origin == (7, x.line, x.line + 1)
    assert got.section_of(5) == got.section_of(7) == 1
    assert got.section_of(4) == 0
    assert got.files() == ["lib.py", "m.py"]
    assert show.places == ()


def test_places_order_a_file_by_their_numbers() -> None:
    """A file named only on headers holds those parts, by number."""
    text = """
        ```python
        <<Later
        f.py 20>>=
        b = 2
        ```

        ```python
        <<Sooner
        f.py 10>>=
        a = 1
        ```
        """
    assert files(text) == {"f.py": "a = 1\n\nb = 2\n"}
    assert read(text).files() == ["f.py"]


def test_a_place_in_the_page_file_moves_the_part() -> None:
    """A part placed in the front matter's file stands at its place."""
    got = files("""
        ---
        tangle: m.py
        ---
        ```python
        <<A>>=
        a = 1
        ```

        ```python
        <<B>>=
        b = 2
        ```

        ```python
        <<C
        m.py 2>>=
        c = 3
        ```
        """)
    assert got == {"m.py": "a = 1\n\nc = 3\n\nb = 2\n"}


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
        ---
        tangle: m.py
        ---
        ```python
        <<A>>+=
        x = 1
        ```
        """)
    assert got == ["p.md:5: lit-web: += before = of A"]


def test_second_equals() -> None:
    """A second ``=`` of one name is a finding at its line."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<A>>=
        x = 1
        ```

        ```python
        <<A>>=
        y = 1
        ```
        """)
    assert got == ["p.md:10: lit-web: a second = of A"]


def test_undefined_use() -> None:
    """A use of a chunk never defined names its page line."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<A>>=
        x = 1
          <<Nope>>
        ```
        """)
    assert got == ["p.md:7: lit-web: <<Nope>> undefined"]


def test_unused_chunk() -> None:
    """A chunk no file reaches is a finding at its first line."""
    got = rules("""
        ```python
        <<A
        m.py 1>>=
        x = 1
        ```

        ```python
        <<Lost>>=
        y = 1
        ```
        """)
    assert got == ["p.md:8: lit-web: <<Lost>> is never used by a file"]


def test_cycle() -> None:
    """A chunk that uses itself, through another, is a cycle."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<Top>>=
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
    assert got == ["p.md:10: lit-web: cycle: Top -> A -> B -> A"]


def test_root_chunk() -> None:
    """A chunk named like a path is the old file root, and refused."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<m.py>>=
        <<A>>
        ```

        ```python
        <<A>>=
        x = 1
        ```
        """)
    assert got == [
        "p.md:5: lit-web: root chunk <<m.py>>: name the file in front"
        " matter `tangle:` and drop this chunk",
        "p.md:2: lit-web: m.py has no parts: every chunk is used by another",
        "p.md:10: lit-web: <<A>> is never used by a file",
    ]


def test_no_file() -> None:
    """A page with chunks names a file, or says it has none."""
    got = rules("""
        ```python
        <<A>>=
        x = 1
        ```
        """)
    assert got == [
        "p.md:1: lit-web: no file: add `tangle: <path>` to the front matter"
    ]


def test_a_page_of_prose_tangles_nothing() -> None:
    """Without chunks and without a file there is nothing to say."""
    assert web.tangle(read("# Just prose\n")) == ([], [])


def test_a_file_without_parts() -> None:
    """A file the front matter names, and no chunk to fill it."""
    got = rules("""
        ---
        tangle: m.py
        ---
        # Nothing yet
        """)
    assert got == [
        "p.md:2: lit-web: m.py has no parts: every chunk is used by another"
    ]


def test_two_parts_at_one_place() -> None:
    """Two chunks placed at one number of one file."""
    got = rules("""
        ```python
        <<A
        f.py 1>>=
        a = 1
        ```

        ```python
        <<B
        f.py 1>>=
        b = 2
        ```
        """)
    assert got == [
        "p.md:9: lit-web: <<A>> and <<B>> both stand at f.py 1",
        "p.md:9: lit-web: <<B>> is never used by a file",
    ]


def test_a_file_line_that_does_not_parse() -> None:
    """A header line after the name is a path and a place, or wrong."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<A
        f.py one>>=
        a = 1
        ```
        """)
    assert got == [
        "p.md:6: lit-web: <<A>>: 'f.py one' is no file line -- write a path"
        " and a place, as fpl/lex.py 3"
    ]


def test_a_continuation_places_nothing() -> None:
    """File lines stand on the ``=`` header, never on a ``+=``."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<A>>=
        a = 1
        ```

        ```python
        <<A
        f.py 1>>+=
        b = 2
        ```
        """)
    assert got == [
        "p.md:10: lit-web: <<A>>+= places nothing: put file lines on its ="
    ]


def test_a_front_matter_file_that_is_no_path() -> None:
    """``tangle:`` names a path, with a suffix."""
    got = rules("""
        ---
        tangle: nowhere
        ---
        ```python
        <<A>>=
        a = 1
        ```
        """)
    assert got == ["p.md:2: lit-web: nowhere is not a path inside the root"]


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
    """`tangle' prints a web's finding, writes nothing, and exits 1."""
    page(
        tmp_path,
        "p.md",
        "---\ntangle: m.py\n---\n```python\n<<A>>+=\nx\n```\n",
    )
    assert lit(tmp_path, "tangle") == 1
    out = capsys.readouterr().out
    assert "p.md:5: lit-web: += before = of A" in out
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
    """A text fence stays prose.

    Blank prose after the last chunk is not a section.
    """
    got = read("""
        ```text
        <<M>>=
        ```

        ```python
        <<M>>=
        x = 1
        ```

        """)
    assert [s.number for s in got.sections] == [1]
    assert got.sections[0].chunk is not None
    assert got.sections[0].prose[0].text == "```text"


def test_a_file_outside_the_root_is_refused() -> None:
    """A file chunk with a ``..`` or ``.`` segment writes nothing."""
    text = md(GOOD).replace("tangle: demo.py", "tangle: ../demo.py")
    files, findings = web.tangle(web.read("p.md", text))
    assert files == []
    assert any("not a path inside the root" in str(f) for f in findings)


def test_discover_finds_a_header_with_trailing_space(tmp_path: Path) -> None:
    """Discovery reads a header as the reader does, spaces and all."""
    text = md(GOOD).replace("<<Functions>>=", "<<Functions>>= ")
    page(tmp_path, "p.md", text)
    assert web.discover(tmp_path) == [tmp_path / "p.md"]


def test_discover_finds_a_two_line_header(tmp_path: Path) -> None:
    """A page whose headers all take two lines is found."""
    text = SECOND.replace("<<Show x>>=", "<<Show x\n    m.py 3>>=")
    page(tmp_path, "p.md", text)
    page(tmp_path, "use.md", "```python\n<<A use>>\n```\n")
    assert web.discover(tmp_path) == [tmp_path / "p.md"]


def test_front_matter_names_the_file() -> None:
    """``tangle:`` in front matter, with its page line."""
    assert read(GOOD).tangle == ("demo.py", 2)

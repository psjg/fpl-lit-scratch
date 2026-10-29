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
        ```python
        <<1 Define A
        out/m.py>>=
        class A:
            <<Body>>
        ```

        ```python
        <<1.1 Body
        out/m.py>>=
        x = 1

        <<Inner>>
        ```

        ```python
        <<1.1.1 Inner
        out/m.py>>=
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
        <<1 Body
        m.py>>=
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


def test_parts_stand_in_the_order_of_their_places() -> None:
    """Places sort by their numbers, not as text; page order is free.

    A used chunk is no part: it stands where it is used.
    """
    got = files("""
        ```python
        <<3.10 Ten
        m.py>>=
        j = 10
        ```

        ```python
        <<3.2 Two
        m.py>>=
        b = 2
        <<Used>>
        ```

        ```python
        <<3.2.1 Used
        m.py>>=
        c = 3
        ```

        ```python
        <<3 Three
        m.py>>=
        a = 1
        ```
        """)
    assert got == {"m.py": "a = 1\n\nb = 2\nc = 3\nj = 10\n"}


def test_the_gap_between_two_parts() -> None:
    """Two around a def or class, none between siblings, else one.

    Places 1 and 2 have no parent, 2 and 3.1 have different ones, and
    3.1 and 3.2 share 3.
    """
    got = files("""
        ```python
        <<1 Say what it is
        m.py>>=
        \"\"\"Doc.\"\"\"
        ```

        ```python
        <<2 Import it
        m.py>>=
        import os
        ```

        ```python
        <<3.1 A constant
        m.py>>=
        X = os.sep
        ```

        ```python
        <<3.2 Another
        m.py>>=
        Y = 2
        ```

        ```python
        <<3.3 A function
        m.py>>=
        def f() -> int:
            return Y
        ```

        ```python
        <<3.4 A use
        m.py>>=
        Z = f()
        ```

        ```python
        <<3.5 A class
        m.py>>=
        @final
        class C:
            pass
        ```
        """)
    want = '"""Doc."""\n\nimport os\n\nX = os.sep\nY = 2\n\n\n'
    want += "def f() -> int:\n    return Y\n\n\nZ = f()\n\n\n"
    assert got == {"m.py": want + "@final\nclass C:\n    pass\n"}


def test_parts_that_are_not_python_have_no_def() -> None:
    """A part Python cannot read is spaced by its place alone."""
    got = files("""
        ```python
        <<1 One
        notes.txt>>=
        one two
        ```

        ```python
        <<2 Two
        notes.txt>>=
        three four
        ```
        """)
    assert got == {"notes.txt": "one two\n\nthree four\n"}


SECOND = """
    ```python
    <<1 Say what it is
    m.py lib.py>>=
    \"\"\"Doc.\"\"\"
    ```

    ```python
    <<3 Set x
    m.py 2:lib.py>>=
    x = 1
    ```

    ```python
    <<2 Show x
    m.py>>=
    print(x)
    ```
    """


def test_a_header_names_two_files_and_a_place_of_its_own() -> None:
    """A path may carry its chunk's place there, before a colon."""
    tangled, findings = web.tangle(read(SECOND))
    assert findings == []
    assert [t.name for t in tangled] == ["m.py", "lib.py"]
    m, lib = (t.text for t in tangled)
    assert m == '"""Doc."""\n\nprint(x)\n\nx = 1\n'
    assert lib == '"""Doc."""\n\nx = 1\n'


def test_a_header_keeps_the_page_lines() -> None:
    """The body follows the header's last line; a gap, the part's."""
    got = read(SECOND)
    [doc, x, show] = got.chunks()
    assert (doc.name, doc.line, doc.head, doc.place) == (
        "Say what it is",
        3,
        2,
        (1,),
    )
    assert doc.files == (("m.py", (1,)), ("lib.py", (1,)))
    assert x.files == (("m.py", (3,)), ("lib.py", (2,)))
    lib = web.tangle(got)[0][1]
    assert lib.origin == (4, x.line, x.line + 1)
    assert got.section_of(2) == got.section_of(4) == 1
    assert got.section_of(1) == got.section_of(5) == 0
    assert got.files() == ["m.py", "lib.py"]
    assert show.place == (2,)


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
        <<A>>+=
        x = 1
        ```
        """)
    assert got == ["p.md:2: lit-web: += before = of A"]


def test_second_equals() -> None:
    """A second ``=`` of one name is a finding at its line."""
    got = rules("""
        ```python
        <<1 A
        m.py>>=
        x = 1
        ```

        ```python
        <<2 A
        m.py>>=
        y = 1
        ```
        """)
    assert got == ["p.md:9: lit-web: a second = of A"]


def test_undefined_use() -> None:
    """A use of a chunk never defined names its page line."""
    got = rules("""
        ```python
        <<1 A
        m.py>>=
        x = 1
          <<Nope>>
        ```
        """)
    assert got == ["p.md:5: lit-web: <<Nope>> undefined"]


def test_a_header_without_a_place_or_a_path() -> None:
    """A definition opens its name line with a place, a path follows.

    A chunk that names no file is not also said to be unused.
    """
    got = rules("""
        ```python
        <<A
        m.py>>=
        a = 1
        ```

        ```python
        <<1 B>>=
        b = 2
        ```
        """)
    assert got == [
        "p.md:2: lit-web: <<A>>= has no place: open its line with one",
        "p.md:8: lit-web: <<B>>= names no file: put a path under it",
    ]


def test_a_path_that_does_not_parse() -> None:
    """A path is a path, or a place, a colon and a path, or wrong.

    All of a header's paths stand on the line under its name.
    """
    got = rules("""
        ```python
        <<1 A
        m.py one:f.py>>=
        a = 1
        ```

        ```python
        <<2 B
        m.py
        n.py>>=
        b = 2
        ```
        """)
    assert got == [
        "p.md:3: lit-web: <<A>>: 'one:f.py' is no path -- write a path, or"
        " a place, a colon and a path, as 2:fpl/lex.py",
        "p.md:10: lit-web: <<B>>= names its files on one line, not 2",
    ]


def test_a_continuation_places_nothing() -> None:
    """A ``+=`` carries no path; its ``=`` gives place and files."""
    got = rules("""
        ```python
        <<1 A
        m.py>>=
        a = 1
        ```

        ```python
        <<A
        f.py>>+=
        b = 2
        ```
        """)
    assert got == ["p.md:8: lit-web: <<A>>+= places nothing: its = does"]


def test_front_matter_tangle_is_gone() -> None:
    """A ``tangle:`` key names nothing now, and says so."""
    got = rules("""
        ---
        tangle: m.py
        ---
        ```python
        <<1 A
        m.py>>=
        a = 1
        ```
        """)
    assert got == [
        "p.md:2: lit-web: `tangle:` is gone: name each chunk's files on its"
        " header"
    ]


def test_root_chunk() -> None:
    """A chunk named like a path is the old file root, and refused.

    So is a chunk that only uses others: its parts take places.
    """
    got = rules("""
        ```python
        <<1 m.py
        m.py>>=
        <<A>>

        <<B>>
        ```

        ```python
        <<1.1 A
        m.py>>=
        x = 1
        ```

        ```python
        <<1.2 B
        m.py>>=
        y = 1
        ```
        """)
    assert got == [
        "p.md:3: lit-web: root chunk <<m.py>>: name the file on the headers"
        " of its parts and drop this chunk",
        "p.md:3: lit-web: <<m.py>> only uses other chunks: list its parts by"
        " place and drop this chunk",
    ]


def test_a_used_chunk_stands_under_its_user() -> None:
    """Under its user's place and in its files, for every user."""
    got = rules("""
        ```python
        <<1 A
        m.py>>=
        a = 1
        <<C>>
        ```

        ```python
        <<2 B
        m.py n.py>>=
        b = 2
        <<C>>
        ```

        ```python
        <<1.1 C
        m.py>>=
        c = 3
        ```

        ```python
        <<1 D
        n.py>>=
        d = 4
        <<E>>
        ```

        ```python
        <<1 E
        n.py>>=
        e = 5
        ```
        """)
    assert got == [
        "p.md:17: lit-web: <<C>> is used in <<B>>: place it under 2, in m.py"
        " n.py",
        "p.md:30: lit-web: <<E>> is used in <<D>>: place it under 1, in n.py",
        "p.md:30: lit-web: <<D>> and <<E>> both stand at n.py 1",
    ]


def test_two_chunks_at_one_place() -> None:
    """Two chunks at one place of one file; a ``+=`` is no second."""
    got = rules("""
        ```python
        <<1 A
        f.py>>=
        a = 1
        ```

        ```python
        <<A>>+=
        b = 1
        ```

        ```python
        <<1 B
        f.py>>=
        b = 2
        ```
        """)
    assert got == ["p.md:14: lit-web: <<A>> and <<B>> both stand at f.py 1"]


def test_cycle() -> None:
    """A chunk that uses itself, through another, is a cycle.

    Two chunks that only use each other fill no file and are never
    used by one.
    """
    got = rules("""
        ```python
        <<1 Top
        m.py>>=
        top = 0
        <<A>>
        ```

        ```python
        <<1.1 A
        m.py>>=
        a = 1
        <<B>>
        ```

        ```python
        <<1.1.1 B
        m.py>>=
        b = 2
        <<A>>
        ```

        ```python
        <<1 C
        n.py>>=
        c = 3
        <<D>>
        ```

        ```python
        <<1.1 D
        n.py>>=
        d = 4
        <<C>>
        ```
        """)
    assert got == [
        "p.md:10: lit-web: <<A>> is used in <<B>>: place it under 1.1.1,"
        " in m.py",
        "p.md:24: lit-web: <<C>> is used in <<D>>: place it under 1.1, in"
        " n.py",
        "p.md:10: lit-web: cycle: Top -> A -> B -> A",
        "p.md:24: lit-web: <<C>> is never used by a file",
        "p.md:31: lit-web: <<D>> is never used by a file",
    ]


def test_a_page_of_prose_tangles_nothing() -> None:
    """Without chunks there is nothing to say."""
    assert web.tangle(read("# Just prose\n")) == ([], [])


def test_unclosed_fence() -> None:
    """A fence that never closes is a finding, and reading stops."""
    got = read("""
        text

        ```python
        <<1 A
        m.py>>=
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
        "```python\n<<1 A\nm.py>>=\nx\n```\n```python\n<<B>>+=\ny\n```\n",
    )
    assert lit(tmp_path, "tangle") == 1
    out = capsys.readouterr().out
    assert "p.md:7: lit-web: += before = of B" in out
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
    assert got.findings == ()


def test_unclosed_front_matter_is_prose() -> None:
    """Front matter that never closes is read as ordinary prose."""
    got = read("---\nlit-allow: [a]\ntangle: m.py\ntext\n")
    assert got.allow == frozenset()
    assert got.findings == ()
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
        <<1 M
        m.py>>=
        x = 1
        ```

        """)
    assert [s.number for s in got.sections] == [1]
    assert got.sections[0].chunk is not None
    assert got.sections[0].prose[0].text == "```text"


def test_a_file_outside_the_root_is_refused() -> None:
    """A path with a ``..`` or ``.`` segment writes nothing."""
    text = md(GOOD).replace("demo.py>>=", "../demo.py>>=")
    tangled, findings = web.tangle(web.read("p.md", text))
    assert tangled == []
    assert [str(f) for f in findings] == [
        "p.md:12: lit-web: ../demo.py is not a path inside the root",
        "p.md:12: lit-web: <<Functions>> is never used by a file",
    ]


def test_discover_finds_a_header_with_trailing_space(tmp_path: Path) -> None:
    """Discovery reads a header as the reader does, spaces and all."""
    text = "```python\n<<1 A \nm.py>>= \nx = 1\n```\n"
    page(tmp_path, "p.md", text)
    assert web.discover(tmp_path) == [tmp_path / "p.md"]
    assert files(text) == {"m.py": "x = 1\n"}


def test_discover_finds_a_one_line_header(tmp_path: Path) -> None:
    """A page whose only header is a continuation is found."""
    page(tmp_path, "p.md", "```python\n<<A>>+=\n```\n")
    page(tmp_path, "use.md", "```python\n<<A use>>\n```\n")
    assert web.discover(tmp_path) == [tmp_path / "p.md"]

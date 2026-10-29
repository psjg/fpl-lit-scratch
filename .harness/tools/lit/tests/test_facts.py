"""The facts: the spans a page is read into, their ids and hashes."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest
from support import md, page

from lit import facts, web

REPO = Path(__file__).resolve().parents[4]
LEX = "01-bootstrap/01.02-pass/01.02.01-lex.md"

TWO = """
    ```python
    <<1 Say what the module is
    m.py>>=
    \"\"\"The module, {word}.\"\"\"
    <<Functions>>
    ```

    ```python
    <<1.1 Functions
    m.py>>=
    def add(a: int, b: int) -> int:
        \"\"\"Sum a and b, {word}.\"\"\"
        return a {op} b  # {word}
    ```
    """

DEMO = """
    # Demo

    The first file.

    ```python
    <<1 The first file
    m.py>>=
    \"\"\"The module.\"\"\"
    <<Functions>>
    ```

    `add' sums, and the second file shares it.

    ```python
    <<1 The second file
    n.py>>=
    <<Functions>>
    ```

    ```python
    <<1.1 Functions
    m.py>>=
    def add(a: int, b: int) -> int:
        return a + b
    ```

    ```pycon
    >>> add(1, 2)
    3
    ```

    ```python
    <<Functions>>+=
    class Box:
        \"\"\"A box.\"\"\"

        size = 1
    ```

    | Refused | Reported at | Message |
    | --- | --- | --- |
    | a size below zero | the size | `size below zero` |

    ```text
    fenced prose
    ```

    ```pycon
    >>> 1
    1
    ```
    """

TESTS = """
    import pytest


    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            (-1, "ERROR: 1:1 size below zero"),
            (
                -2,
                "ERROR: 1:1 size unknown",
            ),
            (1, ""),
        ],
    )
    def test_box_refuses(size: int, expected: str) -> None:
        assert size


    def test_box() -> None:
        assert True
    """


def spans(text: str) -> dict[str, facts.Span]:
    """The spans of a page given as dedented text, by id."""
    body = md(text)
    got = facts.spans(web.read("p.md", body), body, Path(), {})
    return {s.id: s for s in got}


def demo(tmp_path: Path) -> list[facts.Span]:
    """The spans of the demo page and its test file under tmp_path."""
    path = page(tmp_path, "p.md", DEMO)
    page(tmp_path, "tests/test_m.py", TESTS)
    return facts.read(path, tmp_path)


def test_a_docstring_moves_the_text_and_not_the_hash() -> None:
    """Reworded docs change every chunk's text, never its code hash.

    One token changed changes both, in its chunk alone.
    """
    a = spans(TWO.format(word="first", op="+"))
    b = spans(TWO.format(word="second", op="+"))
    c = spans(TWO.format(word="first", op="-"))
    chunks = [i for i, s in a.items() if s.kind == "chunk"]
    assert len(chunks) == 2
    assert all(a[i].text != b[i].text for i in chunks)
    assert all(a[i].code_hash == b[i].code_hash for i in chunks)
    top, functions = chunks
    assert a[top].code_hash == ""
    assert a[functions].code_hash != ""
    assert a[functions].text != c[functions].text
    assert a[functions].code_hash != c[functions].code_hash
    assert a[top] == c[top]


def test_a_chunk_holds_its_fences_and_its_header() -> None:
    """Every page line of a chunk, a header of two lines included."""
    body = md(TWO.format(word="first", op="+"))
    w = facts.Web.of(web.read("p.md", body), body)
    top = "chunk:Say%20what%20the%20module%20is:1"
    assert [w.chunk_at[n] for n in range(1, 7)] == [top] * 6
    assert 7 not in w.chunk_at


def test_every_kind_is_read_and_every_target_resolves(tmp_path: Path) -> None:
    """The demo page holds each kind; no target points at nothing."""
    got = demo(tmp_path)
    kinds = Counter(s.kind for s in got)
    assert kinds == {
        "chunk": 4,
        "paragraph": 4,
        "definition": 3,
        "example": 2,
        "refusal": 1,
        "testrow": 3,
        "tangle": 7,
    }
    ids = {s.id for s in got}
    assert len(ids) == len(got)
    assert all(t in ids for s in got for t in s.targets)
    text = (tmp_path / "p.md").read_text(encoding="utf-8")
    for s in got:
        if s.item == (tmp_path / "p.md").as_posix():
            assert text[s.start : s.end] == s.text


def test_the_demo_page_spans_say_what_they_are(tmp_path: Path) -> None:
    """Labels, targets and hashes of the demo page, kind by kind."""
    by = {s.id: s for s in demo(tmp_path)}
    first, second = "chunk:The%20first%20file:1", "chunk:The%20second%20file:1"
    assert by[first].labels == ("The first file",)
    assert by[first].text.startswith("```python\n<<1 The first file\nm.py>>=")
    assert by[second].labels == ("The second file", "skeleton")
    assert by[second].code_hash == ""
    assert by["chunk:Functions:2"].text.startswith(
        "```python\n<<Functions>>+="
    )
    assert by["chunk:Functions:2"].text.endswith("size = 1\n```")
    assert by["p:1:1"].text == "# Demo"
    assert by["p:5:1"].text.startswith("| Refused |")
    assert by["def:Box.size"].targets == ("chunk:Functions:2",)
    assert (
        by["def:add"].code_hash
        == by["tangle:" + quoted(tmp_path, 2)].code_hash
    )
    assert by["ex:4:1"].targets == ("chunk:Functions:2",)
    assert by["ex:5:1"].targets == ()
    assert by["ex:5:1"].text == "```pycon\n>>> 1\n1\n```"
    assert by["refusal:size%20below%20zero"].labels == ("size below zero",)
    rows = [s for s in by.values() if s.kind == "testrow"]
    assert [r.targets for r in rows] == [
        ("refusal:size%20below%20zero",),
        (),
        (),
    ]
    assert (
        rows[1].text
        == '            -2,\n            "ERROR: 1:1 size unknown",'
    )
    assert rows[2].labels == ("",)
    assert rows[0].item == (tmp_path / "tests" / "test_m.py").as_posix()
    line = by["tangle:" + quoted(tmp_path, 1)]
    assert line.text == '"""The module."""'
    assert line.code_hash == ""
    assert line.targets == (first,)


def test_a_chunk_named_like_a_path_keeps_the_root_label() -> None:
    """The old file root, refused by the web, is still labelled root."""
    got = spans("```python\n<<m.py>>=\nx = 1\n```\n")
    assert got["chunk:m.py:1"].labels == ("m.py", "root")


def quoted(root: Path, line: int) -> str:
    """The quoted file part and line of a tangle id of ``m.py``."""
    return facts.ident("tangle", (root / "m.py").as_posix(), line)[7:]


def test_a_row_is_the_annotation_program_row() -> None:
    """``to_row`` gives the program's keys, with an empty note."""
    span = facts.Span("p:1:1", "p.md", 0, 1, "#", "paragraph")
    assert span.to_row() == {
        "id": "p:1:1",
        "item": "p.md",
        "start": 0,
        "end": 1,
        "text": "#",
        "labels": [],
        "note": "",
        "targets": [],
        "kind": "paragraph",
        "codeHash": "",
    }


def test_a_page_without_code_has_prose_alone() -> None:
    """No Python file: no chunk, no definition, no tangle line."""
    got = spans("Only prose.\n\nAnd more.\n")
    assert list(got) == ["p:1:1", "p:1:2"]


def test_a_refusal_row_without_a_message_is_refused() -> None:
    """A row whose last cell is no message in backticks is an error."""
    head = "| Refused | Reported at | Message |\n| --- | --- | --- |\n"
    text = head + "| a | b | c |\n"
    with pytest.raises(ValueError, match=r"p\.md:3: a refusal row"):
        spans(text)


def test_the_lex_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lex page's spans, counted by kind and pinned (2026-10-29)."""
    monkeypatch.chdir(REPO)
    got = facts.read(Path(LEX), Path("01-bootstrap"))
    assert Counter(s.kind for s in got) == {
        "chunk": 31,
        "paragraph": 51,
        "definition": 47,
        "example": 7,
        "refusal": 7,
        "testrow": 11,
        "tangle": 440,
    }
    rows = [s for s in got if s.kind == "testrow"]
    assert sum(1 for s in rows if s.targets) == 6
    chunks = [s for s in got if s.kind == "chunk"]
    assert [s.id for s in chunks if not s.id.endswith(":1")] == [
        "chunk:Name%20the%20marks%20the%20counter%20looks%20for:2"
    ]
    assert len({s.text for s in chunks}) == len(chunks)
    assert not [s for s in chunks if "skeleton" in s.labels]
    assert all(s.text.startswith("```python\n<<") for s in chunks)


def test_ids_are_url_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """No id holds a space, and no quoted part of one holds a colon."""
    monkeypatch.chdir(REPO)
    got = facts.read(Path(LEX), Path("01-bootstrap"))
    safe = re.compile(r"[A-Za-z0-9_.~%-]+")
    assert len({s.id for s in got}) == len(got)
    for s in got:
        kind, *parts = s.id.split(":")
        assert kind in {"chunk", "p", "def", "ex", "refusal", "test", "tangle"}
        assert all(safe.fullmatch(p) for p in parts), s.id

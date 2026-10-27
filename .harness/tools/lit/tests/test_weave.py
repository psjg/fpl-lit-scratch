"""weave: a page as one HTML file, in the manner of CWEB."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import lit, page

PAGE = """
    # Demo Title

    Intro: `add' and `Box.size' but not `ghost' or `a<b'.

    ```python
    <<demo.py>>=
    <<Functions>>
    class Box:
        <<Methods>>
    <<Missing>>
    ```

    The adder, `add'.

    ```python
    <<Functions>>=
    def add(a, b):
        return a + b
    ```

    ```pycon
    >>> add(1, 2)  # `add' stays plain here
    ```

    More: `sub'.

    ```python
    <<Functions>>+=
    def sub(a, b):
        return add(a, -b)
    ```

    ```python
    <<Methods>>=
    def __init__(self):
        self.n = 1

    def size(self):
        return 1
    ```

    ```python
    <<notes.txt>>=
    plain & <b>
    ```

    Trailing prose.
    """


@pytest.fixture
def html(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """The woven page; the undefined <<Missing>> makes the exit 1."""
    path = page(tmp_path, "demo.md", PAGE)
    out = tmp_path / "out"
    assert lit(tmp_path, "weave", str(out), str(path)) == 1
    printed = capsys.readouterr().out
    assert f"lit weave: {out / 'demo.html'}" in printed
    assert "<<Missing>> undefined" in printed
    return (out / "demo.html").read_text(encoding="utf-8")


def test_sections_are_numbered(html: str) -> None:
    """Every section carries its § number, trailing prose included."""
    for n in range(1, 7):
        assert f'<section id="s{n}"><span class="num">§{n}</span>' in html
    assert "<title>Demo Title</title>" in html
    assert "Trailing prose." in html


def test_chunk_headers_continue_with_plus(html: str) -> None:
    """⟨Name §n⟩ ≡ begins a chunk, +≡ continues it."""
    assert "⟨Functions §2⟩ ≡" in html
    assert "⟨Functions §2⟩ +≡" in html
    assert "⟨demo.py §1⟩ ≡" in html


def test_uses_are_links_and_undefined_uses_are_text(html: str) -> None:
    """A defined use links to its section; indentation is kept."""
    assert '<a class="use" href="#s2">⟨Functions §2⟩</a>' in html
    assert '    <a class="use" href="#s4">⟨Methods §4⟩</a>' in html
    assert "&lt;&lt;Missing&gt;&gt;" in html


def test_footers_say_where_used_and_which_file(html: str) -> None:
    """A chunk's footer lists its users; a file's names the file."""
    assert "This is the file <code>demo.py</code>." in html
    assert 'This code is used in <a href="#s1">§1</a>.' in html


def test_prose_references_link_or_not(html: str) -> None:
    """`name' links to the defining section when the code defines it."""
    assert '<a href="#s2"><code>add</code></a>' in html
    assert '<a href="#s4"><code>Box.size</code></a>' in html
    assert "<code>ghost</code>" in html
    assert "`add' stays plain here" in html


def test_index_tables(html: str) -> None:
    """The chunk and identifier indexes give defining and using §."""
    assert '<h2 id="index">Index</h2>' in html
    assert "<td>⟨Functions⟩</td><td><b>§2</b> §1</td>" in html
    assert '<td><a href="#s2"><b>§2</b></a> <a href="#s3">§3</a></td>' in html
    assert "<code>__init__</code>" not in html


def test_title_falls_back_to_the_page_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A page without a heading is titled by its path."""
    path = page(tmp_path, "d.md", "```python\n<<d.py>>=\nx = 1\n```\n")
    assert lit(tmp_path, "weave", str(tmp_path / "o"), str(path)) == 0
    got = (tmp_path / "o" / "d.html").read_text(encoding="utf-8")
    assert "<title>d.md</title>" in got
    assert capsys.readouterr().out.startswith("lit weave:")

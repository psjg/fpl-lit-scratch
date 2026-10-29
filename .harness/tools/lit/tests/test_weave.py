"""weave: a page as one HTML file, in the manner of CWEB."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import override

import pytest
from support import lit, md, page

from lit import facts, weave

PAGE = """
    ---
    type: Note
    ---
    # Demo Title

    Intro: `add' and `Box.size' but not `ghost' or `a<b'.

    ```python
    <<1 The demo
    demo.py>>=
    <<Functions>>
    class Box:
        <<Methods>>
    <<Missing>>
    ```

    The adder, `add'.

    ```python
    <<1.1 Functions
    demo.py>>=
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
    <<1.2 Methods
    demo.py>>=
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
    assert "⟨The demo §1⟩ ≡" in html


def test_uses_are_links_and_undefined_uses_are_text(html: str) -> None:
    """A defined use links to its section; indentation is kept."""
    assert '<a class="use" href="#s2">⟨Functions §2⟩</a>' in html
    assert '    <a class="use" href="#s4">⟨Methods §4⟩</a>' in html
    assert "&lt;&lt;Missing&gt;&gt;" in html


def test_footers_say_where_used_and_which_file(html: str) -> None:
    """A chunk's footer lists its users; an old file root names it."""
    assert "This is the file <code>notes.txt</code>." in html
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
    text = "```python\n<<1 X\nd.txt>>=\nx = 1\n```\n"
    path = page(tmp_path, "d.md", text)
    assert lit(tmp_path, "weave", str(tmp_path / "o"), str(path)) == 0
    got = (tmp_path / "o" / "d.html").read_text(encoding="utf-8")
    assert "<title>d.md</title>" in got
    assert capsys.readouterr().out.startswith("lit weave:")


FACTS = """
    ---
    type: Note
    ---
    # Facts Demo

    alpha beta gamma delta.

    Counting, `add', is plain.

    | Kind | Note |
    | --- | --- |
    | one | two |

    - a bullet item

    ```pycon
    >>> add(1, 2)
    3
    ```

    ```python
    <<1 The file
    f.py>>=
    \"\"\"The file.\"\"\"
    <<Functions>>
    ```

    ```python
    <<1.1 Functions
    f.py>>=
    def add(a, b):
        return a & b
    ```

    twice twice
    """
LEDGER = (
    "id\ttopic\tdate\twho\tdecision\treason\n"
    "X9\ttabs\t2026-10-28\tPSJ\tNo tabs.\tNo brain power for them.\n"
    "X10\ttabs\t2026-10-28\tagent\tSpaces only.\t\n"
)
SHA = "abc1234def5678abc1234def5678abc1234def56"


def span(rid: str, want: str, n: int = 0) -> facts.Row:
    """A hand span over the ``n``-th ``want`` of the facts page."""
    text = md(FACTS)
    start = -1
    for _ in range(n + 1):
        start = text.index(want, start + 1)
    end = start + len(want)
    return {
        "id": rid,
        "item": "p.md",
        "start": start,
        "end": end,
        "text": want,
    }


def woven(tmp_path: Path, rows: list[facts.Row]) -> str:
    """The facts page woven in a repository, with ``rows`` beside it."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    path = page(tmp_path, "p.md", FACTS)
    (tmp_path / "p.decisions.tsv").write_text(LEDGER, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("a note\n", encoding="utf-8")
    sidecar = json.dumps(rows, indent=1, ensure_ascii=False)
    (tmp_path / "p.facts.json").write_text(sidecar, encoding="utf-8")
    out = tmp_path / "out"
    assert lit(tmp_path, "weave", str(out), str(path)) == 0
    got = (out / "p.html").read_text(encoding="utf-8")
    nested(got)
    return got


def generated(tmp_path: Path) -> dict[str, facts.Row]:
    """The facts page's generated rows, by kind, the first of each."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    path = page(tmp_path, "p.md", FACTS)
    rows, _ = facts.generate(path, tmp_path)
    out: dict[str, facts.Row] = {}
    for r in rows:
        out.setdefault(str(r["kind"]), r)
    return out


class _Nesting(HTMLParser):
    """Every closing tag closes the element opened last."""

    VOID = frozenset({"meta", "br", "hr", "img"})

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []

    @override
    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Open an element, unless it is void."""
        if tag not in self.VOID:
            self.stack.append(tag)

    @override
    def handle_endtag(self, tag: str) -> None:
        """Close the element opened last; it must be this one."""
        assert self.stack.pop() == tag


def nested(doc: str) -> None:
    """Assert that the document's elements nest properly."""
    parser = _Nesting()
    parser.feed(doc)
    assert parser.stack == []


def mark(rid: str, *, first: bool = False, state: str = "vers") -> str:
    """The opening tag of a mark."""
    anchor = f' id="fact-{rid}"' if first else ""
    return f'<mark class="fact fact-{state}"{anchor} data-id="{rid}">'


def test_overlapping_spans_split_at_each_boundary(tmp_path: Path) -> None:
    """Two crossing spans nest: the shared text is in both marks."""
    got = woven(tmp_path, [span("a", "alpha beta"), span("b", "beta gamma")])
    assert (
        f"{mark('a', first=True)}alpha </mark>"
        f"{mark('a')}{mark('b', first=True)}beta</mark></mark>"
        f"{mark('b')} gamma</mark> delta."
    ) in got


def test_a_contained_span_nests_inside_its_container(tmp_path: Path) -> None:
    """The inner mark sits inside the outer one, which goes on after."""
    got = woven(tmp_path, [span("a", "alpha beta gamma"), span("b", "beta")])
    assert (
        f"{mark('a', first=True)}alpha </mark>"
        f"{mark('a')}{mark('b', first=True)}beta</mark></mark>"
        f"{mark('a')} gamma</mark> delta."
    ) in got


def test_marks_keep_the_blocks_and_references_whole(tmp_path: Path) -> None:
    """Headings, tables, lists, fences, links and code stay whole.

    A boundary on markup moves past it, one on a fence line to the next
    line, one past the last line to the end; a span with no text of its
    own is an empty mark.
    """
    got = woven(
        tmp_path,
        [
            span("h", "# Facts"),
            span("r", "dd', is"),
            span("t", "| one | two |"),
            span("l", "- a bullet"),
            span("x", "```pycon\n>>> add"),
            span("u", "<<Functions>>"),
            span("c", "return a & b"),
            span("z", "twice twice\n"),
        ],
    )
    assert f"<h1>{mark('h', first=True)}Facts</mark> Demo</h1>" in got
    assert (
        f'<a href="#s2"><code>a{mark("r", first=True)}dd</mark></code></a>'
        f"{mark('r')}, is</mark> plain." in got
    )
    assert f"<td>{mark('t', first=True)}one</mark></td>" in got
    assert f"<td>{mark('t')}two </mark></td>" in got
    assert f"<li>{mark('l', first=True)}a bullet</mark> item</li>" in got
    assert f"{mark('x', first=True)}&gt;&gt;&gt; add</mark>(1, 2)" in got
    assert f'{mark("u", first=True)}</mark><a class="use"' in got
    assert f"    {mark('c', first=True)}return a &amp; b</mark>" in got
    assert f"<p>{mark('z', first=True)}twice twice</mark></p>" in got


def test_found_spans_are_marked_and_the_rest_listed(tmp_path: Path) -> None:
    """vers and verplaatst are marked; dubbel and stale are listed.

    A span in another file is listed only, with its file; a commit is
    shown short with the full one in a title.
    """
    moved = span("m", "delta") | {"start": 0, "end": 5, "commit": SHA}
    got = woven(
        tmp_path,
        [
            moved,
            span("d", "twice") | {"start": 0, "end": 5, "commit": SHA},
            span("s", "alpha") | {"text": "Never written.", "commit": SHA},
            {
                "id": "n",
                "item": "notes.txt",
                "start": 2,
                "end": 6,
                "text": "note",
            },
        ],
    )
    assert f"{mark('m', first=True, state='verplaatst')}delta</mark>" in got
    assert 'id="fact-d"' not in got
    assert 'id="fact-s"' not in got
    assert 'id="fact-n"' not in got
    assert (
        "4 rows: 4 spans (1 vers, 1 verplaatst, 1 dubbel, 1 stale),"
        " 0 facts, 0 relations." in got
    )
    assert '<li id="fn-d" class="fact-dubbel"><code>d</code>' in got
    assert '<li id="fn-s" class="fact-stale"><code>s</code>' in got
    assert (
        '<a href="#fact-m"><code>m</code></a> <q>delta</q> <span'
        ' class="meta">verplaatst, at <abbr'
        f' title="{SHA}">{SHA[:12]}</abbr></span>' in got
    )
    assert (
        '<q>note</q> <span class="meta">vers, in <code>notes.txt</code>'
        "</span>" in got
    )
    assert "mark.fact-vers" in got


def test_relations_facts_and_the_ledger_read_as_links(
    tmp_path: Path,
) -> None:
    """A relation reads label: from -> to; a fact is about its targets.

    A ledger target shows its decision, and its reason when it has one,
    titled by topic, who and date; each row lists the rows citing it.
    """
    rows: list[facts.Row] = [
        span("a", "alpha"),
        {"id": "r", "labels": ["contradicts"], "targets": ["a", "L-X9"]},
        {"id": "q", "labels": ["cites"], "targets": ["r", "L-X10"]},
        {"id": "f", "labels": ["note"], "note": "why", "targets": ["r"]},
        {"id": "g", "note": "bare"},
    ]
    got = woven(tmp_path, rows)
    assert (
        '<li id="fn-r"><code>r</code> contradicts: <a href="#fn-a"><code>a'
        '</code></a> → <span class="ledger" title="tabs · PSJ · 2026-10-28">'
        "<b>L-X9</b> <q>No tabs.</q> (No brain power for them.)</span>"
        ' cited by <a href="#fn-q"><code>q</code></a>, <a href="#fn-f">'
        "<code>f</code></a></li>" in got
    )
    assert (
        '<span class="ledger" title="tabs · agent · 2026-10-28"><b>L-X10</b>'
        " <q>Spaces only.</q></span></li>" in got
    )
    assert (
        '<li id="fn-f"><code>f</code> [note] about <a href="#fn-r"><code>r'
        "</code></a> — why</li>" in got
    )
    assert '<li id="fn-g"><code>g</code> — bare</li>' in got
    assert "3 rows" not in got
    assert "5 rows: 1 spans" in got
    assert "2 facts, 2 relations." in got


def test_generated_targets_link_to_their_section(tmp_path: Path) -> None:
    """A page span links to its §; a file's span shows its kind."""
    gen = generated(tmp_path)
    chunk, line = gen["chunk"], gen["tangle"]
    got = woven(
        tmp_path,
        [
            {
                "id": "c",
                "labels": ["checkedBy"],
                "targets": [str(chunk["id"]), str(line["id"])],
            }
        ],
    )
    assert '<a href="#s1">chunk The file</a> → tangle</li>' in got


def test_a_page_without_hand_rows_weaves_as_before(
    tmp_path: Path, html: str
) -> None:
    """No sidecar, or an empty one: no facts, no marks, same bytes."""
    assert f"<style>{weave.STYLE}</style>" in html
    assert "fact" not in html
    (tmp_path / ".git").mkdir()
    path = page(tmp_path, "q.md", FACTS)
    out = tmp_path / "plain"
    assert lit(tmp_path, "weave", str(out), str(path)) == 0
    before = (out / "q.html").read_bytes()
    (tmp_path / "q.facts.json").write_text("[]\n", encoding="utf-8")
    assert lit(tmp_path, "weave", str(out), str(path)) == 0
    assert (out / "q.html").read_bytes() == before


def test_a_bad_sidecar_is_a_finding_and_no_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sidecar's findings fail the weave, which shows no facts."""
    (tmp_path / ".git").mkdir()
    path = page(tmp_path, "p.md", FACTS)
    (tmp_path / "p.facts.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "out"
    assert lit(tmp_path, "weave", str(out), str(path)) == 1
    assert "lit-facts-json" in capsys.readouterr().out
    assert "fact" not in (out / "p.html").read_text(encoding="utf-8")

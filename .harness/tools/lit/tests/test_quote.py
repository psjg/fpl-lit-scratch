"""Hand spans named by a quote from the published page, not offsets."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from support import GOOD, lit, md, page

from lit import facts, web

REPO = Path(__file__).resolve().parents[4]
LEX = "01-bootstrap/01.02-pass/01.02.01-lex.md"
SHA = "abc1234def5678abc1234def5678abc1234def56"
ITEM = f"A=p.md@{SHA}"

RAW = md(
    """
    # Demo

    FPL's text is read by `prelex', which keeps
    a wrapped line. See [the guide](https://x.org/g) for more.

    | Refused | Why |
    | --- | --- |
    | tabs | no brain power |

    The pairs are counted twice, twice again; twice.

    ```python
    <<1 Add
    m.py>>=
    def add(a: int, b: int) -> int:
        return a + b
    ```
    """
)


def quote(text: str, **more: str) -> facts.Row:
    """A quote row on the fixture page."""
    row: facts.Row = {"id": "q", "item": "p.md", "text": text}
    return row | more


def found(row: facts.Row, raw: str = RAW) -> tuple[str, str]:
    """The row's state on ``raw``, and the raw text it was found at."""
    got = facts.locate(row, raw, [], [])
    if got.start is None:
        return got.state, ""
    return got.state, raw[got.start : got.end]


@pytest.mark.parametrize(
    ("shown", "raw"),
    [
        ("FPL\u2019s text", "FPL's text"),
        ("read by prelex, which", "read by `prelex', which"),
        ("which keeps a wrapped line", "which keeps\na wrapped line"),
        ("See the guide for", "See [the guide](https://x.org/g) for"),
        ("no brain power", "no brain power"),
        ("tabs no brain power", "tabs | no brain power"),
        ("Demo FPL\u2019s", "Demo\n\nFPL's"),
        ("return a + b", "return a + b"),
    ],
)
def test_a_rendered_quote_is_found_at_its_raw_offsets(
    shown: str, raw: str
) -> None:
    """Alias, apostrophe, hard wrap, link, table, heading, code."""
    assert found(quote(shown)) == ("vers", raw)


def test_several_hits_are_told_apart_by_prefix_and_suffix() -> None:
    """Either one that the row carries; both when it carries both."""
    assert found(quote("twice")) == ("dubbel", "")
    first = RAW.index("twice")
    second = RAW.index("twice", first + 1)
    third = RAW.index("twice", second + 1)
    for row, at in (
        (quote("twice", prefix="are counted "), first),
        (quote("twice", suffix=" again"), second),
        (quote("twice", suffix="."), third),
        (quote("twice", prefix="twice, ", suffix=" again;"), second),
    ):
        got = facts.locate(row, RAW, [], [])
        assert (got.state, got.start, got.end) == ("vers", at, at + 5)
    assert found(quote("twice", prefix="thrice ")) == ("stale", "")
    assert found(quote("twice", prefix="")) == ("dubbel", "")
    assert found(quote("Never written.")) == ("stale", "")


def test_a_quote_in_a_chunk_lies_inside_its_span() -> None:
    """Code is found by its text like prose, inside the chunk's span."""
    w = facts.Web.of(web.read("p.md", RAW), RAW)
    [chunk] = [s for s in facts.kinds(w, Path(), {}) if s.kind == "chunk"]
    got = facts.locate(quote("return a + b"), RAW, facts.stream(w), [])
    assert got.start is not None
    assert got.end is not None
    assert chunk.start <= got.start
    assert got.end <= chunk.end


def test_the_position_map_reads_every_char_back() -> None:
    """Each plain char comes from one raw char that reads as itself."""
    shown, at = facts.plain(RAW)
    assert len(shown) == len(at)
    assert list(at) == sorted(set(at))
    for char, raw in zip(shown, at, strict=True):
        assert facts.plain(RAW[raw])[0] == char
    assert "`" not in shown
    assert "https" not in shown


def test_a_quote_on_the_lex_page_lies_in_its_offset_twin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tabs sentence, quoted as rendered, sits inside s-tabs."""
    monkeypatch.chdir(REPO)
    body = Path(LEX).read_text(encoding="utf-8")
    want = (
        "outside them indentation is tabs, and a space after the tabs"
        " is refused"
    )
    facts.plain.cache_clear()
    started = time.perf_counter()
    row = quote(want, prefix="likes;") | {"item": LEX}
    got = facts.locate(row, body, [], [])
    ms = (time.perf_counter() - started) * 1000
    print(f"lex quote located in {ms:.1f} ms")
    assert got.state == "vers"
    assert got.start is not None
    assert got.end is not None
    assert got.start >= 21778
    assert got.end <= 21909
    assert facts.plain(body[got.start : got.end])[0] == want


def test_validate_reads_a_quote_one_way() -> None:
    """Offsets or a quote, never both; a prefix alone is no span."""
    rows: list[facts.Row] = [
        quote("FPL\u2019s text", prefix="# Demo ", suffix=" is"),
        quote("FPL", prefix="x") | {"id": "b", "start": 0, "end": 3},
        {"id": "c", "prefix": "x"},
        quote("FPL") | {"id": "d", "prefix": 3},
        quote("`` \n") | {"id": "e"},
        quote("FPL") | {"id": "f", "item": 7},
        quote("FPL") | {"id": "g", "start": 0},
    ]
    got = facts.validate(rows, "p.facts.json", {"p.md": RAW}, set())
    assert [(f.line, f.rule) for f in got] == [
        (2, "lit-facts-span"),
        (3, "lit-facts-span"),
        (4, "lit-facts-field"),
        (5, "lit-facts-span"),
        (6, "lit-facts-span"),
        (7, "lit-facts-span"),
    ]
    assert "not both" in got[0].message
    assert "more than markup" in got[3].message


def tool(rid: str, **more: object) -> facts.Row:
    """An overlay quote row over ``The file.`` of the demo page."""
    row: facts.Row = {
        "id": rid,
        "item": "A",
        "text": "The file.",
        "prefix": "Demo\n",
        "suffix": "\n",
        "labels": [],
        "note": "",
        "createdAt": 1,
        "updatedAt": 1,
    }
    return row | more


def test_a_quote_row_goes_in_and_comes_back_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Import keeps a quote; facts locate it; export gives it back."""
    (tmp_path / ".git").mkdir()
    page(tmp_path, "p.md", GOOD)
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([tool("q")]), encoding="utf-8")
    assert lit(tmp_path, "facts", "--import", str(src), "--item", ITEM) == 0
    car = tmp_path / "p.facts.json"
    [held] = facts.read_rows(car.read_text(encoding="utf-8"))
    assert list(held) == [
        "id",
        "item",
        "text",
        "prefix",
        "suffix",
        "labels",
        "note",
        "targets",
        "commit",
        "createdAt",
        "updatedAt",
    ]
    rows, bad = facts.generate(tmp_path / "p.md", tmp_path)
    assert bad == []
    [row] = [r for r in rows if r["id"] == "q"]
    assert (row["state"], row["currentStart"], row["currentEnd"]) == (
        "vers",
        27,
        36,
    )
    assert lit(tmp_path, "anchor", "--verify") == 0
    out = tmp_path / "back.json"
    p = str(tmp_path / "p.md")
    argv = ["facts", "--export", p, "--item", ITEM, "--out", str(out)]
    assert lit(tmp_path, *argv) == 0
    back = json.loads(out.read_text(encoding="utf-8"))
    assert back == [tool("q") | {"targets": []}]
    capsys.readouterr()


def test_an_overlay_row_with_a_broken_place_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One offset alone, or a prefix that is no string: a finding."""
    (tmp_path / ".git").mkdir()
    page(tmp_path, "p.md", GOOD)
    src = tmp_path / "rows.json"
    rows = [tool("a", start=8), tool("b", prefix=3), tool("c", suffix=[])]
    src.write_text(json.dumps(rows), encoding="utf-8")
    assert lit(tmp_path, "facts", "--import", str(src), "--item", ITEM) == 1
    said = capsys.readouterr().out
    for n, message in (
        (1, "start and end come together"),
        (2, "prefix must be a string"),
        (3, "suffix must be a string"),
    ):
        assert f"rows.json:{n}: lit-facts-import: {message}" in said

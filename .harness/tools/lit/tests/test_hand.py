"""The hand rows: validated, located on the current page, verified."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest
from support import lit, md, page

from lit import facts, web

REPO = Path(__file__).resolve().parents[4]
LEX = "01-bootstrap/01.02-pass/01.02.01-lex.md"
SHA = "abc1234def5678abc1234def5678abc1234def56"
NONE = "abcdef0abcdef0abcdef0abcdef0abcdef0abcde"

PAGE = """
    # Demo

    {before}The pairs are counted twice, twice.

    ```python
    <<1 Functions
    m.py>>=
    def add(src: str, a: int, b: int) -> int:
        \"\"\"Sum a and b, {word}.\"\"\"
        return pairs({arg}, a) + b


    def sub(a: int, b: int) -> int:
        return a + b


    def mul(a: int, b: int) -> int:
        return a + b
    ```
    """

LEDGER = (
    "id\ttopic\tdate\twho\tdecision\treason\n"
    "X9\ttabs\t2026-10-28\tPSJ\tNo tabs.\tNo brain power for them.\n"
    "X10\ttabs\t2026-10-28\tagent\tSpaces only.\t\n"
)


def text(before: str = "", word: str = "first", arg: str = "src") -> str:
    """The demo page, with prose before it and its docstring's word."""
    return md(PAGE).format(before=before, word=word, arg=arg)


def at(page_text: str, want: str, n: int = 0, rid: str = "s") -> facts.Row:
    """A row over the ``n``-th occurrence of ``want`` in a page text."""
    start = -1
    for _ in range(n + 1):
        start = page_text.index(want, start + 1)
    return {
        "id": rid,
        "item": "p.md",
        "start": start,
        "end": start + len(want),
        "text": want,
    }


def where(row: facts.Row, now: str) -> facts.Located:
    """Locate a row written on the first page, on the page ``now``."""
    w = facts.Web.of(web.read("p.md", now), now)
    spans = facts.kinds(w, Path(), {})
    chunks = [(s.start, s.end) for s in spans if s.kind == "chunk"]
    return facts.locate(row, now, facts.stream(w), chunks)


def test_the_decision_table() -> None:
    """Prose by text, code by tokens; each state with its offsets."""
    first = text()
    call = at(first, "return pairs(src,")
    doc = at(first, '"""Sum a and b, first."""')
    prose = at(first, "The pairs are counted")
    sum_ = at(first, "return a + b", 0)
    reworded = text(word="now reworded at length")
    moved = text(before="New prose.\n\n")
    assert where(call, first) == facts.Located("vers", *span(call))
    got = where(call, reworded)
    assert got.state == "vers"
    assert reworded[got.start : got.end] == "return pairs(src,"
    assert got.start != call["start"]
    assert where(call, text(arg="dst")).state == "stale"
    assert where(doc, moved).state == "verplaatst"
    assert where(doc, reworded).state == "stale"
    got = where(prose, moved)
    assert got.state == "verplaatst"
    assert moved[got.start : got.end] == "The pairs are counted"
    assert where(sum_, reworded).state == "dubbel"
    assert where(at(first, "twice"), moved).state == "dubbel"
    invented = at(first, "The pairs") | {"text": "Never written."}
    assert where(invented, first).state == "stale"


def span(row: facts.Row) -> tuple[int, int]:
    """A row's start and end."""
    return int(str(row["start"])), int(str(row["end"]))


def test_a_cut_call_keeps_its_tokens_up_to_the_cut() -> None:
    """``return pairs(src,`` holds five tokens, a docstring none."""
    got = facts.fragment("return pairs(src,")
    assert [t for _, _, t in got][1] == (1, "pairs")
    assert len(got) == 5
    assert facts.fragment('    """Sum a and b."""') == []
    assert len(facts.fragment("x\n  y\n z")) == 2


def test_the_lex_tokens_stand_at_their_code_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every one-line token of the lex page is its own text there."""
    monkeypatch.chdir(REPO)
    body = Path(LEX).read_text(encoding="utf-8")
    placed = facts.stream(facts.Web.of(web.read(LEX, body), body))
    assert len(placed) > 1000
    for start, end, (_, string) in placed:
        if "\n" not in string:
            assert body[start:end] == string


ROWS: list[facts.Row] = [
    {"id": "r1", "note": "why", "targets": ["s2", "L-X9", "chunk:m.py:1"]},
    {"id": "r1", "labels": "tabs", "targets": ["L-Z99", "nothing"]},
    {"labels": [], "colour": "red", "note": 3, "commit": "XYZ"},
    {"id": "a b", "item": "p.md", "start": 2, "end": 2, "text": ""},
    {"id": "s2", "item": "p.md", "start": 0},
    {"id": "s3", "item": "p.md", "start": "0", "end": 1, "text": "#"},
    {"id": "s4", "item": 7, "start": 0, "end": 1, "text": "#"},
    {"id": "s5", "item": "elsewhere.md", "start": 0, "end": 1, "text": "#"},
    {"id": "s6", "item": "p.md", "start": 0, "end": 1, "text": "?"},
    {
        "id": "s7",
        "item": "p.md",
        "start": 0,
        "end": 1,
        "text": "?",
        "commit": SHA,
        "createdAt": 1,
        "updatedAt": True,
    },
    {
        "id": "s8",
        "item": "p.md",
        "start": 0,
        "end": 1,
        "text": "#",
        "targets": 5,
    },
    {"id": "f9", "targets": ["s8"], "commit": SHA, "by": 3},
    {"id": "f10", "targets": ["f9"], "commit": SHA, "by": "PSJ"},
]


def test_validate_names_each_fault_at_its_row() -> None:
    """Every rule, each at the number of the row it is about."""
    got = facts.validate(
        ROWS, "p.facts.json", {"p.md": "# Demo"}, {"L-X9", "chunk:m.py:1"}
    )
    assert {(f.line, f.rule) for f in got} == {
        (2, "lit-facts-id"),
        (1, "lit-facts-id"),
        (2, "lit-facts-field"),
        (2, "lit-facts-target"),
        (3, "lit-facts-id"),
        (3, "lit-facts-field"),
        (4, "lit-facts-id"),
        (4, "lit-facts-span"),
        (5, "lit-facts-span"),
        (6, "lit-facts-span"),
        (7, "lit-facts-span"),
        (8, "lit-facts-span"),
        (9, "lit-facts-span"),
        (10, "lit-facts-field"),
        (11, "lit-facts-field"),
        (12, "lit-facts-field"),
    }
    assert [f.message for f in got if f.line == 12] == ["by must be a str"]
    messages = [f.message for f in got if f.line == 2]
    assert "target 'L-Z99' names nothing" in messages
    assert "target 'nothing' names nothing" in messages
    assert len([f for f in got if f.line == 3]) == 4
    assert str(got[0]).startswith("p.facts.json:1: lit-facts-id: ")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("{}", "not a JSON array of objects"),
        ("[1]", "not a JSON array of objects"),
        ('[{"id": "a", "id": "b"}]', "a row holds a key twice"),
        ('[{"start": NaN}]', "NaN is no JSON number"),
        ("[", "Expecting value"),
    ],
)
def test_a_sidecar_is_read_strictly(body: str, message: str) -> None:
    """One spelling: no object, no key twice, no NaN, no bad JSON."""
    with pytest.raises(ValueError, match=message):
        facts.read_rows(body)


@pytest.mark.parametrize(
    ("body", "line", "message"),
    [
        ("id\ttopic\n", 1, "the header must be"),
        (LEDGER.rstrip("\n"), 3, "no newline"),
        (LEDGER + "X11\ttabs\n", 4, "2 cells, not 6"),
        (LEDGER + "X9\tt\t2026-10-28\tw\td\t\n", 4, "is no new"),
        (LEDGER + "X11\tt\t28-10-2026\tw\td\t\n", 4, "is no YYYY-MM-DD"),
        (LEDGER + "X11\tt\t2026-10-28\t\td\tr\n", 4, "only the reason"),
    ],
)
def test_a_ledger_is_read_strictly(body: str, line: int, message: str) -> None:
    """A header, six cells, a new id, a date; only a reason empty."""
    rows, bad = facts.ledger(body, "p.decisions.tsv")
    assert rows == []
    [finding] = bad
    assert (finding.line, finding.rule) == (line, "lit-facts-ledger")
    assert message in finding.message


def test_a_ledger_row_is_a_span_over_its_decision() -> None:
    """Id ``L-<id>``, labels topic, who, date; an empty reason too."""
    rows, bad = facts.ledger(LEDGER, "p.decisions.tsv")
    assert bad == []
    first, second = rows
    assert LEDGER[int(str(first["start"])) : int(str(first["end"]))] == (
        "No tabs."
    )
    assert first["id"] == "L-X9"
    assert first["labels"] == ["tabs", "PSJ", "2026-10-28"]
    assert first["note"] == "No brain power for them."
    assert second["note"] == ""
    assert second["kind"] == "ledger"


def test_an_astral_character_is_one_finding_per_page() -> None:
    """The first code point above U+FFFF, at its line; none else."""
    [f] = facts.astral("p.md", "a\nb \U0001f600 \U0001f600\n")
    assert (f.line, f.rule) == (2, "lit-facts-astral")
    assert "U+1F600" in f.message
    assert facts.astral("p.md", "plain") == []


def test_a_root_outside_a_repository_is_refused(tmp_path: Path) -> None:
    """Items are paths from the repository; without one, none."""
    with pytest.raises(ValueError, match=r"no \.git"):
        facts.top(tmp_path)


def demo(tmp_path: Path, rows: list[facts.Row]) -> Path:
    """A repository holding the demo page, its sidecar and ledger."""
    (tmp_path / ".git").mkdir()
    path = page(tmp_path, "p.md", text(before="New prose.\n\n"))
    (tmp_path / "p.decisions.tsv").write_text(LEDGER, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("a note\n", encoding="utf-8")
    sidecar = json.dumps(rows, indent=1, ensure_ascii=False)
    (tmp_path / "p.facts.json").write_text(sidecar, encoding="utf-8")
    return path


def hand_rows(first: str) -> list[facts.Row]:
    """A span on the page, one in another file, a fact, a relation."""
    return [
        at(first, "return pairs(src,", rid="call") | {"commit": SHA},
        {"id": "n", "item": "notes.txt", "start": 2, "end": 6, "text": "note"},
        {
            "id": "f",
            "note": "why",
            "labels": ["reason", "PSJ"],
            "targets": ["call", "L-X9"],
        },
        {"id": "r", "labels": ["because"], "targets": ["f", "n"]},
        at(first, "The pairs", rid="gone")
        | {"text": "Never written.", "commit": SHA},
    ]


def test_facts_out_writes_each_page_with_its_rows_located(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One file per page; hand rows carry state, start and end stay."""
    demo(tmp_path, hand_rows(text()))
    out = tmp_path / "build"
    assert lit(tmp_path, "facts", "--out", str(out)) == 0
    assert "lit facts: 1 page(s), 0 finding(s)" in capsys.readouterr().out
    rows = json.loads((out / "p.json").read_text(encoding="utf-8"))
    assert Counter(r.get("kind", "hand") for r in rows) == {
        "chunk": 1,
        "paragraph": 3,
        "definition": 3,
        "tangle": 11,
        "ledger": 2,
        "hand": 5,
    }
    by = {r["id"]: r for r in rows}
    assert by["call"]["state"] == "vers"
    assert by["call"]["start"] != by["call"]["currentStart"]
    assert by["n"]["state"] == "vers"
    assert "state" not in by["f"]
    assert by["gone"]["state"] == "stale"
    assert "currentStart" not in by["gone"]
    assert by["L-X9"]["item"] == "p.decisions.tsv"
    assert by["chunk:Functions:1"]["item"] == "p.md"


def test_check_and_facts_report_a_bad_sidecar(tmp_path: Path) -> None:
    """A sidecar with a finding fails both and adds no hand rows."""
    outside: facts.Row = {"item": "../p.md", "start": 0, "end": 1}
    demo(
        tmp_path,
        [
            {"id": "s", "targets": ["L-Z99"]},
            {"id": "o", "text": "#"} | outside,
        ],
    )
    lit(tmp_path, "tangle")
    out = tmp_path / "build"
    assert lit(tmp_path, "facts", "--out", str(out)) == 1
    rows = json.loads((out / "p.json").read_text(encoding="utf-8"))
    assert all("kind" in r for r in rows)
    assert lit(tmp_path, "check") == 1
    (tmp_path / "p.facts.json").write_text("{}", encoding="utf-8")
    assert lit(tmp_path, "check") == 1


def test_check_reports_an_astral_page_without_a_sidecar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The astral check runs on every page, a sidecar or not."""
    page(tmp_path, "p.md", text(before="A smile \U0001f600.\n\n"))
    lit(tmp_path, "tangle")
    capsys.readouterr()
    assert lit(tmp_path, "check") == 1
    assert "p.md:3: lit-facts-astral" in capsys.readouterr().out


def git(root: Path, *argv: str) -> str:
    """Run git in ``root`` with no hooks and no signing; its output."""
    done = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            *argv,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def test_anchor_verify_catches_a_wrong_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A row grounds where its commit has its text, and nowhere else."""
    first = text()
    git(tmp_path, "init", "-q")
    page(tmp_path, "p.md", first)
    git(tmp_path, "add", "-f", "p.md")
    git(tmp_path, "commit", "-qm", "one")
    one = git(tmp_path, "rev-parse", "HEAD")
    page(tmp_path, "p.md", text(before="New prose.\n\n"))
    git(tmp_path, "add", "-f", "p.md")
    git(tmp_path, "commit", "-qm", "two")
    two = git(tmp_path, "rev-parse", "HEAD")
    rows = [
        at(first, "The pairs", rid="a") | {"commit": one},
        at(first, "The pairs", rid="b") | {"commit": two},
        at(first, "The pairs", rid="c") | {"commit": NONE},
        {"id": "f", "note": "no span", "commit": one},
    ]
    sidecar = json.dumps(rows)
    (tmp_path / "p.facts.json").write_text(sidecar, encoding="utf-8")
    capsys.readouterr()
    assert lit(tmp_path, "anchor", "--verify") == 1
    out = capsys.readouterr().out
    assert "p.facts.json:2: lit-facts-ground: text is not at" in out
    assert f"p.facts.json:3: lit-facts-ground: {NONE} holds no p.md" in out
    assert "p.facts.json:1:" not in out
    (tmp_path / "p.facts.json").write_text("[1]", encoding="utf-8")
    assert lit(tmp_path, "anchor", "--verify") == 1
    assert "lit-facts-json" in capsys.readouterr().out
    (tmp_path / "p.facts.json").unlink()
    assert lit(tmp_path, "anchor", "--verify") == 0


def test_the_lex_page_with_its_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real page, its sidecar and ledger: 676 rows, no finding."""
    monkeypatch.chdir(REPO)
    rows, bad = facts.generate(Path(LEX), Path("01-bootstrap"))
    assert bad == []
    assert len(rows) == 676
    assert rows[0]["item"] == LEX


def test_generate_without_a_sidecar_gives_generated_rows_only(
    tmp_path: Path,
) -> None:
    """A page with no sidecar and no ledger: no finding, no hand row."""
    git(tmp_path, "init", "-q")
    path = page(tmp_path, "p.md", text())
    rows, bad = facts.generate(path, tmp_path)
    assert bad == []
    assert rows
    assert all("commit" not in r for r in rows)

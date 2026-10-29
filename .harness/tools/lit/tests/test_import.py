"""The annotation program's rows: imported into a sidecar, exported."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support import GOOD, lit, md, page

from lit import facts

SHA = "abc1234def5678abc1234def5678abc1234def56"
ITEM = f"A=p.md@{SHA}"


def tool(rid: str, item: str = "A", at: int = 27, **more: object) -> facts.Row:
    """A row of the program over ``The file.`` of the demo page."""
    text = md(GOOD)[at : at + 9]
    return {
        "createdAt": 1,
        "end": at + 9,
        "id": rid,
        "item": item,
        "labels": ["good"],
        "note": "",
        "start": at,
        "text": text,
        "updatedAt": 1,
    } | more


def repo(tmp_path: Path, rows: list[facts.Row] | None = None) -> Path:
    """A repository holding the demo page and, if given, its sidecar."""
    (tmp_path / ".git").mkdir()
    page(tmp_path, "p.md", GOOD)
    if rows is not None:
        sidecar = json.dumps(rows, indent=1)
        (tmp_path / "p.facts.json").write_text(sidecar, encoding="utf-8")
    return tmp_path / "p.facts.json"


def dump(path: Path, value: object) -> Path:
    """Write a JSON value; its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def held(car: Path) -> list[facts.Row]:
    """A sidecar's rows."""
    return facts.read_rows(car.read_text(encoding="utf-8"))


def test_a_directory_export_brings_in_the_label_rows_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Another item and a record that is no row are passed over."""
    car = repo(tmp_path)
    out = tmp_path / "export"
    dump(out / "a-1.json", {"id": "a-1", "data": tool("a-1"), "version": 1})
    dump(out / "a-2.json", tool("a-2", item="B"))
    dump(out / "item-A.json", {"item": "A", "niet": [], "updatedAt": 1})
    assert lit(tmp_path, "facts", "--import", str(out), "--item", ITEM) == 0
    said = capsys.readouterr().out
    assert "lit facts: imported 1, replaced 0, kept 0" in said
    assert "lit facts: 1 page(s), 0 finding(s)" in said
    assert held(car) == [
        {
            "id": "a-1",
            "item": "p.md",
            "start": 27,
            "end": 36,
            "text": "The file.",
            "labels": ["good"],
            "note": "",
            "targets": [],
            "commit": SHA,
            "createdAt": 1,
            "updatedAt": 1,
        }
    ]
    assert car.read_text(encoding="utf-8").endswith("\n]\n")


def test_an_array_replaces_by_id_and_appends_by_creation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Old rows keep their place; new ones follow, oldest first."""
    fact = tool("x", note="old")
    old: list[facts.Row] = [{"id": "f", "note": "a fact"}]
    old.append({k: v for k, v in fact.items() if k not in facts.SPAN})
    car = repo(tmp_path, old)
    rows = [
        tool("y", createdAt=5),
        tool("x", note="new", targets=["f"]),
        tool("z", createdAt=2),
        {k: v for k, v in tool("w").items() if k != "createdAt"},
    ]
    src = dump(tmp_path / "rows.json", rows)
    page_ = str(tmp_path / "p.md")
    assert (
        lit(tmp_path, "facts", "--import", str(src), "--item", ITEM, page_)
        == 0
    )
    assert "imported 4, replaced 1, kept 1" in capsys.readouterr().out
    got = held(car)
    assert [r["id"] for r in got] == ["f", "x", "w", "z", "y"]
    assert got[1]["note"] == "new"
    assert got[1]["targets"] == ["f"]


def test_a_row_the_program_cannot_mean_is_refused_at_its_place(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Astral text, odd offsets, odd times, odd ids: each a finding."""
    car = repo(tmp_path)
    rows = [
        tool("ok"),
        tool("smile", text="a \U0001f600"),
        tool("s", start="8"),
        tool("b", end=True),
        tool("t", text=7),
        tool("n") | {"id": 3},
        tool("ok"),
        tool("c", createdAt="now"),
    ]
    src = dump(tmp_path / "rows.json", rows)
    assert lit(tmp_path, "facts", "--import", str(src), "--item", ITEM) == 1
    said = capsys.readouterr().out
    where = f"{src.as_posix()}:"
    for n, message in (
        (2, "text holds U+1F600, two code units in JavaScript"),
        (3, "start and end must be integers"),
        (4, "start and end must be integers"),
        (5, "text must be a string"),
        (6, "id 3 is no new string"),
        (7, "id 'ok' is no new string"),
        (8, "createdAt must be an integer"),
    ):
        assert f"{where}{n}: lit-facts-import: {message}" in said
    assert [r["id"] for r in held(car)] == ["ok"]


@pytest.mark.parametrize(
    ("name", "body", "message"),
    [
        ("rows.json", "[", "rows.json:1: lit-facts-json: Expecting value"),
        ("rows.json", "{}", "not a JSON array of rows"),
        ("rows.json", "[3]", "a row is no JSON object"),
        ("dir/a.json", '{"data": 3}', "dir/a.json:1: lit-facts-json: a row"),
    ],
)
def test_an_unreadable_export_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    body: str,
    message: str,
) -> None:
    """Every file is read strictly; one bad file stops the import."""
    car = repo(tmp_path)
    src = tmp_path / name
    src.parent.mkdir(exist_ok=True)
    src.write_text(body, encoding="utf-8")
    arg = str(src.parent if name.startswith("dir/") else src)
    assert lit(tmp_path, "facts", "--import", arg, "--item", ITEM) == 1
    assert message in capsys.readouterr().out
    assert not car.exists()


def test_an_unreadable_sidecar_is_left_as_it_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No merge into a sidecar that cannot be read."""
    car = repo(tmp_path)
    car.write_text("{}", encoding="utf-8")
    src = dump(tmp_path / "rows.json", [tool("a")])
    assert lit(tmp_path, "facts", "--import", str(src), "--item", ITEM) == 1
    assert "p.facts.json:1: lit-facts-json" in capsys.readouterr().out
    assert car.read_text(encoding="utf-8") == "{}"


def test_an_import_that_breaks_the_sidecar_is_written_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The check runs on the result, so the author sees what to fix."""
    car = repo(tmp_path)
    src = dump(tmp_path / "rows.json", [tool("a b")])
    assert lit(tmp_path, "facts", "--import", str(src), "--item", ITEM) == 1
    assert "p.facts.json:1: lit-facts-id" in capsys.readouterr().out
    assert held(car)[0]["id"] == "a b"


@pytest.mark.parametrize(
    "argv",
    [
        ["facts"],
        ["facts", "--import", "rows.json"],
        ["facts", "--import", "rows.json", "--item", ITEM, "other.md"],
    ],
)
def test_a_command_line_without_its_parts_is_usage(
    tmp_path: Path, argv: list[str]
) -> None:
    """No mode, no --item, or a page the --item does not name."""
    repo(tmp_path)
    assert lit(tmp_path, *argv) == 2


@pytest.mark.parametrize(
    "item", ["A", "A=p.md", "=p.md@" + SHA, "A=@" + SHA, "A=p.md@abc"]
)
def test_an_item_is_spelled_label_page_commit(
    tmp_path: Path, item: str
) -> None:
    """A label, a page and a full 40-hex commit, or exit 2."""
    with pytest.raises(SystemExit) as e:
        lit(tmp_path, "facts", "--export", "p.md", "--item", item)
    assert e.value.code == 2


def test_an_export_of_an_import_gives_back_the_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The program's rows return, with the targets import adds."""
    rows = [tool("a"), tool("b", at=24, end=30, text="# Demo", targets=[])]
    car = repo(tmp_path, [{"id": "f", "note": "a fact", "targets": ["a"]}])
    src = dump(tmp_path / "rows.json", rows)
    assert lit(tmp_path, "facts", "--import", str(src), "--item", ITEM) == 0
    out = tmp_path / "back.json"
    p = str(tmp_path / "p.md")
    assert (
        lit(
            tmp_path, "facts", "--export", p, "--item", ITEM, "--out", str(out)
        )
        == 0
    )
    back = json.loads(out.read_text(encoding="utf-8"))
    assert back == [r | {"targets": r.get("targets", [])} for r in rows]
    capsys.readouterr()
    assert lit(tmp_path, "facts", "--export", p) == 0
    shown = json.loads(capsys.readouterr().out)
    assert [r["item"] for r in shown] == ["p.md", "p.md"]
    car.write_text('[{"id": "a b"}]', encoding="utf-8")
    assert lit(tmp_path, "facts", "--export", p) == 1


def test_merged_leaves_a_row_without_an_id_where_it_is() -> None:
    """An old row with no string id is never replaced."""
    old: list[facts.Row] = [{"note": "x"}, {"id": "a"}]
    new: list[facts.Row] = [{"id": "a", "note": "y"}]
    assert facts.merged(old, new) == ([{"note": "x"}, new[0]], 1)

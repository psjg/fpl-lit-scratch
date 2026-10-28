"""
The pad: one program read top to bottom, its history editable. An edit
evaluates the cell and every cell below it again, from the state the
cells above left; an error stops nothing; an open pair waits.
"""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fpl.__main__ import main
from fpl.pad import Cell, context, removed, replayed, run
from fpl.pad_web import Pad, handler, seeded

CTX = context({})
SQ = "sq : n -- n\n\tdup times\n"
POOL = (SQ, "3 sq", "x", "1 [", "f : -- x\n\t2", "f", "1 | 2 +", "", "\t5")


def pad(*sources: str) -> tuple[Cell, ...]:
    return replayed((), sources, CTX)


def turns(cells: Sequence[Cell]) -> list[tuple[str, ...]]:
    return [cell.turns for cell in cells]


def test_a_turn_is_written_as_the_toplevel_writes_one() -> None:
    assert turns(pad(SQ, "3 sq", "1 | 2 +\n4 sq", "1 drop", "[ 1 2 ]")) == [
        ("sq : number -- number = <word>",),
        ("- : -- number = 9",),
        ("- : -- number = 3", "- : -- number = 16"),
        ("- : -- =",),
        ("- : -- value = [ 1 2 ]",),
    ]


def test_cells_are_read_top_to_bottom() -> None:
    """
    A cell sees the definitions above it, not those below.
    """
    use, define = pad("3 sq", SQ)
    assert use.status == "error"
    assert use.turns[0] == "ERROR: 1:3 unknown word: sq"
    assert define.status == "ok"


def test_an_error_stops_no_cell_and_adds_nothing_to_the_state() -> None:
    cells = pad("x", "1 | 2 +", "sq : n -- n\n\tdup nope", "3 sq")
    assert [cell.status for cell in cells] == ["error", "ok", "error", "error"]
    assert cells[0].turns == ("ERROR: 1:1 unknown word: x", ";; x", ";; ^")
    assert cells[1].turns == ("- : -- number = 3",)
    assert cells[3].turns[0] == "ERROR: 1:3 unknown word: sq"


def test_an_edit_runs_the_cell_and_every_cell_below_from_its_state() -> None:
    before = pad("1 | 1 +", "f : -- x\n\t2", "f", "f f")
    after = run(before, 1, "f : -- x\n\t3", CTX)
    assert after[0] is before[0]
    assert turns(after[2:]) == [
        ("- : -- number = 3",),
        ("- : -- number number = 3 | 3",),
    ]
    assert run(after, 1, "f : -- x\n\t2", CTX)[2:] == before[2:]


def test_an_edit_can_break_and_mend_the_cells_below() -> None:
    cells = run(pad(SQ, "3 sq"), 0, "", CTX)
    assert [cell.status for cell in cells] == ["empty", "error"]
    assert run(cells, 0, SQ, CTX)[1].turns == ("- : -- number = 9",)


def test_an_open_pair_waits_and_the_cells_below_still_run() -> None:
    cells = pad("1 [", "1 | 2 +")
    assert [cell.status for cell in cells] == ["pending", "ok"]
    assert not cells[0].log.events
    closed = run(cells, 0, "1 [\n2 ]", CTX)
    assert closed[0].turns == ("- : -- number value = 1 [ 2 ]",)


def test_a_cell_holds_the_inputs_the_repl_would_group() -> None:
    """
    A blank line ends an input, as in the REPL; a line at the margin
    after a definition head is taken as its body.
    """
    (cell,) = pad("f : -- x\n2\n\nf\n\nx\n\n1 | 1 +")
    assert cell.status == "error"
    assert cell.turns == (
        "f : -- number = <word>",
        "- : -- number = 2",
        "ERROR: 1:1 unknown word: x",
        ";; x",
        ";; ^",
        "- : -- number = 2",
    )
    assert len(cell.log.events) == 4


def test_a_goal_and_a_redefinition_are_noted() -> None:
    cells = pad("f : -- x\n\t2", "f", "f : -- x\n\t3", "g : x -- y\n\t?")
    assert cells[2].turns == ("f : -- number = <word>", ";; CHANGED cell 2")
    assert cells[2].changes == (1,)
    assert cells[3].turns[1] == ";; GOAL 2:2 ? : t0 -- value"


def test_removing_a_cell_runs_the_cells_below_without_it() -> None:
    cells = removed(pad(SQ, "x", "3 sq"), 0, CTX)
    assert [cell.source for cell in cells] == ["x", "3 sq"]
    assert cells[1].status == "error"


def test_an_index_past_the_end_is_refused() -> None:
    with pytest.raises(IndexError):
        run((), 1, "1", CTX)
    with pytest.raises(IndexError):
        removed((), 0, CTX)


@given(st.lists(st.sampled_from(POOL), max_size=5), st.data())
def test_an_edit_to_its_own_text_changes_nothing(
    sources: list[str], data: st.DataObject
) -> None:
    """
    [law: replay-is-identity] running a cell again with its own text
    gives the pad the cells were built as, cell by cell.
    """
    cells = pad(*sources)
    if cells:
        index = data.draw(st.integers(0, len(cells) - 1))
        again = run(cells, index, cells[index].source, CTX)
        assert again == cells


@contextmanager
def served(cells: tuple[Cell, ...] = ()) -> Generator[str]:
    server = HTTPServer(("127.0.0.1", 0), handler(Pad(cells, CTX)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def posted(url: str, body: dict[str, Any] | None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(url, data) as response:
        return json.loads(response.read())


def test_the_page_drives_the_pad_over_http() -> None:
    with served() as url:
        with urllib.request.urlopen(url + "/") as response:
            assert b"<title>FPL pad</title>" in response.read()
        posted(url + "/run", {"index": 0, "source": SQ})
        state = posted(url + "/run", {"index": 1, "source": "3 sq"})
        assert state["cells"][1] == {
            "source": "3 sq",
            "status": "ok",
            "turns": ["- : -- number = 9"],
            "changes": [],
        }
        state = posted(url + "/remove", {"index": 0})
        assert state["cells"][0]["status"] == "error"
        assert posted(url + "/reset", {}) == {"cells": []}
        assert posted(url + "/pad", None) == {"cells": []}


@pytest.mark.parametrize(
    ("route", "body", "code"),
    [("/run", {"index": 5, "source": "1"}, 400), ("/nope", {}, 404)],
)
def test_a_bad_request_is_refused(
    route: str, body: dict[str, Any], code: int
) -> None:
    with served() as url, pytest.raises(urllib.error.HTTPError) as caught:
        posted(url + route, body)
    assert caught.value.code == code


def test_a_file_seeds_one_cell_per_input(tmp_path: Path) -> None:
    cells = seeded(f"{SQ}\n3 sq\n", CTX)
    assert [cell.turns for cell in cells] == [
        ("sq : number -- number = <word>",),
        ("- : -- number = 9",),
    ]
    with pytest.raises(FileNotFoundError):
        main(["pad", str(tmp_path / "missing.fpl"), "--no-browser"])

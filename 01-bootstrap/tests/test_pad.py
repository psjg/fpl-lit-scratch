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
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIServer, make_server

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fpl import pad_web
from fpl.__main__ import main
from fpl.pad import Cell, bar, context, removed, replayed, run
from fpl.pad_web import Pad, app, seeded
from fpl.repl import Tty, phrase_bar

CTX = context({})
AT = datetime(2026, 1, 1, 9, 5, 3)
TICKS = count()
#: A clock that stands still and a timer that gives every cell 1000 ms.
TTY = Tty(now=lambda: AT, timer=lambda: float(next(TICKS)))
SQ = "sq : n -- n\n\tdup times\n"
POOL = (SQ, "3 sq", "x", "1 [", "f : -- x\n\t2", "f", "1 | 2 +", "", "\t5")


def pad(*sources: str) -> tuple[Cell, ...]:
    return replayed((), sources, CTX, TTY)


def turns(cells: Sequence[Cell]) -> list[tuple[str, ...]]:
    return [cell.turns for cell in cells]


def test_a_turn_is_written_as_the_repl_writes_one() -> None:
    """
    A run line is the REPL's result line with the effect in its type
    slot; a definition, as in the REPL, prints nothing; an empty stack
    is a blank line.
    """
    assert turns(pad(SQ, "3 sq", "1 | 2 +\n4 sq", "1 drop", "[ 1 2 ]")) == [
        (),
        ("|- 9 : -- number",),
        ("|- 3 : -- number", "|- 16 : -- number"),
        ("",),
        ("|- [ 1 2 ] : -- value",),
    ]


def test_an_untyped_line_keeps_the_repl_s_dots() -> None:
    clauses = "f : x: Int -- y\n\tdrop #int\nf : x: Text -- y\n\tdrop #text"
    assert turns(pad(clauses, "5 f\n1 [2] [3] if")) == [
        (),
        ("|- #int : -- symbol", "|- 2 : ..."),
    ]


def test_a_phrase_bar_heads_each_cell_and_the_one_to_come() -> None:
    """
    As in the REPL, the bar above a cell counts the phrase, shows the
    head it starts from, and carries the fuel and ms of the cell above;
    a cell that defines only, or fails, leaves no fuel.
    """
    cells = pad(SQ, "3 sq", "x")
    assert [cell.bar for cell in cells] == [
        phrase_bar(1, 0, AT),
        phrase_bar(2, 1, AT, ms=1000.0),
        phrase_bar(3, 2, AT, fuel=4, ms=1000.0),
    ]
    assert bar(cells, TTY) == phrase_bar(4, 3, AT)
    assert bar((), TTY) == phrase_bar(1, 0, AT)


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
    assert cells[1].turns == ("|- 3 : -- number",)
    assert cells[3].turns[0] == "ERROR: 1:3 unknown word: sq"


def test_an_edit_runs_the_cell_and_every_cell_below_from_its_state() -> None:
    before = pad("1 | 1 +", "f : -- x\n\t2", "f", "f f")
    after = run(before, 1, "f : -- x\n\t3", CTX, TTY)
    assert after[0] is before[0]
    assert turns(after[2:]) == [
        ("|- 3 : -- number",),
        ("|- 3 | 3 : -- number number",),
    ]
    assert run(after, 1, "f : -- x\n\t2", CTX, TTY)[2:] == before[2:]


def test_an_edit_can_break_and_mend_the_cells_below() -> None:
    cells = run(pad(SQ, "3 sq"), 0, "", CTX, TTY)
    assert [cell.status for cell in cells] == ["empty", "error"]
    assert run(cells, 0, SQ, CTX, TTY)[1].turns == ("|- 9 : -- number",)


def test_an_open_pair_waits_and_the_cells_below_still_run() -> None:
    cells = pad("1 [", "1 | 2 +")
    assert [cell.status for cell in cells] == ["pending", "ok"]
    assert not cells[0].log.events
    closed = run(cells, 0, "1 [\n2 ]", CTX, TTY)
    assert closed[0].turns == ("|- 1 [ 2 ] : -- number value",)


def test_a_cell_holds_the_inputs_the_repl_would_group() -> None:
    """
    A blank line ends an input, as in the REPL; a line at the margin
    after a definition head is taken as its body.
    """
    (cell,) = pad("f : -- x\n2\n\nf\n\nx\n\n1 | 1 +")
    assert cell.status == "error"
    assert cell.turns == (
        "|- 2 : -- number",
        "ERROR: 1:1 unknown word: x",
        ";; x",
        ";; ^",
        "|- 2 : -- number",
    )
    assert len(cell.log.events) == 4


def test_a_goal_and_a_redefinition_are_noted() -> None:
    cells = pad("f : -- x\n\t2", "f", "f : -- x\n\t3", "g : x -- y\n\t?")
    assert cells[2].turns == (";; CHANGED cell 2",)
    assert cells[2].changes == (1,)
    assert cells[3].turns == (";; GOAL 2:2 ? : t0 -- value",)


def test_removing_a_cell_runs_the_cells_below_without_it() -> None:
    cells = removed(pad(SQ, "x", "3 sq"), 0, CTX, TTY)
    assert [cell.source for cell in cells] == ["x", "3 sq"]
    assert cells[1].status == "error"


def test_an_index_past_the_end_is_refused() -> None:
    with pytest.raises(IndexError):
        run((), 1, "1", CTX, TTY)
    with pytest.raises(IndexError):
        removed((), 0, CTX, TTY)


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
        again = run(cells, index, cells[index].source, CTX, TTY)
        assert again == cells


@contextmanager
def served(cells: tuple[Cell, ...] = ()) -> Generator[str]:
    server = make_server("127.0.0.1", 0, app(Pad(cells, CTX, TTY)))
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
        with urllib.request.urlopen(url + "/pad.js") as response:
            assert b"export async function mount" in response.read()
        with urllib.request.urlopen(url + "/fpl-language.js") as response:
            assert response.headers["Content-Type"].startswith("text/java")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(url + "/nope")
        posted(url + "/run", {"index": 0, "source": SQ})
        state = posted(url + "/run", {"index": 1, "source": "3 sq"})
        assert state["cells"][1] == {
            "source": "3 sq",
            "status": "ok",
            "bar": phrase_bar(2, 1, AT, ms=1000.0),
            "turns": ["|- 9 : -- number"],
            "changes": [],
        }
        assert state["bar"] == phrase_bar(3, 2, AT, fuel=4, ms=1000.0)
        state = posted(url + "/remove", {"index": 0})
        assert state["cells"][0]["status"] == "error"
        empty: dict[str, Any] = {"cells": [], "bar": phrase_bar(1, 0, AT)}
        assert posted(url + "/reset", {}) == empty
        assert posted(url + "/pad", None) == empty


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


def test_the_command_serves_until_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    `python -m fpl pad FILE` binds, opens the page, and stops cleanly at
    Ctrl-C (here raised where the browser would open).
    """
    opened: list[str] = []

    def browse(url: str) -> bool:
        opened.append(url)
        raise KeyboardInterrupt

    monkeypatch.setattr("webbrowser.open", browse)
    (tmp_path / "p.fpl").write_text(SQ)
    assert main(["pad", str(tmp_path / "p.fpl"), "--port", "0"]) == 0
    assert opened[0].startswith("http://127.0.0.1:")
    assert opened[0] in capsys.readouterr().err


def test_without_a_browser_it_serves_until_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupted(_self: WSGIServer) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(WSGIServer, "serve_forever", interrupted)
    assert main(["pad", "--port", "0", "--no-browser"]) == 0


def test_the_pad_colours_with_the_playground_s_tokenizer() -> None:
    """
    fpl/fpl-language.js is a copy of assets/fpl-language.js, which
    ide/gen_highlight.py writes; the pad serves its own copy so that it
    needs nothing outside the package. The two must not drift.
    """
    mine = Path(pad_web.__file__).with_name("fpl-language.js")
    theirs = Path(__file__).parents[2] / "assets" / "fpl-language.js"
    assert mine.read_bytes() == theirs.read_bytes()


def test_a_file_seeds_one_cell_per_input(tmp_path: Path) -> None:
    cells = seeded(f"{SQ}\n3 sq\n", CTX, TTY)
    assert [cell.turns for cell in cells] == [(), ("|- 9 : -- number",)]
    with pytest.raises(FileNotFoundError):
        main(["pad", str(tmp_path / "missing.fpl"), "--no-browser"])

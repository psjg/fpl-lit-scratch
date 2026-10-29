"""
The pad: one program read top to bottom, its history editable. An edit
evaluates the cell and every cell below it again, from the state the
cells above left; an error stops nothing; an open pair waits.
"""

import io
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIServer, make_server

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from fpl import pad_web
from fpl.__main__ import main
from fpl.pad import (
    CUT,
    Cell,
    Ghost,
    bar,
    buffer,
    caret,
    chunks,
    context,
    preview,
    replayed,
    run,
    shaded,
    synced,
    transcript,
)
from fpl.pad_web import Pad, app, seeded
from fpl.repl import Tty, phrase_bar
from fpl.repl import main as repl

CTX = context({})
AT = datetime(2026, 1, 1, 9, 5, 3)
TICKS = count()
#: A clock that stands still and a timer that gives every cell 1000 ms.
TTY = Tty(now=lambda: AT, timer=lambda: float(next(TICKS)))
#: A timer that stands still too, so no preview runs out of time.
STILL = Tty(now=lambda: AT, timer=lambda: 0.0)
SQ = "sq : n -- n\n\tdup times\n"
POOL = (SQ, "3 sq", "x", "1 [", "f : -- x\n\t2", "f", "1 | 2 +", "", "\t5")
#: The cells a buffer keeps one part for each: an empty cell writes a
#: bar with no text, which the reader drops.
FILLED = tuple(source for source in POOL if source)


def pad(*sources: str) -> tuple[Cell, ...]:
    return replayed((), sources, CTX, TTY)


def turns(cells: Sequence[Cell]) -> list[tuple[str, ...]]:
    return [cell.turns for cell in cells]


def test_a_turn_is_written_as_the_repl_writes_one() -> None:
    """
    A run line is the REPL's result line with the sorts on the stack in
    its type slot; a definition, as in the REPL, prints nothing; an
    empty stack is a blank line.
    """
    assert turns(pad(SQ, "3 sq", "1 | 2 +\n4 sq", "1 drop", "[ 1 2 ]")) == [
        (),
        ("|- 9 : Number",),
        ("|- 3 : Number", "|- 16 : Number"),
        ("",),
        ("|- [ 1 2 ] : Value",),
    ]


def test_a_stuck_division_is_one_value_on_the_result_line() -> None:
    """
    By a zero divisor the term stays: one value, written as its source,
    of the sort Value.
    """
    assert turns(pad("7 | 0 kdiv", "1 | 7 | 0 kmod")) == [
        ("|- 7 0 kdiv : Value",),
        ("|- 1 | 7 0 kmod : Nat1 Value",),
    ]


def test_an_untyped_line_keeps_the_repl_s_dots() -> None:
    clauses = "f : x: Int -- y\n\tdrop #int\nf : x: Text -- y\n\tdrop #text"
    assert turns(pad(clauses, "5 f\n1 [2] [3] if")) == [
        (),
        ("|- #int : Symbol", "|- 2 : ..."),
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
    assert cells[0].turns == ("ERROR: 1:1 unknown word: x", ";;! x", ";;! ^")
    assert cells[1].turns == ("|- 3 : Number",)
    assert cells[3].turns[0] == "ERROR: 1:3 unknown word: sq"


def test_an_edit_runs_the_cell_and_every_cell_below_from_its_state() -> None:
    before = pad("1 | 1 +", "f : -- x\n\t2", "f", "f f")
    after = run(before, 1, "f : -- x\n\t3", CTX, TTY)
    assert after[0] is before[0]
    assert turns(after[2:]) == [
        ("|- 3 : Nat1",),
        ("|- 3 | 3 : Nat1 Nat1",),
    ]
    assert run(after, 1, "f : -- x\n\t2", CTX, TTY)[2:] == before[2:]


def test_an_edit_can_break_and_mend_the_cells_below() -> None:
    cells = run(pad(SQ, "3 sq"), 0, "", CTX, TTY)
    assert [cell.status for cell in cells] == ["empty", "error"]
    assert run(cells, 0, SQ, CTX, TTY)[1].turns == ("|- 9 : Number",)


def test_an_open_pair_waits_and_the_cells_below_still_run() -> None:
    cells = pad("1 [", "1 | 2 +")
    assert [cell.status for cell in cells] == ["pending", "ok"]
    assert not cells[0].log.events
    closed = run(cells, 0, "1 [\n2 ]", CTX, TTY)
    assert closed[0].turns == ("|- 1 [ 2 ] : Nat1 Value",)


def test_a_cell_holds_the_inputs_the_repl_would_group() -> None:
    """
    A blank line ends an input, as in the REPL; a line at the margin
    after a definition head is taken as its body.
    """
    (cell,) = pad("f : -- x\n2\n\nf\n\nx\n\n1 | 1 +")
    assert cell.status == "error"
    assert cell.turns == (
        "|- 2 : Nat1",
        "ERROR: 1:1 unknown word: x",
        ";;! x",
        ";;! ^",
        "|- 2 : Number",
    )
    assert len(cell.log.events) == 4


def test_a_goal_and_a_redefinition_are_noted() -> None:
    cells = pad("f : -- x\n\t2", "f", "f : -- x\n\t3", "g : x -- y\n\t?")
    assert cells[2].turns == (";;! CHANGED cell 2",)
    assert cells[2].changes == (1,)
    assert cells[3].turns == (";;! GOAL 2:2 ? : t0 -- Value",)


def test_an_index_past_the_end_is_refused() -> None:
    with pytest.raises(IndexError):
        run((), 1, "1", CTX, TTY)


def test_a_buffer_is_read_as_cells_and_synced_from_the_first_change() -> None:
    """
    The buffer parts at its bars; the loop's lines and the blank edges
    of a cell go. A cell whose text stands is kept as it was; the first
    that differs and every cell below run again.
    """
    before = pad(SQ.rstrip("\n"), "3 sq", "x")
    text = buffer(before, TTY)
    assert chunks(text) == ["sq : n -- n\n\tdup times", "3 sq", "x"]
    assert synced(before, text, CTX, TTY) == before
    edited = text.replace("3 sq", "4 sq").replace("\nx ; \n", "\n\nx\n\n")
    after = synced(before, edited, CTX, TTY)
    assert after[0] is before[0]
    assert turns(after[1:]) == [("|- 16 : Number",), before[2].turns]
    assert chunks("1 2 +\n;;! -( 9 )-< command 2 >-\n\n") == ["1 2 +"]
    assert synced(before, "", CTX, TTY) == ()
    set_in = buffer(before, TTY, "\t")
    assert synced(before, set_in, CTX, TTY) == before
    assert caret(set_in, 0, before, TTY, "\t") == set_in.index("3 sq")


def test_the_caret_goes_to_the_cell_after_the_one_it_was_in() -> None:
    cells = pad("1 | 2 +", "3 sq")
    text = buffer(cells, TTY)
    first = text.index("1 | 2 +")
    second = text.index("3 sq")
    assert text[caret(text, first + 3, cells, TTY) :].startswith("3 sq")
    assert caret(text, second, cells, TTY) == len(text)
    assert caret(text, 0, cells, TTY) == second
    typed = text + "9"
    assert caret(typed, len(typed), cells, TTY) == len(text)


def test_a_cell_of_only_whitespace_counts_for_the_caret() -> None:
    """
    The caret and the reader part a buffer alike: a cell that holds only
    a tab is a cell to both, so the caret leaves it for the next.
    """
    cells = pad("1 | 2 +", "\t", "3 sq")
    text = buffer(cells, TTY)
    tab = len(transcript(cells[:1])) + len(cells[1].bar + " ; ") + 1
    assert text[tab : tab + 2] == "\t\n"
    assert text[caret(text, tab, cells, TTY) :].startswith("3 sq")


def line_of(text: str, line: str) -> int:
    """
    The number, counted from 0, of the first line of *text* that is
    *line*, the pad's terminator not counted.
    """
    return [t.removesuffix(" ; ") for t in text.split("\n")].index(line)


def test_a_preview_evaluates_the_cursor_s_cell_on_the_state_above() -> None:
    """
    The ghost is what a commit would show, from the state the cells
    above leave, on the last text line of the cell; the pad is left as
    it was.
    """
    cells = pad(SQ, "3 sq")
    kept = deepcopy(cells)
    text = buffer(cells, TTY) + "4 sq"
    four = Ghost(line_of(text, "4 sq"), "ok", "|- 16 : Number")
    assert preview(cells, text, len(text), CTX, STILL) == four
    edited = buffer(cells, TTY).replace("\n3 sq ; \n", "\n5 sq\n")
    five = Ghost(line_of(edited, "5 sq"), "ok", "|- 25 : Number")
    for spot in ("5 sq", "< command 2 >", "|- 9 : Number"):
        assert preview(cells, edited, edited.index(spot), CTX, STILL) == five
    both = f"{buffer(cells, TTY)}f : -- x\n\t7\n\n{bar(cells, TTY)}\nf"
    seven = Ghost(len(both.split("\n")) - 1, "ok", "|- 7 : Nat1")
    assert preview(cells, both, len(both), CTX, STILL) == seven
    assert cells == kept


def test_no_ghost_for_a_standing_empty_pending_or_defining_cell() -> None:
    cells = pad(SQ, "3 sq")
    text = buffer(cells, TTY)
    assert preview(cells, text, text.index("3 sq"), CTX, STILL) is None
    assert preview(cells, text, len(text), CTX, STILL) is None
    for typed in ("\t", "1 [", SQ):
        after = text + typed
        assert preview(cells, after, len(after), CTX, STILL) is None


def test_the_ghost_follows_the_last_text_line_of_its_cell() -> None:
    cells = pad(SQ)
    text = buffer(cells, TTY) + "1 | 2 +\n4 sq\n\n"
    at = text.index("1 | 2 +")
    assert preview(cells, text, at, CTX, STILL) == Ghost(
        line_of(text, "4 sq"), "ok", "|- 3 : Number  |- 16 : Number"
    )


def test_a_preview_is_bounded_by_its_fuel() -> None:
    """
    A run line that never ends shows as out of fuel, faded, long before
    the pad's own budget would stop it; a heavy line above the cell is
    run again under the same bound, and a smaller budget of the pad's
    own is kept.
    """
    loop = pad("f : -- x\n\tf")
    text = buffer(loop, TTY) + "f"
    out = Ghost(line_of(text, "f"), "fuel", "ERROR: 1:1 out of fuel")
    assert preview(loop, text, len(text), CTX, STILL, fuel=1000) == out
    started = time.perf_counter()
    assert preview(loop, text, len(text), CTX, Tty(now=lambda: AT)) == out
    assert time.perf_counter() - started < 1.0
    heavy = pad(SQ, "100 sq sq sq")
    one = buffer(heavy, TTY) + "1"
    ghost = preview(heavy, one, len(one), CTX, STILL, fuel=3)
    assert ghost is not None
    assert ghost.kind == "fuel"
    assert ghost.text.startswith("ERROR: @")
    tight = replace(CTX, fuel=3)
    assert preview(heavy, one, len(one), tight, STILL, fuel=1000) == ghost


def test_a_preview_is_bounded_in_time() -> None:
    """
    The whole preview has a deadline, read between inputs: past it, no
    input is entered, of the cell or of an edited cell above it, and
    the ghost ends in the cut, faded as out of fuel. The test's timer
    gains a second a read; the preview reads it once to set its
    deadline, a cell once as it starts and once as it ends, and once
    before each input.
    """
    loop = pad("f : -- x\n\tf")
    many = buffer(loop, TTY) + "1 | 2 +\nf\nf\nf"
    first = Ghost(line_of(many, "f") + 2, "fuel", "|- 3 : Number  " + CUT)
    assert preview(loop, many, len(many), CTX, TTY, seconds=2.5) == first
    cut = Ghost(first.line, "fuel", CUT)
    assert preview(loop, many, len(many), CTX, TTY, seconds=0.5) == cut
    cells = pad(SQ, "3 sq")
    text = buffer(cells, TTY).replace("\n3 sq ; \n", "\n1\n2\n") + "4 sq"
    kept = deepcopy(cells)
    four = Ghost(line_of(text, "4 sq"), "fuel", CUT)
    assert preview(cells, text, len(text), CTX, TTY, seconds=3.5) == four
    assert cells == kept
    lines = buffer(loop, TTY) + "\n".join(["f"] * 40)
    started = time.perf_counter()
    ghost = preview(loop, lines, len(lines), CTX, Tty(now=lambda: AT))
    assert time.perf_counter() - started < 1.0
    assert ghost is not None
    assert ghost.text.endswith(CUT)


def test_shaded_keeps_results_and_errors() -> None:
    """
    A ghost is one line: the results and the ERROR line of the cell,
    without its carets, notes and blank empty stacks.
    """
    (ok,) = pad("1 | 2 +")
    assert shaded(ok, 4) == Ghost(4, "ok", "|- 3 : Number")
    (error,) = pad("x")
    assert shaded(error, 0) == Ghost(0, "error", "ERROR: 1:1 unknown word: x")
    changed = pad("f : -- x\n\t2", "f", "f : -- x\n\t3")[2]
    assert changed.turns == (";;! CHANGED cell 2",)
    assert shaded(changed, 0) is None
    (blank,) = pad("1 drop\n2")
    assert blank.turns == ("", "|- 2 : Nat1")
    assert shaded(blank, 1) == Ghost(1, "ok", "|- 2 : Nat1")


@given(st.lists(st.sampled_from(FILLED), max_size=4))
def test_a_standing_buffer_shows_no_ghost(sources: list[str]) -> None:
    """
    [law: standing-no-ghost] wherever the cursor is in the buffer of a
    pad, nothing differs from what was committed, so nothing is
    previewed.
    """
    cells = pad(*sources)
    text = buffer(cells, TTY)
    for cursor in range(len(text) + 1):
        assert preview(cells, text, cursor, CTX, STILL) is None


@given(st.lists(st.sampled_from(FILLED), max_size=4), st.data())
def test_a_ghost_is_what_a_commit_shows(
    sources: list[str], data: st.DataObject
) -> None:
    """
    [law: ghost-is-commit] a cell typed in place of a cell, or after the
    last, previews as the cell a commit of the buffer gives, shaded on
    its last text line; the ghost is one line.
    """
    cells = pad(*sources)
    index = data.draw(st.integers(0, len(cells)))
    typed = data.draw(st.sampled_from(FILLED))
    if index < len(cells):
        assume(typed.rstrip("\n") != cells[index].source.rstrip("\n"))
    head = transcript(cells[:index]) + bar(cells[:index], TTY) + "\n"
    below = transcript(cells[index + 1 :]) + bar(cells, TTY) + "\n"
    text = f"{head}{typed}\n\n{below}"
    cursor = len(head) + data.draw(st.integers(0, len(typed)))
    line = head.count("\n") + typed.rstrip("\n").count("\n")
    ghost = preview(cells, text, cursor, CTX, STILL)
    assert ghost == shaded(synced(cells, text, CTX, TTY)[index], line)
    assert ghost is None or "\n" not in ghost.text


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


def values(text: str) -> list[str]:
    """
    The values of the result lines in a transcript, in order.
    """
    return [
        line.removeprefix("|- ").rsplit(" : ", 1)[0]
        for line in text.splitlines()
        if line.startswith("|- ")
    ]


def test_a_transcript_reads_back_as_the_pad_and_as_a_repl_session() -> None:
    """
    [law: transcript-round-trip] the pad as text, seeded into a pad
    again, is the same pad (a cell's text without its final newline);
    fed to the REPL loop, it prints the same values and appends one
    event per input, a cell the pad holds open included: the bars,
    results and notes are the loop's lines, and its reader drops them.
    """
    sources = (SQ.rstrip("\n"), "3 sq", "x", "1 [", "f : -- x\n\t2", "f")
    cells = pad(*sources, "1 drop")
    text = transcript(cells)
    assert seeded(text, CTX, TTY) == cells
    assert seeded(transcript(cells, "\t"), CTX, TTY) == cells
    assert "\n\t|- 9 : Number ; \n" in transcript(cells, "\t")
    assert all(
        line.endswith(" ; ") for line in text.splitlines() if line.strip()
    )
    out, err = io.StringIO(), io.StringIO()
    ticks = count()
    still = Tty(now=lambda: AT, timer=lambda: float(next(ticks)))
    code = repl([], io.StringIO(text), out, err, {}, tty=still)
    assert code == 0
    assert values(out.getvalue()) == values(text)
    held = sum(cell.status == "pending" for cell in cells)
    phrases = len(cells[-1].log.events) + held
    assert out.getvalue().count("< command ") == phrases + 1
    assert "ERROR: 1:1 unknown word: x" in out.getvalue()


@contextmanager
def served(cells: tuple[Cell, ...] = (), tty: Tty = TTY) -> Generator[str]:
    server = make_server("127.0.0.1", 0, app(Pad(cells, CTX, tty)))
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
        empty: dict[str, Any] = {
            "cells": [],
            "buffer": phrase_bar(1, 0, AT) + " ; \n",
            "caret": len(phrase_bar(1, 0, AT)) + 4,
        }
        assert posted(url + "/pad", None) == empty
        text = empty["buffer"] + SQ + "\n" + phrase_bar(2, 1, AT) + "\n3 sq"
        state = posted(url + "/buffer", {"text": text, "cursor": len(text)})
        set_in = posted(url + "/pad", {"indent": "\t"})
        assert "\n\t|- 9 : Number ; \n" in set_in["buffer"]
        assert set_in["caret"] == len(set_in["buffer"])
        assert state["cells"][1] == {
            "source": "3 sq",
            "status": "ok",
            "bar": phrase_bar(2, 1, AT, ms=1000.0),
            "turns": ["|- 9 : Number"],
            "changes": [],
        }
        assert state["buffer"].endswith(
            "3 sq ; \n|- 9 : Number ; \n"
            + phrase_bar(3, 2, AT, fuel=4, ms=1000.0)
            + " ; \n"
        )
        assert state["caret"] == len(state["buffer"])
        assert posted(url + "/reset", {}) == empty


def test_a_preview_route_answers_the_ghost_and_changes_nothing() -> None:
    """
    ``/preview`` answers the ghost of the cell under the cursor, or
    null; neither the cells nor the indent of the pad change. Past its
    deadline (on the ticking timer, at once) the ghost is the cut.
    """
    cells = pad(SQ, "3 sq")
    text = buffer(cells, TTY) + "4 sq"
    line = line_of(text, "4 sq")
    ghost = {"line": line, "kind": "ok", "text": "|- 16 : Number"}
    held = Pad(cells, CTX, STILL)
    held.indent = "\t"
    body = {"text": text, "cursor": len(text)}
    assert held.change("/preview", body) == {"ghost": ghost}
    assert held.cells is cells
    assert held.indent == "\t"
    late = Pad(cells, CTX, TTY).change("/preview", body)
    assert late == {"ghost": {"line": line, "kind": "fuel", "text": CUT}}
    with served(cells, STILL) as url:
        before = posted(url + "/pad", None)
        assert posted(url + "/preview", body) == {"ghost": ghost}
        standing = {"text": before["buffer"], "cursor": 0}
        assert posted(url + "/preview", standing) == {"ghost": None}
        assert posted(url + "/pad", None) == before


@pytest.mark.parametrize(
    ("route", "body", "code"),
    [
        ("/buffer", {"text": "1"}, 400),
        ("/preview", {"text": "1"}, 400),
        ("/preview", {"text": "1", "cursor": "x"}, 400),
        ("/nope", {}, 404),
    ],
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
    assert [cell.turns for cell in cells] == [(), ("|- 9 : Number",)]
    with pytest.raises(FileNotFoundError):
        main(["pad", str(tmp_path / "missing.fpl"), "--no-browser"])

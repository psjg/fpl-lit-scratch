"""
The session kernel: a transcript fed back in is the program it came
from, a kernel serves JSON lines on a unix socket, a watcher hears what
another client feeds, and the REPL's refusals reach the client as codes.
"""

import json
import socket
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fpl.kernel import (
    Kernel,
    Outbox,
    Turn,
    main,
    names,
    replayed,
    serve,
    split,
    swallowed,
)
from fpl.log import keyed, load

lines = st.text(alphabet="ab1 +[]|=;", max_size=8)


@given(st.lists(lines, min_size=1, max_size=4), st.lists(lines, max_size=4))
def test_a_transcript_swallows_to_its_inputs(
    text: list[str], out: list[str]
) -> None:
    """
    [law: transcript-round-trip] the result lines of a turn swallow
    away, leaving the input as it was entered.
    """
    entered = "".join(f"x {line}\n" for line in text)
    turn = Turn(entered, "".join(f"{o}\n" for o in out), (), 0, None, 0.0)
    assert swallowed(turn.block()) == entered


def test_a_block_writes_results_and_notes() -> None:
    turn = Turn("1 2 +\n", "a\n\nb\n", ("HEAD 1\nx",), 0, None, 0.0)
    assert turn.block() == "1 2 +\n|= a\n|=\n|= b\n;; HEAD 1\n;; x\n"
    assert swallowed(turn.block()) == "1 2 +\n;; HEAD 1\n;; x\n"


def test_split_groups_inputs_as_the_repl_does() -> None:
    assert split("1\n2\n|= 1\n\n[ 1\n 2 ]\n") == ["1\n", "2\n", "[ 1\n 2 ]\n"]


class Client:
    """
    A blocking client of one connection.
    """

    def __init__(self, path: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(path))
        self.reader = self.sock.makefile("rb")

    def read(self) -> dict[str, Any]:
        return cast("dict[str, Any]", json.loads(self.reader.readline()))

    def ask(self, **request: object) -> dict[str, Any]:
        self.sock.sendall(json.dumps(request).encode() + b"\n")
        return self.read()

    def close(self) -> None:
        self.reader.close()
        self.sock.close()


@contextmanager
def running() -> Generator[tuple[Kernel, Path, Path]]:
    """
    A kernel serving in a thread, its log and its socket.
    """
    with tempfile.TemporaryDirectory(dir="/tmp") as root:
        work = Path(root)
        env = {"FPL_LOG_KEY": f"{root}/key", "HOME": root}
        kernel = Kernel("t", work / "t.log", 1000, env)
        path = work / "run" / "t.sock"
        thread = threading.Thread(target=serve, args=(kernel, path))
        thread.start()
        while not _live(path):
            thread.join(0.01)
        try:
            yield kernel, path, work
        finally:
            kernel.stopped.set()
            thread.join()
            assert not path.exists()


def test_feed_replay_and_commands() -> None:
    with running() as (kernel, path, _work):
        c = Client(path)
        assert c.ask(op="hello", id=7) == {
            "id": 7,
            "session": "t",
            "head": 0,
            "fuel": 1000,
            "status": "done",
        }
        fed = c.ask(op="feed", text="1 2 +\n\nnope\n", id=1)
        assert fed["transcript"].startswith("1 2 +\n|= [ 1 2 + ]\n;; HEAD 1 $")
        codes = [t["code"] for t in fed["turns"]]
        assert codes == [0, 1]
        assert "1 input ok" in c.ask(op="log")["out"]
        assert c.ask(op="show")["out"] == "1 2 +\n"
        assert c.ask(op="rewind", event="0")["code"] == 0
        listed = c.ask(op="feed", text=":log\n:show\n:rewind 1\n")
        assert [t["code"] for t in listed["turns"]] == [0, 0, 0]
        again = c.ask(op="replay")["transcript"]
        assert again.count(":rewind") == 2
        assert load(kernel.log, keyed(kernel.env)).head is not None
        c.close()


def test_a_watcher_hears_a_feed_and_a_gone_watcher_is_dropped() -> None:
    with running() as (kernel, path, _work):
        watcher, doer = Client(path), Client(path)
        assert watcher.ask(op="watch")["status"] == "done"
        doer.ask(op="feed", text="1\n", who={"model": "m", "session": "s"})
        heard = watcher.read()
        assert heard["event"] == "feed"
        assert "|= 1\n" in heard["transcript"]
        assert len(kernel.watchers) == 1
        watcher.close()
        for _ in range(3):
            doer.ask(op="feed", text="2\n")
        assert kernel.watchers == []
        doer.close()


def test_a_watcher_that_cannot_be_written_to_is_dropped() -> None:
    with running() as (kernel, path, _work):

        def broken(_message: dict[str, Any]) -> None:
            raise BrokenPipeError

        kernel.watchers.append(broken)
        doer = Client(path)
        assert doer.ask(op="feed", text="1\n")["status"] == "done"
        assert kernel.watchers == []
        doer.close()


def test_refusals_are_errors_not_crashes() -> None:
    with running() as (_kernel, path, _work):
        c = Client(path)
        for bad in (
            {"op": "nope"},
            {"op": "feed"},
            {"op": "feed", "text": "1", "fuel": True},
            {"op": "feed", "text": "1", "fuel": -1},
            {"op": "feed", "text": "1", "who": {"model": 1}},
            {"op": "feed", "text": "1", "who": 3},
        ):
            assert c.ask(**bad)["status"] == "error"
        c.sock.sendall(b"[1]\n")
        assert c.read()["status"] == "error"
        c.sock.sendall(b"{\n")
        assert c.read()["status"] == "error"
        refused = c.ask(op="feed", text="1\n", who={"model": "é"})
        assert refused["turns"][0]["code"] == 2
        usage = c.ask(op="feed", text=":rewind --x\n")
        assert usage["turns"][0]["code"] == 2
        c.close()


def test_stop_is_answered_and_main_yields_to_a_live_kernel() -> None:
    with tempfile.TemporaryDirectory(dir="/tmp") as root:
        sock = Path(root) / "k.sock"
        sock.write_text("stale")
        env = {"FPL_LOG_KEY": f"{root}/key"}
        argv = ["--name", "k", "--log", f"{root}/k.log", "--socket", str(sock)]
        done: list[int] = []
        thread = threading.Thread(target=lambda: done.append(main(argv, env)))
        thread.start()
        while not _live(sock):
            thread.join(0.01)
        assert main(argv, env) == 0
        assert _live(sock)
        assert Client(sock).ask(op="stop")["status"] == "done"
        thread.join()
        assert done == [0]
        assert not sock.exists()


def test_a_feed_reads_at_one_head_and_writes_at_another() -> None:
    with running() as (kernel, path, _work):
        c = Client(path)
        c.ask(op="feed", text="1\n2\n")
        read = c.ask(op="feed", text="3\n", at="1")
        assert read["turns"][0]["code"] == 0
        events = load(kernel.log, keyed(kernel.env)).events
        assert len(events) == 2
        stale = c.ask(op="feed", text="4\n5\n", head="1")
        assert [t["code"] for t in stale["turns"]] == [2, 0]
        assert "head moved" in stale["turns"][0]["out"]
        fresh = c.ask(op="feed", text="6\n7\n", head="3")
        assert [t["code"] for t in fresh["turns"]] == [0, 0]
        assert c.ask(op="feed", text="1", at=1)["status"] == "error"
        c.close()


def test_a_refusal_names_its_request() -> None:
    with running() as (_kernel, path, _work):
        c = Client(path)
        huge = c.ask(op="feed", text="1", fuel=2**64, id=5)
        assert (huge["id"], huge["status"]) == (5, "error")
        c.close()


def test_a_feed_is_recorded_under_the_client_that_made_it() -> None:
    with running() as (kernel, path, _work):
        c = Client(path)
        c.ask(op="feed", text="1\n", who={"model": "m", "session": "s"})
        event = load(kernel.log, keyed(kernel.env)).events[0]
        assert (event.who, event.model, event.session) == ("agent", "m", "s")
        c.close()


def test_a_watcher_that_never_reads_is_dropped_not_waited_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fpl.kernel.BACKLOG", 1)
    with running() as (kernel, path, _work):
        idle, doer = Client(path), Client(path)
        doer.sock.settimeout(60)
        idle.ask(op="watch")
        for _ in range(12):
            assert doer.ask(op="feed", text="a" * 400_000)["status"] == "done"
            if not kernel.watchers:
                break
        assert kernel.watchers == []
        idle.close()
        doer.close()


def test_saying_waits_for_room_and_gives_up_on_a_gone_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fpl.kernel.BACKLOG", 1)
    ours, theirs = socket.socketpair()
    out = Outbox(ours)
    big = {"x": "y" * 4_000_000}

    def say() -> None:
        for _ in range(4):
            out.say(big)

    saying = threading.Thread(target=say)
    saying.start()
    time.sleep(0.6)
    assert saying.is_alive()
    theirs.close()
    saying.join(20)
    assert not saying.is_alive()
    out.close()
    ours.close()


def test_closing_cuts_off_a_client_that_does_not_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fpl.kernel.BACKLOG", 1)
    monkeypatch.setattr("fpl.kernel.PATIENCE", 0.2)
    ours, theirs = socket.socketpair()
    out = Outbox(ours)
    big = {"x": "y" * 4_000_000}
    out.push(big)
    time.sleep(0.3)
    out.push(big)
    out.close()
    assert not out.thread.is_alive()
    ours.close()
    theirs.close()


def test_a_client_that_leaves_before_its_answer_costs_nothing() -> None:
    with running() as (_kernel, path, _work):
        gone = Client(path)
        request = json.dumps({"op": "feed", "text": "1\n", "id": 1})
        gone.sock.sendall(request.encode() + b"\n")
        gone.close()
        c = Client(path)
        assert c.ask(op="hello")["status"] == "done"
        time.sleep(0.3)
        c.close()


def _live(path: Path) -> bool:
    try:
        Client(path).close()
    except OSError:
        return False
    return True


def test_names_refuses_a_bad_name(capsys: pytest.CaptureFixture[str]) -> None:
    assert names(["--name", "a.b", "--log", "l", "--socket", "s"])[0] == "a.b"
    with pytest.raises(SystemExit):
        names(["--name", "../x", "--log", "l", "--socket", "s"])
    assert "not a session name" in capsys.readouterr().err


def test_a_replay_of_an_empty_log_is_empty() -> None:
    with tempfile.TemporaryDirectory(dir="/tmp") as root:
        assert replayed(load(Path(root) / "none", b"")) == ""

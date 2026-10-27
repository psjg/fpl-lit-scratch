"""
The session kernel: a transcript fed back in is the program it came
from, a kernel serves JSON lines on a unix socket, a watcher hears what
another client feeds, and the REPL's refusals reach the client as codes.
"""

import json
import socket
import tempfile
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fpl.kernel import (
    Kernel,
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


def test_stop_ends_the_kernel_and_main_yields_to_a_live_one() -> None:
    with running() as (_kernel, path, work):
        assert (
            main(
                [
                    "--name",
                    "t",
                    "--log",
                    str(work / "t.log"),
                    "--socket",
                    str(path),
                ]
            )
            == 0
        )
        Client(path).ask(op="stop")
    with tempfile.TemporaryDirectory(dir="/tmp") as root:
        sock = Path(root) / "k.sock"
        sock.write_text("stale")
        done: list[int] = []
        env = {"FPL_LOG_KEY": f"{root}/key"}
        thread = threading.Thread(
            target=lambda: done.append(
                main(
                    [
                        "--name",
                        "k",
                        "--log",
                        f"{root}/k.log",
                        "--socket",
                        str(sock),
                    ],
                    env,
                )
            )
        )
        thread.start()
        while not _live(sock):
            thread.join(0.01)
        Client(sock).ask(op="stop")
        thread.join()
        assert done == [0]


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

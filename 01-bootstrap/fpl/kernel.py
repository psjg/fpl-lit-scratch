"""
`python -m fpl.kernel`: the kernel of one named session, which the
frontends (`fpl repl`, `fpl pty`, `fpl tui`) attach to. It owns the
session's log and a unix socket, and serves JSON lines: a request is an
object with an `op` and an `id`, and its response carries the `id` and
`"status": "done"`, or `"status": "error"` and an `error` text. Turns
are serialised, and each is carried out by `fpl.repl.once`, the REPL's
own call, so a frontend cannot see a result the REPL would not give.
The design is docs 02.05.14.

Ops: `hello`; `feed` (text, optionally fuel and who); `replay`; `log`;
`show`; `rewind` (event); `watch`, after which every feed of any client
is pushed to this connection as an `event` object; `stop`. Exit 0 when
the kernel stopped, or another one already serves the socket; 2 for
argv not taken.
"""

import contextlib
import fcntl
import json
import os
import queue
import re
import select
import socket
import sys
import threading
import time
from argparse import ArgumentParser
from collections.abc import Callable, Generator, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from fpl.driver import FUEL_DEFAULT
from fpl.log import U64, Log, keyed, load
from fpl.repl import Said, inputs, once

RESULT = "|="
"""
A line that starts with this, then a space or the end of the line, is a
result: written after the input that printed it, swallowed on the way
in.
"""
WHO = {"model": "FPL_MODEL", "session": "FPL_SESSION_ID"}
"""
The fields of a feed's `who`, and the variables the REPL reads.
"""
PATIENCE = 2.0
"""
Seconds a closing connection waits for a client that does not read.
"""
BACKLOG = 64
"""
Messages a connection may have waiting to be written before a watcher
that does not read is dropped.
"""
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
Sender = Callable[[dict[str, Any]], None]
Request = Mapping[str, Any]


def swallowed(text: str) -> str:
    """
    The text without its result lines, so a transcript fed back in is
    the program it came from. A result is not checked against the run.
    """
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not (line.startswith(RESULT + " ") or line.rstrip("\n") == RESULT)
    )


def split(text: str) -> list[str]:
    """
    The inputs of a text, grouped as the REPL groups the lines it reads.
    """
    lines = iter(swallowed(text).splitlines())
    return list(inputs(lambda _on: next(lines, None)))


@dataclass(frozen=True)
class Turn:
    """
    An input and what it left: its stdout, its notes, its exit status
    (0 ok, 1 failed, 2 refused), the steps it took if it ran any, and
    the wall milliseconds.
    """

    text: str
    out: str
    notes: tuple[str, ...]
    code: int
    spent: int | None
    ms: float

    def block(self) -> str:
        """
        The input as entered, then its output as `|=` lines and its
        notes as `;;` comments, each ending in a newline.
        """
        shown = [f"{RESULT} {line}".rstrip() for line in self.out.splitlines()]
        notes = [
            f";; {line}".rstrip()
            for note in self.notes
            for line in note.split("\n")
        ]
        lines = [self.text.rstrip("\n"), *shown, *notes]
        return "".join(line + "\n" for line in lines)


def argv_of(
    session: Path, fuel: int, text: str, heads: list[str]
) -> list[str]:
    """
    The REPL call an input stands for: `:log`, `:show` and `:rewind N`
    as the loop reads them, else the input as -e; `heads` is the
    --at and --head the call carries.
    """
    match text.split():
        case [":log"]:
            tail = ["--log"]
        case [":show"]:
            tail = ["--show"]
        case [":rewind", event]:
            tail = ["--rewind", event]
        case _:
            tail = ["-e", text]
    return ["--session", str(session), "--fuel", str(fuel), *heads, *tail]


def turned(told: Said, text: str, ms: float) -> Turn:
    """
    What a call said, as the turn of the input.
    """
    return Turn(text, told.out, told.notes, told.code, told.spent, ms)


def replayed(log: Log) -> str:
    """
    The whole log as a transcript: each input with its output, a rewind
    as the `:rewind N` that makes it, so feeding it to a fresh session
    walks the same inputs.
    """
    seqs = {event.ident: event.seq for event in log.events}
    parts: list[str] = []
    for event in log.events:
        if event.kind == "rewind":
            target = seqs[event.deps[0]] if event.deps else 0
            parts.append(f":rewind {target}\n")
            continue
        body = log.bodies[event.body].decode()
        out = log.bodies[event.out].decode()
        code = 0 if event.status == "ok" else 1
        parts.append(Turn(body, out, (), code, None, 0.0).block())
    return "".join(parts)


class Kernel:
    """
    The state of a kernel: the session's log path, the default fuel, the
    environment the REPL runs under, and the connections that watch.
    Turns run one at a time under `lock`.
    """

    def __init__(
        self,
        name: str,
        log: Path,
        fuel: int,
        env: Mapping[str, str],
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.name = name
        self.log = log
        self.fuel = fuel
        self.env = {k: v for k, v in env.items() if k not in WHO.values()}
        self.clock = clock
        self.lock = threading.Lock()
        self.watchers: list[Sender] = []
        self.stopped = threading.Event()
        self.stopper: int | None = None
        self.plain: dict[str, Callable[[], dict[str, Any]]] = {
            "hello": self.hello,
            "replay": self.replay,
            "log": lambda: self.asked(["--log"]),
            "show": lambda: self.asked(["--show"]),
            "stop": self.stop,
        }

    def turn(
        self, text: str, fuel: int, env: Mapping[str, str], heads: list[str]
    ) -> Turn:
        """
        One input, carried out; the REPL's refusal is its code 2.
        """
        started = self.clock()
        told = once(argv_of(self.log, fuel, text, heads), env)
        return turned(told, text, (self.clock() - started) * 1000.0)

    @staticmethod
    def heads(request: Request, n: int) -> list[str]:
        """
        The heads input `n` of a feed carries: the read head `at`, if
        the request names one, for every input; the write head `head`,
        if it does, for the first only, since an append moves it.
        """
        at, head = request.get("at"), request.get("head")
        return [
            *(["--at", at] if at is not None else []),
            *(["--head", head] if head is not None and n == 0 else []),
        ]

    def fed(self, request: Request) -> dict[str, Any]:
        """
        The inputs of the request's text, entered one after another, and
        their transcript; every watcher is told.
        """
        text, fuel = request["text"], request.get("fuel", self.fuel)
        who: Mapping[str, str] = request.get("who", {})
        env = {
            **self.env,
            **{WHO[key]: value for key, value in who.items() if key in WHO},
        }
        with self.lock:
            turns = [
                self.turn(each, fuel, env, self.heads(request, n))
                for n, each in enumerate(split(text))
            ]
        answer = {
            "turns": [asdict(each) for each in turns],
            "transcript": "".join(each.block() for each in turns),
        }
        for watcher in list(self.watchers):
            try:
                watcher({"event": "feed", **answer})
            except (OSError, queue.Full):
                self.watchers.remove(watcher)
        return answer

    def asked(self, argv: list[str]) -> dict[str, Any]:
        """
        A call of the REPL that appends nothing, or a rewind, as `out`.
        """
        with self.lock:
            told = once(["--session", str(self.log), *argv], self.env)
        return {"out": told.out, "code": told.code}

    def stop(self) -> dict[str, Any]:
        """
        Ask the server to end: the thread of the connection that asked
        sets `stopped` once its answer is out.
        """
        self.stopper = threading.get_ident()
        return {}

    def hello(self) -> dict[str, Any]:
        """
        Who this kernel is: the session, its head, its default fuel.
        """
        with self.lock:
            events = len(load(self.log, keyed(self.env)).events)
        return {"session": self.name, "head": events, "fuel": self.fuel}

    def replay(self) -> dict[str, Any]:
        """
        The transcript of the whole log.
        """
        with self.lock:
            log = load(self.log, keyed(self.env))
        return {"transcript": replayed(log)}

    def answer(self, request: Request, send: Sender) -> dict[str, Any]:
        """
        The response to a request that is an object: its fields, or the
        reason it is refused.
        """
        match request:
            case {"op": "watch"}:
                self.watchers.append(send)
                return {}
            case {"op": "rewind", "event": str(event)}:
                return self.asked(["--rewind", event])
            case {"op": "feed", "text": str()} if fuel_ok(request):
                return self.fed(request)
            case {"op": str(op)} if op in self.plain:
                return self.plain[op]()
            case _:
                raise ValueError(f"not a request this kernel takes: {request}")


def fuel_ok(request: Request) -> bool:
    """
    A feed's fuel, if it names one, is a decimal budget below 2^64, its
    `who`, if any, holds text only, and so do `at` and `head`.
    """
    fuel = request.get("fuel", 0)
    who = request.get("who", {})
    return (
        type(fuel) is int
        and 0 <= fuel < U64
        and all(isinstance(request.get(k, ""), str) for k in ("at", "head"))
        and isinstance(who, dict)
        and all(
            isinstance(v, str) for v in cast("dict[str, Any]", who).values()
        )
    )


def failed(ident: object, error: object) -> dict[str, Any]:
    """
    The response to a request refused, which still names the request.
    """
    return {"id": ident, "status": "error", "error": str(error)}


def response(kernel: Kernel, line: bytes, send: Sender) -> dict[str, Any]:
    """
    The response to one line: the request's `id` echoed, `status` done,
    or error with the reason, for a line that is not JSON, not an
    object, or not a request this kernel takes.
    """
    try:
        parsed: object = json.loads(line)
    except ValueError as error:
        return failed(None, error)
    if not isinstance(parsed, dict):
        return failed(None, "a request is a JSON object")
    request = cast("Request", parsed)
    try:
        answer = kernel.answer(request, send)
    except ValueError as error:
        return failed(request.get("id"), error)
    return {"id": request.get("id"), **answer, "status": "done"}


class Outbox:
    """
    The messages to one client, written by a thread of its own from a
    bounded queue, so that a client that stops reading holds up only
    itself: `push` never waits, and at the bound it cuts the connection
    and raises queue.Full.
    """

    def __init__(self, conn: socket.socket) -> None:
        self.conn = conn
        self.queue: queue.Queue[dict[str, Any] | None] = queue.Queue(BACKLOG)
        self.dead = threading.Event()
        self.thread = threading.Thread(target=self.write, daemon=True)
        self.thread.start()

    def cut(self) -> None:
        """
        Cut the connection, which ends the threads waiting on it.
        """
        with contextlib.suppress(OSError):
            self.conn.shutdown(socket.SHUT_RDWR)

    def push(self, message: dict[str, Any]) -> None:
        """
        Queue a message; if the client is that far behind, cut the
        connection, so its threads end, and raise queue.Full.
        """
        try:
            self.queue.put_nowait(message)
        except queue.Full:
            self.cut()
            raise

    def write(self) -> None:
        """
        Write the queue until the end mark; a client gone ends it.
        """
        try:
            with self.conn.makefile("wb") as writer:
                while (message := self.queue.get()) is not None:
                    writer.write(json.dumps(message).encode() + b"\n")
                    writer.flush()
        except OSError:
            self.dead.set()

    def say(self, message: dict[str, Any] | None) -> None:
        """
        Queue a message, waiting for room, unless the writer is gone.
        """
        while not self.dead.is_set():
            try:
                self.queue.put(message, timeout=0.2)
                return
            except queue.Full:
                continue

    def close(self) -> None:
        """
        End the queue and give the writer a moment to empty it; a
        client that does not read is cut off.
        """
        try:
            self.queue.put(None, timeout=PATIENCE)
        except queue.Full:
            self.cut()
        self.thread.join(PATIENCE)


def connection(kernel: Kernel, conn: socket.socket) -> None:
    """
    One connection: a response per line until the client goes, or the
    kernel is asked to stop, which is set once the answer is written.
    """
    out = Outbox(conn)
    with conn, conn.makefile("rb") as reader:
        try:
            for line in reader:
                out.say(response(kernel, line, out.push))
                if kernel.stopper:
                    break
        finally:
            with contextlib.suppress(ValueError):
                kernel.watchers.remove(out.push)
            out.close()
            if kernel.stopper == threading.get_ident():
                kernel.stopped.set()


def serve(kernel: Kernel, path: Path) -> None:
    """
    Serve the kernel on a socket at path (mode 0600, in a directory
    only the user may enter), a thread per connection, until a client
    stops it. A socket file found there is a dead kernel's, and
    replaced.
    """
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(path))
        path.chmod(0o600)
        listener.listen()
        while not kernel.stopped.is_set():
            if select.select([listener], [], [], 0.1)[0]:
                conn, _ = listener.accept()
                threading.Thread(
                    target=connection, args=(kernel, conn), daemon=True
                ).start()
    path.unlink(missing_ok=True)


def names(argv: list[str]) -> tuple[str, Path, Path, int]:
    """
    The name, the log, the socket and the fuel of argv. Refused
    (SystemExit 2): a name outside NAME, anything else argparse refuses.
    """
    parser = ArgumentParser(prog="python -m fpl.kernel", allow_abbrev=False)
    parser.add_argument("--name", required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--fuel", type=int, default=FUEL_DEFAULT)
    args = parser.parse_args(argv)
    if not NAME.fullmatch(args.name):
        parser.error(f"{args.name!r} is not a session name")
    return args.name, args.log, args.socket, args.fuel


@contextlib.contextmanager
def lifetime(path: Path) -> Generator[bool]:
    """
    The right to be the kernel behind the socket at path: an exclusive
    lock on `<path>.lock`, held for the block and dropped with the
    process, so a kernel that died leaves nothing to clear. False where
    another kernel holds it.
    """
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(f"{path}.lock", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(fd)


def main(argv: list[str], env: Mapping[str, str] = os.environ) -> int:
    """
    Serve the named session, unless another kernel already does.
    """
    name, log, path, fuel = names(argv)
    with lifetime(path) as mine:
        if mine:
            serve(Kernel(name, log, fuel, env), path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

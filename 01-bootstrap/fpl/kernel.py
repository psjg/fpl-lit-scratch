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
import json
import os
import re
import select
import socket
import sys
import threading
import time
from argparse import ArgumentParser
from collections.abc import Callable, Mapping
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


def argv_of(session: Path, fuel: int, text: str) -> list[str]:
    """
    The REPL call an input stands for: `:log`, `:show` and `:rewind N`
    as the loop reads them, else the input as -e.
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
    return ["--session", str(session), "--fuel", str(fuel), *tail]


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
        self.env = {
            k: v
            for k, v in env.items()
            if k not in ("FPL_MODEL", "FPL_SESSION_ID")
        }
        self.clock = clock
        self.lock = threading.Lock()
        self.watchers: list[Sender] = []
        self.stopped = threading.Event()
        self.plain: dict[str, Callable[[], dict[str, Any]]] = {
            "hello": self.hello,
            "replay": self.replay,
            "log": lambda: self.asked(["--log"]),
            "show": lambda: self.asked(["--show"]),
            "stop": self.stop,
        }

    def turn(self, text: str, fuel: int, env: Mapping[str, str]) -> Turn:
        """
        One input, carried out; the REPL's refusal is its code 2.
        """
        started = self.clock()
        told = once(argv_of(self.log, fuel, text), env)
        return turned(told, text, (self.clock() - started) * 1000.0)

    def fed(self, request: Request) -> dict[str, Any]:
        """
        The inputs of the request's text, entered one after another, and
        their transcript; every watcher is told.
        """
        text, fuel = request["text"], request.get("fuel", self.fuel)
        who: Mapping[str, str] = request.get("who", {})
        env = {
            **self.env,
            **{
                f"FPL_{key.upper()}": value
                for key, value in who.items()
                if key in ("model", "session")
            },
        }
        with self.lock:
            turns = [self.turn(each, fuel, env) for each in split(text)]
        answer = {
            "turns": [asdict(each) for each in turns],
            "transcript": "".join(each.block() for each in turns),
        }
        for watcher in list(self.watchers):
            try:
                watcher({"event": "feed", **answer})
            except OSError:
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
        Ask the server to end; the answer still goes out first.
        """
        self.stopped.set()
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
    A feed's fuel, if it names one, is a decimal budget below 2^64, and
    its `who`, if any, holds text only.
    """
    fuel = request.get("fuel", 0)
    who = request.get("who", {})
    return (
        type(fuel) is int
        and 0 <= fuel < U64
        and isinstance(who, dict)
        and all(
            isinstance(v, str) for v in cast("dict[str, Any]", who).values()
        )
    )


def response(kernel: Kernel, line: bytes, send: Sender) -> dict[str, Any]:
    """
    The response to one line: the request's `id` echoed, `status` done,
    or error with the reason, for a line that is not JSON, not an
    object, or not a request this kernel takes.
    """
    try:
        parsed: object = json.loads(line)
        if not isinstance(parsed, dict):
            raise ValueError("a request is a JSON object")
        request = cast("Request", parsed)
        return {
            "id": request.get("id"),
            **kernel.answer(request, send),
            "status": "done",
        }
    except ValueError as error:
        return {"id": None, "status": "error", "error": str(error)}


def connection(kernel: Kernel, conn: socket.socket) -> None:
    """
    One connection: a response per line until the client goes. Writes
    go under a lock of the connection's own, since a watcher is written
    to from another connection's thread.
    """
    mine = threading.Lock()
    reader, writer = conn.makefile("rb"), conn.makefile("wb")

    def send(message: dict[str, Any]) -> None:
        data = json.dumps(message).encode() + b"\n"
        with mine:
            writer.write(data)
            writer.flush()

    with conn, reader, writer:
        try:
            for line in reader:
                send(response(kernel, line, send))
        finally:
            with contextlib.suppress(ValueError):
                kernel.watchers.remove(send)


def alive(path: Path) -> bool:
    """
    Something accepts connections on the socket at path.
    """
    with socket.socket(socket.AF_UNIX) as probe:
        try:
            probe.connect(str(path))
        except OSError:
            return False
    return True


def serve(kernel: Kernel, path: Path) -> None:
    """
    Serve the kernel on a socket at path (mode 0600, in a directory
    only the user may enter), a thread per connection, until a client
    stops it. A socket nobody answers on is a dead kernel's, and
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


def main(argv: list[str], env: Mapping[str, str] = os.environ) -> int:
    """
    Serve the named session, unless another kernel already does.
    """
    name, log, path, fuel = names(argv)
    if not alive(path):
        serve(Kernel(name, log, fuel, env), path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

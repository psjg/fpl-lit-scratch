"""Serve one named FPL session over a unix socket.

Run as ``python -m fpl.kernel``; the frontends (``fpl repl``, ``fpl
pty``, ``fpl tui``) attach to it. :func:`main` serves the socket with
:func:`serve`, and each turn is carried out by :func:`fpl.repl.once`, so
a frontend sees only results the REPL would give. The protocol is JSON
lines: a request is an object with an ``op`` and an ``id``, and the
response carries the ``id`` and ``"status": "done"``, or ``"status":
"error"`` and an ``error`` text. Turns run one at a time.

Ops: ``hello``; ``feed`` (``text``, optionally ``fuel``, ``who``,
``at``, ``head``); ``replay``; ``log``; ``show``; ``rewind``
(``event``); ``watch``, after which every feed of any client is pushed
to this connection as an ``event`` object; ``stop``.

The design is docs 02.05.14. Exit status: 0 when the kernel stopped or
another one already serves the socket, 2 for refused argv.
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
from fpl.errors import FAIL
from fpl.log import U64, Log, keyed, load
from fpl.repl import Said, inputs, once

#: Marks a result line: the prefix, then a space or the end of the line.
#: Written after the input that printed it, dropped by
#: :func:`swallowed`.
RESULT = "|="
#: Maps each key of a feed's ``who`` to the environment variable the
#: REPL reads it from.
WHO = {"model": "FPL_MODEL", "session": "FPL_SESSION_ID"}
#: Seconds :meth:`Outbox.close` waits for a client that does not read.
PATIENCE = 2.0
#: Messages one connection may have queued before :meth:`Outbox.push`
#: drops it.
BACKLOG = 64
#: A session name: what ``--name`` must match in full.
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
#: A function that delivers one message to a connection.
Sender = Callable[[dict[str, Any]], None]
#: A decoded request object.
Request = Mapping[str, Any]


def swallowed(text: str) -> str:
    r"""Drop the result lines and the fail lines of *text*.

    A transcript fed back in is then the program it came from. The
    results are not checked against a run.

    Examples:
        >>> swallowed("1\n|= 1\n|=\n|=x\n")
        '1\n|=x\n'
        >>> swallowed("x\n|- ! err/no-row 1:1 “m”\n")
        'x\n'
    """
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not (
            line.startswith((RESULT + " ", FAIL + " "))
            or line.rstrip("\n") == RESULT
        )
    )


def split(text: str) -> list[str]:
    r"""Split *text* into inputs, grouped as the REPL groups lines.

    Result and fail lines are dropped first, as in :func:`swallowed`.

    Examples:
        >>> split("(a)\n(b)\n|= 3\n")
        ['(a)\n', '(b)\n']
    """
    lines = iter(swallowed(text).splitlines())
    return list(inputs(lambda _on: next(lines, None)))


@dataclass(frozen=True)
class Turn:
    """One input and what it left."""

    #: The input as entered.
    text: str
    #: Its stdout.
    out: str
    #: Its notes.
    notes: tuple[str, ...]
    #: Exit status: 0 ok, 1 failed, 2 refused.
    code: int
    #: Steps taken, or ``None`` if it ran none.
    spent: int | None
    #: Wall time in milliseconds.
    ms: float

    def block(self) -> str:
        r"""Render the input, then its output and notes, as text.

        Returns:
            The input as entered, its output as ``|=`` lines and its
            notes as ``;;`` comments, each line ending in a newline. A
            turn that failed has no output but its fail line, which
            stands as it is: ``|-`` is the turnstile, ``|=`` before it
            would be a result of the failure.

        Examples:
            >>> Turn("1", " 2\n", ("n",), 0, None, 0.0).block()
            '1\n|=  2\n;; n\n'
            >>> fail = "|- ! err 1:1 “m”\n"
            >>> Turn("x", fail, (), 1, None, 0.0).block()
            'x\n|- ! err 1:1 “m”\n'
        """
        lines = self.out.splitlines()
        shown = (
            lines
            if self.code
            else [f"{RESULT} {line}".rstrip() for line in lines]
        )
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
    """Build the :func:`fpl.repl.once` argv an input stands for.

    ``:log``, ``:show`` and ``:rewind N`` become ``--log``, ``--show``
    and ``--rewind N``, as the REPL loop reads them; any other input is
    passed as ``-e``.

    Args:
        session: The session's log path.
        fuel: The step budget.
        text: The input.
        heads: The ``--at`` and ``--head`` arguments the call carries.

    Examples:
        >>> argv_of(Path("s"), 5, ":rewind 3", ["--at", "x"])
        ['--session', 's', '--fuel', '5', '--at', 'x', '--rewind', '3']
        >>> argv_of(Path("s"), 5, "(+ 1 2)", [])
        ['--session', 's', '--fuel', '5', '-e', '(+ 1 2)']
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
    """Make the :class:`Turn` of *text* from what the REPL call said."""
    return Turn(text, told.out, told.notes, told.code, told.spent, ms)


def replayed(log: Log) -> str:
    """Render the whole *log* as a transcript.

    Each input is followed by its output; a rewind is the ``:rewind N``
    that makes it. Feeding the transcript to a fresh session walks the
    same inputs.
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
    """A kernel's state: the session log, fuel, environment, watchers.

    Turns run one at a time under ``lock``.
    """

    def __init__(
        self,
        name: str,
        log: Path,
        fuel: int,
        env: Mapping[str, str],
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        """Hold a session's state; *env* loses the :data:`WHO` names.

        Args:
            name: The session name.
            log: The session's log path.
            fuel: The default step budget of a feed.
            env: The environment the REPL runs under.
            clock: The time source for :attr:`Turn.ms`.
        """
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
        """Carry out one input; a REPL refusal is code 2 in the turn.

        Args:
            text: The input.
            fuel: The step budget.
            env: The environment the REPL runs under.
            heads: The ``--at`` and ``--head`` arguments, from
                :meth:`heads`.
        """
        started = self.clock()
        told = once(argv_of(self.log, fuel, text, heads), env)
        return turned(told, text, (self.clock() - started) * 1000.0)

    @staticmethod
    def heads(request: Request, n: int) -> list[str]:
        """Build the head arguments for input *n* of a feed.

        The read head ``at``, if the request names one, goes to every
        input. The write head ``head``, if it names one, goes to the
        first input only, since an append moves it.

        Examples:
            >>> Kernel.heads({"at": "a", "head": "h"}, 0)
            ['--at', 'a', '--head', 'h']
            >>> Kernel.heads({"at": "a", "head": "h"}, 1)
            ['--at', 'a']
        """
        at, head = request.get("at"), request.get("head")
        return [
            *(["--at", at] if at is not None else []),
            *(["--head", head] if head is not None and n == 0 else []),
        ]

    def fed(self, request: Request) -> dict[str, Any]:
        """Enter the inputs of the request's ``text`` one after another.

        Every watcher is sent a ``feed`` event with the answer; a
        watcher that fails is removed.

        Returns:
            The ``turns`` as dicts and their ``transcript``.
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
        """Run a REPL call that appends nothing, or a rewind.

        Returns:
            The call's ``out`` and ``code``.
        """
        with self.lock:
            told = once(["--session", str(self.log), *argv], self.env)
        return {"out": told.out, "code": told.code}

    def stop(self) -> dict[str, Any]:
        """Ask the server to end.

        The thread of the connection that asked sets ``stopped``
        once its answer is out (see :func:`connection`).
        """
        self.stopper = threading.get_ident()
        return {}

    def hello(self) -> dict[str, Any]:
        """Describe this kernel.

        Returns:
            The ``session`` name, its ``head`` (the number of events in
            the log) and the default ``fuel``.
        """
        with self.lock:
            events = len(load(self.log, keyed(self.env)).events)
        return {"session": self.name, "head": events, "fuel": self.fuel}

    def replay(self) -> dict[str, Any]:
        """Return the :func:`replayed` log under ``transcript``."""
        with self.lock:
            log = load(self.log, keyed(self.env))
        return {"transcript": replayed(log)}

    def answer(self, request: Request, send: Sender) -> dict[str, Any]:
        """Answer a request that is a JSON object.

        Args:
            request: The decoded request.
            send: Delivers messages to the requesting connection; a
                ``watch`` keeps it for later events.

        Returns:
            The response fields, without ``id`` and ``status``.

        Raises:
            ValueError: *request* is not an op this kernel takes, or a
                ``feed`` or ``rewind`` has malformed fields.
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
    """Check the fields of a ``feed`` request.

    Returns:
        True if ``fuel``, when present, is an integer in [0, 2^64), and
        ``who`` (when present) holds text values only, as do ``at`` and
        ``head``.

    Examples:
        >>> fuel_ok({"fuel": 3, "who": {"model": "m"}})
        True
        >>> fuel_ok({"fuel": -1})
        False
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
    """Build the error response to a refused request *ident*.

    Examples:
        >>> failed(1, "x")
        {'id': 1, 'status': 'error', 'error': 'x'}
    """
    return {"id": ident, "status": "error", "error": str(error)}


def response(kernel: Kernel, line: bytes, send: Sender) -> dict[str, Any]:
    """Answer one request line.

    Returns:
        The request's ``id`` and the answer with ``"status": "done"``;
        or ``"status": "error"`` and the reason, for a line that is not
        JSON, not an object, or not a request this kernel takes.
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
    """The messages to one client, written by a thread of its own.

    The queue is bounded by :data:`BACKLOG`. :meth:`push` never waits;
    at the bound it cuts the connection and raises :exc:`queue.Full`, so
    a client that stops reading holds up only itself.
    """

    def __init__(self, conn: socket.socket) -> None:
        """Start the writer thread for *conn*."""
        self.conn = conn
        self.queue: queue.Queue[dict[str, Any] | None] = queue.Queue(BACKLOG)
        self.dead = threading.Event()
        self.thread = threading.Thread(target=self.write, daemon=True)
        self.thread.start()

    def cut(self) -> None:
        """Cut the connection, which ends the threads waiting on it."""
        with contextlib.suppress(OSError):
            self.conn.shutdown(socket.SHUT_RDWR)

    def push(self, message: dict[str, Any]) -> None:
        """Queue *message* without waiting.

        Raises:
            queue.Full: The queue is at :data:`BACKLOG`; the connection
                is cut first.
        """
        try:
            self.queue.put_nowait(message)
        except queue.Full:
            self.cut()
            raise

    def write(self) -> None:
        """Write the queue until the end mark; a client gone ends it."""
        try:
            with self.conn.makefile("wb") as writer:
                while (message := self.queue.get()) is not None:
                    writer.write(json.dumps(message).encode() + b"\n")
                    writer.flush()
        except OSError:
            self.dead.set()

    def say(self, message: dict[str, Any] | None) -> None:
        """Queue *message*, waiting for room, unless the writer quit."""
        while not self.dead.is_set():
            try:
                self.queue.put(message, timeout=0.2)
                return
            except queue.Full:
                continue

    def close(self) -> None:
        """End the queue and give the writer time to empty it.

        The writer gets :data:`PATIENCE` seconds; a client that does
        not read is cut off.
        """
        try:
            self.queue.put(None, timeout=PATIENCE)
        except queue.Full:
            self.cut()
        self.thread.join(PATIENCE)


def connection(kernel: Kernel, conn: socket.socket) -> None:
    """Serve one connection: a response per line until the client goes.

    Also ends when the kernel is asked to stop; ``Kernel.stopped``
    is set once that answer is written.
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
    """Serve *kernel* on a socket at *path* until a client stops it.

    The socket has mode 0600 in a directory only the user may enter, and
    each connection gets a thread. A socket file already at *path* is
    taken to be a dead kernel's and replaced; :func:`lifetime` guards
    against a live one.
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
    """Parse *argv* into the name, log path, socket path and fuel.

    Raises:
        SystemExit: With status 2, for a name outside :data:`NAME` or
            anything else :mod:`argparse` refuses.
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
    """Take the right to be the kernel behind the socket at *path*.

    Holds an exclusive lock on ``<path>.lock`` for the block. The lock
    is dropped with the process, so a kernel that died leaves nothing to
    clear.

    Yields:
        True if the lock was taken, False if another kernel holds it.
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
    """Serve the session in *argv*, unless a kernel already does.

    Returns:
        0.

    Raises:
        SystemExit: With status 2, from :func:`names`.
    """
    name, log, path, fuel = names(argv)
    with lifetime(path) as mine:
        if mine:
            serve(Kernel(name, log, fuel, env), path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

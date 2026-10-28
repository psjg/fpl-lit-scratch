"""Store a session's events as canonical FON records, one per line.

An :class:`Event` (an input or a rewind) is named by the blake2b-256 of
its header bytes, :attr:`Event.ident`; its record also carries a keyed
blake2b of that id, :func:`mac` (HOLES.md: log-signing). :func:`load`
reads a session file back, :func:`write` appends to it under
:func:`locked`, and :func:`keyed` supplies the key.
"""

import contextlib
import fcntl
import hashlib
import hmac
import os
import re
import secrets
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from typing import Literal

from fpl import fon
from fpl.errors import FplError
from fpl.fon import Cell, Dict, Hash, List, Num, Str, Sym, Value
from fpl.multihash import INLINE, Multihash, content, hashed, spelling

#: What an event is: an input, or a rewind to an earlier event.
type Kind = Literal["input", "rewind"]
#: How the event's run ended.
type Status = Literal["ok", "error"]
#: Who entered the event.
type Who = Literal["agent", "operator"]

#: The record schema version; :func:`parsed` refuses any other.
SCHEMA = 1
#: The values a record's ``kind`` may take.
KINDS: tuple[Kind, ...] = ("input", "rewind")
#: The values a record's ``status`` may take.
STATUSES: tuple[Status, ...] = ("ok", "error")
#: The values a record's ``who`` may take.
WHO: tuple[Who, ...] = ("agent", "operator")
#: The fifteen record keys in the order a record writes them: the
#: thirteen header fields, then ``id`` and ``mac``.
FIELDS = (
    "schema",
    "evaluator",
    "kind",
    "seq",
    "deps",
    "links",
    "body",
    "out",
    "status",
    "who",
    "model",
    "session",
    "fuel",
    "id",
    "mac",
)
#: :data:`FIELDS` as FON symbols.
KEYS = tuple(Sym(name) for name in FIELDS)
#: The text a ``model`` or ``session`` may hold: 0 to 256 printable
#: ASCII characters.
ASCII = re.compile(r"[\x20-\x7e]{0,256}")
#: The bound of every number in a record: it must be below 2^64.
U64 = 1 << 64


class RefusedError(Exception):
    """A record, log file or append was refused; nothing is written."""


def u64(n: int) -> bytes:
    """Return *n* as eight big-endian bytes.

    Raises:
        OverflowError: *n* is negative or 2^64 or more.

    Examples:
        >>> u64(258).hex()
        '0000000000000102'
        >>> u64(1 << 64)
        Traceback (most recent call last):
            ...
        OverflowError: int too big to convert
    """
    return n.to_bytes(8, "big")


def prefixed(data: bytes) -> bytes:
    """Return *data* after its length, as eight big-endian bytes.

    Examples:
        >>> prefixed(b"ab").hex()
        '00000000000000026162'
    """
    return u64(len(data)) + data


def _joined(ids: tuple[Multihash, ...]) -> bytes:
    """Return the raw multihashes, each length-prefixed."""
    return b"".join(prefixed(each.raw()) for each in ids)


@dataclass(frozen=True)
class Event:
    """One step of a session: an input or a rewind.

    An input has *body* as its text and *out* as its output. *deps*
    names the event whose state this one extends, *links* the head it
    abandons; *fuel* is the step budget each run line had.
    """

    #: The record schema version, :data:`SCHEMA`.
    schema: int
    #: The evaluator the event ran under.
    evaluator: Multihash
    #: Whether this is an input or a rewind.
    kind: Kind
    #: The event's position in the log, counting from 1.
    seq: int
    #: The events whose state this one extends: none or one.
    deps: tuple[Multihash, ...]
    #: The head a rewind abandons; empty for an input.
    links: tuple[Multihash, ...]
    #: The ``&`` of the input text.
    body: Multihash
    #: The ``&`` of the output text.
    out: Multihash
    #: How the run ended.
    status: Status
    #: Who entered the event.
    who: Who
    #: The model that entered it; printable ASCII.
    model: str
    #: The session it belongs to; printable ASCII.
    session: str
    #: The step budget of each run line.
    fuel: int

    def header(self) -> bytes:
        """Return the preimage of the event's id.

        The preimage is the thirteen fields in order, each
        length-prefixed. Numbers are eight big-endian bytes, multihashes
        raw, *deps* and *links* a length-prefixed run of raw
        multihashes, and text ASCII.

        Raises:
            OverflowError: A number is negative or 2^64 or more (from
                :func:`u64`).
            UnicodeEncodeError: *model* or *session* is not ASCII.
        """
        fields = (
            u64(self.schema),
            self.evaluator.raw(),
            self.kind.encode(),
            u64(self.seq),
            _joined(self.deps),
            _joined(self.links),
            self.body.raw(),
            self.out.raw(),
            self.status.encode(),
            self.who.encode(),
            self.model.encode("ascii"),
            self.session.encode("ascii"),
            u64(self.fuel),
        )
        return b"".join(prefixed(field) for field in fields)

    @cached_property
    def ident(self) -> Multihash:
        """The event's ``$``: the blake2b-256 of :meth:`header`.

        It has no domain tag, as ``$`` is ``&`` applied to the log.
        """
        return hashed(self.header())


def mac(ident: Multihash, key: bytes) -> Multihash:
    """Return the keyed blake2b-256 of an id, 32 bytes held inline.

    It lies outside the preimage of the id, so a signature can replace
    it without renaming history.
    """
    return content(
        hashlib.blake2b(ident.raw(), digest_size=32, key=key).digest()
    )


def record(event: Event, key: bytes) -> bytes:
    """Return *event* as one canonical FON dict and a newline, in ASCII.

    The dict holds the fields in header order, then ``id`` and ``mac``,
    and is written as ``dict/15``.

    Args:
        event: The event to write.
        key: The key for :func:`mac`.

    Raises:
        OverflowError: A number of *event* is negative or 2^64 or more
            (from :meth:`Event.header` through :attr:`Event.ident`).
        UnicodeEncodeError: *model* or *session* is not ASCII
            (likewise).
    """
    values: tuple[Value, ...] = (
        Num(Decimal(event.schema)),
        Hash(event.evaluator),
        Sym(event.kind),
        Num(Decimal(event.seq)),
        List(tuple(map(Cell, event.deps))),
        List(tuple(map(Cell, event.links))),
        Hash(event.body),
        Hash(event.out),
        Sym(event.status),
        Sym(event.who),
        Str(event.model),
        Str(event.session),
        Num(Decimal(event.fuel)),
        Cell(event.ident),
        Hash(mac(event.ident, key)),
    )
    return (
        fon.write(Dict(tuple(zip(KEYS, values, strict=True)))) + "\n"
    ).encode()


def _fields(line: bytes) -> dict[str, Value]:
    """Return the values of a record's fifteen keys, in their order.

    Raises:
        RefusedError: *line* is not UTF-8 or not FON,
            or its keys differ from :data:`FIELDS`.
    """
    try:
        value = fon.read(line.decode())
    except UnicodeDecodeError:
        raise RefusedError("not UTF-8") from None
    except FplError as error:
        raise RefusedError(
            f"{error.span.line}:{error.span.col} {error.message}"
        ) from None
    if (
        not isinstance(value, Dict)
        or tuple(key for key, _ in value.entries) != KEYS
    ):
        raise RefusedError("fields differ from " + " ".join(FIELDS))
    return {
        name: item
        for name, (_, item) in zip(FIELDS, value.entries, strict=True)
    }


def _number(fields: dict[str, Value], name: str) -> int:
    """Return a whole number below 2^64.

    Raises:
        RefusedError: The value is not such a number.
    """
    value = fields[name]
    if (
        isinstance(value, Num)
        and value.value % 1 == 0
        and 0 <= value.value < U64
    ):
        return int(value.value)
    raise RefusedError(f"{name} is not a number below 2^64")


def _hash(fields: dict[str, Value], name: str) -> Multihash:
    """Return a ``&``.

    Raises:
        RefusedError: The value is not a ``&``.
    """
    value = fields[name]
    if isinstance(value, Hash):
        return value.ref
    raise RefusedError(f"{name} is not a hash")


def _identity(value: Value, what: str) -> Multihash:
    """Return a ``$`` that names by hash.

    Raises:
        RefusedError: *value* is not such a ``$``.
    """
    if isinstance(value, Cell) and isinstance(value.name, Multihash):
        return value.name
    raise RefusedError(f"{what} is not an identity")


def _identities(fields: dict[str, Value], name: str) -> tuple[Multihash, ...]:
    """Return a list of ``$`` that name by hash.

    Raises:
        RefusedError: The value is not a list or an item is not
            such a ``$`` (from :func:`_identity`).
    """
    value = fields[name]
    if not isinstance(value, List):
        raise RefusedError(f"{name} is not a list")
    return tuple(_identity(item, f"an item of {name}") for item in value.items)


def _choice[T: str](
    fields: dict[str, Value], name: str, choices: tuple[T, ...]
) -> T:
    """Return the one of *choices* that the symbol spells.

    Raises:
        RefusedError: The value is none of *choices*.
    """
    for choice in choices:
        if fields[name] == Sym(choice):
            return choice
    raise RefusedError(f"{name} is not one of {' '.join(choices)}")


def _text(fields: dict[str, Value], name: str) -> str:
    """Return printable ASCII of at most 256 characters.

    Raises:
        RefusedError: The value is not such a string.
    """
    value = fields[name]
    if isinstance(value, Str) and ASCII.fullmatch(value.text):
        return value.text
    raise RefusedError(
        f"{name} is not printable ASCII of at most 256 characters"
    )


def _event(fields: dict[str, Value]) -> Event:
    """Return the event that the thirteen header fields spell.

    Raises:
        RefusedError: A field has the wrong kind or is out of range
            (from the field readers).
    """
    return Event(
        schema=_number(fields, "schema"),
        evaluator=_hash(fields, "evaluator"),
        kind=_choice(fields, "kind", KINDS),
        seq=_number(fields, "seq"),
        deps=_identities(fields, "deps"),
        links=_identities(fields, "links"),
        body=_hash(fields, "body"),
        out=_hash(fields, "out"),
        status=_choice(fields, "status", STATUSES),
        who=_choice(fields, "who", WHO),
        model=_text(fields, "model"),
        session=_text(fields, "session"),
        fuel=_number(fields, "fuel"),
    )


def parsed(line: bytes, key: bytes) -> Event:
    """Return the event that a record spells.

    Args:
        line: The record without its newline.
        key: The key the record's mac must verify under.

    Raises:
        RefusedError: *line* is not UTF-8 or not FON, its keys are not
            the fifteen in order, or a value has the wrong kind or is
            out of range (from :func:`_fields` and :func:`_event`); the
            schema is not :data:`SCHEMA`; the id does not recompute; the
            mac does not verify under *key*; or the spelling is not the
            one :func:`record` writes. The reason carries no position.
    """
    fields = _fields(line)
    event = _event(fields)
    if event.schema != SCHEMA:
        raise RefusedError(f"schema {event.schema} is unknown")
    if _identity(fields["id"], "id") != event.ident:
        raise RefusedError("id does not recompute")
    if not hmac.compare_digest(
        _hash(fields, "mac").raw(), mac(event.ident, key).raw()
    ):
        raise RefusedError("mac does not verify")
    if record(event, key) != line + b"\n":
        raise RefusedError("not canonical")
    return event


@dataclass(frozen=True)
class Log:
    """A session file's events, their bodies' bytes, and its size.

    Every body and output that the events name has its bytes in
    *bodies*. *size* is the size of the file's complete records; a torn
    tail lies beyond it.
    """

    #: The events in file order.
    events: tuple[Event, ...]
    #: The bytes of every body and output the events name.
    bodies: Mapping[Multihash, bytes]
    #: The size in bytes of the complete records in the file.
    size: int

    @property
    def head(self) -> Event | None:
        """The last event, or ``None`` before the first."""
        return self.events[-1] if self.events else None

    def grown(
        self, event: Event, bodies: Mapping[Multihash, bytes], size: int
    ) -> "Log":
        """Return the log with one more event, its bodies, a new size.

        Args:
            event: The event to add at the end.
            bodies: The bytes of its body and output.
            size: The file's size after the event's record.
        """
        return Log((*self.events, event), {**self.bodies, **bodies}, size)


def _follows(idents: set[Multihash], event: Event) -> None:
    """Refuse an event that cannot come next after the events *idents*.

    An event is refused if its seq is not the next one, if it names an
    event that is not in *idents*, if it names one event both as its
    state and as the head it abandons, or if it has more deps or links
    than its kind allows: an input has at most one dep and no link, a
    rewind at most one dep and one link.

    Raises:
        RefusedError: On each of those conditions.
    """
    if event.seq != len(idents) + 1:
        raise RefusedError(f"seq {event.seq} is not {len(idents) + 1}")
    if not idents.issuperset(event.deps + event.links):
        raise RefusedError("names no earlier event")
    if set(event.deps) & set(event.links):
        raise RefusedError("deps and links overlap")
    links = 1 if event.kind == "rewind" else 0
    if len(event.deps) > 1 or len(event.links) != links:
        raise RefusedError(
            f"{event.kind} has deps {len(event.deps)} "
            f"and links {len(event.links)}"
        )


def _store(path: Path) -> Path:
    """Return the directory beside the log holding long bodies.

    Bodies of more than 32 bytes are kept there.
    """
    return Path(f"{path}.bodies")


def _stored(path: Path, name: Multihash) -> bytes | None:
    """Return the bytes *name* holds inline or the store keeps.

    Returns:
        The bytes, or ``None`` if the store has no file for *name*.
    """
    if name.code == INLINE:
        return name.digest
    try:
        return (_store(path) / name.spelled()).read_bytes()
    except FileNotFoundError:
        return None


def _bodies(
    path: Path, event: Event, given: Mapping[Multihash, bytes]
) -> dict[Multihash, bytes]:
    """Return the bytes of the event's body and output.

    They come from *given* or else the store. Each must be exactly the
    bytes its name promises, with one ``&`` per byte string: a hashed
    name for bytes that fit inline is refused too.

    Raises:
        RefusedError: A body is missing or does not hash to its
            name.
    """
    found: dict[Multihash, bytes] = {}
    for name in (event.body, event.out):
        data = given[name] if name in given else _stored(path, name)
        if data is None:
            raise RefusedError(f"body {name.spelled()} is missing")
        if content(data) != name:
            raise RefusedError(
                f"body {name.spelled()} does not hash to its name"
            )
        found[name] = data
    return found


def load(path: Path, key: bytes) -> Log:
    """Return the log that the session file at *path* holds.

    A missing file is the empty log. Records end in a newline, so bytes
    after the last newline are a torn append and are dropped. Readers
    take no lock.

    Args:
        path: The session file.
        key: The key every record's mac must verify under.

    Raises:
        RefusedError: Record *n* is refused as ``<path>:<n> <reason>``
            for anything :func:`parsed` refuses, a seq other than *n*, a
            dep or link that names no earlier event, deps and links that
            overlap, more deps or links than the kind allows, or a body
            that is missing or is not the bytes its name promises.
        OSError: The file exists but cannot be read.
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return Log((), {}, 0)
    complete, newline, _ = data.rpartition(b"\n")
    events: list[Event] = []
    idents: set[Multihash] = set()
    bodies: dict[Multihash, bytes] = {}
    for n, line in enumerate(complete.split(b"\n") if newline else [], 1):
        try:
            event = parsed(line, key)
            _follows(idents, event)
            bodies.update(_bodies(path, event, {}))
        except RefusedError as error:
            raise RefusedError(f"{path}:{n} {error}") from None
        events.append(event)
        idents.add(event.ident)
    return Log(tuple(events), bodies, len(complete) + len(newline))


def _ident(name: str) -> Multihash | None:
    """Return the id that *name* spells after an optional ``$``.

    The id is in decimal or a hex multihash; ``None`` if *name* spells
    none.
    """
    try:
        return spelling(name.removeprefix("$"), inline=False)
    except ValueError:
        return None


def resolve(log: Log, name: str) -> Event | None:
    """Return the event that an operator's *name* picks out of *log*.

    ``0`` is the origin, which is ``None``; a seq is read as written;
    any other name is read as an id.

    Raises:
        RefusedError: No event of *log* answers to *name*.
    """
    if name == "0":
        return None
    ident = _ident(name)
    for event in log.events:
        if name == str(event.seq) or event.ident == ident:
            return event
    raise RefusedError(f"no event {name}")


def _written(fd: int, data: bytes) -> None:
    """Write all of *data* to *fd* in one call.

    Raises:
        OSError: The write is short or fails.
    """
    if os.write(fd, data) != len(data):
        raise OSError(f"short write of {len(data)} bytes")


def _synced(directory: Path) -> None:
    """Make the entries of *directory* durable."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _kept(store: Path, name: Multihash, data: bytes) -> None:
    """Make *data* durable in *store* under *name*, whole or not at all.

    A store made here has its own entry synced too, so a record that
    names a body in it never outlives the store.
    """
    with contextlib.suppress(FileExistsError):
        store.mkdir(mode=0o700)
        _synced(store.parent)
    temporary = store / f".{name.spelled()}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        _written(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, store / name.spelled())
    _synced(store)


def _recorded(event: Event, key: bytes) -> bytes:
    """Return the event's record, refusing one that cannot be read back.

    Raises:
        RefusedError: A number is 2^64 or more or a model or session is
            not ASCII, so that no record can spell it; or the record is
            one :func:`parsed` would not read back.
    """
    try:
        line = record(event, key)
    except (OverflowError, UnicodeEncodeError):
        raise RefusedError(
            "a number is not below 2^64 or a text is not ASCII"
        ) from None
    parsed(line.removesuffix(b"\n"), key)
    return line


def write(
    path: Path,
    key: bytes,
    log: Log,
    event: Event,
    bodies: Mapping[Multihash, bytes],
) -> Log:
    """Return *log* after appending *event* to the file at *path*.

    The caller holds :func:`locked` on *path* and loaded *log* under it.
    Bodies are made durable first, so a reader never meets a record
    whose body is missing. Then any torn tail past ``log.size`` is cut,
    the record is appended in one write, and file and directory are
    synced before this returns (HOLES.md: log-fsync-barrier).

    Args:
        path: The session file.
        key: The key for :func:`mac`.
        log: The log as loaded from *path*.
        event: The event to append.
        bodies: The bytes of the event's body and output, unless already
            stored.

    Raises:
        RefusedError: *event* is one :func:`load` would refuse after
            *log*; nothing is written then.
        OSError: A file or directory operation fails.
    """
    _follows({each.ident for each in log.events}, event)
    line = _recorded(event, key)
    found = _bodies(path, event, bodies)
    for name, data in found.items():
        if name.code != INLINE and name in bodies:
            _kept(_store(path), name, data)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.ftruncate(fd, log.size)
        _written(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)
    _synced(path.parent)
    return log.grown(event, found, log.size + len(line))


@contextlib.contextmanager
def locked(path: Path) -> Generator[None]:
    """Hold an exclusive lock on the session at *path* for the block.

    The lock is a blocking ``flock`` on ``<path>.lock`` through a
    descriptor of its own, so threads exclude one another too.

    Raises:
        OSError: The lock file cannot be opened.
    """
    fd = os.open(f"{path}.lock", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _key_file(env: Mapping[str, str]) -> Path:
    """Return the key file named by ``$FPL_LOG_KEY``, else XDG's.

    The order is ``$FPL_LOG_KEY``, then
    ``$XDG_CONFIG_HOME/fpl/log.key``, then
    ``$HOME/.config/fpl/log.key``.

    Raises:
        RefusedError: None of the three variables is set.
    """
    if env.get("FPL_LOG_KEY"):
        return Path(env["FPL_LOG_KEY"])
    if env.get("XDG_CONFIG_HOME"):
        return Path(env["XDG_CONFIG_HOME"], "fpl", "log.key")
    if env.get("HOME"):
        return Path(env["HOME"], ".config", "fpl", "log.key")
    raise RefusedError(
        "no key file: $FPL_LOG_KEY, $XDG_CONFIG_HOME and $HOME are unset"
    )


def _made(directory: Path, mode: int) -> None:
    """Make *directory* and its missing ancestors, from the top down.

    Ancestors get the default mode and *directory* gets *mode*. Each
    entry is synced into its parent before the next directory is made
    under it. The deepest directory found made, before the loop or
    inside it, has its entry synced all the same, as a racing maker may
    not have run that sync yet. The directories above it need none, as
    such a maker synced each before it made the next under it.
    """
    missing: list[Path] = []
    while not directory.exists():
        missing.append(directory)
        directory = directory.parent
    _synced(directory.parent)
    for made in reversed(missing):
        with contextlib.suppress(FileExistsError):
            made.mkdir(mode=mode if made == missing[0] else 0o777)
        _synced(made.parent)


def keyed(env: Mapping[str, str]) -> bytes:
    """Return the key that macs this operator's records.

    The key is made on first use as 32 random bytes in a file only its
    owner may read, in a directory only its owner may enter. Each
    directory made on the way, and the deepest one found, has its entry
    synced into its parent. The file's bytes, once read, and its entry
    in its directory are synced before the key is used, whether made
    here or found made by a racing maker whose own sync may not have
    run, so no record outlives the key that macs it. The bytes are read
    before their sync, so none read can have been written after it.

    Args:
        env: The environment that locates the key file, as in
            :func:`_key_file`.

    Raises:
        RefusedError: No key file location is set; the key file can be
            read or written by others or is not 32 bytes long. A reader
            racing the first maker may meet the file empty and be
            refused.
        OSError: A file or directory operation fails.
    """
    path = _key_file(env)
    _made(path.parent, 0o700)
    with contextlib.suppress(FileExistsError):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _written(fd, secrets.token_bytes(32))
        finally:
            os.close(fd)
    with path.open("rb") as file:
        if os.fstat(file.fileno()).st_mode & 0o077:
            raise RefusedError(f"{path} is open to others")
        key = file.read()
        os.fsync(file.fileno())
    _synced(path.parent)
    if len(key) != 32:
        raise RefusedError(f"{path} holds {len(key)} bytes, not 32")
    return key

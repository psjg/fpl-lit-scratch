"""Desugar surface syntax into core syntax, and resugar core back.

:func:`desugar` turns a parsed :class:`~fpl.ast_surface.Program` into
core :class:`~fpl.ast_core.Statement` values: definitions with their
code, and lines to run. Frames and bars, sections, strands, blocks,
directories, ``match`` rows and dispatch on several keys or typed inputs
are resolved there into plain nodes. :func:`resugar` writes core back as
source that desugars to the same code, and :func:`listing` writes stacks
as a program, both for the printer.
"""

from collections import ChainMap
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from decimal import Decimal
from functools import partial
from itertools import combinations, groupby
from typing import NoReturn, assert_never

from fpl import trivia
from fpl.ast_core import (
    DIGITS,
    EFFECTS,
    ONE_VALUE,
    PLANNED,
    Atom,
    Bind,
    Call,
    Define,
    Dict,
    Effect,
    Equal,
    Guarded,
    Inverse,
    Judgment,
    Keyed,
    Listed,
    Match,
    Node,
    Number,
    Pattern,
    Push,
    Quotation,
    Refuse,
    Row,
    Run,
    Slot,
    Statement,
    Strand,
    Symbol,
    Value,
    Var,
    Wild,
)
from fpl.ast_surface import (
    Cell,
    Comment,
    Enclosure,
    Frame,
    Item,
    Line,
    Program,
    Text,
    Word,
)
from fpl.errors import (
    AmbiguousClauseError,
    AmbiguousQueryError,
    CheckFormError,
    ClauseError,
    DictError,
    MatchError,
    NoEvaluatorError,
    NotInvertibleError,
    PatternError,
    PrintError,
    RowError,
    Span,
    TooLongError,
    UnknownWordError,
    UnresolvedError,
)
from fpl.print import render

#: Where a refusal without a position of its own is reported: the
#: source's start.
START = Span(1, 1)
#: The sigils that name the top of the stack for the rest of a line.
ARROWS = ("→", "->")
#: The effect of a bound name: it takes nothing and leaves one value.
LOCAL = Effect((), ("x",))
#: The effect of the ``history`` query of a word: it leaves its log.
HISTORY = Effect((), ("h",))
#: The effect of the ``doc`` query of a word: it leaves its docstring.
DOC = Effect((), ("d",))
#: The queries every word answers, with their effects.
QUERIES = {"history": HISTORY, "doc": DOC, "effect": Effect((), ("e",))}
#: The mark between a generated name and the position it is made for.
PRIME = "\N{PRIME}"
#: The refusal of a check that starts with ``!`` but is no judgment.
JUDGMENT = "a fail judgment is ! err/<tag> “message”"
#: The builtin type words, unless the program defines a word of that
#: name.
TYPES = frozenset(("Int", "Decimal", "Text", "Symbol"))

#: The path of a directory, one name per level.
type Here = tuple[str, ...]
#: The type of one input, None where it is untyped.
type Part = str | None
#: A definition's key: the type or kind of each of its inputs.
type Key = tuple[Part, ...]
#: The effect of a definition's head, and the position of the head.
type Head = tuple[Effect, Span]
#: Two clause ordinals of one arity group.
type Pair = tuple[int, int]
#: The path of a clause word and its effect.
type Clause = tuple[str, Effect]


def unimplemented() -> NoReturn:
    """Refuse what no part implements yet, at the source's start.

    Raises:
        :exc:`~fpl.errors.NoEvaluatorError`: Always, at :data:`START`,
            with the message ``no evaluator yet``.
    """
    raise NoEvaluatorError(START, "no evaluator yet")


def missing(word: Word, directory: bool) -> UnresolvedError:
    """Build the refusal for a call that nothing answers.

    The message names the word as written: ``unknown word: w``, but ``no
    evaluator yet: w`` where the word names a directory, which is not
    called, or is a word the language's examples call
    (:data:`~fpl.ast_core.PLANNED`).

    Args:
        word: The call that nothing answers.
        directory: Whether *word* names a directory.

    Returns:
        A :exc:`~fpl.errors.NoEvaluatorError` or an
        :exc:`~fpl.errors.UnknownWordError` at *word*, for the caller to
        raise.
    """
    name = "/".join(word.body)
    spelled = f"{word.prefix}{name}"
    if directory or name in PLANNED:
        return NoEvaluatorError(word.span, f"no evaluator yet: {spelled}")
    return UnknownWordError(word.span, f"unknown word: {spelled}")


def desugar(program: Program) -> tuple[Statement, ...]:
    r"""Desugar a program into statements, in order.

    A directory's definitions are named by path. Every effect is known
    before any line is read, so a word may be used above its definition;
    a later definition shadows an earlier one.

    Returns:
        One :class:`~fpl.ast_core.Define` per definition, with the
        dispatchers and group tests it makes, and one
        :class:`~fpl.ast_core.Run` per top-level line to run.

    Raises:
        :exc:`FplError`: A line is refused: it uses what nothing
            implements yet, or its clauses conflict
            (:meth:`Catalog.keyed`, :meth:`Catalog.settle`).
        :exc:`~fpl.errors.UnresolvedError`: A call names a word that
            nothing defines.
        :exc:`FplError`: A check ``L |- R`` stands elsewhere than on a
            run line at the top (``a check is a run line``), or a fail
            judgment is left in (``a fail judgment closes the program``;
            :func:`closing` takes the closing one out first).

    Examples:
        >>> from fpl.parse import parse
        >>> program = parse("sq : x -- y\n\tdup +\n")
        >>> [type(s).__name__ for s in desugar(program)]
        ['Define']
        >>> desugar(parse("frob\n"))
        Traceback (most recent call last):
            ...
        fpl.errors.UnknownWordError: ERROR: 1:1 unknown word: frob
    """
    lines = coded(program.lines)
    catalog = Catalog({(): list(EFFECTS)}, dict(EFFECTS))
    catalog.enter(lines, ())
    catalog.settle()
    for here, log in catalog.logs.items():
        for entry in log:
            if isinstance(entry, Mount):
                catalog.directory(here, entry.name)
    return tuple(
        _Desugar(catalog, trivia.docstrings(program)).statements(lines, ())
    )


@dataclass(frozen=True)
class Mount:
    """A ``#name bind`` line.

    It names a directory, as seen from the directory that binds it.
    """

    #: The directory bound, as named in the directory that binds it.
    name: str


@dataclass
class Catalog:
    """The directory logs and word effects, known before desugaring.

    A word is a directory too, holding its history. Each directory keeps
    an ordered log of its definitions, subdirectories and ``#name bind``
    mounts, where a later entry shadows an earlier one.
    """

    #: Each directory's log by path: its entries in order, as names and
    #: mounts.
    logs: dict[Here, list[str | Mount]]
    #: The effect of every word, by its path joined with ``/``.
    effects: dict[str, Effect]
    #: Each word's heads by key, in the order first written.
    heads: dict[str, dict[Key, Head]] = field(
        default_factory=dict[str, dict[Key, Head]]
    )
    #: Each dispatched word's arities, in ascending order.
    groups: dict[str, tuple[int, ...]] = field(
        default_factory=dict[str, tuple[int, ...]]
    )
    #: The queries that answer at another path: the path asked, then the
    #: path that answers.
    aliases: dict[str, str] = field(default_factory=dict[str, str])
    #: The queries that are refused, with the message of the refusal.
    refused: dict[str, str] = field(default_factory=dict[str, str])
    #: Per arity group, the pairs of clauses (by ordinal) that cross
    #: typed two ways at one input.
    crossings: dict[str, list[Pair]] = field(
        default_factory=dict[str, list[Pair]]
    )

    def enter(self, lines: tuple[Line, ...], here: Here) -> None:
        """Log a directory's definitions, subdirectories and mounts.

        Args:
            lines: The lines of the directory that hold code.
            here: The path of the directory.

        Raises:
            :exc:`FplError`: A line in a directory is none of a
                definition, a ``name/`` head and a ``#name bind``; or a
                head is refused (:func:`definition`, :meth:`keyed`).
        """
        log = self.logs.setdefault(here, [])
        for line in lines:
            head, name = definition(line), directory(line)
            if head is not None:
                log.append(head[0])
                self.keyed("/".join((*here, head[0])), head[1], line.span)
                self.queried((*here, head[0]), head[1], [])
            elif name is not None:
                log.append(name)
                self.enter(coded(line.block), (*here, name))
            elif here:
                log.append(Mount(mount(line)))

    def keyed(self, path: str, effect: Effect, span: Span) -> None:
        """Note a definition's head by its key.

        A same key shadows in its place. The head must take the slot
        kinds and leave the number of values of every other key of its
        arity, else it is refused at its head (design 09 §2.3).

        Args:
            path: The word's path.
            effect: The head's effect.
            span: The head's position.

        Raises:
            :exc:`FplError`: The head disagrees with another key of its
                arity (:func:`agree`).
        """
        heads, key = self.heads.setdefault(path, {}), keyed(effect)
        group = [other for other in heads if len(other) == len(key)]
        at = group.index(key) + 1 if key in group else len(group) + 1
        for i, other in enumerate(group, 1):
            if other != key:
                agree(
                    f"{path}/{len(key)}",
                    (at, effect, span),
                    (i, heads[other][0]),
                )
        heads[key] = (effect, span)

    def queried(self, here: Here, effect: Effect, entries: list[str]) -> None:
        """Record a word's effect and its queries.

        The word's log holds *entries*, then the query names.

        Args:
            here: The path of the word.
            effect: The word's effect.
            entries: The log entries that come before the query names.
        """
        path = "/".join(here)
        self.effects[path] = effect
        self.effects |= {f"{path}/{query}": e for query, e in QUERIES.items()}
        self.logs.setdefault(here, []).extend([*entries, *QUERIES])

    def settle(self) -> None:
        """Dispatch each word with two or more keys or a typed input.

        A type word counts as a builtin unless the program defines a
        word of that name.

        Raises:
            :exc:`FplError`: Two clauses of a word are ambiguous
                (:meth:`dispatched`).
        """
        builtins = TYPES - {path.rsplit("/", 1)[-1] for path in self.heads}
        for path, heads in self.heads.items():
            if len(heads) > 1 or any(
                typings(effect) for effect, _ in heads.values()
            ):
                self.dispatched(path, builtins)

    def clauses(self, path: str, n: int) -> list[Head]:
        """Return the heads of a word's arity-*n* clauses by ordinal."""
        return [
            head for key, head in self.heads[path].items() if len(key) == n
        ]

    def ordinal(self, path: str, effect: Effect) -> int:
        """Return the 1-based ordinal of a clause within its arity."""
        key = keyed(effect)
        return [k for k in self.heads[path] if len(k) == len(key)].index(
            key
        ) + 1

    def dispatched(self, path: str, builtins: frozenset[str]) -> None:
        """Set up the ``f/n`` groups and ``f/n/i`` clauses of a word.

        Two clauses whose typed inputs cross are refused unless the
        builtins make them disjoint, or their meet is a clause or is
        typed two ways at one input. The ``doc`` and ``history`` of
        ``f/n`` are its clause's when it has one, and are refused naming
        its clauses otherwise. The queries of ``f`` are those of its
        only group, and are refused naming its groups when it has more.

        Args:
            path: The path of the word ``f``.
            builtins: The builtin type words that the program does not
                define.

        Raises:
            :exc:`FplError`: Two clauses are ambiguous
                (:func:`crossed`).
        """
        here = tuple(path.split("/"))
        groups = {
            len(key): self.clauses(path, len(key)) for key in self.heads[path]
        }
        self.groups[path] = tuple(sorted(groups))
        for n, clauses in groups.items():
            self.crossings[f"{path}/{n}"] = crossed(
                f"{path}/{n}", clauses, builtins
            )
            self.logs[here].append(str(n))
            ordinals = [str(i) for i in range(1, len(clauses) + 1)]
            self.queried(
                (*here, str(n)),
                shared([effect for effect, _ in clauses]),
                ordinals,
            )
            for i, (clause, _) in zip(ordinals, clauses, strict=True):
                self.queried((*here, str(n), i), clause, [])
            self.answered(
                f"{path}/{n}", [f"{path}/{n}/{i}" for i in ordinals], "clause"
            )
        self.effects[path] = self.effects[f"{path}/{self.groups[path][0]}"]
        self.answered(
            path, [f"{path}/{n}" for n in self.groups[path]], "group"
        )

    def answered(self, path: str, parts: list[str], kind: str) -> None:
        """Make the queries of *path* answer as at its one part.

        The ``doc`` and ``history`` of *path*, and at a word its
        ``effect``, answer as at its one part. With more parts they are
        refused, naming the parts.

        Args:
            path: The path asked.
            parts: The paths of its parts.
            kind: What the parts are: ``clause`` (of an arity group,
                which has no ``effect`` query) or ``group`` (of a word).
        """
        queries = ("history", "doc") if kind == "clause" else tuple(QUERIES)
        for query in queries:
            asked = f"{path}/{query}"
            if len(parts) > 1:
                self.refused[asked] = (
                    f"{asked} names more than one {kind}: {' '.join(parts)}"
                )
                continue
            answer = f"{parts[0]}/{query}"
            self.aliases[asked] = self.aliases.get(answer, answer)
            if answer in self.refused:
                self.refused[asked] = self.refused[answer].replace(
                    answer, asked, 1
                )

    def dispatch(self, path: str, balance: int) -> str:
        """Return the path that a call on *balance* values takes.

        For a dispatched word, the arity group: the largest arity the
        balance saturates, else the smallest. For a word that is not
        dispatched, *path* itself.
        """
        groups = self.groups.get(path)
        if groups is None:
            return path
        fits = [n for n in groups if n <= balance]
        return f"{path}/{max(fits, default=groups[0])}"

    def directory(self, here: Here, name: str) -> Here:
        """Return the directory that *name* reaches from *here* outward.

        Raises:
            :exc:`FplError`: No directory of that name is in *here* or
                an enclosing one.
        """
        for depth in range(len(here), -1, -1):
            if (*here[:depth], name) in self.logs:
                return (*here[:depth], name)
        unimplemented()

    def lookup(self, here: Here, segments: Here) -> str | None:
        """Return the word *segments* name in one directory, or None.

        The latest entry of the log that holds it wins.
        """
        for entry in reversed(self.logs.get(here, [])):
            found = self.through(here, entry, segments)
            if found is not None:
                return found
        return None

    def through(
        self, here: Here, entry: str | Mount, segments: Here
    ) -> str | None:
        """Return the word *segments* name through a log entry, or None.

        A subdirectory looks on in its own log. A mount looks only at
        the words its directory defines, so mounts do not chain.
        """
        if isinstance(entry, Mount):
            path = "/".join((*self.directory(here, entry.name), *segments))
            return path if path in self.effects else None
        if entry != segments[0]:
            return None
        if len(segments) > 1:
            return self.lookup((*here, entry), segments[1:])
        path = "/".join((*here, entry))
        return path if path in self.effects else None

    def find(self, here: Here, segments: Here) -> str | None:
        """Return the word that *segments* name from *here*, or None.

        *here* is tried first, then each enclosing directory.
        """
        for depth in range(len(here), -1, -1):
            found = self.lookup(here[:depth], segments)
            if found is not None:
                return found
        return None

    def listed(self, here: Here, segments: Here) -> bool:
        """Tell whether *segments* name a directory from *here*.

        *here* is tried first, then each enclosing directory, and in
        each the directories mounted in it.
        """
        for depth in range(len(here), -1, -1):
            there = here[:depth]
            roots = [there] + [
                self.directory(there, entry.name)
                for entry in self.logs.get(there, [])
                if isinstance(entry, Mount)
            ]
            if any((*root, *segments) in self.logs for root in roots):
                return True
        return False

    def resolve(self, here: Here, segments: Here) -> str:
        """Return the word that *segments* name from *here*, or refuse.

        Raises:
            :exc:`FplError`: No directory from *here* outward holds the
                word.
        """
        found = self.find(here, segments)
        if found is None:
            unimplemented()
        return found


def directory(line: Line) -> str | None:
    """Return the name of a ``name/`` head, or None for any other line.

    Raises:
        :exc:`FplError`: The line is a path head ending in ``/`` that is
            not a lone ``name/`` with a block: a deeper path, or a head
            with no block.
    """
    items = [
        item
        for frame in line.frames
        for cell in frame.cells
        for item in cell.items
    ]
    match items:
        case [Word(prefix="", kind="path", body=(name, ""), mods="")] if (
            line.block
        ):
            return name
        case [Word(kind="path", body=(*_, "")), *_]:
            unimplemented()
        case _:
            return None


def mount(line: Line) -> str:
    """Return the name of a ``#name bind`` line.

    Raises:
        :exc:`FplError`: The line is anything else.
    """
    items = [
        item
        for frame in line.frames
        for cell in frame.cells
        for item in cell.items
    ]
    match items:
        case [Word(prefix="#", kind="name", body=(name,), mods=""), word] if (
            plain(word) == "bind"
        ):
            return name
        case _:
            unimplemented()


def coded(lines: tuple[Line, ...]) -> tuple[Line, ...]:
    """Return the lines that hold code: a bar, or an item in a frame.

    A line with none is a comment's or the empty first line, and heading
    a block it is refused (holes ``comment-heads-block``,
    ``empty-first-line``).

    Raises:
        :exc:`FplError`: A line with no code heads a block.
    """
    kept: list[Line] = []
    for line in lines:
        if trivia.code(line):
            kept.append(line)
        elif line.block:
            unimplemented()
    return tuple(kept)


def unchecked(lines: tuple[Line, ...]) -> None:
    r"""Refuse a check in a block, at any depth.

    Args:
        lines: The lines of a block.

    Raises:
        :exc:`FplError`: A line of *lines* or of a block under one has a
            check (``a check is a run line``).

    Examples:
        >>> from fpl.parse import parse
        >>> unchecked(parse("1\n").lines)
        >>> unchecked(parse("1\n\t2 |- 2\n").lines)
        Traceback (most recent call last):
            ...
        fpl.errors.CheckFormError: ERROR: 2:2 a check is a run line
    """
    for line in lines:
        if line.check is not None:
            raise CheckFormError(line.span, "a check is a run line")
        unchecked(line.block)


def closing(program: Program) -> tuple[Program, Judgment | None]:
    r"""Take the closing fail judgment off a program.

    The judgment is the last line that holds code, when it is
    ``|- ! err/<tag>`` alone. It is taken off before the program is
    desugared, since desugaring may be the failure it judges.

    Args:
        program: The parsed program.

    Returns:
        The program without its judgment line, and the judgment; or the
        program as it is and None.

    Raises:
        :exc:`FplError`: The last line is a malformed judgment
            (:func:`judgment`).

    Examples:
        >>> from fpl.parse import parse
        >>> rest, judged = closing(parse("$x\n|- ! err/no-row\n"))
        >>> len(rest.lines), judged.tag, judged.span.line
        (1, 'err/no-row', 2)
        >>> closing(parse("1 |- 1\n"))[1] is None
        True
    """
    lines = program.lines
    at = max(
        (n for n, line in enumerate(lines) if trivia.code(line)), default=-1
    )
    found = None if at < 0 else judgment(lines[at])
    if found is None or trivia.code(replace(lines[at], check=None)):
        return program, None
    return replace(program, lines=lines[:at] + lines[at + 1 :]), found


def judgment(line: Line) -> Judgment | None:
    r"""Read the check ``|- ! err/<tag> “message”`` as a judgment.

    Args:
        line: A line; only its check is read.

    Returns:
        The judgment, when the check's first item is the word ``!``;
        None for any other line.

    Raises:
        :exc:`FplError`: The check starts with ``!`` but is not one
            frame of one cell, or :func:`verdict` refuses the rest.

    Examples:
        >>> from fpl.parse import parse
        >>> judgment(parse("|- ! err/check “why”\n").lines[0]).message
        'why'
        >>> judgment(parse("|- 1 2\n").lines[0]) is None
        True
    """
    match line.check:
        case (Frame(cells=(Cell(items=(bang, *said)),)),) if (
            plain(bang) == "!"
        ):
            return verdict(said, line.span)
        case (Frame(cells=(Cell(items=(bang, *_)), *_)), *_) if (
            plain(bang) == "!"
        ):
            raise CheckFormError(line.span, JUDGMENT)
        case _:
            return None


def verdict(said: list[Item], span: Span) -> Judgment:
    r"""Read what follows ``!`` in a fail judgment.

    Args:
        said: The items after ``!``: a path under ``err/``, no part of
            it empty, then at most one string, without islands, that the
            error's message must equal.
        span: The judgment's line.

    Raises:
        :exc:`FplError`: The items are anything else.

    Returns:
        The judgment the items spell.

    Examples:
        >>> verdict([], Span(1, 1))  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        fpl.errors.CheckFormError: ERROR: 1:1 a fail judgment is ...
    """
    match said:
        case [
            Word(prefix="", kind="path", body=("err", *_) as path, mods="")
        ] if all(path):
            return Judgment("/".join(path), None, span)
        case [
            Word(prefix="", kind="path", body=("err", *_) as path, mods=""),
            Text(kind="str", parts=(str() as message,)),
        ] if all(path):
            return Judgment("/".join(path), message, span)
        case _:
            raise CheckFormError(span, JUDGMENT)


def definition(line: Line) -> tuple[str, Effect] | None:
    """Return name and effect of a ``name : ins -- outs`` line, or None.

    Raises:
        :exc:`FplError`: The head has a bar or a second cell, or
            :func:`effect_line` refuses it.
    """
    if not trivia.head(line):
        return None
    cells = line.frames[0].cells
    if len(line.frames) + len(cells) > 2:
        unimplemented()
    return effect_line(cells[0].items)


def effect_line(items: tuple[Item, ...]) -> tuple[str, Effect]:
    """Read ``name : ins -- outs``; each is ``name`` or ``name: Type``.

    An output's type is read past.

    Args:
        items: The items of the head, from the name on.

    Returns:
        The word's name and its effect.

    Raises:
        :exc:`FplError`: The name is not plain or there is no ``--``
            (also :func:`typed`).
    """
    name = plain(items[0])
    declared = typed(items[2:])
    names = [pair[0] for pair in declared]
    if name is None or "--" not in names:
        unimplemented()
    cut = names.index("--")
    slots: tuple[Slot, ...] = tuple(kind for _, kind, _ in declared[:cut])
    types = tuple(part for _, _, part in declared[:cut])
    return name, Effect(
        tuple(names[:cut]), tuple(names[cut + 1 :]), slots=slots, types=types
    )


def typed(items: tuple[Item, ...]) -> list[tuple[str, Slot, Part]]:
    """Read each plain name with its slot and type.

    ``name: Type`` has the slot its type makes, and a bare name is an
    untyped value (hole ``bare-slot-names``). A group ``( p )`` is a
    value named ``_``, typed by its spelling.

    Returns:
        A triple of name, slot and type per name, ``--`` included.

    Raises:
        :exc:`FplError`: An item is not a plain name, or is ``∈`` (also
            :func:`slot`).
    """
    declared: list[tuple[str, Slot, Part]] = []
    rest = iter(items)
    for item in rest:
        name = plain(item)
        if isinstance(item, Enclosure) and item.pair == "prefix":
            declared.append(("_", "value", spelt(item)))
        elif name is None or name == "∈":
            unimplemented()
        elif ascribed(item):
            declared.append((name[:-1], *slot(next(rest, None))))
        else:
            declared.append((name, "value", None))
    return declared


def slot(kind: Item | None) -> tuple[Slot, Part]:
    """Return the slot that a type makes (S49 rule 5), and the type.

    ``[ ]`` makes a thunk and ``Code`` code, both untyped; any other
    name makes a value of that type (a word ``x -- b``).

    Raises:
        :exc:`FplError`: No type follows ``name:``, or the type is
            compound (hole ``compound-type``).
    """
    if kind is None or plain(kind) == "--":
        unimplemented()
    if isinstance(kind, Enclosure) and kind.pair == "quotation":
        return "thunk", None
    part = plain(kind)
    if part is None:
        unimplemented()
    return ("code", None) if part == "Code" else ("value", part)


def ascribed(item: Item) -> bool:
    """Tell whether *item* is a plain ``name:``, a type following it."""
    name = plain(item)
    return name is not None and len(name) > 1 and name.endswith(":")


def grouped(part: Part) -> bool:
    """Tell whether a slot's type is a group.

    The group is ``( p )``, written as the printer writes it.

    Examples:
        >>> grouped("( p )"), grouped("Int"), grouped(None)
        (True, False, False)
    """
    return part is not None and part.startswith("(")


def spelt(item: Item) -> str:
    """Return an item as the printer writes it."""
    line = Line((framed((item,)),), (), START)
    return render(Program((Line((), (), START), line), START)).strip()


def pins(items: list[Item]) -> bool:
    """Tell whether *items* hold a ``$`` pin at any depth."""
    return any(
        (isinstance(item, Word) and item.prefix == "$")
        or (isinstance(item, Enclosure) and pins(contents(item)))
        for item in items
    )


def keyed(effect: Effect) -> Key:
    """Return a definition's key.

    It holds per input its type, or its kind for a thunk or code slot
    (hole ``clause-identity``).

    Examples:
        >>> from fpl.ast_core import Effect
        >>> keyed(Effect(("a", "b"), (), types=("Int", None)))
        ('Int', None)
    """
    pairs = zip(effect.slots, effect.types, strict=True)
    return tuple(part if kind == "value" else kind for kind, part in pairs)


def agree(
    group: str, later: tuple[int, Effect, Span], earlier: tuple[int, Effect]
) -> None:
    """Refuse two clauses of one arity group that differ in shape.

    Both take the same slot kinds and leave as many values, else the
    later is refused at its head.

    Args:
        group: The path ``f/n`` of the arity group.
        later: The ordinal, effect and head position of the later
            clause.
        earlier: The ordinal and effect of the earlier clause.

    Raises:
        :exc:`FplError`: At the later head: the clauses take different
            slot kinds at a position, or leave different numbers of
            values.
    """
    at, effect, span = later
    i, other = earlier
    for position, (kind, before) in enumerate(
        zip(effect.slots, other.slots, strict=True), 1
    ):
        if kind != before:
            message = (
                f"{group}/{at} takes a {kind} at {position}, "
                f"{group}/{i} a {before}"
            )
            raise ClauseError(span, message)
    if len(effect.outs) != len(other.outs):
        message = (
            f"{group}/{at} leaves {len(effect.outs)}, "
            f"{group}/{i} {len(other.outs)}"
        )
        raise ClauseError(span, message)


def typings(effect: Effect) -> frozenset[int]:
    """Return the positions of a clause's typed inputs."""
    return frozenset(
        i for i, part in enumerate(effect.types) if part is not None
    )


def crossed(
    group: str, clauses: list[Head], builtins: frozenset[str]
) -> list[Pair]:
    """Refuse ambiguous clauses, and return the pairs a run must decide.

    Two clauses each typed where the other is not are ambiguous, unless
    they are disjoint, or their meet (each input typed as either types
    it) is itself a clause. The later head is refused, naming the meet
    (design 09 §3.3).

    Args:
        group: The path ``f/n`` of the arity group.
        clauses: The heads of its clauses, in ordinal order.
        builtins: The builtin type words that the program does not
            define.

    Returns:
        The pairs of ordinals whose meet would type one input two ways:
        only a run can tell whether both fit (§3.4).

    Raises:
        :exc:`FplError`: At the later head: two clauses are ambiguous.
    """
    written = {effect.types for effect, _ in clauses}
    undecided: list[Pair] = []
    for a, b in combinations(enumerate(clauses, 1), 2):
        first, second = a[1][0], b[1][0]
        ordered = typings(first) <= typings(second) or typings(
            second
        ) <= typings(first)
        if ordered or disjoint(first, second, builtins):
            continue
        meet = met(first, second)
        if meet is None:
            undecided.append((a[0], b[0]))
        elif meet.types not in written:
            (later, (_, span)), (earlier, _) = sorted(
                (a, b), key=lambda c: -c[1][1].line
            )
            message = (
                f"{group}/{later} is ambiguous with {group}/{earlier} "
                f"at {spoken(meet)}"
            )
            raise AmbiguousClauseError(span, message)
    return undecided


def disjoint(a: Effect, b: Effect, builtins: frozenset[str]) -> bool:
    """Tell whether no value fits both clauses.

    That holds when they type one position as two different builtins.
    """
    return any(
        x != y and {x, y} <= builtins
        for x, y in zip(a.types, b.types, strict=True)
    )


def met(a: Effect, b: Effect) -> Effect | None:
    """Return the meet of two clauses, or None.

    The meet is the effect of *a* with each input typed as either types
    it. None when both type one input differently.
    """
    pairs = list(zip(a.types, b.types, strict=True))
    if any(x is not None and y is not None and x != y for x, y in pairs):
        return None
    return replace(a, types=tuple(x or y for x, y in pairs))


def spoken(effect: Effect) -> str:
    """Return an effect's inputs as a head writes them.

    That is ``x: T`` where typed, two spaces apart.

    Examples:
        >>> from fpl.ast_core import Effect
        >>> spoken(Effect(("a", "b"), (), types=("Int", None)))
        'a: Int  b'
    """
    pairs = zip(effect.ins, effect.types, strict=True)
    return "  ".join(
        name if part is None else f"{name}: {part}" for name, part in pairs
    )


def shared(clauses: list[Effect]) -> Effect:
    """Return a dispatcher's effect.

    It is the first clause's, keeping a type only where all clauses
    agree.
    """
    first = clauses[0]
    types = tuple(
        part if all(c.types[i] == part for c in clauses) else None
        for i, part in enumerate(first.types)
    )
    return replace(first, types=types)


def plain(item: Item) -> str | None:
    """Return the name of a word with no sigil or modifier, or None."""
    if (
        isinstance(item, Word)
        and item.kind == "name"
        and not (item.prefix or item.mods)
    ):
        return item.body[0]
    return None


def atom(item: Item) -> Atom:
    """Return the value of a literal.

    Raises:
        :exc:`FplError`: The literal is refused by :func:`text` or
            :func:`number`.
    """
    return text(item) if isinstance(item, Text) else number(item)


def text(item: Text) -> str:
    """Return a string that holds no islands.

    Raises:
        :exc:`FplError`: The string holds an island.
    """
    texts = [part for part in item.parts if isinstance(part, str)]
    if len(texts) < len(item.parts):
        unimplemented()
    return "".join(texts)


def number(item: Item) -> Number:
    """Return an integer, or a decimal, kept exact as written.

    Raises:
        :exc:`FplError`: The item is not a plain numeral (``∞``, ``π``
            and a sigil or modifier are refused), or the numeral has
            more than :data:`~fpl.ast_core.DIGITS` digits, at its
            position.
    """
    if (
        not isinstance(item, Word)
        or item.prefix
        or item.mods
        or not item.body[0][-1].isdigit()
    ):
        unimplemented()
    numeral = item.body[0]
    if sum(map(str.isdecimal, numeral)) > DIGITS:
        raise TooLongError(item.span, "number too long")
    return Decimal(numeral) if "." in numeral else int(numeral)


def bare(word: Word) -> str:
    """Return the name after a sigil.

    Raises:
        :exc:`FplError`: The word is a path, or has a modifier.
    """
    if word.kind != "name" or word.mods:
        unimplemented()
    return word.body[0]


def contents(enclosure: Enclosure) -> list[Item]:
    """Return the items of an enclosure, bars and tabs aside."""
    return [
        item
        for frame in enclosure.frames
        for cell in frame.cells
        for item in cell.items
    ]


def scoped(code: tuple[Node, ...]) -> tuple[Node, ...]:
    """Return the code with each binder holding the rest as its body."""
    out: list[Node] = []
    for node in reversed(code):
        if isinstance(node, Bind):
            out = [
                Bind(node.name, node.body + tuple(reversed(out)), node.span)
            ]
        else:
            out.append(node)
    return tuple(reversed(out))


def fallible(code: tuple[Node, ...]) -> bool:
    """Tell whether a match in the code lacks a row that catches all.

    Matches inside a quotation are not looked at.
    """
    for node in code:
        if isinstance(node, Match) and not any(map(catches, node.rows)):
            return True
        if isinstance(node, Bind) and fallible(node.body):
            return True
    return False


def catches(row: Row) -> bool:
    """Tell whether the row matches any values: all names or ``_``."""
    return all(isinstance(pattern, Wild | Var) for pattern in row.patterns)


def matcher(line: Line) -> bool:
    """Tell whether a line is ``match`` alone, its rows as its block."""
    items = [
        item
        for frame in line.frames
        for cell in frame.cells
        for item in cell.items
    ]
    return bool(line.block) and len(items) == 1 and plain(items[0]) == "match"


def literal(item: Item) -> bool:
    """Tell whether *item* is a number or a string, which strand."""
    return isinstance(item, Text) or (
        isinstance(item, Word) and item.kind == "number"
    )


class _Desugar:
    """Turn lines into code, knowing the effect of every word."""

    def __init__(self, catalog: Catalog, docs: dict[int, str]) -> None:
        """Keep the catalog, the docstrings and the words' effects.

        Args:
            catalog: The directories and effects, from the builtins and
                the definitions.
            docs: The docstrings, by the number of the line they
                document.
        """
        self.catalog = catalog
        self.docs = docs
        self.effects = ChainMap(catalog.effects)
        self.here: Here = ()
        self.dispatchers: set[str] = set()

    def statements(
        self, lines: tuple[Line, ...], here: Here
    ) -> Iterator[Statement]:
        """Yield a directory's definitions and, at the top, its runs.

        Args:
            lines: The lines of the directory that hold code.
            here: The path of the directory.

        Raises:
            :exc:`FplError`: A line is refused (:meth:`code`,
                :meth:`body`, :meth:`run`); a check stands on a head or
                in a block (``a check is a run line``).
        """
        for line in lines:
            head, name = definition(line), directory(line)
            unchecked(line.block)
            if line.check is not None and head is not None:
                raise CheckFormError(line.span, "a check is a run line")
            if head is not None:
                path = (*here, head[0])
                code = self.code(line, head[1], path)
                effect = replace(head[1], fails=fallible(code))
                doc = self.docs.get(line.span.line, "")
                yield from self.defined(
                    Define("/".join(path), effect, code, doc, line.span), here
                )
            elif name is not None:
                yield from self.statements(coded(line.block), (*here, name))
            elif not here:
                yield self.run(line)

    def run(self, line: Line) -> Run:
        """Return a top-level line to run, with its check if it has one.

        The right side of ``L |- R`` is built as a line of its own, so
        it is code on a fresh stack as the left side is.

        Args:
            line: A top-level line that is neither a head nor a
                directory.

        Returns:
            The run, its ``check`` the code of ``R`` where there is one.

        Raises:
            :exc:`FplError`: A side is refused (:meth:`body`), or the
                check is a fail judgment, which only the driver takes,
                from the last line (``a fail judgment closes the
                program``).
        """
        code = self.body((line,), 0, ())
        if line.check is None:
            return Run(code, line.span)
        if judgment(line) is not None:
            raise CheckFormError(
                line.span, "a fail judgment closes the program"
            )
        right = Line(line.check, (), line.span)
        return Run(code, line.span, self.body((right,), 0, ()))

    def code(self, line: Line, effect: Effect, here: Here) -> tuple[Node, ...]:
        """Return a definition's code.

        That is its body. With a head group it is one row that binds a
        fresh name at every other input and the group's pattern at each
        group, pushes the other inputs back in order, and then runs the
        body, which sees the group's names (design 09 §2.4).

        Args:
            line: The definition's line.
            effect: The effect of its head.
            here: The path of the definition.

        Raises:
            :exc:`FplError`: A ``$`` pin is in a head group (hole
                ``head-group-pin``), or :meth:`body` or :meth:`simple`
                refuses.
        """
        groups = iter(
            i
            for i in line.frames[0].cells[0].items[2:]
            if isinstance(i, Enclosure) and i.pair == "prefix"
        )
        if not any(map(grouped, effect.types)):
            return self.body(line.block, len(effect.ins), here)
        outer, patterns, repush = self.effects, list[Pattern](), list[Node]()
        self.here = here
        for name, part in zip(fresh(effect), effect.types, strict=True):
            if grouped(part):
                group = next(groups)
                if pins(contents(group)):
                    unimplemented()
                patterns.append(self.simple(group))
            else:
                patterns.append(Var(name))
                repush.append(Call(name, line.span))
        body = self.body(line.block, len(repush), here)
        self.effects = outer
        return (Match((Row(tuple(patterns), (*repush, *body)),), line.span),)

    def defined(self, define: Define, here: Here) -> Iterator[Define]:
        """Yield the statements of one definition.

        A dispatched word yields its clause, the test words of its head
        groups (:func:`tests`) and, after the first clause of an arity,
        the dispatcher of that arity at that clause's head (design 09
        §2.4).

        Raises:
            :exc:`FplError`: A typed input names a type word that no
                word answers (:meth:`dispatcher`).
        """
        if define.name not in self.catalog.groups:
            yield define
            return
        n = len(define.effect.ins)
        clause = replace(
            define,
            clause=(n, self.catalog.ordinal(define.name, define.effect)),
        )
        yield clause
        yield from tests(clause)
        group = f"{define.name}/{n}"
        if group not in self.dispatchers:
            self.dispatchers.add(group)
            yield self.dispatcher(define.name, n, clause.span, here)

    def dispatcher(self, name: str, n: int, span: Span, here: Here) -> Define:
        """Return the dispatcher of arity group *n* of the word *name*.

        It has a row per clause and a refusing row per pair that crosses
        typed two ways at one input, the most typed inputs first. Among
        as many, the clauses' rows come newest first, then the refusing
        ones (design 09 §3.2). It is +fail when no row catches every
        value.

        Args:
            name: The path of the word.
            n: The arity of the group.
            span: The position given to the generated code.
            here: The directory in which type words are looked up.

        Raises:
            :exc:`FplError`: A typed input names a type word that no
                word answers (:meth:`checks`).
        """
        group = f"{name}/{n}"
        clauses = [
            (f"{group}/{i}", c)
            for i, (c, _) in enumerate(self.catalog.clauses(name, n), 1)
        ]
        ranked = [
            (
                (-len(typings(effect)), 0, -i, 0),
                self.guarding(word, effect, span, here),
            )
            for i, (word, effect) in enumerate(clauses, 1)
        ]
        for i, j in self.catalog.crossings[group]:
            sides = (clauses[i - 1], clauses[j - 1])
            count = len(typings(sides[0][1]) | typings(sides[1][1]))
            ranked.append(
                ((-count, 1, i, j), self.refusing(name, sides, span, here))
            )
        rows = tuple(
            row for _, row in sorted(ranked, key=lambda rank: rank[0])
        )
        code = (Match(rows, span),)
        effect = replace(self.catalog.effects[group], fails=fallible(code))
        words = tuple(word for word, _ in clauses)
        return Define(
            name, effect, code, span=span, clause=(n,), clauses=words
        )

    def guarding(
        self, word: str, effect: Effect, span: Span, here: Here
    ) -> Row:
        """Return a clause's dispatcher row.

        At each input it has a fresh name (:func:`fresh`), guarding each
        typed input with its test. It pushes every input back in order
        and calls the clause.

        Raises:
            :exc:`FplError`: A typed input names a type word that no
                word answers (:meth:`checks`).
        """
        names = fresh(effect)
        tests = zip(names, self.checks(word, effect, here), strict=True)
        patterns = tuple(
            guard(Var(name), (test,), span) for name, test in tests
        )
        return Row(
            patterns, (*(Call(name, span) for name in names), Call(word, span))
        )

    def refusing(
        self, name: str, sides: tuple[Clause, Clause], span: Span, here: Here
    ) -> Row:
        """Return the row that fits where both clauses fit.

        Each input is under the first clause's test and then the
        second's, and the row refuses the call as ambiguous (design 09
        §2.4).

        Raises:
            :exc:`FplError`: A typed input names a type word that no
                word answers (:meth:`checks`).
        """
        tests = [self.checks(word, effect, here) for word, effect in sides]
        patterns = tuple(
            guard(Wild(), column, span) for column in zip(*tests, strict=True)
        )
        both = " and ".join(word for word, _ in sides)
        return Row(
            patterns,
            (Refuse(f"ambiguous call to {name}: {both} both fit", span),),
        )

    def checks(
        self, word: str, effect: Effect, here: Here
    ) -> list[str | None]:
        """Return each input's test of a clause, None where untyped.

        Raises:
            :exc:`FplError`: A type names no word (:meth:`tested`).
        """
        return [
            None if part is None else self.tested(word, part, i, here)
            for i, part in enumerate(effect.types, 1)
        ]

    def tested(self, word: str, part: str, position: int, here: Here) -> str:
        """Return the word that tests a clause's typed input.

        For a group, its generated word. Otherwise the arity-1 form of
        the word its type names, looked up from the directory of the
        definition.

        Raises:
            :exc:`FplError`: The type names no word
                (:meth:`Catalog.resolve`).
        """
        if grouped(part):
            return f"{word}{PRIME}{position}"
        return self.catalog.dispatch(self.catalog.resolve(here, (part,)), 1)

    def routed(
        self, nodes: tuple[Node, ...], balance: int, *, whole: bool = False
    ) -> tuple[Node, ...]:
        """Return the nodes with each dispatched call routed.

        A call of a dispatched word takes the arity group its balance
        picks. A word that reaches below the balance leaves it at what
        the word adds.

        Args:
            nodes: The nodes in order.
            balance: The number of values on the stack before the first
                node.
            whole: Whether *balance* counts every value on the stack,
                as in a line, and not only those the code below puts
                there, as in a quotation, which runs on any stack. Only
                a balance that is whole can say a word has exactly one
                value (:meth:`chosen`).
        """
        out: list[Node] = []
        for node in nodes:
            taken = node
            if isinstance(node, Call) and not self.local(node.name):
                taken = Call(self.chosen(node.name, balance, whole), node.span)
            takes, leaves = self.arity(taken)
            balance = max(0, balance - takes) + leaves
            out.append(taken)
        return tuple(out)

    def chosen(self, name: str, balance: int, whole: bool) -> str:
        """Return the word a call of *name* on *balance* values runs.

        A binary arithmetic word that the program does not define is
        its one-value form (:data:`~fpl.ast_core.ONE_VALUE`) where
        exactly one value is on the stack. Anything else is the arity
        group its balance picks (:meth:`Catalog.dispatch`).

        Args:
            name: The called word.
            balance: The number of values on the stack before the call.
            whole: Whether those are all the values on the stack.
        """
        alone = whole and balance == 1
        if alone and name in ONE_VALUE and name not in self.catalog.heads:
            return ONE_VALUE[name]
        return self.catalog.dispatch(name, balance)

    def body(
        self, lines: tuple[Line, ...], balance: int, here: Here
    ) -> tuple[Node, ...]:
        """Return lines as code on one stack.

        Each starts on the balance the one before left. Names are looked
        up from *here*. A name bound in the lines is in scope until they
        end, and one bound in a section until the section ends. Within a
        line, the children come first, filling the inputs of the head
        (:meth:`filled`), then each frame. A frame whose words would
        reach below the balance it starts on is a section, pushed whole
        as a quotation (decision f). A ``match`` line takes all the
        values of the balance, which is 0 after it.

        Args:
            lines: The lines of the body.
            balance: The number of values on the stack before the first
                line.
            here: The path of the directory the lines are in.

        Raises:
            :exc:`FplError`: A line is refused (:meth:`match`,
                :meth:`child`, :meth:`frame`).
        """
        outer = self.effects
        self.here = here
        code: list[Node] = []
        for line in coded(lines):
            if matcher(line):
                code.append(self.match(line, balance))
                balance = 0
                continue
            parts = (
                *(
                    partial(self.child, child, kind)
                    for child, kind in self.filled(line)
                ),
                *(partial(self.frame, frame) for frame in line.frames),
            )
            for part in parts:
                before = self.effects
                written = part()
                nodes = self.routed(written, balance, whole=True)
                after = self.balance(nodes, balance)
                if after is None:
                    nodes, after = (
                        (Push(Quotation(scoped(self.routed(written, 0)))),),
                        balance + 1,
                    )
                    self.effects = before
                code.extend(nodes)
                balance = after
        self.effects = outer
        return scoped(tuple(code))

    def balance(self, nodes: tuple[Node, ...], balance: int) -> int | None:
        """Return the balance after *nodes* run on *balance* values.

        The result is None if a node reaches below the values it has.
        """
        for node in nodes:
            takes, leaves = self.arity(node)
            if balance < takes:
                return None
            balance += leaves - takes
        return balance

    def arity(self, node: Node) -> tuple[int, int]:
        """Return how many values a node takes and leaves.

        A call's counts are those of its word's effect.
        """
        match node:
            case Push() | Keyed():
                return 0, 1
            case Bind():
                return 1, 0
            case Match():  # pragma: no cover -- never in a frame
                return len(node.rows[0].patterns), 0
            case Refuse():  # pragma: no cover -- generated, never routed
                return 0, 0
            case Call():
                effect = self.effects[node.name]
                return len(effect.ins), len(effect.outs)
            case _:
                assert_never(node)

    def match(self, line: Line, arity: int) -> Match:
        """Return the rows of a ``match`` taking *arity* values.

        Raises:
            :exc:`FplError`: The block holds no rows (comments alone),
                at the word; or :meth:`row` refuses a row.
        """
        word = line.frames[0].cells[0].items[0]
        rows = tuple(self.row(row, arity) for row in coded(line.block))
        if not rows:
            raise MatchError(word.span, "a match has no rows")
        return Match(rows, word.span)

    def row(self, line: Line, arity: int) -> Row:
        """Return a row: *arity* pattern cells, then at most a body.

        The names that the patterns bind are read in the body.

        Raises:
            :exc:`FplError`: The line is not *arity* patterns and a
                body; or :meth:`pattern` refuses a cell.
        """
        cells = [cell for frame in line.frames for cell in frame.cells]
        if (
            line.block
            or len(line.frames) > 1
            or len(cells) - arity not in (0, 1)
        ):
            raise RowError(line.span, f"a row is {arity} patterns and a body")
        outer = self.effects
        patterns = tuple(self.pattern(cell.items) for cell in cells[:arity])
        body = self.routed(
            self.frame(Frame(tuple(cells[arity:]), line.span)), 0
        )
        self.effects = outer
        return Row(patterns, scoped(body))

    def pattern(self, items: tuple[Item, ...]) -> Pattern:
        """Return the one pattern of a cell, or of ``( p ∈ test )``.

        Raises:
            :exc:`FplError`: The items are not exactly one pattern (also
                :meth:`patterns`).
        """
        found = self.patterns(items)
        if len(found) != 1:
            unimplemented()
        return found[0]

    def patterns(self, items: tuple[Item, ...]) -> tuple[Pattern, ...]:
        """Return items as patterns, ``∈ test`` guarding the one before.

        Raises:
            :exc:`FplError`: :meth:`guarded` or :meth:`simple` refuses
                an item.
        """
        found: list[Pattern] = []
        marks = iter(items)
        for item in marks:
            if plain(item) == "∈" and found:
                found[-1] = self.guarded(
                    found[-1], next(marks, None), item.span
                )
            elif isinstance(item, Word) and ascribed(item):
                name = replace(item, body=(item.body[0][:-1],))
                found.append(
                    self.guarded(
                        self.simple(name), next(marks, None), item.span
                    )
                )
            else:
                found.append(self.simple(item))
        return tuple(found)

    def guarded(
        self, pattern: Pattern, test: Item | None, span: Span
    ) -> Guarded:
        """Return a pattern guarded by *test*.

        It fits where the pattern matches and the test word leaves 1.

        Raises:
            :exc:`FplError`: *test* is missing or not a word, or names
                no word (:meth:`call`).
        """
        if not isinstance(test, Word):
            unimplemented()
        return Guarded(
            pattern, self.catalog.dispatch(self.call(test).name, 1), span
        )

    def simple(self, item: Item) -> Pattern:
        """Return the pattern that one item makes.

        It is ``_``, ``$x`` of a bound name, a name it binds (a local
        from then on), ``( constructor patterns )``, ``( p ∈ test )`` or
        a literal.

        Raises:
            :exc:`FplError`: :meth:`inverse` or :meth:`constant` refuses
                the item.
        """
        match item:
            case Word(prefix="", kind="name", body=("_",), mods=""):
                return Wild()
            case Word(prefix="$", kind="name", body=(name,), mods="") if (
                self.local(name)
            ):
                return Equal(Call(name, item.span))
            case Word() if plain(item) is not None:
                self.effects = self.effects.new_child({item.body[0]: LOCAL})
                return Var(item.body[0])
            case Enclosure(pair="prefix"):
                return self.inverse(contents(item))
            case _:
                return self.constant(item)

    def local(self, name: str) -> bool:
        """Tell whether a binder or an earlier pattern binds *name*."""
        return any(name in scope for scope in self.effects.maps[:-1])

    def constant(self, item: Item) -> Equal:
        """Return a literal as a pattern that matches by equality.

        Raises:
            :exc:`FplError`: The item is not a single literal.
        """
        nodes = self.item(item)
        if len(nodes) != 1 or not isinstance(nodes[0], Push):
            unimplemented()
        return Equal(nodes[0])

    def inverse(self, items: list[Item]) -> Pattern:
        """Return the pattern of ``( p ∈ test )``, or of a constructor.

        A constructor takes one pattern per input and leaves one value.

        Raises:
            :exc:`FplError`: The parentheses are empty or do not start
                with a word; the constructor does not leave one value
                (``is not invertible``) or takes another number of
                patterns; or :meth:`call` refuses its word.
        """
        if not items:
            unimplemented()
        if len(items) > 1 and (plain(items[1]) == "∈" or ascribed(items[0])):
            return self.pattern(tuple(items))
        head, *args = items
        if not isinstance(head, Word):
            unimplemented()
        called = self.call(head).name
        found = self.patterns(tuple(args))
        name = self.catalog.dispatch(called, len(found))
        effect = self.effects[name]
        if len(effect.outs) != 1:
            raise NotInvertibleError(head.span, f"{name} is not invertible")
        if len(found) != len(effect.ins):
            raise PatternError(
                head.span, f"{name} takes {len(effect.ins)} patterns"
            )
        return Inverse(name, found, head.span)

    def quote(self, build: Callable[[], tuple[Node, ...]]) -> Push:
        """Return the code that *build* makes as a pushed quotation.

        The code is built in a scope of its own.
        """
        outer = self.effects
        code = self.routed(build(), 0)
        self.effects = outer
        return Push(Quotation(scoped(code)))

    def children(self, line: Line) -> tuple[tuple[Node, ...], ...]:
        """Return the code of each line of the block, in order.

        The lines fill the head's inputs, the last child the top one:
        under a value slot its code, run at once; under a thunk or code
        slot, or past the head's inputs, a quotation (hole
        ``child-slots``).
        """
        return tuple(
            self.child(child, kind) for child, kind in self.filled(line)
        )

    def filled(self, line: Line) -> tuple[tuple[Line, Slot | None], ...]:
        """Pair each child with its slot, None past the head's inputs.

        The head is read in a scope thrown away, so its binders reach
        neither the children nor the later reading of the same frames.
        """
        block = coded(line.block)
        outer = self.effects
        inputs = self.inputs(self.routed(self.frames(line.frames), len(block)))
        self.effects = outer
        kinds: list[Slot | None] = [None] * len(block)
        kinds += inputs
        return tuple(zip(block, kinds[len(inputs) :], strict=True))

    def child(self, line: Line, kind: Slot | None) -> tuple[Node, ...]:
        """Return a child's code, or its quotation.

        A child that fills no value slot is a quotation, built in a
        scope of its own.
        """
        if kind == "value":
            return self.later(line)
        return (self.quote(partial(self.later, line)),)

    def inputs(self, code: tuple[Node, ...]) -> tuple[Slot, ...]:
        """Return the slots *code* takes from below it, deepest first.

        The head phrase is taken as a whole, so the inputs that the code
        of an earlier word does not supply lie under those already taken
        (hole ``multi-word-head``). A binder's input is a value.
        """
        taken: tuple[Slot, ...] = ()
        held = 0
        for node in code:
            takes, leaves = self.arity(node)
            effect = (
                self.effects[node.name]
                if isinstance(node, Call)
                else Effect(("x",) * takes, ())
            )
            short = max(0, takes - held)
            taken = effect.slots[:short] + taken
            held += short + leaves - takes
        return taken

    def later(self, line: Line) -> tuple[Node, ...]:
        """Return a line as code to run later.

        That is its children, then its frames joined.
        """
        children = (node for part in self.children(line) for node in part)
        return (*children, *self.frames(line.frames))

    def frames(self, frames: tuple[Frame, ...]) -> tuple[Node, ...]:
        """Return frames joined into one sequence, with no sections."""
        return tuple(node for frame in frames for node in self.frame(frame))

    def frame(self, frame: Frame) -> tuple[Node, ...]:
        """Return a frame's cells in turn as code.

        Within a cell, literals side by side strand.
        """
        code: list[Node] = []
        for cell in frame.cells:
            for strands, run in groupby(cell.items, key=literal):
                items = tuple(run)
                if strands and len(items) > 1:
                    code.append(Push(Strand(tuple(map(atom, items)))))
                else:
                    code.extend(
                        node for item in items for node in self.item(item)
                    )
        return tuple(code)

    def item(self, item: Item) -> tuple[Node, ...]:
        """Return one item's code."""
        match item:
            case Word():
                return (self.word(item),)
            case Text():
                return (Push(text(item)),)
            case Enclosure():
                return self.enclosure(item)
            case _:
                assert_never(item)

    def word(self, word: Word) -> Node:
        """Return a word's node: a number, a symbol, a binder or a call.

        Raises:
            :exc:`FplError`: The word is refused by :func:`number`,
                :func:`bare` or :meth:`call`.
        """
        if word.kind == "number":
            return Push(number(word))
        if word.prefix == "#":
            return Push(Symbol(bare(word)))
        if word.prefix in ARROWS:
            name = (
                "/".join(word.body)
                if word.kind == "path" and word.body[-1]
                else bare(word)
            )
            self.effects = self.effects.new_child({name: LOCAL})
            return Bind(name, (), word.span)
        return self.call(word)

    def call(self, word: Word) -> Call:
        """Return the call that a word makes.

        The word is a name bound on its line, else the word its path
        names from the current directory, or after ``../`` from the
        directory holding it.

        Raises:
            :exc:`~fpl.errors.UnresolvedError`: Nothing answers the word
                (:func:`missing`).
            :exc:`FplError`: The word is a query that is refused, or has
                a modifier or another sigil (:meth:`origin`).
        """
        path = "/".join(word.body)
        if not (word.prefix or word.mods) and any(
            path in s for s in self.effects.maps[:-1]
        ):
            return Call(path, word.span)
        here = self.origin(word)
        found = self.catalog.find(here, word.body)
        if found is None:
            raise missing(word, self.catalog.listed(here, word.body))
        if found in self.catalog.refused:
            raise AmbiguousQueryError(word.span, self.catalog.refused[found])
        return Call(self.catalog.aliases.get(found, found), word.span)

    def origin(self, word: Word) -> Here:
        """Return the directory where a word's lookup starts.

        That is the current directory, or after ``../`` the one holding
        it.

        Raises:
            :exc:`FplError`: The word has a modifier or another sigil,
                or ``../`` is used at the top.
        """
        match word.prefix:
            case "" if not word.mods:
                return self.here
            case "../" if self.here and not word.mods:
                return self.here[:-1]
            case _:
                unimplemented()

    def enclosure(self, enclosure: Enclosure) -> tuple[Node, ...]:
        """Return an enclosure's code.

        ``[ ]`` is a quotation, ``( )`` has its head last and ``⟨ ⟩`` is
        a list of literals.

        Raises:
            :exc:`FplError`: A part is refused (:meth:`prefix`,
                :meth:`dict`, :meth:`element`).
        """
        match enclosure.pair:
            case "quotation":
                return (self.quote(partial(self.frames, enclosure.frames)),)
            case "prefix":
                return self.prefix(enclosure)
            case "group":
                return (
                    Push(
                        Listed(tuple(map(self.element, contents(enclosure))))
                    ),
                )
            case "dict":
                return (self.dict(enclosure),)
            case _:
                assert_never(enclosure.pair)

    def prefix(self, enclosure: Enclosure) -> tuple[Node, ...]:
        """Return the code of ``( head args )``.

        Each argument's code comes first, then the head's.

        Arguments never strand.

        Raises:
            :exc:`FplError`: The parentheses do not hold exactly one
                cell.
        """
        cells = [cell for frame in enclosure.frames for cell in frame.cells]
        if len(cells) != 1:
            unimplemented()
        head, *args = cells[0].items
        return tuple(
            node for item in (*args, head) for node in self.item(item)
        )

    def dict(self, enclosure: Enclosure) -> Keyed:
        """Return a ``{ }`` as its keys and values in turn.

        A key is a plain name and a value one item that pushes one
        value.

        Raises:
            :exc:`FplError`: The items are odd in number, a key is not a
                plain name, a value does not push exactly one value, or
                a key repeats, at its second use.
        """
        items = contents(enclosure)
        if len(items) % 2:
            unimplemented()
        entries: dict[str, Node] = {}
        for key_item, value_item in zip(items[::2], items[1::2], strict=True):
            key, nodes = plain(key_item), self.routed(self.item(value_item), 0)
            if (
                key is None
                or len(nodes) != 1
                or self.arity(nodes[0]) != (0, 1)
            ):
                unimplemented()
            if key in entries:
                raise DictError(key_item.span, f"repeated key {key}")
            entries[key] = nodes[0]
        return Keyed(tuple(entries.items()), enclosure.span)

    def element(self, item: Item) -> Value:
        """Return a list element's value, from an item that pushes one.

        Raises:
            :exc:`FplError`: The item does not push exactly one value.
        """
        nodes = self.item(item)
        if len(nodes) == 1 and isinstance(nodes[0], Push):
            return nodes[0].value
        unimplemented()


def resugar(statements: tuple[Statement, ...]) -> Program:
    r"""Return core as source that desugars to the same code.

    The source has no bar but between two literals, which would
    otherwise strand, no ``( )``, and no block but a definition's
    one-line body and its docs. A dispatcher is generated, never
    written.

    Examples:
        >>> from fpl.parse import parse
        >>> from fpl.print import render
        >>> render(resugar(desugar(parse("sq : x -- y\n\tdup +\n"))))
        'sq : x -- y\n\tdup +\n'

    Raises:
        :exc:`FplError`: A statement holds a ``match`` or a refusal
            (:func:`spelled`).
    """
    kept = (s for s in statements if not generated(s))
    return Program(
        tuple(line for s in kept for line in (*above(s), written(s))), START
    )


def generated(statement: Statement) -> bool:
    """Tell whether a statement is made from a head, never written.

    That holds for a dispatcher, a group's test word and a clause with a
    group (hole ``resugar-match``).
    """
    if not isinstance(statement, Define):
        return False
    made = len(statement.clause) == 1 or PRIME in statement.name
    return made or any(map(grouped, statement.effect.types))


def guard(
    pattern: Pattern, tests: Iterable[str | None], span: Span
) -> Pattern:
    """Return the pattern guarded by each test, the first innermost.

    A test that is None is skipped.
    """
    for test in tests:
        if test is not None:
            pattern = Guarded(pattern, test, span)
    return pattern


def fresh(effect: Effect) -> list[str]:
    """Return a fresh name per input.

    Each is the input's name, a prime and its position (design 09 §2.4).

    Examples:
        >>> from fpl.ast_core import Effect
        >>> fresh(Effect(("a", "b"), ("c",)))
        ['a′1', 'b′2']
    """
    return [f"{name}{PRIME}{i}" for i, name in enumerate(effect.ins, 1)]


def tests(clause: Define) -> Iterator[Define]:
    """Yield the test word of each group of a clause.

    The word is ``x -- b``, leaving 1 where the group matches, else 0.

    Each is named by the clause's word, a prime and the group's
    position.
    """
    for position, part in enumerate(clause.effect.types, 1):
        match clause.code:
            case (Match(rows=(row,)),) if grouped(part):
                fits = Row((row.patterns[position - 1],), (Push(1),))
                code = Match((fits, Row((Wild(),), (Push(0),))), clause.span)
                name = f"{clause.word}{PRIME}{position}"
                yield Define(
                    name, Effect(("x",), ("b",)), (code,), span=clause.span
                )
            case _:
                pass


def listing(stacks: tuple[tuple[Value, ...], ...]) -> Program:
    r"""Return one line per stack, a program that pushes that stack.

    Raises:
        :exc:`FplError`: A value is nested deeper than the build can
            recurse to, at the source's start, as the parser refuses
            such source (issue #95).

    Examples:
        >>> from fpl.print import render
        >>> render(listing(((1, "a"), ())))
        '1 | “a”\n\n'
    """
    try:
        return Program(
            tuple(
                Line(sugared(tuple(map(Push, s))), (), START) for s in stacks
            ),
            START,
        )
    except RecursionError:
        raise PrintError(START, "nesting too deep to print") from None


def written(statement: Statement) -> Line:
    """Return one statement as a line, a run with its check."""
    match statement:
        case Run(check=check):
            right = None if check is None else sugared(check)
            return Line(sugared(statement.code), (), START, check=right)
        case Define():
            effect = statement.effect
            fails = ("+fail",) if effect.fails else ()
            ins = zip(effect.ins, effect.slots, effect.types, strict=True)
            taken = (
                item
                for name, kind, part in ins
                for item in declaration(name, kind, part)
            )
            head = (named(statement.name), named(":"), *taken, named("--"))
            body = (
                (Line(sugared(statement.code), (), START),)
                if statement.code
                else ()
            )
            outs = (*effect.outs, *fails)
            return Line(
                (framed((*head, *map(named, outs))),),
                documented(statement) + body,
                START,
            )
        case _:
            assert_never(statement)


def documented(statement: Define) -> tuple[Line, ...]:
    """Return a definition's docstring as the ``;;`` lines of its body.

    There are none when it has no body, as its docs are written above
    its head instead.
    """
    return doc_lines(statement.doc) if statement.code else ()


def above(statement: Statement) -> tuple[Line, ...]:
    """Return the ``;;`` lines written above a statement.

    Only a definition with no code has them, as its docstring under its
    head would be read as the next code line's (fpl/trivia.py).
    """
    if isinstance(statement, Define) and not statement.code:
        return doc_lines(statement.doc)
    return ()


def doc_lines(doc: str) -> tuple[Line, ...]:
    """Return a docstring as ``;;`` lines, one per line of it.

    The empty docstring gives none.
    """
    texts = doc.split("\n") if doc else []
    return tuple(
        Line((), (), START, Comment(2, (f";; {text}",), START))
        for text in texts
    )


def sugared(code: tuple[Node, ...]) -> tuple[Frame, ...]:
    """Return code as frames, with a bar between two literals."""
    frames: list[list[Item]] = [[]]
    before: Node | None = None
    for node in unfolded(code):
        if stranding(before) and stranding(node):
            frames.append([])
        frames[-1].extend(spelled(node))
        before = node
    return tuple(framed(tuple(items)) for items in frames)


def unfolded(code: tuple[Node, ...]) -> Iterator[Node]:
    """Yield the nodes in the order written: a binder, then its body."""
    for node in code:
        yield node
        if isinstance(node, Bind):
            yield from unfolded(node.body)


#: The word that is written for each one-value form, which is never
#: written: it is what the word is called as where one value is below.
written_as = {form: word for word, form in ONE_VALUE.items()}


def spelled(node: Node) -> tuple[Item, ...]:
    """Return the items that write one node.

    A binder's body is written after it (:func:`unfolded`).

    Raises:
        :exc:`FplError`: The node is a ``match`` or a refusal.
    """
    match node:
        case Push():
            return shown(node.value)
        case Call():
            return (named(written_as.get(node.name, node.name)),)
        case Bind():
            return (
                Word(
                    "→",
                    named(node.name).kind,
                    named(node.name).body,
                    "",
                    START,
                ),
            )
        case Keyed():
            pairs = tuple(
                item
                for key, n in node.entries
                for item in (named(key), *spelled(n))
            )
            return (Enclosure("dict", (framed(pairs),), START),)
        case Match() | Refuse():
            unimplemented()
        case _:
            assert_never(node)


def stranding(node: Node | None) -> bool:
    """Tell whether a node pushes a number, a string or a strand."""
    return isinstance(node, Push) and isinstance(
        node.value, int | Decimal | str | Strand
    )


def framed(items: tuple[Item, ...]) -> Frame:
    """Return items as a frame of one cell, or of none."""
    return Frame((Cell(items, START),) if items else (), START)


def declaration(name: str, kind: Slot, part: Part) -> tuple[Item, ...]:
    """Return an input as written.

    A value is bare or ``name: Type``, a thunk ``name: []`` and code
    ``name: Code``.

    The type a thunk was declared with is not kept (hole
    ``thunk-type-dropped``).
    """
    match kind:
        case "value" if part is not None:
            return (named(name + ":"), named(part))
        case "value":
            return (named(name),)
        case "thunk":
            return (
                named(name + ":"),
                Enclosure("quotation", (framed(()),), START),
            )
        case "code":
            return (named(name + ":"), named("Code"))
        case _:
            assert_never(kind)


def named(name: str) -> Word:
    """Return a name as written: a path when it holds a slash."""
    segments = tuple(name.split("/"))
    return Word(
        "", "path" if len(segments) > 1 else "name", segments, "", START
    )


def shown(value: Value) -> tuple[Item, ...]:
    """Return a value as the items that push it."""
    match value:
        case str():
            return (Text("str", (value,), START),)
        case Strand():
            return spread(value.items)
        case Listed() | Quotation() | Dict():
            return (enclosed(value),)
        case Symbol():
            return (Word("#", "name", (value.name,), "", START),)
        case _:
            numeral = (
                format(value, "f")
                if isinstance(value, Decimal)
                else str(value)
            )
            return (Word("", "number", (numeral,), "", START),)


def enclosed(value: Listed | Quotation | Dict) -> Enclosure:
    """Return a value written between its delimiters."""
    match value:
        case Listed():
            return Enclosure("group", (framed(spread(value.items)),), START)
        case Quotation():
            return Enclosure("quotation", sugared(value.code), START)
        case Dict():
            pairs = tuple(
                item
                for key, v in value.entries
                for item in (named(key), *shown(v))
            )
            return Enclosure("dict", (framed(pairs),), START)
        case _:
            assert_never(value)


def spread(values: tuple[Value, ...]) -> tuple[Item, ...]:
    """Return values side by side, as items."""
    return tuple(item for value in values for item in shown(value))

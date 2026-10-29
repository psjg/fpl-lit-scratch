"""The web: a literate page read into sections and chunks, and tangled.

A page is Markdown. A fence opened by a line that is exactly
```` ```python ```` is a code chunk, and its header names it, gives
its place and the files it stands in, one path a line::

    <<3.1 Name the characters of the pairs
    fpl/lex.py
    python/fpl/lex/__init__.py>>=

A place is a dotted number; places sort by their numbers, so 3 < 3.1 <
3.2 < 3.10. A path line may open with a place of its own for that
file, as ``2 fpl/lex.py``. A
continuation, ``<<Name the characters of the pairs>>+=``, adds lines to
the chunk and carries neither. Other chunks name it without its place.

A line of a chunk that holds only ``<<Name>>`` is a use: the chunk's
lines go there, each indented by the use's indentation. A used chunk
stands under its user's place and in its user's files. Any other fence
(``pycon``, ``text``, ``fpl``) is prose. A section is the prose up to
and including one chunk; the prose after the last chunk is a section
without one.

A file is the chunks that name it and that no chunk uses, by place.
Between two of them stand two blank lines when either is a def or a
class, as PEP 8 has them; none when their places share a parent, as 3.1
and 3.2 do; one otherwise.

The reader is strict: a python fence without a header, a header without
a place or without a path, a path line that does not parse, a ``+=``
that places, a ``+=`` before its ``=``, a second ``=``, a use of a chunk
never defined, a chunk named like a path, a chunk that only lists
others, a used chunk outside its user's place or files, two chunks at
one place of a file, a chunk no file reaches, a cycle, a ``tangle:``
key in the front matter and an unclosed fence are each a `Finding` at
its page line, and nothing is guessed. Everything here is pure: a page
is read from its text, and a tangle is a value, written by the caller.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Callable

HEAD = re.compile(
    r"<<(?P<name>[^<>\n]+)(?P<paths>(?:\n[^<>\n]+)*)>>(?P<plus>\+?)="
)
USE = re.compile(r"(?P<indent>[ \t]*)<<(?P<name>[^<>]+)>>[ \t]*")
FILE = re.compile(r"[\w.-]+(/[\w.-]+)*\.\w+")
PLACE = r"(?P<place>[0-9]+(?:\.[0-9]+)*)"
NAMED = re.compile(rf"{PLACE}[ \t]+(?P<name>.*\S)")
PATH = re.compile(rf"(?:{PLACE}[ \t]+)?(?P<path>{FILE.pattern})")
ALLOW = re.compile(r"lit-allow:\s*\[(?P<names>[^\]]*)\]\s*")
GONE = re.compile(r"tangle:.*")
CODE = "python"
TOP = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True)
class Finding:
    """One problem, at a place a reader can open: ``path:line``."""

    path: str
    line: int
    rule: str
    message: str

    @override
    def __str__(self) -> str:
        """The finding as ``path:line: rule: message``."""
        return f"{self.path}:{self.line}: {self.rule}: {self.message}"


@dataclass(frozen=True)
class Line:
    """A prose line, its page line, and whether a fence holds it."""

    number: int
    text: str
    fenced: bool


Place = tuple[int, ...]


@dataclass(frozen=True)
class Chunk:
    """A code fence: its name, ``+=`` or not, header, body and files.

    ``line`` is the header's last line, so that ``body[k]`` stands at
    page line ``line + 1 + k``; ``head`` counts the header's lines.
    ``place`` is the name line's; ``files`` are the header's paths, each
    with the chunk's place in that file. A ``+=`` has neither.
    """

    name: str
    plus: bool
    line: int
    body: tuple[str, ...]
    place: Place = ()
    files: tuple[tuple[str, Place], ...] = ()
    head: int = 1


@dataclass(frozen=True)
class Example:
    """A ``pycon`` fence of the prose: its opening line and its text."""

    line: int
    text: str


@dataclass(frozen=True)
class Section:
    """Prose, the examples in it, and at most one chunk, numbered."""

    number: int
    prose: tuple[Line, ...]
    examples: tuple[Example, ...]
    chunk: Chunk | None


@dataclass(frozen=True)
class Page:
    """A literate page: where it is, its sections and its allowlist."""

    path: str
    sections: tuple[Section, ...]
    allow: frozenset[str]
    findings: tuple[Finding, ...]

    def chunks(self) -> list[Chunk]:
        """Every chunk, in page order."""
        return [s.chunk for s in self.sections if s.chunk is not None]

    def defined(self) -> dict[str, list[Chunk]]:
        """Each chunk name with its definitions, the ``=`` first."""
        out: dict[str, list[Chunk]] = {}
        for chunk in self.chunks():
            out.setdefault(chunk.name, []).append(chunk)
        return out

    def files(self) -> list[str]:
        """The files the page names, in the order first named."""
        named = (path for c in self.chunks() for path, _ in c.files)
        return list(dict.fromkeys(named))

    def section_of(self, line: int) -> int:
        """The number of the section whose chunk holds a page line."""
        for s in self.sections:
            c = s.chunk
            if c is not None and c.line - c.head < line <= c.line + len(
                c.body
            ):
                return s.number
        return 0


@dataclass(frozen=True)
class Tangled:
    """A file expanded: its lines, and the page line of each."""

    name: str
    page: str
    lines: tuple[str, ...]
    origin: tuple[int, ...]

    @property
    def text(self) -> str:
        """The file's text, ending in one newline."""
        return "".join(line + "\n" for line in self.lines)


def is_file(name: str) -> bool:
    """Whether a name is a path: no spaces, a dot before its suffix."""
    return FILE.fullmatch(name) is not None


def norm(name: str) -> str:
    """A chunk name with its runs of white space made one space."""
    return " ".join(name.split())


def dotted(place: Place) -> str:
    """A place as it is written: ``3.1``."""
    return ".".join(map(str, place))


def _place(text: str) -> Place:
    """A written place as its numbers: ``3.10`` is ``(3, 10)``."""
    return tuple(map(int, text.split(".")))


def front(lines: list[str]) -> tuple[int, frozenset[str], int | None]:
    """Where the body starts after front matter, and its allowlist.

    Also the page line of a ``tangle:`` key, which is gone, or None.
    """
    if not lines or lines[0] != "---":
        return 0, frozenset(), None
    allow: set[str] = set()
    gone: int | None = None
    for k in range(1, len(lines)):
        if lines[k] == "---":
            return k + 1, frozenset(allow), gone
        if m := ALLOW.fullmatch(lines[k]):
            allow |= {n.strip() for n in m["names"].split(",") if n.strip()}
        elif GONE.fullmatch(lines[k]):
            gone = k + 1
    return 0, frozenset(), None


def _head(body: list[str]) -> tuple[re.Match[str] | None, int]:
    """A fence's header and how many lines it takes.

    The header ends on the first line that holds ``>>``.
    """
    size = next((k + 1 for k, t in enumerate(body) if ">>" in t), 0)
    return HEAD.fullmatch("\n".join(t.rstrip() for t in body[:size])), size


class _Reader:
    """The state of reading one page: the section being gathered."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.sections: list[Section] = []
        self.prose: list[Line] = []
        self.examples: list[Example] = []
        self.findings: list[Finding] = []

    def bad(self, line: int, message: str) -> None:
        """Record a finding of the web at a page line."""
        self.findings.append(Finding(self.path, line, "lit-web", message))

    def close(self, chunk: Chunk | None) -> None:
        """End the section being gathered, with its chunk if any."""
        if chunk is None and not any(p.text.strip() for p in self.prose):
            return
        n = len(self.sections) + 1
        self.sections.append(
            Section(n, tuple(self.prose), tuple(self.examples), chunk)
        )
        self.prose, self.examples = [], []

    def fence(self, info: str, at: int, body: list[str]) -> None:
        """Take one fence that opened on page line ``at``."""
        if info != CODE:
            self.prose.append(Line(at, "```" + info, fenced=True))
            self.prose.extend(
                Line(at + 1 + k, t, fenced=True) for k, t in enumerate(body)
            )
            self.prose.append(Line(at + 1 + len(body), "```", fenced=True))
            if info == "pycon":
                self.examples.append(Example(at, "\n".join(body) + "\n"))
            return
        head, size = _head(body)
        if head is None:
            self.findings.append(
                Finding(
                    self.path,
                    at,
                    "lit-header",
                    "a python fence opens without <<Name>>= -- name it,"
                    " or fence an example as pycon",
                )
            )
            return
        self.close(self.chunk(head, at + size, tuple(body[size:]), size))

    def chunk(
        self, head: re.Match[str], line: int, body: tuple[str, ...], size: int
    ) -> Chunk:
        """The chunk whose header of ``size`` lines ends on ``line``."""
        at = line - size + 1
        paths = head["paths"].split("\n")[1:]
        if head["plus"]:
            name = norm(head["name"])
            if paths:
                message = f"<<{name}>>+= places nothing: its = does"
                self.bad(at, message)
            return Chunk(name, True, line, body, head=size)
        named = NAMED.fullmatch(head["name"].strip())
        name = norm(named["name"] if named else head["name"])
        place = _place(named["place"]) if named else ()
        if not named:
            self.bad(at, f"<<{name}>>= has no place: open its line with one")
        if not paths:
            self.bad(at, f"<<{name}>>= names no file: put a path under it")
        files: list[tuple[str, Place]] = []
        for k, text in enumerate(paths, 1):
            if m := PATH.fullmatch(text.strip()):
                own = _place(m["place"]) if m["place"] else place
                files.append((m["path"], own))
                continue
            message = (
                f"<<{name}>>: {text.strip()!r} is no path line -- write a"
                " path, after its own place if it differs, as 2 fpl/lex.py"
            )
            self.bad(at + k, message)
        return Chunk(name, False, line, body, place, tuple(files), size)


def read(path: str, text: str) -> Page:
    """Read a page's text into sections; ``path`` is how it is named."""
    lines = text.split("\n")
    start, allow, gone = front(lines)
    reader = _Reader(path)
    if gone is not None:
        message = "`tangle:` is gone: name each chunk's files on its header"
        reader.bad(gone, message)
    k = start
    while k < len(lines):
        if not lines[k].startswith("```"):
            reader.prose.append(Line(k + 1, lines[k], fenced=False))
            k += 1
            continue
        end = next(
            (j for j in range(k + 1, len(lines)) if lines[j] == "```"), None
        )
        if end is None:
            reader.findings.append(
                Finding(path, k + 1, "lit-fence", "a fence never closes")
            )
            break
        reader.fence(lines[k][3:].strip(), k + 1, lines[k + 1 : end])
        k = end + 1
    reader.close(None)
    return Page(path, tuple(reader.sections), allow, tuple(reader.findings))


def rules(page: Page) -> list[Finding]:
    """The web's own rules: one ``=`` first, every use defined.

    A chunk named like a path, the old file root, and a chunk that only
    uses others, the old way to order a file, are refused.
    """
    out = list(page.findings)
    seen: set[str] = set()
    names = page.defined()
    for chunk in page.chunks():
        if chunk.plus and chunk.name not in seen:
            out.append(_bad(page, chunk.line, f"+= before = of {chunk.name}"))
        if not chunk.plus and chunk.name in seen:
            out.append(_bad(page, chunk.line, f"a second = of {chunk.name}"))
        if chunk.name not in seen and is_file(chunk.name):
            message = (
                f"root chunk <<{chunk.name}>>: name the file on the headers"
                " of its parts and drop this chunk"
            )
            out.append(_bad(page, chunk.line, message))
        seen.add(chunk.name)
        for k, text in enumerate(chunk.body):
            use = USE.fullmatch(text)
            if use and norm(use["name"]) not in names:
                where = chunk.line + 1 + k
                out.append(_bad(page, where, f"<<{use['name']}>> undefined"))
    return out + _listers(page)


def _listers(page: Page) -> list[Finding]:
    """The chunks whose lines are uses of others and nothing else."""
    out: list[Finding] = []
    for name, chunks in page.defined().items():
        lines = [t for c in chunks for t in c.body if t.strip()]
        if lines and all(USE.fullmatch(t) for t in lines):
            message = (
                f"<<{name}>> only uses other chunks: list its parts by"
                " place and drop this chunk"
            )
            out.append(_bad(page, chunks[0].line, message))
    return out


def _bad(page: Page, line: int, message: str) -> Finding:
    return Finding(page.path, line, "lit-web", message)


class _Expander:
    """Expands one part, recording each chunk it reaches."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.names = page.defined()
        self.reached: set[str] = set()
        self.lines: list[str] = []
        self.origin: list[int] = []
        self.findings: list[Finding] = []

    def expand(self, name: str, indent: str, stack: tuple[str, ...]) -> None:
        """Append chunk ``name``'s lines, uses expanded, indented."""
        if name in stack:
            cycle = " -> ".join((*stack, name))
            line = self.names[name][0].line
            self.findings.append(_bad(self.page, line, f"cycle: {cycle}"))
            return
        self.reached.add(name)
        for chunk in self.names[name]:
            for k, text in enumerate(chunk.body):
                use = USE.fullmatch(text)
                target = norm(use["name"]) if use else ""
                if use and target in self.names:
                    deeper = indent + use["indent"]
                    self.expand(target, deeper, (*stack, name))
                elif not use:
                    self.lines.append(indent + text if text else "")
                    self.origin.append(chunk.line + 1 + k)


def _statements(lines: list[str]) -> list[ast.stmt]:
    """A part's statements, or none when it is not Python."""
    try:
        return ast.parse("\n".join(lines)).body
    except SyntaxError:
        return []


def _gap(before: list[str], after: list[str], was: Place, place: Place) -> int:
    """The blank lines between two parts at places ``was``, ``place``.

    Two stand around a def or a class at the top, as PEP 8 has them;
    none between parts whose places share a parent; one otherwise.
    """
    ends, opens = _statements(before)[-1:], _statements(after)[:1]
    if any(isinstance(s, TOP) for s in ends + opens):
        return 2
    return 0 if len(was) > 1 and was[:-1] == place[:-1] else 1


def _uses(page: Page) -> list[tuple[str, Chunk]]:
    """Each chunk another uses, once with the ``=`` of each user."""
    names = page.defined()
    return list(
        dict.fromkeys(
            (norm(m["name"]), names[c.name][0])
            for c in page.chunks()
            for text in c.body
            if (m := USE.fullmatch(text)) and norm(m["name"]) in names
        )
    )


def _nested(page: Page, uses: list[tuple[str, Chunk]]) -> list[Finding]:
    """The used chunks outside a user's place or files."""
    out: list[Finding] = []
    names = page.defined()
    for name, user in uses:
        c = names[name][0]
        paths = [p for p, _ in user.files]
        under = c.place[: len(user.place)] == user.place
        inside = under and len(c.place) > len(user.place)
        if not inside or {p for p, _ in c.files} != set(paths):
            message = (
                f"<<{name}>> is used in <<{user.name}>>: place it under"
                f" {dotted(user.place)}, in {' '.join(paths)}"
            )
            out.append(_bad(page, c.line, message))
    return out


def _crowded(page: Page) -> list[Finding]:
    """The chunks at a place of a file that an earlier one holds."""
    out: list[Finding] = []
    seen: dict[tuple[str, Place], str] = {}
    for c in page.chunks():
        for path, place in c.files:
            if (path, place) in seen:
                message = (
                    f"<<{seen[path, place]}>> and <<{c.name}>> both stand"
                    f" at {path} {dotted(place)}"
                )
                out.append(_bad(page, c.line, message))
            seen.setdefault((path, place), c.name)
    return out


def tangle(page: Page) -> tuple[list[Tangled], list[Finding]]:
    """Every file of the page, its parts expanded; and the findings.

    A file's parts are the chunks naming it that no chunk uses, by
    their places in it.
    """
    uses = _uses(page)
    used = {name for name, _ in uses}
    findings = rules(page) + _nested(page, uses) + _crowded(page)
    names = page.defined()
    done: dict[str, _Expander] = {}

    def part(name: str) -> _Expander:
        if name not in done:
            done[name] = ex = _Expander(page)
            ex.expand(name, "", ())
            findings.extend(ex.findings)
        return done[name]

    out: list[Tangled] = []
    for path in page.files():
        named = [
            (place, c)
            for c in (cs[0] for cs in names.values())
            for p, place in c.files
            if p == path
        ]
        if {".", ".."} & set(path.split("/")):
            message = f"{path} is not a path inside the root"
            findings.append(_bad(page, named[0][1].line, message))
            continue
        parts = sorted((pl, c.name) for pl, c in named if c.name not in used)
        if parts:
            out.append(_join(page, path, parts, part))
    reached = {n for ex in done.values() for n in ex.reached}
    for name, chunks in names.items():
        if name not in reached and chunks[0].files:
            message = f"<<{name}>> is never used by a file"
            findings.append(_bad(page, chunks[0].line, message))
    return out, findings


def _join(
    page: Page,
    path: str,
    parts: list[tuple[Place, str]],
    part: Callable[[str], _Expander],
) -> Tangled:
    """A file's parts, expanded, with blank lines between them.

    A blank line comes from the header of the part after it.
    """
    names = page.defined()
    lines: list[str] = []
    origin: list[int] = []
    for k, (place, name) in enumerate(parts):
        if k:
            was, before = parts[k - 1]
            gap = _gap(part(before).lines, part(name).lines, was, place)
            lines += [""] * gap
            origin += [names[name][0].line] * gap
        lines += part(name).lines
        origin += part(name).origin
    return Tangled(path, page.path, tuple(lines), tuple(origin))


def discover(root: Path) -> list[Path]:
    """The literate pages under ``root``: Markdown holding a header.

    A header is one line, or a name line that file lines follow.
    """
    found = re.compile(
        r"^```python\n<<[^<>\n]+(?:>>\+?=)?[ \t]*$", re.MULTILINE
    )
    return sorted(
        p
        for p in root.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(root).parts)
        and found.search(p.read_text(encoding="utf-8"))
    )

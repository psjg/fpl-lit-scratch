"""The web: a literate page read into sections and chunks, and tangled.

A page is Markdown. A fence opened by a line that is exactly
```` ```python ```` is a code chunk, and its first line names it::

    <<Name the characters of the pairs>>=     a definition
    <<Name the characters of the pairs>>+=    more of the same chunk

A line of a chunk that holds only ``<<Name>>`` is a use: the chunk's
lines go there, each indented by the use's indentation. Any other fence
(``pycon``, ``text``, ``fpl``) is prose. A section is the prose up to
and including one chunk; the prose after the last chunk is a section
without one.

The front matter names the file a page tangles to, relative to the root
directory: ``tangle: python/fpl/lex/__init__.py``. Its parts are the
chunks no other chunk uses, in page order, except that a part holding
only imports moves up to stand after the docstring, or first when there
is none. One blank line stands between two parts, or two around a def
or a class, as PEP 8 has them. A header may also place its chunk, one
line per file after the name, each a path and a place::

    <<Define the pre-lexer
    fpl/lex.py 3>>=

The chunk is then the third part of ``fpl/lex.py``, and stays a part of
the front matter's file; placed in that file itself, it moves to its
place. A file named only so holds its placed parts in the order of their
places.

The reader is strict: a python fence without a header, a header's file
line that is no path and place or stands on a ``+=``, a ``+=`` before
its ``=``, a second
``=``, a use of a chunk never defined, a chunk named like a path, a
page that names no file, a file without parts, two parts at one place,
a chunk no file reaches, a cycle and an unclosed fence are each a
`Finding` at its page line, and nothing is guessed. Everything here is
pure: a page is read from its text, and a tangle is a value, written by
the caller.
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
    r"<<(?P<name>[^<>\n]+)(?P<places>(?:\n[^<>\n]+)*)>>(?P<plus>\+?)="
)
USE = re.compile(r"(?P<indent>[ \t]*)<<(?P<name>[^<>]+)>>[ \t]*")
FILE = re.compile(r"[\w.-]+(/[\w.-]+)*\.\w+")
PLACE = re.compile(rf"(?P<path>{FILE.pattern})[ \t]+(?P<seq>[1-9][0-9]*)")
ALLOW = re.compile(r"lit-allow:\s*\[(?P<names>[^\]]*)\]\s*")
TANGLE = re.compile(r"tangle:\s*(?P<path>\S+)\s*")
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


@dataclass(frozen=True)
class Chunk:
    """A code fence: its name, ``+=`` or not, header, body and places.

    ``line`` is the header's last line, so that ``body[k]`` stands at
    page line ``line + 1 + k``; ``head`` counts the header's lines.
    ``places`` are the header's file lines, each a path and a place.
    """

    name: str
    plus: bool
    line: int
    body: tuple[str, ...]
    places: tuple[tuple[str, int], ...] = ()
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
    """A literate page: where it is, its sections, allowlist and file.

    ``tangle`` is the file its front matter names, with that line.
    """

    path: str
    sections: tuple[Section, ...]
    allow: frozenset[str]
    findings: tuple[Finding, ...]
    tangle: tuple[str, int] | None = None

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
        """The files the page names: each placed one, then its own."""
        out = [path for c in self.chunks() for path, _ in c.places]
        out += [self.tangle[0]] if self.tangle else []
        return list(dict.fromkeys(out))

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


def front(
    lines: list[str],
) -> tuple[int, frozenset[str], tuple[str, int] | None]:
    """Where the body starts after front matter; its allowlist and file.

    The file is the ``tangle:`` value with its page line, or None.
    """
    if not lines or lines[0] != "---":
        return 0, frozenset(), None
    allow: set[str] = set()
    named: tuple[str, int] | None = None
    for k in range(1, len(lines)):
        if lines[k] == "---":
            return k + 1, frozenset(allow), named
        if m := ALLOW.fullmatch(lines[k]):
            allow |= {n.strip() for n in m["names"].split(",") if n.strip()}
        elif m := TANGLE.fullmatch(lines[k]):
            named = (m["path"], k + 1)
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
        name = norm(head["name"])
        self.close(
            Chunk(
                name,
                bool(head["plus"]),
                at + size,
                tuple(body[size:]),
                self.places(name, head, at + 1),
                size,
            )
        )

    def places(
        self, name: str, head: re.Match[str], at: int
    ) -> tuple[tuple[str, int], ...]:
        """The file lines of a header whose name is on line ``at``."""
        lines = head["places"].split("\n")[1:]
        if lines and head["plus"]:
            message = f"<<{name}>>+= places nothing: put file lines on its ="
            self.findings.append(Finding(self.path, at, "lit-web", message))
            return ()
        out: list[tuple[str, int]] = []
        for k, text in enumerate(lines, 1):
            if m := PLACE.fullmatch(text.strip()):
                out.append((m["path"], int(m["seq"])))
                continue
            message = (
                f"<<{name}>>: {text.strip()!r} is no file line -- write a"
                " path and a place, as fpl/lex.py 3"
            )
            self.findings.append(
                Finding(self.path, at + k, "lit-web", message)
            )
        return tuple(out)


def read(path: str, text: str) -> Page:
    """Read a page's text into sections; ``path`` is how it is named."""
    lines = text.split("\n")
    start, allow, named = front(lines)
    reader = _Reader(path)
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
    return Page(
        path, tuple(reader.sections), allow, tuple(reader.findings), named
    )


def rules(page: Page) -> list[Finding]:
    """The web's own rules: one ``=`` first, every use defined.

    A chunk named like a path, the old way to name a file, is refused.
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
                f"root chunk <<{chunk.name}>>: name the file in front"
                " matter `tangle:` and drop this chunk"
            )
            out.append(_bad(page, chunk.line, message))
        seen.add(chunk.name)
        for k, text in enumerate(chunk.body):
            use = USE.fullmatch(text)
            if use and norm(use["name"]) not in names:
                where = chunk.line + 1 + k
                out.append(_bad(page, where, f"<<{use['name']}>> undefined"))
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


def _imports(lines: list[str]) -> bool:
    """Whether a part holds imports and nothing else but comments."""
    body = _statements(lines)
    return bool(body) and all(
        isinstance(s, ast.Import | ast.ImportFrom) for s in body
    )


def _docstring(lines: list[str]) -> bool:
    """Whether a part's text opens a string, as a docstring does."""
    return "\n".join(lines).lstrip().startswith(('"""', "'''"))


def _gap(before: list[str], after: list[str]) -> int:
    """The blank lines between two parts.

    Two stand around a def or a class at the top, one otherwise.
    """
    ends, opens = _statements(before)[-1:], _statements(after)[:1]
    return 2 if any(isinstance(s, TOP) for s in ends + opens) else 1


def _order(
    loose: list[str],
    placed: dict[int, str],
    lines: Callable[[str], list[str]],
) -> list[str]:
    """A file's parts in their order.

    The loose parts keep page order, but their imports come after the
    docstring, or first; each placed part is then put at its place.
    """
    imports = [n for n in loose if _imports(lines(n))]
    rest = [n for n in loose if n not in imports]
    at = 1 if loose and _docstring(lines(loose[0])) else 0
    out = rest[:at] + imports + rest[at:]
    for seq, name in sorted(placed.items()):
        out.insert(seq - 1, name)
    return out


Files = dict[str, tuple[list[str], dict[int, str]]]


def _files(
    page: Page, tops: list[str]
) -> tuple[Files, dict[str, int], list[Finding]]:
    """Each file a page names, with its loose and its placed parts.

    Also the line that first names each file, and a finding for each
    place two parts share. The placed files come first, in page order;
    then the front matter's file, whose loose parts are the tops not
    placed in it.
    """
    where: dict[str, int] = {}
    placed: dict[str, dict[int, str]] = {}
    bad: list[Finding] = []
    for chunk in page.chunks():
        for path, seq in chunk.places:
            where.setdefault(path, chunk.line)
            seqs = placed.setdefault(path, {})
            if seq in seqs:
                message = (
                    f"<<{seqs[seq]}>> and <<{chunk.name}>> both stand at"
                    f" {path} {seq}"
                )
                bad.append(_bad(page, chunk.line, message))
                continue
            seqs[seq] = chunk.name
    files: Files = {path: ([], seqs) for path, seqs in placed.items()}
    if page.tangle is not None:
        path, line = page.tangle
        where[path] = line
        seqs = placed.get(path, {})
        mine = set(seqs.values())
        files[path] = ([n for n in tops if n not in mine], seqs)
    return files, where, bad


def tangle(page: Page) -> tuple[list[Tangled], list[Finding]]:
    """Every file of the page, its parts expanded; and the findings."""
    findings = rules(page)
    names = page.defined()
    used = {
        norm(m["name"])
        for c in page.chunks()
        for t in c.body
        if (m := USE.fullmatch(t))
    }
    tops = [n for n in names if n not in used and not is_file(n)]
    files, where, bad = _files(page, tops)
    findings += bad
    if names and not files:
        message = "no file: add `tangle: <path>` to the front matter"
        return [], [*findings, _bad(page, 1, message)]
    done: dict[str, _Expander] = {}

    def part(name: str) -> _Expander:
        if name not in done:
            done[name] = ex = _Expander(page)
            ex.expand(name, "", ())
            findings.extend(ex.findings)
        return done[name]

    out: list[Tangled] = []
    for path, (loose, placed) in files.items():
        parts = _order(loose, placed, lambda n: part(n).lines)
        if refused := _refused(page, path, where[path], parts):
            findings.append(refused)
        else:
            out.append(_join(page, path, parts, part))
    reached = {n for ex in done.values() for n in ex.reached}
    for name, chunks in names.items():
        if name not in reached and not is_file(name):
            message = f"<<{name}>> is never used by a file"
            findings.append(_bad(page, chunks[0].line, message))
    return out, findings


def _refused(
    page: Page, path: str, line: int, parts: list[str]
) -> Finding | None:
    """Why a file named on ``line`` is not written, if it is not."""
    if not is_file(path) or {".", ".."} & set(path.split("/")):
        return _bad(page, line, f"{path} is not a path inside the root")
    if not parts:
        message = f"{path} has no parts: every chunk is used by another"
        return _bad(page, line, message)
    return None


def _join(
    page: Page,
    path: str,
    parts: list[str],
    part: Callable[[str], _Expander],
) -> Tangled:
    """A file's parts, expanded, with blank lines between them.

    A blank line comes from the header of the part after it.
    """
    names = page.defined()
    lines: list[str] = []
    origin: list[int] = []
    for k, name in enumerate(parts):
        if k:
            gap = _gap(part(parts[k - 1]).lines, part(name).lines)
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

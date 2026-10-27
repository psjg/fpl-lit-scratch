"""The web: a literate page read into sections and chunks, and tangled.

A page is Markdown. A fence opened by a line that is exactly
```` ```python ```` is a code chunk, and its first line names it::

    <<Name the characters of the pairs>>=     a definition
    <<Name the characters of the pairs>>+=    more of the same chunk
    <<fpl/lex.py>>=                           a file: its name is a path

A line of a chunk that holds only ``<<Name>>`` is a use: the chunk's
lines go there, each indented by the use's indentation. A chunk whose
name is a path (no spaces, a dot before its suffix) is a file root,
written relative to the root directory. Any other fence (``pycon``,
``text``, ``fpl``) is prose. A section is the prose up to and including
one chunk; the prose after the last chunk is a section without one.

The reader is strict: a python fence without a header, a ``+=`` before
its ``=``, a second ``=``, a use of a chunk never defined, a chunk no
file reaches, a cycle and an unclosed fence are each a `Finding` at its
page line, and nothing is guessed. Everything here is pure: a page is
read from its text, and a tangle is a value, written by the caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import override

HEAD = re.compile(r"<<(?P<name>[^<>]+)>>(?P<plus>\+?)=")
USE = re.compile(r"(?P<indent>[ \t]*)<<(?P<name>[^<>]+)>>[ \t]*")
FILE = re.compile(r"[\w.-]+(/[\w.-]+)*\.\w+")
ALLOW = re.compile(r"lit-allow:\s*\[(?P<names>[^\]]*)\]\s*")
CODE = "python"


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
    """A code fence: its name, ``+=`` or not, header line, and body."""

    name: str
    plus: bool
    line: int
    body: tuple[str, ...]


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
    """A literate page: where it is, its sections, its allowlist."""

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

    def section_of(self, line: int) -> int:
        """The number of the section whose chunk holds a page line."""
        for s in self.sections:
            c = s.chunk
            if c is not None and c.line <= line <= c.line + len(c.body):
                return s.number
        return 0


@dataclass(frozen=True)
class Tangled:
    """A file root expanded: its lines, and the page line of each."""

    name: str
    page: str
    lines: tuple[str, ...]
    origin: tuple[int, ...]

    @property
    def text(self) -> str:
        """The file's text, ending in one newline."""
        return "".join(line + "\n" for line in self.lines)


def is_file(name: str) -> bool:
    """Whether a chunk name is a path, and so a file root."""
    return FILE.fullmatch(name) is not None


def norm(name: str) -> str:
    """A chunk name with its runs of white space made one space."""
    return " ".join(name.split())


def front(lines: list[str]) -> tuple[int, frozenset[str]]:
    """Where the body starts after front matter, and its allowlist."""
    if not lines or lines[0] != "---":
        return 0, frozenset()
    allow: set[str] = set()
    for k in range(1, len(lines)):
        if lines[k] == "---":
            return k + 1, frozenset(allow)
        if m := ALLOW.fullmatch(lines[k]):
            allow |= {n.strip() for n in m["names"].split(",") if n.strip()}
    return 0, frozenset()


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
        head = HEAD.fullmatch(body[0].rstrip()) if body else None
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
        self.close(Chunk(name, bool(head["plus"]), at + 1, tuple(body[1:])))


def read(path: str, text: str) -> Page:
    """Read a page's text into sections; ``path`` is how it is named."""
    lines = text.split("\n")
    start, allow = front(lines)
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
    return Page(path, tuple(reader.sections), allow, tuple(reader.findings))


def rules(page: Page) -> list[Finding]:
    """The web's own rules: one ``=`` first, every use defined."""
    out = list(page.findings)
    seen: set[str] = set()
    names = page.defined()
    for chunk in page.chunks():
        if chunk.plus and chunk.name not in seen:
            out.append(_bad(page, chunk.line, f"+= before = of {chunk.name}"))
        if not chunk.plus and chunk.name in seen:
            out.append(_bad(page, chunk.line, f"a second = of {chunk.name}"))
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
    """Expands one file root, recording each chunk it reaches."""

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


def tangle(page: Page) -> tuple[list[Tangled], list[Finding]]:
    """Every file root of the page, expanded; and the web's findings."""
    findings = rules(page)
    reached: set[str] = set()
    out: list[Tangled] = []
    for name, chunks in page.defined().items():
        if not is_file(name):
            continue
        if {".", ".."} & set(name.split("/")):
            message = f"{name} is not a path inside the root"
            findings.append(_bad(page, chunks[0].line, message))
            continue
        ex = _Expander(page)
        ex.expand(name, "", ())
        reached |= ex.reached
        findings += ex.findings
        out.append(Tangled(name, page.path, tuple(ex.lines), tuple(ex.origin)))
    for name, chunks in page.defined().items():
        if name not in reached:
            message = f"<<{name}>> is never used by a file"
            findings.append(_bad(page, chunks[0].line, message))
    return out, findings


def discover(root: Path) -> list[Path]:
    """The literate pages under ``root``: Markdown holding a header."""
    found = re.compile(r"^```python\n<<[^<>]+>>\+?=[ \t]*$", re.MULTILINE)
    return sorted(
        p
        for p in root.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(root).parts)
        and found.search(p.read_text(encoding="utf-8"))
    )

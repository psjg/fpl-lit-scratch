"""The facts: a literate page read as spans, with a text and a hash.

A span is a stretch of one file, ``item[start:end]``, counted in
Unicode code points with the end exclusive, together with the text it
holds. The spans here are generated: nobody types them, and they are
read again from the page whenever they are wanted. Each has a kind:

- **chunk**: a code fence, from its opening line through its closing
  line; labelled with its name, ``root`` when the name is a file, and
  ``skeleton`` when every non-blank line of its body is a use;
- **paragraph**: a run of unfenced prose between blank lines, from its
  first character to its last; a ``pycon`` or ``text`` fence is not
  one;
- **definition**: the page line where the tangled code binds a name,
  labelled with the qualified name; it targets its chunk;
- **example**: a ``pycon`` fence; it targets its section's chunk;
- **refusal**: a row of the table headed ``| Refused | Reported at |
  Message |``, labelled with its message;
- **testrow**: a row of the parametrize table of a refusal test (one
  whose name holds ``_refuses``), in the test file; labelled with the
  expected line, it targets the refusal whose message that line ends
  in;
- **tangle**: a line of the page's first Python file; it targets the
  chunk the line came from.

Ids are stable where the page lets them be and URL-safe throughout:
every name in one is quoted by `quote', so a space or a colon never
stands inside a part. A chunk is ``chunk:<name>:<n>``, its ``n``-th
definition (1 for ``=``, 2 for the first ``+=``); a definition is
``def:<qualified name>``; a refusal is ``refusal:<message>``. Three
kinds are positional, and an inserted neighbour renumbers them: a
paragraph is ``p:<section>:<n>`` and an example ``ex:<section>:<n>``,
the ``n``-th in their section, and a test row ``test:<function>:<n>``;
a tangle line is ``tangle:<file>:<line>``. Every ordinal counts from 1.

The code hash of a span says what code it holds, with layout, comments
and docstrings left out, so that a commit that only rewords them
changes the text of a chunk but not its hash. Each Python file is
tokenized once, whole (a chunk alone is a fragment, and often no
Python); comments, the tokens of line structure that carry no code and
every docstring are dropped, and each token left is put on the page
line it came from. A span's tokens are those on its lines. A chunk
that two files reach takes its tokens from the first.
"""

from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import takewhile
from pathlib import Path
from urllib.parse import quote

from lit import readable, web
from lit.lint import definitions

# The header row of the table of refusals, a data row of it (its last
# cell the message in backticks), and the line a refusal test expects.
HEADER = re.compile(r"\|\s*Refused\s*\|\s*Reported at\s*\|\s*Message\s*\|")
ROW = re.compile(r"\|.*\|\s*`(?P<message>[^`]+)`\s*\|")
ERROR = re.compile(r"ERROR: \d+:\d+ (?P<message>.*)")
# The tokens that carry no code: comments, the newlines inside a
# statement, and the file's two ends.
DROPPED = frozenset(
    {tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER}
)

# The kind of a page span by the head of its id.
KINDS = {
    "chunk": "chunk",
    "p": "paragraph",
    "def": "definition",
    "ex": "example",
    "refusal": "refusal",
}

type Token = tuple[int, str]


@dataclass(frozen=True)
class Span:
    """A stretch of one file, what it holds, and what it points at.

    Attributes:
        id: The span's id, unique among the spans of one page.
        item: The file: the page's path as it was read, or the path
            of a tangled file or a test file.
        start: The first code point of the span in the item's text.
        end: The code point after the span's last.
        text: The text the span holds, ``item_text[start:end]``.
        kind: chunk, paragraph, definition, example, refusal, testrow
            or tangle.
        labels: What the span is called: a chunk's name, a qualified
            name, a message.
        code_hash: The hash of the span's code tokens; empty when it
            holds none.
        targets: The ids of the spans this one points at.
    """

    id: str
    item: str
    start: int
    end: int
    text: str
    kind: str
    labels: tuple[str, ...] = ()
    code_hash: str = ""
    targets: tuple[str, ...] = ()

    def to_row(self) -> dict[str, object]:
        """The span as a row of the annotation program, with no note."""
        return {
            "id": self.id,
            "item": self.item,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "labels": list(self.labels),
            "note": "",
            "targets": list(self.targets),
            "kind": self.kind,
            "codeHash": self.code_hash,
        }


def ident(kind: str, *parts: object) -> str:
    """An id: the kind and each part quoted, joined by colons."""
    return ":".join([kind, *(quote(str(p), safe="") for p in parts)])


def code_hash(tokens: list[Token]) -> str:
    """The first 16 hex digits of the tokens' sha256; empty for none."""
    if not tokens:
        return ""
    return hashlib.sha256(repr(tokens).encode()).hexdigest()[:16]


def docstrings(tree: ast.Module) -> set[tuple[int, int]]:
    """The docstrings of a module's scopes, as token types and lines.

    A docstring is two tokens: its string, on the line it opens, and the
    newline that ends its statement, on the line it closes.
    """
    return {
        pair
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        )
        for first in node.body[:1]
        if isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
        for pair in (
            (tokenize.STRING, first.lineno),
            (tokenize.NEWLINE, first.end_lineno or first.lineno),
        )
    }


def file_tokens(source: str) -> list[tuple[int, Token]]:
    """A Python file's code tokens, each with its line in the file."""
    skip = docstrings(ast.parse(source))
    return [
        (tok.start[0], (tok.type, tok.string))
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type not in DROPPED and (tok.type, tok.start[0]) not in skip
    ]


def page_tokens(files: Sequence[web.Tangled]) -> dict[int, list[Token]]:
    """Each page line's code tokens, from the first file reaching it.

    The dedents that close a file stand on the line after its last; they
    are put on the last line, as the tokenizer would have them.
    """
    out: dict[int, list[Token]] = {}
    claimed: set[int] = set()
    for t in files:
        for line, token in file_tokens(t.text):
            at = t.origin[min(line, len(t.origin)) - 1]
            if at not in claimed:
                out.setdefault(at, []).append(token)
        claimed |= set(t.origin)
    return out


@dataclass(frozen=True)
class Text:
    """A file's text, split into lines, with where each line starts."""

    item: str
    lines: tuple[str, ...]
    starts: tuple[int, ...]

    @classmethod
    def of(cls, item: str, text: str) -> Text:
        """The text of ``item``, its lines numbered from 1."""
        lines = tuple(text.split("\n"))
        starts = [0]
        for line in lines[:-1]:
            starts.append(starts[-1] + len(line) + 1)
        return cls(item, lines, tuple(starts))

    def place(self, first: int, last: int) -> tuple[int, int, str]:
        """Start, end and text of the lines ``first`` to ``last``."""
        start = self.starts[first - 1]
        end = self.starts[last - 1] + len(self.lines[last - 1])
        return start, end, "\n".join(self.lines[first - 1 : last])


@dataclass(frozen=True)
class Web:
    """What every kind of span is read from: one page and its code.

    Attributes:
        page: The page, read.
        text: The page's text, as lines.
        files: The page's Python files, tangled, in page order.
        tokens: Each page line's code tokens.
        chunk_at: Each page line of a chunk, fences included, to the
            chunk's id.
        section_chunk: Each section's number to its chunk's id.
    """

    page: web.Page
    text: Text
    files: tuple[web.Tangled, ...]
    tokens: dict[int, list[Token]]
    chunk_at: dict[int, str]
    section_chunk: dict[int, str]

    def span(
        self,
        sid: str,
        lines: tuple[int, int],
        labels: tuple[str, ...] = (),
        targets: tuple[str, ...] = (),
    ) -> Span:
        """The page's span over ``lines``, first and last both in."""
        first, last = lines
        ours = range(first, last + 1)
        code = code_hash([t for n in ours for t in self.tokens.get(n, [])])
        start, end, text = self.text.place(first, last)
        kind = KINDS[sid.split(":", 1)[0]]
        return Span(
            sid, self.text.item, start, end, text, kind, labels, code, targets
        )


def chunk_ids(page: web.Page) -> Iterator[tuple[int, web.Chunk, str]]:
    """Each chunk with its section's number and its id."""
    seen: dict[str, int] = {}
    for s in page.sections:
        if s.chunk is not None:
            seen[s.chunk.name] = seen.get(s.chunk.name, 0) + 1
            yield (
                s.number,
                s.chunk,
                ident("chunk", s.chunk.name, seen[s.chunk.name]),
            )


def chunks(w: Web) -> Iterator[Span]:
    """Each code fence, from its opening line through its closing."""
    for _, c, sid in chunk_ids(w.page):
        labels = [c.name]
        if web.is_file(c.name):
            labels.append("root")
        if all(web.USE.fullmatch(b) for b in c.body if b.strip()):
            labels.append("skeleton")
        lines = (c.line - 1, c.line + len(c.body) + 1)
        yield w.span(sid, lines, tuple(labels))


def paragraphs(w: Web) -> Iterator[Span]:
    """Each run of unfenced prose lines that holds no blank line."""
    for s in w.page.sections:
        runs: list[list[int]] = []
        last = -1
        for line in s.prose:
            if line.fenced or not line.text.strip():
                continue
            if line.number != last + 1:
                runs.append([])
            runs[-1].append(line.number)
            last = line.number
        for n, run in enumerate(runs, 1):
            yield w.span(ident("p", s.number, n), (run[0], run[-1]))


def defined(w: Web) -> Iterator[Span]:
    """Each name the Python files define, at its page line, once."""
    seen: set[str] = set()
    for t in w.files:
        for d in definitions(ast.parse(t.text)):
            if d.qualified in seen:
                continue
            seen.add(d.qualified)
            at = t.origin[d.line - 1]
            sid = ident("def", d.qualified)
            yield w.span(sid, (at, at), (d.qualified,), (w.chunk_at[at],))


def examples(w: Web) -> Iterator[Span]:
    """Each ``pycon`` fence; it points at its section's chunk."""
    for s in w.page.sections:
        chunk = w.section_chunk.get(s.number)
        targets = (chunk,) if chunk else ()
        for n, e in enumerate(s.examples, 1):
            close = w.text.lines.index("```", e.line)
            yield w.span(
                ident("ex", s.number, n), (e.line, close + 1), (), targets
            )


def refusals(w: Web) -> Iterator[Span]:
    """Each row of the table of refusals: one span per data row.

    The table is the one whose header row is ``| Refused | Reported at
    | Message |``; a row's label is its message, out of its backticks.

    Raises:
        ValueError: A row whose last cell is no message in backticks.
    """
    heads = [
        line.number
        for s in w.page.sections
        for line in s.prose
        if not line.fenced and HEADER.fullmatch(line.text.strip())
    ]
    for head in heads:
        rows = takewhile(lambda x: x.startswith("|"), w.text.lines[head + 1 :])
        for at, row in enumerate(rows, head + 2):
            m = ROW.fullmatch(row.strip())
            if m is None:
                where = f"{w.text.item}:{at}"
                raise ValueError(f"{where}: a refusal row without a message")
            sid = ident("refusal", m["message"])
            yield w.span(sid, (at, at), (m["message"],))


def testrows(
    tests: Mapping[str, str], refused: Mapping[str, str]
) -> Iterator[Span]:
    """Each row of a refusal test's table: the lines of its values.

    A refusal test is a test function whose name holds ``_refuses``,
    and its table names the line it expects ``expected``; a row points
    at the refusal whose message that line ends in, when there is one.
    ``refused`` maps each refusal's message to its id.
    """
    for item, source in tests.items():
        text = Text.of(item, source)
        for fn in ast.parse(source).body:
            if isinstance(fn, ast.FunctionDef) and "_refuses" in fn.name:
                for n, row in enumerate(readable.rows(fn), 1):
                    yield testrow(
                        text, ident("test", fn.name, n), row, refused
                    )


def testrow(
    text: Text, sid: str, row: dict[str, ast.expr], refused: Mapping[str, str]
) -> Span:
    """One row of a refusal test, labelled with the line it expects."""
    expected = str(ast.literal_eval(row["expected"]))
    first = min(v.lineno for v in row.values())
    last = max(v.end_lineno or v.lineno for v in row.values())
    m = ERROR.fullmatch(expected)
    target = refused.get(m["message"], "") if m else ""
    targets = (target,) if target else ()
    start, end, body = text.place(first, last)
    return Span(
        sid, text.item, start, end, body, "testrow", (expected,), "", targets
    )


def tangle(w: Web, root: Path) -> Iterator[Span]:
    """Each line of the page's first Python file, at its chunk."""
    if not w.files:
        return
    t = w.files[0]
    item = (root / t.name).as_posix()
    text = Text.of(item, t.text)
    tokens: dict[int, list[Token]] = {}
    for line, token in file_tokens(t.text):
        tokens.setdefault(line, []).append(token)
    for n, at in enumerate(t.origin, 1):
        start, end, body = text.place(n, n)
        code = code_hash(tokens.get(n, []))
        chunk = (w.chunk_at[at],)
        sid = ident("tangle", item, n)
        yield Span(sid, item, start, end, body, "tangle", (), code, chunk)


def spans(
    page: web.Page, text: str, root: Path, tests: Mapping[str, str]
) -> list[Span]:
    """Every generated span of a page, kind by kind, in page order.

    Args:
        page: The page, read from ``text``.
        text: The page's text.
        root: The directory the page's files are written under; a
            tangled file's item is its path joined to it.
        tests: The page's test files, each path to its source.

    Returns:
        The chunks, paragraphs, definitions, examples, refusals, test
        rows and tangle lines.
    """
    files = tuple(t for t in web.tangle(page)[0] if t.name.endswith(".py"))
    chunk_at: dict[int, str] = {}
    section_chunk: dict[int, str] = {}
    for number, c, sid in chunk_ids(page):
        section_chunk[number] = sid
        chunk_at |= dict.fromkeys(
            range(c.line - 1, c.line + len(c.body) + 2), sid
        )
    w = Web(
        page,
        Text.of(page.path, text),
        files,
        page_tokens(files),
        chunk_at,
        section_chunk,
    )
    refused = list(refusals(w))
    by_message = {s.labels[0]: s.id for s in refused}
    return [
        *chunks(w),
        *paragraphs(w),
        *defined(w),
        *examples(w),
        *refused,
        *testrows(tests, by_message),
        *tangle(w, root),
    ]


def read(path: Path, root: Path) -> list[Span]:
    """The spans of the page at ``path``, its tests under ``root``."""
    text = path.read_text(encoding="utf-8")
    page = web.read(path.as_posix(), text)
    tests = {
        t.as_posix(): t.read_text(encoding="utf-8")
        for t in readable.tests_for(page, root)
    }
    return spans(page, text, root, tests)

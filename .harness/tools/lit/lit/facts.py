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

Beside the generated spans stand two files a person writes. A
decisions ledger ``<page stem>.decisions.tsv`` gives one ``ledger``
span per decision, id ``L-<id>``. A sidecar ``<page stem>.facts.json``
holds hand rows in the annotation program's shape, plus ``targets``
and ``commit``: a span, a fact about rows, or a relation between them.
A hand row's span is immutable, ``item@commit[start, end) = text``;
whether its text is still on the page is computed each time
(`locate'), never written back. Items are paths from the repository.

The annotation program keeps its rows elsewhere, each ``item`` a label
it knows (``A``, ``lex``) rather than a path. `imported' turns its
rows for one label into hand rows on one page at one commit, `merged'
folds them into a sidecar, and `exported' is the way back.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import tokenize
from collections import Counter
from collections.abc import (
    Callable,
    Collection,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import suppress
from dataclasses import dataclass
from itertools import takewhile
from pathlib import Path
from textwrap import dedent
from typing import cast
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


def code_tokens(source: str) -> list[tokenize.TokenInfo]:
    """A Python file's code tokens, with where each starts and ends."""
    skip = docstrings(ast.parse(source))
    return [
        tok
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type not in DROPPED and (tok.type, tok.start[0]) not in skip
    ]


def file_tokens(source: str) -> list[tuple[int, Token]]:
    """A Python file's code tokens, each with its line in the file."""
    return [
        (tok.start[0], (tok.type, tok.string)) for tok in code_tokens(source)
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

    @classmethod
    def of(cls, page: web.Page, text: str) -> Web:
        """The page read from ``text``, its Python files tangled."""
        files = tuple(t for t in web.tangle(page)[0] if t.name.endswith(".py"))
        chunk_at: dict[int, str] = {}
        section_chunk: dict[int, str] = {}
        for number, c, sid in chunk_ids(page):
            section_chunk[number] = sid
            chunk_at |= dict.fromkeys(
                range(c.line - 1, c.line + len(c.body) + 2), sid
            )
        return cls(
            page,
            Text.of(page.path, text),
            files,
            page_tokens(files),
            chunk_at,
            section_chunk,
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
    return kinds(Web.of(page, text), root, tests)


def kinds(w: Web, root: Path, tests: Mapping[str, str]) -> list[Span]:
    """The spans of `spans', read from a page already tangled."""
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


# The hand-written rows: a sidecar ``<page>.facts.json`` beside a page.

type Row = dict[str, object]
# A code token on the page: its first code point, the code point after
# its last, and the token.
type Placed = tuple[int, int, Token]

# The tokens of line structure. A fragment's indentation never matches
# the whole file's, so a match by tokens leaves them out on both sides.
LAYOUT = frozenset({tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT})
# A hand-written id, a ledger id, a commit, a ledger date.
NAME = re.compile(r"[A-Za-z0-9._-]+")
COMMIT = re.compile(r"[0-9a-f]{40}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# A code point JavaScript counts as two: offsets would differ there.
ASTRAL = re.compile("[\U00010000-\U0010ffff]")
# The keys of a hand row, each with the one type its value has; the
# four that ground a span; the columns of a decisions ledger.
FIELDS: dict[str, type] = {
    "id": str,
    "item": str,
    "start": int,
    "end": int,
    "text": str,
    "labels": list,
    "note": str,
    "targets": list,
    "commit": str,
    "createdAt": int,
    "updatedAt": int,
}
SPAN = ("item", "start", "end", "text")
COLUMNS = ("id", "topic", "date", "who", "decision", "reason")
VERS, MOVED, TWICE, STALE = "vers", "verplaatst", "dubbel", "stale"


def top(root: Path) -> Path:
    """The repository holding ``root``: the nearest ``.git`` above it.

    Items are paths from there, as okfgraph reads them, whatever the
    directory lit runs in.

    Raises:
        ValueError: No directory at or above ``root`` holds ``.git``.
    """
    here = root.resolve()
    for d in (here, *here.parents):
        if (d / ".git").exists():
            return d
    raise ValueError(f"{root}: no .git at or above it")


def astral(path: str, text: str) -> list[web.Finding]:
    """The first code point above U+FFFF on a page, if there is one."""
    m = ASTRAL.search(text)
    if m is None:
        return []
    line = text.count("\n", 0, m.start()) + 1
    message = (
        f"U+{ord(m[0]):X} is two code units in JavaScript, so the"
        " annotation program's offsets would differ from lit's -- write"
        " it as an entity or a name"
    )
    return [web.Finding(path, line, "lit-facts-astral", message)]


def offset(w: Web, t: web.Tangled, at: tuple[int, int]) -> int:
    """The page code point of a line and column of a tangled file.

    A tangled line is its page line behind the use's indentation
    (``web.expand``), so the column, less that indentation, is one on
    the page line.
    """
    line, col = at
    page = t.origin[line - 1]
    shift = len(t.lines[line - 1]) - len(w.text.lines[page - 1])
    return w.text.starts[page - 1] + col - shift


def stream(w: Web) -> list[Placed]:
    """Each code token of the page at its code points, in page order.

    Layout is left out, and a chunk two files reach takes its tokens
    from the first, as in `page_tokens'.
    """
    out: list[Placed] = []
    claimed: set[int] = set()
    for t in w.files:
        out += [
            (offset(w, t, tok.start), offset(w, t, tok.end), token)
            for tok in code_tokens(t.text)
            if tok.type not in LAYOUT
            and t.origin[tok.start[0] - 1] not in claimed
            for token in [(tok.type, tok.string)]
        ]
        claimed |= set(t.origin)
    return sorted(out)


def fragment(text: str) -> list[Placed]:
    """The code tokens of a row's text, at code points of that text.

    A row may cut a statement in half (``return pairs(src,``), and no
    tokenizer reads past the cut: the tokens are those read before it.
    A docstring is left out when the text, dedented, parses, so that
    a row over a docstring alone holds no tokens.
    """
    skip: set[tuple[int, int]] = set()
    with suppress(SyntaxError):
        skip = docstrings(ast.parse(dedent(text)))
    starts = Text.of("", text).starts
    out: list[Placed] = []
    with suppress(tokenize.TokenError, SyntaxError):
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if (
                tok.type not in DROPPED | LAYOUT
                and (tok.type, tok.start[0]) not in skip
            ):
                first = starts[tok.start[0] - 1] + tok.start[1]
                last = starts[tok.end[0] - 1] + tok.end[1]
                out.append((first, last, (tok.type, tok.string)))
    return out


@dataclass(frozen=True)
class Located:
    """Where a hand row's text is on the current page, if anywhere.

    Attributes:
        state: vers, verplaatst, dubbel or stale.
        start: The row's first code point now; None unless found once.
        end: The code point after its last now; None unless found once.
    """

    state: str
    start: int | None = None
    end: int | None = None


def locate(
    row: Row,
    text: str,
    tokens: Sequence[Placed],
    chunks: Sequence[tuple[int, int]],
) -> Located:
    """Where a valid hand row's text is in the current ``text``.

    A row is code when its ``[start, end)`` lies inside a chunk span
    of ``chunks`` and its text holds code tokens (`fragment'); then
    its token sequence is matched against the page's ``tokens``, so
    that a docstring or comment edit around the code leaves it found.
    Otherwise its text is searched for.

    ==========================  ====================================
    found                       state and current offsets
    ==========================  ====================================
    text at ``[start, end)``    vers, the same offsets
    code: tokens once           vers, the match widened by what the
                                row holds around its first and last
                                token
    code: tokens twice or more  dubbel
    code: tokens nowhere        stale
    text once elsewhere         verplaatst, the new offsets
    text twice or more          dubbel
    text nowhere                stale
    ==========================  ====================================
    """
    start, end = cast("int", row["start"]), cast("int", row["end"])
    want = cast("str", row["text"])
    if text[start:end] == want:
        return Located(VERS, start, end)
    inside = any(a <= start and end <= b for a, b in chunks)
    mine = fragment(want) if inside else []
    return by_tokens(mine, want, tokens) if mine else by_text(want, text)


def by_text(want: str, text: str) -> Located:
    """A row found by its text alone."""
    first = text.find(want)
    if first < 0:
        return Located(STALE)
    if text.find(want, first + 1) >= 0:
        return Located(TWICE)
    return Located(MOVED, first, first + len(want))


def by_tokens(
    mine: Sequence[Placed], want: str, tokens: Sequence[Placed]
) -> Located:
    """A code row found by its token sequence among the page's."""
    seq = [t for _, _, t in mine]
    page = [t for _, _, t in tokens]
    k = len(seq)
    hits = [
        i
        for i in range(len(page) - k + 1)
        if page[i] == seq[0] and page[i : i + k] == seq
    ]
    if not hits:
        return Located(STALE)
    if len(hits) > 1:
        return Located(TWICE)
    i = hits[0]
    start = tokens[i][0] - mine[0][0]
    end = tokens[i + k - 1][1] + len(want) - mine[-1][1]
    return Located(VERS, start, end)


def unique(items: list[tuple[str, object]]) -> Row:
    """A JSON object whose keys are each written once."""
    out = dict(items)
    if len(out) != len(items):
        raise ValueError("a row holds a key twice")
    return out


def constant(name: str) -> object:
    """No ``NaN`` or ``Infinity``: JSON has no such number."""
    raise ValueError(f"{name} is no JSON number")


def loads(text: str) -> object:
    """A JSON text read strictly: no key twice, no ``NaN``.

    Raises:
        ValueError: Not JSON, a key twice in an object, or ``NaN``.
    """
    data: object = json.loads(
        text, object_pairs_hook=unique, parse_constant=constant
    )
    return data


def read_rows(text: str) -> list[Row]:
    """A sidecar's rows: a bare JSON array of objects, read strictly.

    Raises:
        ValueError: Not JSON, a key twice in a row, ``NaN``, or not
            an array of objects.
    """
    data = loads(text)
    if not isinstance(data, list):
        raise ValueError("not a JSON array of objects")
    rows = cast("list[object]", data)
    if not all(isinstance(r, dict) for r in rows):
        raise ValueError("not a JSON array of objects")
    return cast("list[Row]", rows)


def strings(value: object) -> bool:
    """Whether a value is a list of strings."""
    return isinstance(value, list) and all(
        isinstance(v, str) for v in cast("list[object]", value)
    )


def id_faults(row: Row, ids: Counter[object]) -> Iterator[str]:
    """What is wrong with a row's id."""
    rid = row.get("id")
    if not isinstance(rid, str):
        yield "a row needs a string id"
    elif not NAME.fullmatch(rid):
        yield f"id {rid!r} holds a character outside [A-Za-z0-9._-]"
    elif ids[rid] > 1:
        yield f"id {rid!r} names {ids[rid]} rows"


def field_faults(row: Row) -> Iterator[str]:
    """Unknown keys, and values of the wrong type outside a span."""
    for key, value in row.items():
        want = FIELDS.get(key)
        if want is None:
            yield f"{key!r} is no key of a row"
        elif key in {"labels", "targets"} and not strings(value):
            yield f"{key} must be a list of strings"
        elif key in {"note", "commit", "createdAt", "updatedAt"} and (
            type(value) is not want
        ):
            yield f"{key} must be a {want.__name__}"
        elif key == "commit" and not COMMIT.fullmatch(cast("str", value)):
            yield f"commit {value!r} is not a full 40-hex commit"


def span_shape(row: Row) -> str:
    """What makes a row's span no span, or ``""``."""
    if not all(k in row for k in SPAN):
        return "a span needs item, start, end and text together"
    start, end = row["start"], row["end"]
    if type(start) is not int or type(end) is not int:
        return "start and end must be integers"
    if start >= end:
        return f"start {start} is not before end {end}"
    if not isinstance(row["item"], str) or not isinstance(row["text"], str):
        return "item and text must be strings"
    return ""


def span_faults(row: Row, texts: Mapping[str, str]) -> Iterator[str]:
    """What is wrong with a row's span; nothing for a row without one.

    A row with a commit is grounded there, and `lit anchor --verify'
    checks it; one without is grounded in the current text.
    """
    if not any(k in row for k in SPAN):
        return
    if shape := span_shape(row):
        yield shape
        return
    item = cast("str", row["item"])
    if item not in texts:
        yield f"item {item!r} is neither the page nor a file of the repo"
    elif "commit" not in row:
        start, end = cast("int", row["start"]), cast("int", row["end"])
        if texts[item][start:end] != row["text"]:
            yield f"text is not at [{start}, {end}) of {item}"


def target_faults(row: Row, names: Collection[str]) -> Iterator[str]:
    """Each target that names no row, generated span or ledger row."""
    targets = row.get("targets", [])
    if strings(targets):
        for t in cast("list[str]", targets):
            if t not in names:
                yield f"target {t!r} names nothing"


def validate(
    rows: list[Row],
    where: str,
    texts: Mapping[str, str],
    known: Collection[str],
) -> list[web.Finding]:
    """The findings of a sidecar's rows, each at its row's number.

    Args:
        rows: The rows, as `read_rows' read them.
        where: The sidecar's path, the place of every finding.
        texts: The text of each item a row may name: the page, and
            each file of the repo a row names.
        known: The ids of the page's generated spans and ledger rows.

    Returns:
        ``lit-facts-id``, ``lit-facts-field``, ``lit-facts-span`` and
        ``lit-facts-target`` findings, row by row.
    """
    ids: Counter[object] = Counter(r.get("id") for r in rows)
    names = {i for i in ids if isinstance(i, str)} | set(known)
    out: list[web.Finding] = []
    for n, row in enumerate(rows, 1):
        for rule, faults in (
            ("lit-facts-id", id_faults(row, ids)),
            ("lit-facts-field", field_faults(row)),
            ("lit-facts-span", span_faults(row, texts)),
            ("lit-facts-target", target_faults(row, names)),
        ):
            out += [web.Finding(where, n, rule, m) for m in faults]
    return out


def ledger_fault(row: dict[str, str], seen: set[str]) -> str:
    """What is wrong with one row of a ledger, or ``""``."""
    if not NAME.fullmatch(row["id"]) or row["id"] in seen:
        return f"id {row['id']!r} is no new [A-Za-z0-9._-] id"
    if not DATE.fullmatch(row["date"]):
        return f"date {row['date']!r} is no YYYY-MM-DD"
    if not all(row[c] for c in COLUMNS[1:5]):
        return "only the reason may be empty"
    return ""


def ledger_rows(
    text: str,
) -> tuple[list[dict[str, str]], list[tuple[int, str]]]:
    """A decisions ledger's rows, or each line that is no row.

    The ledger is tab separated, its first line the header ``id topic
    date who decision reason``, every line six cells, the last line
    ended by a newline; only the reason may be empty. A ledger with a
    fault yields no rows, so a row's line is always its index plus 2.
    """
    lines = text.split("\n")
    if lines[-1]:
        return [], [(len(lines), "the last line has no newline")]
    if lines[0] != "\t".join(COLUMNS):
        return [], [(1, "the header must be " + " ".join(COLUMNS))]
    rows: list[dict[str, str]] = []
    bad: list[tuple[int, str]] = []
    for n, line in enumerate(lines[1:-1], 2):
        cells = line.split("\t")
        if len(cells) != len(COLUMNS):
            bad.append((n, f"{len(cells)} cells, not {len(COLUMNS)}"))
            continue
        row: dict[str, str] = dict(zip(COLUMNS, cells, strict=True))
        if fault := ledger_fault(row, {r["id"] for r in rows}):
            bad.append((n, fault))
        rows.append(row)
    return ([], bad) if bad else (rows, [])


def ledger(text: str, item: str) -> tuple[list[Row], list[web.Finding]]:
    """A ledger's rows as generated spans, or its findings.

    A row's span is its decision cell, its id ``L-<id>``, its labels
    the topic, who and date, its note the reason.
    """
    rows, bad = ledger_rows(text)
    starts = Text.of(item, text).starts
    out: list[Row] = []
    for n, r in enumerate(rows, 2):
        at = starts[n - 1] + sum(len(r[c]) + 1 for c in COLUMNS[:4])
        out.append(
            {
                "id": "L-" + r["id"],
                "item": item,
                "start": at,
                "end": at + len(r["decision"]),
                "text": r["decision"],
                "labels": [r["topic"], r["who"], r["date"]],
                "note": r["reason"],
                "targets": [],
                "kind": "ledger",
                "codeHash": "",
            }
        )
    return out, [web.Finding(item, n, "lit-facts-ledger", m) for n, m in bad]


@dataclass(frozen=True)
class Here:
    """A page as its hand rows are read against it.

    Attributes:
        repo: The repository; items are paths from it.
        page: The page's item.
        text: The page's text.
        tokens: The page's code tokens, placed.
        chunks: The start and end of each chunk span.
        known: The ids of the generated spans and ledger rows.
    """

    repo: Path
    page: str
    text: str
    tokens: list[Placed]
    chunks: list[tuple[int, int]]
    known: frozenset[str]

    def texts(self, rows: list[Row]) -> dict[str, str]:
        """The text of the page and of each file of the repo named."""
        out = {self.page: self.text}
        for row in rows:
            item = row.get("item")
            if isinstance(item, str) and item not in out:
                path = (self.repo / item).resolve()
                if path.is_relative_to(self.repo) and path.is_file():
                    out[item] = path.read_text(encoding="utf-8")
        return out

    def place(self, row: Row, texts: Mapping[str, str]) -> Row:
        """A valid row with its state and current offsets added."""
        item = row.get("item")
        if not isinstance(item, str):
            return dict(row)
        if item == self.page:
            found = locate(row, self.text, self.tokens, self.chunks)
        else:
            found = locate(row, texts[item], [], [])
        out = dict(row, state=found.state)
        if found.start is not None:
            out |= {"currentStart": found.start, "currentEnd": found.end}
        return out

    def hand(
        self, text: str, where: str
    ) -> tuple[list[Row], list[web.Finding]]:
        """A sidecar's rows located, or its findings and no rows."""
        try:
            rows = read_rows(text)
        except ValueError as e:
            return [], [web.Finding(where, 1, "lit-facts-json", str(e))]
        texts = self.texts(rows)
        bad = validate(rows, where, texts, self.known)
        if bad:
            return [], bad
        return [self.place(r, texts) for r in rows], []


def generate(path: Path, root: Path) -> tuple[list[Row], list[web.Finding]]:
    """A page's fact layer: every generated span and each hand row.

    The rows are the spans of `spans', the ledger's rows when
    ``<page stem>.decisions.tsv`` lies beside the page, and each row of
    ``<page stem>.facts.json`` beside it, located (`locate'): a copy
    with ``state`` and, when found once, ``currentStart`` and
    ``currentEnd``; ``start`` and ``end`` stay as written. Every item
    is a path from the repository (`top'). The sidecar itself is never
    written.

    Args:
        path: The page.
        root: The directory the page's files are written under.

    Returns:
        The rows, and the findings of the page, the ledger and the
        sidecar; a sidecar with a finding adds no rows.
    """
    repo = top(root)

    def name(p: Path) -> str:
        return p.resolve().relative_to(repo).as_posix()

    text = path.read_text(encoding="utf-8")
    page = web.read(name(path), text)
    tests = {
        name(t): t.read_text(encoding="utf-8")
        for t in readable.tests_for(page, root)
    }
    w = Web.of(page, text)
    rows = [s.to_row() for s in kinds(w, Path(name(root)), tests)]
    findings = astral(page.path, text)
    tsv = path.with_suffix(".decisions.tsv")
    if tsv.is_file():
        led, bad = ledger(tsv.read_text(encoding="utf-8"), name(tsv))
        rows += led
        findings += bad
    car = path.with_suffix(".facts.json")
    if car.is_file():
        here = Here(
            repo,
            page.path,
            text,
            stream(w),
            [
                (cast("int", r["start"]), cast("int", r["end"]))
                for r in rows
                if r["kind"] == "chunk"
            ],
            frozenset(cast("str", r["id"]) for r in rows),
        )
        hand, bad = here.hand(car.read_text(encoding="utf-8"), name(car))
        rows += hand
        findings += bad
    return rows, findings


def ground(
    rows: list[Row], where: str, held: Callable[[str, str], str | None]
) -> list[web.Finding]:
    """Each valid row with a commit whose text was not at its place.

    ``held(commit, item)`` is the item's text at the commit, or None
    when the commit does not hold it; the shell asks git.
    """
    out: list[web.Finding] = []
    for n, row in enumerate(rows, 1):
        commit = row.get("commit")
        if not isinstance(commit, str) or "item" not in row:
            continue
        item = cast("str", row["item"])
        start, end = cast("int", row["start"]), cast("int", row["end"])
        then = held(commit, item)
        if then is None:
            message = f"{commit} holds no {item}"
        elif then[start:end] != row["text"]:
            message = f"text is not at [{start}, {end}) of {item}@{commit}"
        else:
            continue
        out.append(web.Finding(where, n, "lit-facts-ground", message))
    return out


# The keys a row of the annotation program may carry over, besides
# its id and its span, in the order a sidecar row writes them.
TOOL_KEYS = ("labels", "note", "targets", "createdAt", "updatedAt")


@dataclass(frozen=True)
class Tool:
    """A row of the annotation program, at the place it was read.

    Attributes:
        where: The file it was read from.
        number: Its number there: 1-based in an array, 1 in a file of
            one row.
        row: The row, out of its export envelope.
    """

    where: str
    number: int
    row: Row


def envelope(value: object) -> Row:
    """A row out of its export envelope: ``data`` when present.

    Raises:
        ValueError: The value, or its ``data``, is no object.
    """
    if isinstance(value, dict) and "data" in value:
        value = cast("Row", value)["data"]
    if not isinstance(value, dict):
        raise ValueError("a row is no JSON object")
    return cast("Row", value)


def tool_rows(where: str, text: str, *, array: bool) -> list[Tool]:
    """The rows of one file of the annotation program's export.

    The program exports either one file holding a JSON array of rows
    (``array``) or a directory of files holding one row each. A row
    may stand in its envelope ``{"id", "data", "version",
    "updatedAt"}``, and then its ``data`` is the row.

    Args:
        where: The file's name, the place of its rows.
        text: The file's text, read strictly (`loads').
        array: Whether the file is an array of rows.

    Raises:
        ValueError: No JSON, an array file that holds no array, or a
            row that is no object.
    """
    data = loads(text)
    if not array:
        return [Tool(where, 1, envelope(data))]
    if not isinstance(data, list):
        raise ValueError("not a JSON array of rows")
    items = cast("list[object]", data)
    return [Tool(where, n, envelope(v)) for n, v in enumerate(items, 1)]


def import_faults(row: Row, seen: set[str]) -> Iterator[str]:
    """Why a row of the program cannot become a hand row, if it can't.

    Its id must be a new string, its offsets integers, its text one
    without astral code points (JavaScript counts those as two, so the
    program's offsets would not be lit's), and its times integers,
    since the new rows are ordered by them.
    """
    rid, text = row.get("id"), row["text"]
    if not isinstance(rid, str) or rid in seen:
        yield f"id {rid!r} is no new string"
    if type(row["start"]) is not int or type(row["end"]) is not int:
        yield "start and end must be integers"
    if not isinstance(text, str):
        yield "text must be a string"
    elif m := ASTRAL.search(text):
        yield f"text holds U+{ord(m[0]):X}, two code units in JavaScript"
    for key in ("createdAt", "updatedAt"):
        if key in row and type(row[key]) is not int:
            yield f"{key} must be an integer"


def imported(
    rows: Sequence[Tool], label: str, page: str, commit: str
) -> tuple[list[Row], list[web.Finding]]:
    """The program's rows for one label as hand rows on a page.

    A row is the label's when its ``item`` is ``label`` and it holds
    ``start``, ``end`` and ``text``; every other row (another item,
    the program's own records of labels and items) is passed over. A
    row of the label becomes ``{id, item: page, start, end, text,
    labels, note, targets, commit, createdAt, updatedAt}``: its
    ``targets`` are ``[]`` when it has none, and ``labels``, ``note``
    and the times are carried only when it has them.

    Returns:
        The hand rows, and a ``lit-facts-import`` finding for each row
        refused (`import_faults'), at its place.
    """
    out: list[Row] = []
    bad: list[web.Finding] = []
    seen: set[str] = set()
    for t in rows:
        d = t.row
        if d.get("item") != label or not all(k in d for k in SPAN[1:]):
            continue
        if faults := list(import_faults(d, seen)):
            bad += [
                web.Finding(t.where, t.number, "lit-facts-import", m)
                for m in faults
            ]
            continue
        rid = cast("str", d["id"])
        seen.add(rid)
        row: Row = {"id": rid, "item": page}
        row |= {k: d[k] for k in SPAN[1:]}
        row |= {k: d[k] for k in TOOL_KEYS[:2] if k in d}
        row |= {"targets": d.get("targets", []), "commit": commit}
        row |= {k: d[k] for k in TOOL_KEYS[3:] if k in d}
        out.append(row)
    return out, bad


def created(row: Row) -> int:
    """When a valid imported row was made; 0 when it does not say."""
    return cast("int", row.get("createdAt", 0))


def merged(old: Sequence[Row], new: Sequence[Row]) -> tuple[list[Row], int]:
    """A sidecar's rows with the imported ``new`` folded in.

    A new row whose id an old row has takes that row's place; every
    other old row stays where it is; the remaining new rows follow,
    ordered by ``createdAt`` (a row without one first, ties in the
    order read).

    Returns:
        The rows, and how many old rows were replaced.
    """
    by = {cast("str", r["id"]): r for r in new}
    out: list[Row] = []
    for r in old:
        rid = r.get("id")
        out.append(by.pop(rid) if isinstance(rid, str) and rid in by else r)
    rest = sorted(by.values(), key=created)
    return out + rest, len(new) - len(rest)


def exported(
    rows: Sequence[Row], labels: Mapping[tuple[str, str], str]
) -> list[Row]:
    """A sidecar's span rows in the annotation program's shape.

    Each row with a span becomes ``{id, item, start, end, text}`` and
    whichever of ``labels``, ``note``, ``targets``, ``createdAt`` and
    ``updatedAt`` it holds; its ``commit`` is dropped. Its ``item`` is
    the program's label for ``(item, commit)`` in ``labels``, or the
    path itself when none is given. Rows without a span (facts,
    relations) stay behind: the program has no place for them yet.
    """
    out: list[Row] = []
    for r in rows:
        if not all(k in r for k in SPAN):
            continue
        at = (cast("str", r["item"]), cast("str", r.get("commit", "")))
        row: Row = {"id": r["id"], "item": labels.get(at, at[0])}
        row |= {k: r[k] for k in (*SPAN[1:], *TOOL_KEYS) if k in r}
        out.append(row)
    return out

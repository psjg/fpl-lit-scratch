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

A hand row may name its span by a quote instead of offsets: ``item``,
``text`` and, beside them, a ``prefix`` and a ``suffix`` (the W3C Web
Annotation's text quote), as a selection on the published page gives
them. That page is the markdown rendered, and shows text the markdown
writes otherwise; `plain' reads both as the same text, and `by_quote'
finds the quote's raw offsets through it.

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
from bisect import bisect_left
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
from functools import cache
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
                range(c.line - c.head, c.line + len(c.body) + 2), sid
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
        lines = (c.line - c.head, c.line + len(c.body) + 1)
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
    "prefix": str,
    "suffix": str,
    "labels": list,
    "note": str,
    "targets": list,
    "commit": str,
    "by": str,
    "weight": int,
    "shares": dict,
    "proposal": str,
    "createdAt": int,
    "updatedAt": int,
}
SPAN = ("item", "start", "end", "text")
QUOTE = ("prefix", "suffix")
# The two times of a row, in milliseconds since the epoch.
STAMPS = ("createdAt", "updatedAt")
# The labels that make a row a relation, its targets read from -> to.
# Two of them argue, after the Argument Interchange Format (Chesnevar
# et al. 2006): a claim never points at a claim, a ``supports`` or
# ``attacks`` row stands between them, and since that row has an id of
# its own an ``attacks`` row may aim at it (an undercut: the inference
# is attacked, not its premise or its conclusion).
ARGUING = frozenset({"supports", "attacks"})
# How much an arguing row bears, 1 to 5 (Kialo's impact): a reader's
# judgement of the inference, kept on the row that stands for it.
WEIGHTS = range(1, 6)
# A reason's share (PSJ 2026-11-02: ``slop/writing/{filler:0.7,
# isnotxisy:0.1}``): ``shares`` maps some of a row's own labels to a
# number above 0 and at most 1, all of them together at most 1, a soft
# label as a distribution over its reasons. The brace form is only
# typed; a row holds the labels written out and the map beside them.
# A ``proposal`` is the text a span's ``text`` would become (board
# V5d); a row whose first label is a DECISION settles one, its only
# target that row: ``adopts`` takes it over, ``keeps`` leaves the text
# as it stands and says why in a label after it.
DECISIONS = frozenset({"adopts", "keeps"})
# A clause that takes up an earlier one (Danes 1974, thematic
# progression): ``targets[0]``, the bound clause, -> ``targets[1]``.
RESUMES = "resumes"
# The neutral link: two ends joined with no stance, what the overlay's
# knob writes when its reader picks "verbindt", and what a kind may
# replace later.
RELATES = "relates"
RELATIONS = ARGUING | {
    "because",
    "contradicts",
    "supersedes",
    "checkedBy",
    "cites",
    RELATES,
    RESUMES,
}
# Rows that group rather than point. ``coref`` is Mueller (2005)'s set
# relation, undirected and transitive: its targets name one referent.
# ``parts`` holds what Mueller keeps as a span of several token ranges:
# its targets, spans, are the pieces of one discontinuous span, and a
# row about that span names the ``parts`` row; a piece may itself be a
# ``parts`` row, a tree with one whole per piece. Both are read and
# gated here, and the overlay draws a ``parts`` row as one span.
# ``group`` is a set a reader names, ``group/<naam>`` its first label:
# rows put together as one thing (a frame in the graph, a chip on each
# card), with at most one ``role/<rol>`` (claim, bewijs, tegen: free,
# as every label) and one ``order/<n>``, its place among the groups.
# ``group/gepakt`` is the tray of pulled sentences, a group without a
# role. A group may hold one member, as the tray may hold one sentence.
GROUP = "group"
SETS = frozenset({"coref", "parts", GROUP})
# The tray of pulled sentences: a group like any other, without a role.
TRAY = "group/gepakt"
# A group's place among the groups, as the chain length is written.
ORDER = re.compile(r"order/[1-9][0-9]*")
# Topic-focus articulation as the Prague t-layer marks it (Mikulova et
# al. 2006, ch. 10): one value per unit, ``t`` contextually bound, ``c``
# bound and contrastive, ``f`` not bound; topic and focus as wholes
# follow from these and from the order, and are not marked.
TFA = frozenset({"tfa/t", "tfa/c", "tfa/f"})
# A label: a name, or a name scoped by names (``fn/claim``,
# ``slop/beeld/dood``), to any depth; no segment empty or holding space.
# Labels are free, after Marshall (1997: no fixed palette; 1994: types
# arise from use): their shape is gated, and of their vocabulary only
# the reserved kinds (a relation or set as the first label, the
# ``tfa/`` scope), which the gates below read. Whitespace is spelt
# out, so that the overlay's pattern accepts exactly the same labels.
# A brace is no part of a label: ``a/{b:0.7}`` is typed, never kept.
LABEL = re.compile(r"[^/{} \t\n\r\f\v]+(?:/[^/{} \t\n\r\f\v]+)*")
# An address essay.lua gives a block, sentence or clause, under the
# path of its heading: ``[<heading>/.../]b<n>[s<n>[c<n>]]``, each number
# from 1. lit does not number the page, so a target of this shape is
# taken here and resolved by the page.
ADDRESS = re.compile(
    r"(?:[^/\s]+/)*" r"b[1-9]\d*" r"(?:s[1-9]\d*(?:c[1-9]\d*)?)?"
)
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

    A quote row (no offsets) is found by `by_quote'.
    """
    if "start" not in row:
        return by_quote(row, text)
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


# What the published page writes otherwise than its markdown, one
# group per difference (see `plain'); the alias is the one rewrite the
# site's ``.qmd`` copy of a page makes before it is rendered.
MARKUP = re.compile(
    r"`(?P<alias>[A-Za-z_][\w.]*)'"
    r"|(?P<tick>`)"
    r"|(?P<curly>\u2019)"
    r"|(?P<open>\[)(?=[^\]\n]*\]\()"
    r"|(?P<url>\]\([^)\s]*\))"
    r"|(?m:^)(?P<head>#+[ \t]+)"
    r"|(?P<space>[\s|]+)"
)
# The text each group leaves; one not named here leaves nothing.
SHOWN = {"curly": "'", "space": " "}


@cache
def plain(text: str) -> tuple[str, tuple[int, ...]]:
    """A text as the published page shows it, and where each char was.

    Markdown and the page it renders write the same sentence apart in
    a few ways; both sides read through this one function become the
    same string:

    =========================  ===========================
    written                    read as
    =========================  ===========================
    `` `name' `` (an alias)    ``name``
    a backtick                 nothing
    U+2019 (Pandoc's ``'``)    ``'``
    ``[text](url)``            ``text``
    ``#`` opening a heading    nothing, with its spaces
    spaces, newlines, ``|``    one space
    =========================  ===========================

    Returns:
        The plain text, and for each of its characters the code point
        of ``text`` it was read from: a run of space at its first, an
        alias's name at its own. The map strictly increases, so a hit
        at ``[i, j)`` is ``text[at[i] : at[j - 1] + 1]``.
    """
    out: list[str] = []
    at: list[int] = []
    last = 0
    for m in MARKUP.finditer(text):
        out.append(text[last : m.start()])
        at += range(last, m.start())
        last = m.end()
        kind = cast("str", m.lastgroup)
        if kind == "alias":
            shown, first = m["alias"], m.start("alias")
        else:
            shown, first = SHOWN.get(kind, ""), m.start()
        out.append(shown)
        at += range(first, first + len(shown))
    out.append(text[last:])
    at += range(last, len(text))
    return "".join(out), tuple(at)


def hits(page: str, want: str) -> Iterator[int]:
    """Every place ``want`` starts in ``page``, overlaps included."""
    i = page.find(want)
    while i >= 0:
        yield i
        i = page.find(want, i + 1)


def by_quote(row: Row, text: str) -> Located:
    """A quote row found in the page as it is shown (`plain').

    The quote's ``text`` is searched for in the plain page. Of several
    hits, those stay that its ``prefix`` ends right before and its
    ``suffix`` starts right after, each as plain text, whichever the
    row carries. There are no written offsets to compare, so a quote
    found once is vers, at the raw offsets of its first and last
    character; found more than once it is dubbel, and nowhere stale.
    """
    page, at = plain(text)
    want = plain(cast("str", row["text"]))[0]
    found = list(hits(page, want))
    if len(found) > 1:
        before = plain(cast("str", row.get("prefix", "")))[0]
        after = plain(cast("str", row.get("suffix", "")))[0]
        found = [
            i
            for i in found
            if page.endswith(before, 0, i)
            and page.startswith(after, i + len(want))
        ]
    if not found:
        return Located(STALE)
    if len(found) > 1:
        return Located(TWICE)
    i = found[0]
    return Located(VERS, at[i], at[i + len(want) - 1] + 1)


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
        elif key == "labels" and (
            odd := [
                x for x in cast("list[str]", value) if not LABEL.fullmatch(x)
            ]
        ):
            yield f"label {odd[0]!r} is no name/scope/... path"
        elif key in {"note", "commit", "by", "weight", *QUOTE, *STAMPS} and (
            type(value) is not want
        ):
            yield f"{key} must be a {want.__name__}"
        elif key == "commit" and not COMMIT.fullmatch(cast("str", value)):
            yield f"commit {value!r} is not a full 40-hex commit"


def reason_shape(row: Row) -> Iterator[str]:
    """A row's shares or proposal out of shape."""
    if "shares" in row:
        yield from share_faults(row)
    if "proposal" in row and (
        not isinstance(row["proposal"], str) or "text" not in row
    ):
        yield "a proposal is a string on a span"


def share_faults(row: Row) -> Iterator[str]:
    """A share off the row's labels, out of (0, 1], or a sum over 1."""
    shares, labels = row["shares"], row.get("labels")
    if not isinstance(shares, dict):
        yield "shares must be a map of label to number"
        return
    own = set(cast("list[str]", labels)) if strings(labels) else set()
    vs = cast("dict[str, object]", shares)
    for k, v in vs.items():
        if k not in own:
            yield f"share {k!r} is no label of the row"
        elif type(v) not in (int, float) or not 0 < cast("float", v) <= 1:
            yield f"share {k!r} is {v!r}, not above 0 and at most 1"
    if all(type(v) in (int, float) for v in vs.values()) and (
        sum(cast("list[float]", list(vs.values()))) > 1 + 1e-9
    ):
        yield "the shares add up to more than 1"


def span_shape(row: Row) -> str:
    """What makes a row's span no span, or ``""``.

    A span is written one way of two: by offsets, or by a quote (no
    offsets, a ``prefix`` or ``suffix`` beside its text if need be).
    """
    if "start" not in row and "end" not in row:
        return quote_shape(row)
    if any(k in row for k in QUOTE):
        return "a span has offsets or a prefix and suffix, not both"
    return offset_shape(row)


def quote_shape(row: Row) -> str:
    """What makes a quote no quote, or ``""``."""
    item, text = row.get("item"), row.get("text")
    if not isinstance(item, str) or not isinstance(text, str):
        return "a span needs a string item and text, or offsets too"
    if not plain(text)[0].strip():
        return "a quote must show more than markup and space"
    return ""


def offset_shape(row: Row) -> str:
    """What makes a span by offsets no span, or ``""``."""
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
    checks it; one without is grounded in the current text. A quote has
    no offsets to hold there: whether it is found is `locate's.
    """
    if not any(k in row for k in (*SPAN, *QUOTE)):
        return
    if shape := span_shape(row):
        yield shape
        return
    item = cast("str", row["item"])
    if item not in texts:
        yield f"item {item!r} is neither the page nor a file of the repo"
    elif "commit" not in row and "start" in row:
        start, end = cast("int", row["start"]), cast("int", row["end"])
        if texts[item][start:end] != row["text"]:
            yield f"text is not at [{start}, {end}) of {item}"


def target_faults(row: Row, names: Collection[str]) -> Iterator[str]:
    """Each target naming no row, generated span, ledger or address."""
    targets = row.get("targets", [])
    if strings(targets):
        for t in cast("list[str]", targets):
            if t not in names and not ADDRESS.fullmatch(t):
                yield f"target {t!r} names nothing"


def argument_faults(row: Row) -> Iterator[str]:
    """What keeps a ``supports`` or ``attacks`` row from arguing.

    It reads ``targets[0]`` -> ``targets[1:]``: one source, at least one
    end, none of them the row itself or its own source. A ``weight``
    is 1 to 5 and only an arguing row bears one. Nothing else for any
    other row.
    """
    labels, targets = row.get("labels"), row.get("targets", [])
    kind = first(row)
    yield from weight_faults(row, kind)
    if not strings(labels) or not kind:
        return
    if kind not in ARGUING | {RESUMES} or not strings(targets):
        return
    ts = cast("list[str]", targets)
    if kind == RESUMES and len(ts) != 2:
        yield f"resumes runs from one clause to one, {len(ts)} given"
    elif len(ts) < 2:
        yield f"{kind} needs a source and at least one end, {len(ts)} given"
    elif row.get("id") in ts:
        yield f"{kind} row {row.get('id')!r} names itself"
    elif ts[0] in ts[1:]:
        yield f"{kind} runs from {ts[0]!r} to itself"


def reason_faults(row: Row, proposed: set[object]) -> Iterator[str]:
    """Shares or proposal out of shape, or a decision off its proposal.

    An ``adopts`` or ``keeps`` row names one proposal, and ``keeps``
    says why in a second label.
    """
    yield from reason_shape(row)
    kind, targets = first(row), row.get("targets")
    if kind not in DECISIONS:
        return
    if not strings(targets) or len(cast("list[str]", targets)) != 1:
        yield f"{kind} settles one proposal, its only target"
    elif cast("list[str]", targets)[0] not in proposed:
        yield f"{kind} names {cast('list[str]', targets)[0]!r}, no proposal"
    if kind == "keeps" and len(cast("list[str]", row["labels"])) < 2:
        yield "keeps says why in a label after it"


def weight_faults(row: Row, kind: str) -> Iterator[str]:
    """A weight off an arguing row, or outside 1 to 5."""
    weight = row.get("weight")
    if "weight" in row and kind not in ARGUING:
        yield "only a supports or attacks row has a weight"
    elif type(weight) is int and weight not in WEIGHTS:
        yield f"weight {weight} is not 1 to 5"


def first(row: Row) -> str:
    """A row's first label, or ``""``."""
    labels = row.get("labels")
    return cast("list[str]", labels)[0] if strings(labels) and labels else ""


def kind(row: Row) -> str:
    """A row's kind, its first label, ``group/<naam>`` read ``group``.

    Every other first label is its own kind, so a relation or a set is
    read here as `first` reads it.
    """
    label = first(row)
    return GROUP if label.startswith(GROUP + "/") else label


def set_faults(row: Row, spans: Collection[str]) -> Iterator[str]:
    """What keeps a ``coref``, ``parts`` or ``group`` row from a set.

    Two members at least (a group one: the tray may hold one
    sentence), none twice, not itself; a ``parts`` row's members are
    span rows, the pieces of one discontinuous span, or ``parts`` rows,
    a piece that is itself in pieces (``spans`` holds both kinds of id).
    """
    k, targets = kind(row), row.get("targets", [])
    yield from group_faults(row)
    if k not in SETS or not strings(targets):
        return
    ts = cast("list[str]", targets)
    least = 1 if k == GROUP else 2
    if len(set(ts)) < least or len(set(ts)) < len(ts):
        many = "one member" if least == 1 else "two members"
        yield f"{k} needs {many} at least, each once"
    elif row.get("id") in ts:
        yield f"{k} row {row.get('id')!r} names itself"
    elif k == "parts" and (odd := [t for t in ts if t not in spans]):
        yield f"parts are span or parts rows, {odd[0]!r} is neither"


def group_faults(row: Row) -> Iterator[str]:
    """What is wrong with a row's group, role or order labels.

    A group is named: ``group/<naam>`` is its first label and its only
    one under ``group``. ``role/`` and ``order/`` stand on a group row
    only, one of each, the order a whole number from 1; the tray,
    ``group/gepakt``, has no role.
    """
    labels = row.get("labels")
    if not strings(labels):
        return
    ls = cast("list[str]", labels)
    named = [x for x in ls if x == GROUP or x.startswith(GROUP + "/")]
    roles = [x for x in ls if x.startswith("role/")]
    orders = [x for x in ls if x.startswith("order/")]
    if GROUP in named:
        yield "a group is named: group/<naam>"
    elif named and first(row) != named[0]:
        yield "a group's name is the row's first label"
    elif len(named) > 1:
        yield f"one row is one group, {len(named)} names given"
    elif (roles or orders) and not named:
        yield "role/ and order/ stand on a group row only"
    elif named:
        yield from role_faults(first(row), roles, orders)


def role_faults(
    name: str, roles: list[str], orders: list[str]
) -> Iterator[str]:
    """What is wrong with the role and order labels of a group."""
    if len(roles) > 1 or len(orders) > 1:
        yield "a group has one role and one order at most"
    elif odd := [x for x in orders if not ORDER.fullmatch(x)]:
        yield f"{odd[0]!r} is no order/<n>, n from 1"
    elif roles and name == TRAY:
        yield "the tray, group/gepakt, has no role"


def twice_named(rows: list[Row], where: str) -> list[web.Finding]:
    """A ``lit-facts-set`` finding for each group named twice on a page.

    A name is one group, so that the tray, and a chip, say which.
    """
    seen: dict[str, int] = {}
    out: list[web.Finding] = []
    for n, row in enumerate(rows, 1):
        if kind(row) != GROUP:
            continue
        name = first(row)
        if name in seen:
            m = f"{name!r} names the group at row {seen[name]}"
            out.append(web.Finding(where, n, "lit-facts-set", m))
        else:
            seen[name] = n
    return out


def bundles(rows: list[Row]) -> dict[str, tuple[int, list[str]]]:
    """Each ``parts`` row's id: its line and its pieces."""
    out: dict[str, tuple[int, list[str]]] = {}
    for n, row in enumerate(rows, 1):
        targets, me = row.get("targets"), row.get("id")
        if first(row) == "parts" and strings(targets) and isinstance(me, str):
            out[me] = (n, cast("list[str]", targets))
    return out


def nested(rows: list[Row], where: str) -> list[web.Finding]:
    """A ``lit-facts-set`` finding per piece of two wholes, or ring.

    Pieces nest as a tree: a row is a piece of one ``parts`` row at
    most, and no ``parts`` row holds itself through the bundles in it,
    or the overlay could not say which card a piece lights, nor stop
    when it gathers a bundle's spans.
    """
    holds = bundles(rows)
    owner: dict[str, str] = {}
    out: list[web.Finding] = []

    def inside(me: str, at: str, seen: set[str]) -> bool:
        """Whether ``me`` lies in the bundle ``at``, at any depth."""
        seen.add(at)
        ts = holds.get(at, (0, []))[1]
        return me in ts or any(
            inside(me, t, seen) for t in ts if t not in seen
        )

    for me, (n, ts) in holds.items():
        for t in ts:
            if t in owner:
                m = f"{t!r} is a piece of {owner[t]} already"
                out.append(web.Finding(where, n, "lit-facts-set", m))
            owner.setdefault(t, me)
        if back := [t for t in ts if t in holds and inside(me, t, set())]:
            m = f"parts {me} holds itself through {back[0]!r}"
            out.append(web.Finding(where, n, "lit-facts-set", m))
    return sorted(out, key=lambda f: f.line)


def tfa_faults(row: Row) -> Iterator[str]:
    """What is wrong with a row's topic-focus value."""
    labels = row.get("labels")
    if not strings(labels):
        return
    marks = [x for x in cast("list[str]", labels) if x.startswith("tfa/")]
    if not marks:
        return
    if first(row) not in marks:
        yield "a topic-focus value is a row's first label"
    elif odd := [x for x in marks if x not in TFA]:
        yield f"{odd[0]!r} is none of tfa/t, tfa/c, tfa/f"
    elif len(marks) > 1:
        yield f"one unit has one topic-focus value, {len(marks)} given"
    elif (
        not strings(t := row.get("targets", []))
        or len(cast("list[str]", t)) != 1
    ):
        yield "a topic-focus value marks one unit, its one target"


def twice_marked(rows: list[Row], where: str) -> list[web.Finding]:
    """A ``lit-facts-tfa`` finding for each unit marked twice."""
    seen: dict[str, int] = {}
    out: list[web.Finding] = []
    for n, row in enumerate(rows, 1):
        labels, targets = row.get("labels"), row.get("targets")
        if not (strings(labels) and strings(targets) and targets):
            continue
        ls, ts = cast("list[str]", labels), cast("list[str]", targets)
        if not any(x in TFA for x in ls):
            continue
        if ts[0] in seen:
            m = f"{ts[0]!r} has a topic-focus value at row {seen[ts[0]]}"
            out.append(web.Finding(where, n, "lit-facts-tfa", m))
        else:
            seen[ts[0]] = n
    return out


def layer(row: Row, rows: Mapping[str, Row]) -> str:
    """The layer a row is in, read from what it is, never written down.

    A span (it names an item, or it is a ``parts`` set of spans); an
    ``argument`` (supports, attacks); ``tfa`` (a topic-focus value, or
    a clause resuming another); ``coref``; a ``group``; another
    ``relation``; a ``thread`` (a fact whose first target is a row that
    is no span); else a ``fact``. One spelling: a layer field beside the
    labels could disagree with them.
    """
    k = kind(row)
    named = {"parts": "span", "coref": "coref", RESUMES: "tfa", GROUP: GROUP}
    named |= dict.fromkeys(ARGUING, "argument")
    if "item" in row:
        return "span"
    if k in named or k.startswith("tfa/"):
        return named.get(k, "tfa")
    if k in RELATIONS:
        return "relation"
    ts = row.get("targets")
    up = rows.get(cast("list[str]", ts)[0]) if strings(ts) and ts else None
    spanlike = up is None or "item" in up or first(up) == "parts"
    return "fact" if spanlike else "thread"


def argdown(rows: list[Row], claim: str) -> str:
    """The argument tree on ``claim`` as Argdown text (argdown.org).

    The claim is a statement ``[claim]``, or an argument ``<claim>``
    when it is an arguing row itself; each arguing row that ends at it
    is an argument named by the row's id, ``<+ <r>`` when it supports
    and ``<- <r>`` when it attacks, described by what its source says
    and carrying its ``{weight: n}``. Under an argument come first the
    rows that end at the row itself, the inference (``<_`` for an
    attack: Argdown's undercut, which holds only between arguments;
    ``<+`` for a support), then those that end at its source. A row met
    again is named and not described, so the text grows with the rows
    and stops at a cycle, as the tree on the page does; a premise two
    arguments share names its grounds under both. Argdown's markup in a
    text (brackets, braces, a tag's ``#``) is defused.

    Raises:
        ValueError: when no row or address is ``claim``.
    """
    byid = {
        cast("str", r["id"]): r for r in rows if isinstance(r.get("id"), str)
    }
    if claim not in byid and not ADDRESS.fullmatch(claim):
        raise ValueError(f"{claim!r} names no row")

    def says(rid: str) -> str:
        return defused(byid.get(rid, {}), rid)

    def tree(rid: str, depth: int, inference: bool, expand: bool) -> None:
        for r in grounds(rows, rid):
            name = cast("str", r["id"])
            src = cast("list[str]", r["targets"])[0]
            sign = "+" if first(r) == "supports" else "_" if inference else "-"
            line = f"{'  ' * depth}<{sign} <{name}>"
            if name in drawn or not expand:
                out.append(line)
                continue
            drawn.add(name)
            out.append(f"{line}: {says(src)}{weight(r)}")
            below(name, src, depth + 1)

    def below(name: str, src: str, depth: int) -> None:
        tree(name, depth, True, True)
        tree(src, depth, False, src not in drawn)
        drawn.add(src)

    drawn = {claim}
    root = byid.get(claim, {})
    if first(root) in ARGUING and strings(root.get("targets")):
        src = cast("list[str]", root["targets"])[0]
        out = [f"<{claim}>: {says(src)}{weight(root)}"]
        below(claim, src, 1)
    else:
        out = [f"[{claim}]: {says(claim)}"]
        tree(claim, 1, False, True)
    return "\n".join(out) + "\n"


def defused(row: Row, rid: str) -> str:
    """What a row says on one line, its Argdown markup defused."""
    said = " ".join(str(row.get("note") or row.get("text") or rid).split())
    return re.sub(r"#(?=\S)", "# ", said.translate(DEFUSE))


def grounds(rows: list[Row], rid: str) -> list[Row]:
    """The arguing rows that end at ``rid``."""
    return [
        r
        for r in rows
        if first(r) in ARGUING
        and strings(ts := r.get("targets"))
        and rid in cast("list[str]", ts)[1:]
    ]


def weight(row: Row) -> str:
    """An arguing row's weight as Argdown data, or ``""``."""
    return f" {{weight: {row['weight']}}}" if "weight" in row else ""


# The Argdown markup a text must not carry: a title's brackets, the
# braces of data. A tag's ``#`` is split from its word instead.
DEFUSE = str.maketrans("[]{}", "()()")


QUERY_KEYS = ("label", "layer", "by", "text", "has", "gives")
LAYERS = (
    "span", "fact", "thread", "argument", "tfa", "coref", "group", "relation"
)  # fmt: skip

# A query term: (negated, key, value, chain length, column). The
# chain length is 0 for a bare ``has:R`` or ``gives:R`` and other keys.
type Term = tuple[bool, str, str, int, int]


def parse_query(q: str) -> list[list[Term]]:
    """A query's groups of terms: a row is found when one group holds.

    A query is terms apart by spaces, each ``[!]key:value`` (after
    PML-TQ, Pajas and Stepanek 2009: conditions joined by and, a
    negation as a condition met zero times). Keys: ``label`` (a label at
    or under a scope), ``layer``, ``by``, ``text`` (in the text or the
    note, lower-cased, not case folded), ``has:R`` (an R row ends at it)
    and ``gives:R`` (an R row starts from it).

    A term that is exactly ``|`` closes a group: the query holds for a
    row when every term of at least one group does (disjunctive normal
    form, PML-TQ's or). ``has:R+N`` and ``gives:R+N``, ``N`` a decimal
    from 1 without leading zeros, ask for a chain of at least ``N`` R
    edges ending or starting there (see `query`). An empty query is
    one group of no terms, which every row meets.

    A strict reader: any other spelling is a `ValueError` naming its
    column, counted from 1 in code points; a ``|`` at either end or next
    to another is ``empty group`` at that ``|``.
    """
    groups: list[list[Term]] = [[]]
    bar = 0  # the column of the last ``|``, 0 before any
    for m in re.finditer(
        r"[^ ]+", q
    ):  # terms apart by U+0020 only, as the overlay
        term, col = m.group(), m.start() + 1
        if term != "|":
            groups[-1].append(parse_term(term, col))
        elif not groups[-1]:
            raise ValueError(f"empty group at {col}")
        else:
            groups.append([])
            bar = col
    if bar and not groups[-1]:
        raise ValueError(f"empty group at {bar}")
    return groups


def parse_term(term: str, col: int) -> Term:
    """One ``[!]key:value`` term of a query, read at column `col`."""
    neg = term.startswith("!")
    key, colon, value = term[neg:].partition(":")
    if not colon or not re.fullmatch(r"[a-z]+", key):
        raise ValueError(f"no key:value at {col}")
    if key not in QUERY_KEYS:
        raise ValueError(f"unknown key '{key}' at {col}")
    if not value:
        raise ValueError(f"empty value at {col}")
    n = 0
    if key in {"has", "gives"}:
        value, n = parse_chain(value, col)
    if key == "layer" and value not in LAYERS:
        raise ValueError(f"'{value}' is no layer at {col}")
    return (neg, key, value, n, col)


def parse_chain(value: str, col: int) -> tuple[str, int]:
    r"""A ``has`` or ``gives`` value, ``R`` or ``R+N``: R, N (0 bare).

    ``N`` is ``[1-9][0-9]*``, written so rather than ``\d`` and `int`
    alone, which take other digits and ``1_0``: the overlay's reader
    takes ASCII only. Past nine digits it reads as ``10**9``, which no
    page reaches either: `int` refuses more than 4300 digits, and the
    overlay's `Number` rounds past ``2**53``.
    """
    value, plus, length = value.partition("+")
    if value not in RELATIONS | SETS:
        raise ValueError(f"'{value}' is no relation or set at {col}")
    if plus and not re.fullmatch(r"[1-9][0-9]*", length):
        raise ValueError(f"bad chain length at {col}")
    if not plus:
        return value, 0
    return value, int(length) if len(length) <= 9 else 10**9


# Per kind, the edges of each node: kind -> node -> the nodes it joins,
# a dict for a set kept in the order the edges came, as the overlay's
# `Set`: a walk then tries them in the same order in both readers.
type Edges = dict[str, dict[str, dict[str, None]]]

# The steps one chain walk may take before it gives up with an error,
# rather than freeze the overlay's tab: a simple path is a search that
# can grow as the factorial of a set's members.
CHAIN_BUDGET = 100_000


def relation_edges(rows: list[Row]) -> tuple[Edges, Edges]:
    """Each kind's edges, into each node and out of it.

    An edge runs from a relation row's first target to each of the
    others; a set's members are joined both ways, each to every other.
    A node never joins itself, so a row with one target, or one member
    named twice, bears no edge.
    """
    back: Edges = {}
    ahead: Edges = {}
    for r in rows:
        k, ts = kind(r), r.get("targets")
        if not strings(ts):
            continue
        t = cast("list[str]", ts)
        pairs = (
            [(a, b) for a in t for b in t if a != b]
            if k in SETS
            else [(t[0], b) for b in t[1:] if b != t[0]]
        )
        for a, b in pairs:
            ahead.setdefault(k, {}).setdefault(a, {})[b] = None
            back.setdefault(k, {}).setdefault(b, {})[a] = None
    return back, ahead


def reaches(step: Mapping[str, Mapping[str, None]], x: str, n: int) -> bool:
    """Whether `x` reaches `n` other nodes along `step`.

    The count stops at `n`, so it costs no more than the answer needs.
    """
    reach, todo = {x}, [x]
    while todo and len(reach) <= n:
        for y in step.get(todo.pop(), {}):
            if y not in reach:
                reach.add(y)
                todo.append(y)
    return len(reach) > n


def chained(
    step: Mapping[str, Mapping[str, None]], x: str, n: int, col: int
) -> bool:
    """Whether a path of at least `n` edges along `step` leaves `x`.

    The path is simple, no node twice, so a cycle does not lengthen it.
    It needs ``n + 1`` nodes, so when `x` `reaches` too few the answer
    is no at once (a set of eleven holds no path of eleven edges). Else
    a depth-first walk, kept on a stack of its own rather than Python's,
    stops at `n` edges, or past `CHAIN_BUDGET` steps with ``chain too
    long to search`` at `col`.
    """
    if not reaches(step, x, n):
        return False
    path, seen = [x], {x}
    nexts = [iter(step.get(x, {}))]
    budget = CHAIN_BUDGET
    while nexts:
        y = next((y for y in nexts[-1] if y not in seen), None)
        if y is None:
            nexts.pop()
            seen.discard(path.pop())
            continue
        if len(path) == n:
            return True
        budget -= 1
        if budget < 0:
            raise ValueError(f"chain too long to search at {col}")
        path.append(y)
        seen.add(y)
        nexts.append(iter(step.get(y, {})))
    return False


def query(rows: list[Row], q: str) -> list[str]:
    """The ids of the rows one group of `q` wholly holds for, in order.

    ``has`` and ``gives`` look at the row and, for a fact on a page
    address, at that address too: a topic-focus value is about its
    clause, so ``label:tfa/f !has:resumes`` is a focus no clause takes
    up. A relation's ends are its targets after the first; a set's are
    all.

    Chains run along `relation_edges`. ``has:R+N`` holds when a chain of
    at least ``N`` R edges ends at the row, or at the address it speaks
    for (the widening applies to the chain's end only; the nodes before
    are ids as written), and ``gives:R+N`` when one starts there, as
    `chained` walks them, cheap for a page's tens to hundreds of rows.
    A bare ``has:R`` is ``has:R+1``, one edge ending there, so a row
    that bears no edge (one target, or a target that is also the first)
    gives it nothing. A bare ``gives:R`` is ``gives:R+1`` for a relation
    and never holds for a set's member, where ``gives:R+1`` does.
    """
    groups = parse_query(q)
    by = {
        cast("str", r["id"]): r for r in rows if isinstance(r.get("id"), str)
    }
    back, ahead = relation_edges(rows)

    def about(r: Row) -> list[str]:
        # a fact on an address speaks for the address; one on a row, or
        # a relation, only for itself
        ts = r.get("targets")
        t0 = cast("list[str]", ts)[:1] if strings(ts) else []
        own = "item" in r or kind(r) in RELATIONS | SETS
        up = [] if own or not t0 or t0[0] in by else t0
        return [cast("str", r.get("id")), *up]

    def holds(r: Row, key: str, value: str, n: int, col: int) -> bool:
        labels = (
            cast("list[str]", r.get("labels"))
            if strings(r.get("labels"))
            else []
        )
        said = [r.get("text"), r.get("note")]
        words = " ".join(x for x in said if isinstance(x, str)).lower()
        return {
            "label": lambda: any(
                x == value or x.startswith(value + "/") for x in labels
            ),
            "layer": lambda: layer(r, by) == value,
            "by": lambda: r.get("by") == value,
            "text": lambda: value.lower() in words,
            "has": lambda: any(
                chained(back.get(value, {}), x, n or 1, col) for x in about(r)
            ),
            "gives": lambda: (
                bool(n or value in RELATIONS)
                and any(
                    chained(ahead.get(value, {}), x, n or 1, col)
                    for x in about(r)
                )
            ),
        }[key]()

    return [
        cast("str", r["id"])
        for r in rows
        if isinstance(r.get("id"), str)
        and any(
            all(holds(r, k, v, n, c) != neg for neg, k, v, n, c in group)
            for group in groups
        )
    ]


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
        ``lit-facts-id``, ``lit-facts-field``, ``lit-facts-span``,
        ``lit-facts-target``, ``lit-facts-argument``, ``lit-facts-set``,
        ``lit-facts-tfa`` and ``lit-facts-reason`` findings, row by
        row.
    """
    ids: Counter[object] = Counter(r.get("id") for r in rows)
    names = {i for i in ids if isinstance(i, str)} | set(known)
    spans = {
        i
        for r in rows
        if ("item" in r or first(r) == "parts")
        and isinstance(i := r.get("id"), str)
    } | set(known)
    proposed = {r.get("id") for r in rows if "proposal" in r}
    out: list[web.Finding] = []
    for n, row in enumerate(rows, 1):
        for rule, faults in (
            ("lit-facts-id", id_faults(row, ids)),
            ("lit-facts-field", field_faults(row)),
            ("lit-facts-span", span_faults(row, texts)),
            ("lit-facts-target", target_faults(row, names)),
            ("lit-facts-argument", argument_faults(row)),
            ("lit-facts-set", set_faults(row, spans)),
            ("lit-facts-tfa", tfa_faults(row)),
            ("lit-facts-reason", reason_faults(row, proposed)),
        ):
            out += [web.Finding(where, n, rule, m) for m in faults]
    out += twice_marked(rows, where)
    out += twice_named(rows, where)
    out += nested(rows, where)
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


def graph(
    path: Path, root: Path
) -> tuple[dict[str, object], list[web.Finding]]:
    """A page's code as a graph, for the overlay beside its rows.

    Nodes: each chunk (its id as in the fact layer, its name, its
    section) and each file it tangles to (``file:<path>``). Edges: a
    chunk ``uses`` the chunks its body names (``<<name>>``, every chunk
    of that name), and ``tangles`` to a file with the number of lines it
    gives it, read from the tangle rows, and its first and last line
    there (`spread'). Sources: each hand row that quotes another file
    of the repo, a transclusion the page shows at its target
    (`source'). Generated, never committed: `lit graph' writes it
    beside the page and the site ships it.
    """
    rows, bad = generate(path, root)
    page = web.read(path.as_posix(), path.read_text(encoding="utf-8"))
    # a use naming no chunk leaves a hole in the graph; the web's other
    # findings are `lit check's, not this graph's
    holes = [
        f for f in web.tangle(page)[1] if f.message.endswith(">> undefined")
    ]
    bad += holes
    named: dict[str, list[str]] = {}
    found = list(chunk_ids(page))
    for _, c, cid in found:
        named.setdefault(web.norm(c.name), []).append(cid)
    nodes: list[dict[str, object]] = [
        {"id": cid, "kind": "chunk", "label": c.name, "section": n}
        for n, c, cid in found
    ]
    edges: list[dict[str, object]] = []
    for _, c, cid in found:
        used = [
            web.norm(m["name"]) for b in c.body if (m := web.USE.fullmatch(b))
        ]  # normalised as the tangler reads them
        for name in dict.fromkeys(used):
            edges += [
                {"a": cid, "b": u, "label": "uses"}
                for u in named.get(name, [])
            ]
    lines: dict[tuple[str, str], int] = {}
    for r in rows:
        ts = r.get("targets")
        if r.get("kind") == "tangle" and strings(ts) and ts:
            key = (cast("list[str]", ts)[0], cast("str", r["item"]))
            lines[key] = lines.get(key, 0) + 1
    for f in dict.fromkeys(item for _, item in lines):
        nodes.append({"id": f"file:{f}", "kind": "file", "label": f})
    at = spread(page)
    for (cid, f), n in lines.items():
        edge: dict[str, object] = {"a": cid, "b": f"file:{f}", "n": n}
        edges.append(edge | {"label": "tangles", "lines": at[cid]})
    repo = top(root)
    here = path.resolve().relative_to(repo).as_posix()
    sources = [
        source(r, (repo / cast("str", r["item"])).read_text(encoding="utf-8"))
        for r in rows
        if "state" in r and r.get("item") not in (None, here)
    ]
    return {"nodes": nodes, "edges": edges, "sources": sources}, bad


def spread(page: web.Page) -> dict[str, list[int]]:
    """Each chunk's first and last line in the page's first file.

    The lines of its own body, so a chunk it uses in between is inside
    the range; the first file is the one the tangle rows hold.
    """
    owner = {
        c.line + 1 + k: cid
        for _, c, cid in chunk_ids(page)
        for k in range(len(c.body))
    }
    seen: dict[str, list[int]] = {}
    for t in web.tangle(page)[0][:1]:
        for n, o in enumerate(t.origin, 1):
            seen.setdefault(owner.get(o, ""), []).append(n)
    return {cid: [ns[0], ns[-1]] for cid, ns in seen.items() if cid}


def source(row: Row, text: str) -> dict[str, object]:
    """A hand row quoting another file of the repo, as a page shows it.

    Its lines are counted where `locate' found its text, else where it
    was written; ``changed`` when its text is not in the file as it
    was, moved or not: the source changed since the row's commit.
    """
    at = cast("int", row.get("currentStart", row["start"]))
    first = text.count("\n", 0, at) + 1
    last = first + cast("str", row["text"]).count("\n")
    return {
        "row": row["id"],
        "path": row["item"],
        "lines": [first, last],
        "commit": row.get("commit", ""),
        "changed": row["state"] not in (VERS, MOVED),
    }


# A name in inline code: `name' (lit's alias) or `name`.
INLINE = re.compile(r"`(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)['`]")

# The shown text kept either side of a mention, as the overlay's rows
# keep it (fpl-annot.js: prefix and suffix).
SIDE = 32

type Address = dict[str, object]
type Name = dict[str, object]


@dataclass
class Spun:
    """A page's names while `spin' reads them, and its findings.

    Attributes:
        w: The page, tangled.
        order: Each chunk's id to its place among the page's chunks
            (from 1) and the page line its header ends on.
        names: Each qualified name to what `spin' writes for it.
        member: Each member's plain name to the qualified names that
            define it.
        bad: What could not be placed.
    """

    w: Web
    order: dict[str, tuple[int, int]]
    names: dict[str, Name]
    member: dict[str, list[str]]
    bad: list[web.Finding]

    def address(
        self, t: web.Tangled, line: int, col: int, name: str
    ) -> Address | None:
        """Where ``name``, at byte ``col`` of file line ``line``, shows.

        ``ast`` counts UTF-8 bytes, the page characters; a line the
        tangle took from an included chunk carries that chunk's indent,
        which the page does not show. None, and a finding, when the
        page does not hold ``name`` there.
        """
        src = t.lines[line - 1]
        at = t.origin[line - 1]
        shown = self.w.text.lines[at - 1]
        col = len(src.encode()[:col].decode()) - (len(src) - len(shown))
        cid = self.w.chunk_at.get(at)
        if cid is None or shown[col : col + len(name)] != name:
            message = f"`{name}' is not at its column on the page"
            self.bad.append(
                web.Finding(self.w.page.path, at, "lit-spin", message)
            )
            return None
        k, head = self.order[cid]
        return {"chunk": cid, "n": k, "line": at - head, "col": col}

    def define(self, t: web.Tangled) -> None:
        """Each name a file defines, at its definition, once."""
        for d in definitions(ast.parse(t.text)):
            src = t.lines[d.line - 1]
            m = re.search(rf"\b{re.escape(d.name)}\b", src)
            if d.qualified in self.names or m is None:
                continue
            col = len(src[: m.start()].encode())
            where = self.address(t, d.line, col, d.name)
            if where is None:
                continue
            self.names[d.qualified] = {
                "name": d.name,
                "qualified": d.qualified,
                "id": ident("def", d.qualified),
                "def": where,
                "uses": [],
                "mentions": [],
            }
            if d.qualified != d.name:
                self.member.setdefault(d.name, []).append(d.qualified)

    def use(self, t: web.Tangled) -> None:
        """Each load of a defined name, and each read of a member."""
        for node in ast.walk(ast.parse(t.text)):
            match node:
                case ast.Name(id=n, ctx=ast.Load()) if n in self.names:
                    hits = [(n, node.lineno, node.col_offset, n)]
                case ast.Attribute(
                    attr=a, end_lineno=int(line), end_col_offset=int(end)
                ) if a in self.member:
                    col = end - len(a.encode())
                    hits = [(q, line, col, a) for q in self.member[a]]
                case _:
                    continue
            for q, line, col, shown in hits:
                where = self.address(t, line, col, shown)
                uses = cast("list[Address]", self.names[q]["uses"])
                if where is not None and where not in uses:
                    uses.append(where)

    def named(self, n: str) -> Name | None:
        """What inline code ``n`` names: a name, a member, or nothing.

        ``mod.Class.member`` is read from its last two parts, and a
        member's plain name when one class alone defines it.
        """
        one = self.member.get(n, [])
        tail = ".".join(n.split(".")[-2:])
        lone = self.names[one[0]] if len(one) == 1 else None
        return self.names.get(n) or self.names.get(tail) or lone

    def mention(self, text: str) -> None:
        """Each name in inline code in the prose, as a row finds it."""
        shown, at = plain(text)
        lines = self.w.text
        for line in (x for s in self.w.page.sections for x in s.prose):
            for m in INLINE.finditer("" if line.fenced else line.text):
                hit = self.named(m["name"])
                if hit is None:
                    continue
                i = bisect_left(at, lines.starts[line.number - 1] + m.start(1))
                lo, hi = (bisect_left(at, o) for o in paragraph(lines, line))
                end = i + len(m["name"])
                cast("list[Address]", hit["mentions"]).append(
                    {
                        "text": m["name"],
                        "prefix": shown[max(lo, i - SIDE) : i].lstrip(),
                        "suffix": shown[end : min(hi, end + SIDE)].rstrip(),
                    }
                )


def spin(path: Path) -> tuple[dict[str, object], list[web.Finding]]:
    """Each name a page's code defines, where it is used and mentioned.

    The spin of the overlay (board V5b): a name in a fence opens its
    definition, its uses in code and its mentions in prose. Python is
    read with `ast' (no tree-sitter in the environment); a fence of any
    other language adds no name. A name's ``def`` and each of its
    ``uses`` is an address in a chunk: its id as in the fact layer,
    ``n`` its place among the page's chunks (from 1), ``line`` the line
    of its body (from 1, the number Pandoc gives its code line) and
    ``col`` the character the name starts at. A plain name is used
    where it is loaded; ``Class.member`` wherever ``.member`` is read,
    whatever the object. A mention is the name in inline code in the
    prose, as a row of the overlay finds it: ``text`` with ``prefix``
    and ``suffix``, read by `plain' and cut at the paragraph; a bare
    word is no mention. A name the page does not show at its column is
    a finding, never a wrong address. Generated, never committed: `lit
    spin' writes it beside the page.
    """
    text = path.read_text(encoding="utf-8")
    page = web.read(path.as_posix(), text)
    order = {
        cid: (k, c.line) for k, (_, c, cid) in enumerate(chunk_ids(page), 1)
    }
    s = Spun(Web.of(page, text), order, {}, {}, [])
    for t in s.w.files:
        s.define(t)
    for t in s.w.files:
        s.use(t)
    s.mention(text)
    return {"names": list(s.names.values())}, s.bad


def paragraph(text: Text, line: web.Line) -> tuple[int, int]:
    """The code points of the run of non-blank lines round ``line``."""
    first = last = line.number
    while first > 1 and text.lines[first - 2].strip():
        first -= 1
    while last < len(text.lines) and text.lines[last].strip():
        last += 1
    start, end, _ = text.place(first, last)
    return start, end


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
    when the commit does not hold it; the shell asks git. A quote row
    has no place to check, and is passed over.
    """
    out: list[web.Finding] = []
    for n, row in enumerate(rows, 1):
        commit = row.get("commit")
        if not isinstance(commit, str) or "start" not in row:
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
# its id and its span, in the order a sidecar row writes them: ``by``
# is who wrote it, a person's name or an agent's model id.
TOOL_KEYS = (
    "labels",
    "note",
    "targets",
    "by",
    "weight",
    "shares",
    "proposal",
    *STAMPS,
)


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

    Its id must be a new string, its offsets both there and integers
    or both away (a quote), its ``prefix`` and ``suffix`` strings, its
    text one without astral code points (JavaScript counts those as
    two, so the program's offsets would not be lit's), its targets a
    list of strings, its ``by`` a string, and its times integers,
    since the new rows are ordered by them. A row without a text is a
    fact about its first target: it needs one, and has no place of
    its own (`text_faults').
    """
    rid = row.get("id")
    if not isinstance(rid, str) or rid in seen:
        yield f"id {rid!r} is no new string"
    yield from place_faults(row)
    yield from text_faults(row)
    if "targets" in row and not strings(row["targets"]):
        yield "targets must be a list of strings"
    if "by" in row and not isinstance(row["by"], str):
        yield "by must be a string"
    if "weight" in row and (
        type(row["weight"]) is not int or row["weight"] not in WEIGHTS
    ):
        yield "weight must be an integer 1 to 5"
    yield from reason_shape(row)
    for key in STAMPS:
        if key in row and type(row[key]) is not int:
            yield f"{key} must be an integer"


def text_faults(row: Row) -> Iterator[str]:
    """A text without astral code points, or targets and no place."""
    if "text" not in row:
        if not row.get("targets"):
            yield "a row with neither text nor targets is about nothing"
        if any(k in row for k in (*SPAN[1:3], *QUOTE)):
            yield "a row without text has no offsets, prefix or suffix"
    elif not isinstance(text := row["text"], str):
        yield "text must be a string"
    elif m := ASTRAL.search(text):
        yield f"text holds U+{ord(m[0]):X}, two code units in JavaScript"


def place_faults(row: Row) -> Iterator[str]:
    """Both offsets as integers or neither; prefix, suffix strings."""
    have = [k for k in ("start", "end") if k in row]
    if len(have) == 1:
        yield "start and end come together"
    elif have and any(type(row[k]) is not int for k in have):
        yield "start and end must be integers"
    for key in QUOTE:
        if key in row and not isinstance(row[key], str):
            yield f"{key} must be a string"


def imported(
    rows: Sequence[Tool], label: str, page: str, commit: str
) -> tuple[list[Row], list[web.Finding]]:
    """The program's rows for one label as hand rows on a page.

    A row is the label's when its ``item`` is ``label`` and it holds a
    ``text`` or an ``id``; every other row (another item, the
    program's own records of labels and items) is passed over. A row
    of the label with a text becomes ``{id, item: page, start, end,
    text, prefix, suffix, labels, note, targets, commit, by,
    createdAt, updatedAt}``: its ``targets`` are ``[]`` when it has
    none, and the offsets (a quote has none), the prefix and suffix,
    ``labels``, ``note``, ``by`` and the times are carried only when
    it has them. A row without a text (a reply, a fact about a fact
    or about an address on the page) is a fact about its first
    target, and becomes ``{id, labels, note, targets, commit, by,
    createdAt, updatedAt}``: no ``item``, since a sidecar row that
    names one is a span, and the sidecar is the page's already.

    Returns:
        The hand rows, and a ``lit-facts-import`` finding for each row
        refused (`import_faults'), at its place.
    """
    out: list[Row] = []
    bad: list[web.Finding] = []
    seen: set[str] = set()
    for t in rows:
        d = t.row
        if d.get("item") != label or not ("text" in d or "id" in d):
            continue
        if faults := list(import_faults(d, seen)):
            bad += [
                web.Finding(t.where, t.number, "lit-facts-import", m)
                for m in faults
            ]
            continue
        rid = cast("str", d["id"])
        seen.add(rid)
        row: Row = {"id": rid, "item": page} if "text" in d else {"id": rid}
        row |= {k: d[k] for k in (*SPAN[1:], *QUOTE, *TOOL_KEYS[:2]) if k in d}
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
    rows: Sequence[Row], labels: Mapping[tuple[str, str], str], page: str
) -> list[Row]:
    """A sidecar's hand rows in the annotation program's shape.

    Each row becomes ``{id, item, start, end, text}`` (a quote: ``{id,
    item, text}``; a row without a span, a fact about rows: ``{id,
    item}``) and whichever of ``prefix``, ``suffix``, ``labels``,
    ``note``, ``targets``, ``by``, ``createdAt`` and ``updatedAt`` it
    holds; its ``commit`` is dropped. Its ``item`` is the program's
    label for ``(item, commit)`` in ``labels``, or the path itself when
    none is given. A row without a span is about rows of ``page``, the
    sidecar's, at no text of it: it takes any label ``page`` has.
    """
    mine = next((v for (i, _), v in labels.items() if i == page), page)
    out: list[Row] = []
    for r in rows:
        at = (cast("str", r.get("item", "")), cast("str", r.get("commit", "")))
        item = labels.get(at, at[0]) if "text" in r else mine
        row: Row = {"id": r["id"], "item": item}
        row |= {k: r[k] for k in (*SPAN[1:], *QUOTE, *TOOL_KEYS) if k in r}
        out.append(row)
    return out

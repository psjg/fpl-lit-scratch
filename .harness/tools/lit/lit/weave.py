"""The weave: a literate page as one HTML page, in the manner of CWEB.

Every section is numbered, §1 onwards. A chunk is headed ⟨Name §n⟩ ≡,
or +≡ where it continues a chunk begun earlier; each use inside a chunk
is a link to the section that defines it, and a footer says where the
chunk is used, or which file it is. A reference in the prose, `name',
links to the section that defines the name. The page ends with two
indexes: the chunks, and the identifiers the code defines, each with
the section that defines it (bold) and the sections whose code uses it.
The HTML is one file with its style inline; prose is CommonMark, read
by markdown-it-py.

A page with hand rows beside it (``<page stem>.facts.json``) shows
them, from the rows `facts.generate' located, never from the sidecar
alone. Each hand span found on the page (vers or verplaatst) is a
``<mark>`` at its current offsets. The offsets are code points of the
raw page, so each boundary is put into its page line as a sentinel,
``⸨k⸩`` or ``⸨/k⸩`` (U+2E28 and U+2E29, which CommonMark reads as
punctuation, so emphasis beside one still closes), before the line is
rendered. A boundary on a line that renders no text of its own (a
fence, a chunk header, a blank line, a table rule) moves to the first
column of the next line that does; one before a heading's ``#`` or a
list's bullet moves past it, so the block is still read as one. After
rendering, every run of text is wrapped in the marks open over it:
marks split at every boundary and every tag, so overlapping and nested
spans both nest properly, and only a span's first piece carries its
``id``. A boundary inside a link's address is lost to the address; a
page holding U+2E28 itself is not marked correctly.

The page then ends with a section of footnotes: a legend, the rows
counted by state, and one entry per hand row in the sidecar's order,
with its targets as links and the rows that cite it.
"""

from __future__ import annotations

import ast
import html
import re
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from markdown_it import MarkdownIt

from lit import facts
from lit.facts import Row
from lit.lint import REF, definitions
from lit.web import USE, Line, Page, Section, Tangled, is_file, norm

STYLE = """
body { max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
  font: 16px/1.5 Georgia, serif; color: #222; background: #fff; }
.num { font-weight: bold; margin-right: .5em; }
.chunk { margin: .5rem 0 1.5rem; }
.head, .foot { font-size: .9em; color: #555; }
pre { background: #f6f6f2; padding: .5rem; overflow-x: auto;
  font: 14px/1.4 Menlo, monospace; }
a.use { text-decoration: none; }
table { border-collapse: collapse; } td { padding: 0 .75em 0 0; }
@media (prefers-color-scheme: dark) {
  body { color: #ddd; background: #161616; } pre { background: #222; }
  .head, .foot { color: #aaa; } }
"""
# Added to the style only on a page that has hand rows.
FACTS_STYLE = """
mark.fact { color: inherit; padding: 0; }
mark.fact-vers { background: rgba(70, 190, 70, .28); }
mark.fact-verplaatst { background: rgba(240, 160, 0, .35); }
.facts li { margin: .5rem 0; } .facts .meta { font-size: .9em; color: #555; }
.facts .fact-stale, .facts .fact-dubbel { color: #b00; }
@media (prefers-color-scheme: dark) { .facts .meta { color: #aaa; }
  .facts .fact-stale, .facts .fact-dubbel { color: #f77; } }
"""

# A mark's boundary in the rendered text, and the text cut at every
# tag and boundary.
OPEN, SHUT = "\u2e28", "\u2e29"
BOUNDARY = re.compile(r"\u2e28(/?)(\d+)\u2e29")
PIECES = re.compile(r"(<[^>]*>|\u2e28/?\d+\u2e29)")
# The block markup that opens a prose line (headings, bullets, quotes,
# a table's first pipe), and a line that renders no text of its own.
BLOCK = re.compile(
    r"(?:[ \t]*(?:#{1,6}|[-+*]|\d{1,9}[.)]|>|\|)(?=[ \t]|$))*[ \t]*"
)
RULE = re.compile(r"[-=*_:|\s]*")
# The labels that make a row a relation, its targets read from -> to.
RELATIONS = frozenset(
    {"because", "supports", "contradicts", "supersedes", "checkedBy", "cites"}
)
MARKED = frozenset({facts.VERS, facts.MOVED})


def defining(tangled: list[Tangled], page: Page) -> dict[str, int]:
    """Each module or class level name, to its defining section."""
    out: dict[str, int] = {}
    for t in tangled:
        if t.name.endswith(".py"):
            for d in definitions(ast.parse(t.text)):
                n = page.section_of(t.origin[d.line - 1])
                if n and not d.name.startswith("__"):
                    out.setdefault(d.name, n)
    return out


def uses(page: Page) -> dict[str, list[int]]:
    """Each chunk name, to the sections whose code uses it."""
    out: dict[str, list[int]] = {}
    for s in page.sections:
        for text in s.chunk.body if s.chunk else ():
            if m := USE.fullmatch(text):
                out.setdefault(norm(m["name"]), []).append(s.number)
    return out


def _first(page: Page) -> dict[str, int]:
    """Each chunk name, to the section of its ``=``."""
    out: dict[str, int] = {}
    for s in page.sections:
        if s.chunk is not None:
            out.setdefault(s.chunk.name, s.number)
    return out


type Boundaries = Mapping[int, Mapping[int, str]]


def _slot(line: Line) -> tuple[int, int] | None:
    """The columns of a prose line that may take a boundary, or None.

    A fence line, a blank line and a rule (a table's, a thematic break,
    a heading's underline) take none. A line's opening block markup and
    a table row's last pipe stay outside.
    """
    text = line.text
    if line.fenced:
        return None if text.startswith("```") else (0, len(text))
    if RULE.fullmatch(text):
        return None
    first = cast("re.Match[str]", BLOCK.match(text)).end()
    last = len(text)
    if text.lstrip().startswith("|"):
        last = len(text.rstrip().removesuffix("|"))
    return first, max(first, last)


def _slots(page: Page) -> dict[int, tuple[int, int]]:
    """Each page line that renders text, to the columns it may take.

    A use in a chunk takes its boundaries at its indentation, before
    the link that stands for it.
    """
    out: dict[int, tuple[int, int]] = {}
    for s in page.sections:
        for line in s.prose:
            if (at := _slot(line)) is not None:
                out[line.number] = at
        for chunk in [s.chunk] if s.chunk else []:
            for k, text in enumerate(chunk.body):
                use = USE.fullmatch(text)
                width = len(use["indent"]) if use else len(text)
                out[chunk.line + 1 + k] = (width if use else 0, width)
    return out


def _boundaries(
    page: Page, text: str, spans: Sequence[tuple[int, int]]
) -> tuple[Boundaries, str]:
    """Each span's two boundaries, as sentinels at page line columns.

    Span ``k`` opens with ``⸨k⸩`` and closes with ``⸨/k⸩``. The
    boundaries are placed in the order of their offsets, a close
    before an open at one offset; a boundary off every slot moves to
    the next slot's first column, so the order holds. Those past the
    last slot are returned apart, for the end of the page.
    """
    starts = facts.Text.of("", text).starts
    slots = _slots(page)
    lines = sorted(slots)
    ends = [(e, 0, k) for k, (_, e) in enumerate(spans)]
    events = sorted([(s, 1, k) for k, (s, _) in enumerate(spans)] + ends)
    out: dict[int, dict[int, str]] = {}
    rest = ""
    for offset, opens, k in events:
        tag = f"{OPEN}{'' if opens else '/'}{k}{SHUT}"
        n = bisect_right(starts, offset)
        at = bisect_left(lines, n)
        if at == len(lines):
            rest += tag
            continue
        line = lines[at]
        lo, hi = slots[line]
        col = min(max(offset - starts[n - 1], lo), hi) if line == n else lo
        cols = out.setdefault(line, {})
        cols[col] = cols.get(col, "") + tag
    return out, rest


def _put(text: str, cols: Mapping[int, str], lo: int = 0, hi: int = -1) -> str:
    """``text[lo:hi]`` with each boundary of ``cols`` at its column.

    A column counts in the whole text; ``hi`` of -1 is past its end,
    so a boundary at the end is put too.
    """
    end = len(text) + 1 if hi < 0 else hi
    cut = text[lo:end]
    at = {c - lo: tag for c, tag in cols.items() if lo <= c < end}
    return "".join(at.get(k, "") + ch for k, ch in enumerate(cut)) + at.get(
        len(cut), ""
    )


def _refs(
    text: str, cols: Mapping[int, str], link: Callable[[str, str], str]
) -> str:
    """A prose line, its `name' references linked, boundaries placed.

    A boundary inside a reference goes into the name the link shows,
    so the reference still links.
    """
    out: list[str] = []
    pos = 0
    for m in REF.finditer(text):
        a, b = m.span()
        inner = {c - a - 1: tag for c, tag in cols.items() if a < c < b}
        out += [
            _put(text, cols, pos, a),
            cols.get(a, ""),
            link(m["name"], _put(m["name"], inner)),
        ]
        pos = b
    return "".join(out) + _put(text, cols, pos)


def _prose(
    s: Section, defs: dict[str, int], md: MarkdownIt, at: Boundaries
) -> str:
    def link(name: str, shown: str) -> str:
        n = defs.get(name.rsplit(".", maxsplit=1)[-1])
        code = f"<code>{html.escape(shown)}</code>"
        return f'<a href="#s{n}">{code}</a>' if n else code

    text = "\n".join(
        _put(line.text, at.get(line.number, {}))
        if line.fenced
        else _refs(line.text, at.get(line.number, {}), link)
        for line in s.prose
    )
    return str(md.render(text))


def _code(
    s: Section,
    first: dict[str, int],
    used: dict[str, list[int]],
    at: Boundaries,
) -> str:
    chunk = s.chunk
    assert chunk is not None
    rows: list[str] = []
    for k, text in enumerate(chunk.body):
        cols = at.get(chunk.line + 1 + k, {})
        m = USE.fullmatch(text)
        if m and norm(m["name"]) in first:
            name = norm(m["name"])
            n = first[name]
            rows.append(
                f"{html.escape(_put(m['indent'], cols))}"
                f'<a class="use" href="#s{n}">'
                f"⟨{html.escape(name)} §{n}⟩</a>"
            )
        else:
            rows.append(html.escape(_put(text, cols)))
    sign = "+≡" if chunk.plus else "≡"
    head = f"⟨{html.escape(chunk.name)} §{first[chunk.name]}⟩ {sign}"
    if is_file(chunk.name):
        foot = f"This is the file <code>{html.escape(chunk.name)}</code>."
    else:
        where = ", ".join(
            f'<a href="#s{n}">§{n}</a>' for n in used.get(chunk.name, [])
        )
        foot = f"This code is used in {where}."
    body = "\n".join(rows)
    return (
        f'<div class="chunk"><div class="head">{head}</div>'
        f'<pre>{body}</pre><div class="foot">{foot}</div></div>'
    )


def _mark(row: Row, first: bool) -> str:
    """The opening tag of a hand span's mark; the first has its id."""
    rid = html.escape(str(row["id"]))
    anchor = f' id="fact-{rid}"' if first else ""
    return f'<mark class="fact fact-{row["state"]}"{anchor} data-id="{rid}">'


def _marks(body: str, spans: Sequence[Row]) -> str:
    """The rendered body, its boundaries made marks around its text.

    Every run of text between two tags or boundaries that holds more
    than white space is wrapped in the marks open over it, the earliest
    opened outermost. A span whose boundaries hold no such text is an
    empty mark where it closes, so its id still has a place.
    """
    out: list[str] = []
    active: list[int] = []
    shown: set[int] = set()
    for piece in PIECES.split(body):
        m = BOUNDARY.fullmatch(piece)
        if m and not m[1]:
            active.append(int(m[2]))
        elif m:
            k = int(m[2])
            active = [a for a in active if a != k]
            out += [] if k in shown else [_mark(spans[k], True), "</mark>"]
            shown.add(k)
        elif active and piece.strip() and not piece.startswith("<"):
            opens = [_mark(spans[a], a not in shown) for a in active]
            out += [*opens, piece, "</mark>" * len(active)]
            shown.update(active)
        else:
            out.append(piece)
    return "".join(out)


def _index(
    page: Page, defs: dict[str, int], used: dict[str, list[int]]
) -> str:
    first = _first(page)
    rows = [
        f"<tr><td>⟨{html.escape(name)}⟩</td><td><b>§{n}</b> "
        + " ".join(f"§{u}" for u in used.get(name, []))
        + "</td></tr>"
        for name, n in sorted(first.items())
    ]
    ids: list[str] = []
    for name, n in sorted(defs.items(), key=lambda i: i[0].lower()):
        word = re.compile(rf"\b{re.escape(name)}\b")
        at = [
            s.number
            for s in page.sections
            if s.chunk
            and s.number != n
            and any(map(word.search, s.chunk.body))
        ]
        ids.append(
            f"<tr><td><code>{html.escape(name)}</code></td>"
            f'<td><a href="#s{n}"><b>§{n}</b></a> '
            + " ".join(f'<a href="#s{u}">§{u}</a>' for u in at)
            + "</td></tr>"
        )
    return (
        '<h2 id="index">Index</h2><h3>Chunks</h3><table>'
        + "".join(rows)
        + "</table><h3>Identifiers</h3><table>"
        + "".join(ids)
        + "</table>"
    )


def _kind(row: Row) -> str:
    """A hand row is a span, a relation, or a fact about rows."""
    if "item" in row:
        return "span"
    labels = cast("list[str]", row.get("labels", []))
    return "relation" if labels[:1] and labels[0] in RELATIONS else "fact"


@dataclass(frozen=True)
class Notes:
    """What the footnotes of a page are written from.

    Attributes:
        item: The page's path from the repository, as rows name it.
        rows: Every row of the page's fact layer, by id.
        marked: The ids of the hand spans marked on the page.
        sections: Each page line to the number of its section.
        starts: Where each page line starts, in code points.
        cited: Each row's id to the hand rows that target it.
    """

    item: str
    rows: Mapping[str, Row]
    marked: frozenset[str]
    sections: Mapping[int, int]
    starts: Sequence[int]
    cited: Mapping[str, list[str]]

    def link(self, rid: str) -> str:
        """A hand row's id, linked to its footnote."""
        return f'<a href="#fn-{rid}"><code>{rid}</code></a>'

    def target(self, tid: str) -> str:
        """A target: a hand row, a ledger row, or a generated span.

        A generated span on the page links to its section; one in
        another file shows its kind and label.
        """
        row = self.rows[tid]
        kind = row.get("kind")
        if kind is None:
            return self.link(tid)
        labels = cast("list[str]", row["labels"])
        if kind == "ledger":
            title = html.escape(" · ".join(labels))
            reason = html.escape(str(row["note"]))
            return (
                f'<span class="ledger" title="{title}"><b>{tid}</b> '
                f"<q>{html.escape(str(row['text']))}</q>"
                + (f" ({reason})" if reason else "")
                + "</span>"
            )
        shown = html.escape(" ".join([str(kind), *labels[:1]]))
        n = 0
        if row["item"] == self.item:
            line = bisect_right(self.starts, cast("int", row["start"]))
            n = self.sections.get(line, 0)
        return f'<a href="#s{n}">{shown}</a>' if n else shown

    def span(self, row: Row) -> str:
        """A hand span: text, state, file if not the page, commit."""
        meta = [str(row["state"])]
        if row["item"] != self.item:
            meta.append(f"in <code>{html.escape(str(row['item']))}</code>")
        if "commit" in row:
            commit = str(row["commit"])
            meta.append(f'at <abbr title="{commit}">{commit[:12]}</abbr>')
        text = html.escape(str(row["text"]))
        return f'<q>{text}</q> <span class="meta">{", ".join(meta)}</span>'

    def entry(self, row: Row) -> str:
        """One hand row's footnote."""
        rid = str(row["id"])
        kind = _kind(row)
        labels = cast("list[str]", row.get("labels", []))
        targets = [
            self.target(t) for t in cast("list[str]", row.get("targets", []))
        ]
        parts = [
            f'<a href="#fact-{rid}"><code>{rid}</code></a>'
            if rid in self.marked
            else f"<code>{rid}</code>"
        ]
        if kind != "relation" and labels:
            parts.append(f"[{html.escape(', '.join(labels))}]")
        if kind == "span":
            parts.append(self.span(row))
        if kind == "relation":
            rest = ", ".join(targets[1:])
            parts.append(f"{html.escape(labels[0])}: {targets[0]} → {rest}")
        elif targets:
            parts.append("about " + ", ".join(targets))
        if note := str(row.get("note", "")):
            parts.append(f"— {html.escape(note)}")
        if by := self.cited.get(rid):
            parts.append("cited by " + ", ".join(map(self.link, by)))
        state = f' class="fact-{row["state"]}"' if "state" in row else ""
        return f'<li id="fn-{rid}"{state}>' + " ".join(parts) + "</li>"


def _legend(hand: Sequence[Row]) -> str:
    """The legend of the marks, and the hand rows counted."""
    states = Counter(str(r["state"]) for r in hand if "state" in r)
    kinds = Counter(map(_kind, hand))
    counted = ", ".join(
        f"{states[s]} {s}"
        for s in (facts.VERS, facts.MOVED, facts.TWICE, facts.STALE)
    )
    return (
        '<p class="legend"><mark class="fact fact-vers">vers</mark>: the'
        " text is where it was written; "
        '<mark class="fact fact-verplaatst">verplaatst</mark>: it is'
        ' found once, elsewhere; <span class="fact-dubbel">dubbel</span>:'
        ' found more than once; <span class="fact-stale">stale</span>: not'
        " found. Only the first two are marked on the page.</p>"
        f'<p class="counts">{len(hand)} rows: {kinds["span"]} spans'
        f" ({counted}), {kinds['fact']} facts,"
        f" {kinds['relation']} relations.</p>"
    )


def _notes(page: Page, text: str, rows: Sequence[Row], item: str) -> str:
    """The footnotes: a legend, the counts, one entry per hand row."""
    hand = [r for r in rows if "kind" not in r]
    sections = {
        line.number: s.number for s in page.sections for line in s.prose
    }
    for s in page.sections:
        if c := s.chunk:
            for n in range(c.line - c.head, c.line + len(c.body) + 2):
                sections[n] = s.number
    cited: dict[str, list[str]] = {}
    for r in hand:
        for t in cast("list[str]", r.get("targets", [])):
            cited.setdefault(t, []).append(str(r["id"]))
    notes = Notes(
        item,
        {str(r["id"]): r for r in rows},
        frozenset(str(r["id"]) for r in _spans(hand, item)),
        sections,
        facts.Text.of(item, text).starts,
        cited,
    )
    return (
        '<section class="facts" id="facts"><h2>Facts</h2>'
        + _legend(hand)
        + "<ul>"
        + "".join(map(notes.entry, hand))
        + "</ul></section>"
    )


def _spans(hand: Sequence[Row], item: str) -> list[Row]:
    """The hand spans found on the page, in the sidecar's order."""
    return [
        r for r in hand if r.get("item") == item and r.get("state") in MARKED
    ]


def weave(
    page: Page,
    tangled: list[Tangled],
    title: str,
    text: str = "",
    rows: Sequence[Row] = (),
) -> str:
    """The page as one HTML document.

    Args:
        page: The page, read.
        tangled: Its files.
        title: The document's title.
        text: The page's text, which the rows' offsets count in.
        rows: The page's fact layer (`facts.generate'); with no hand
            row in it, the page is woven as if there were none.
    """
    md = MarkdownIt("commonmark").enable("table")
    defs = defining(tangled, page)
    used = uses(page)
    first = _first(page)
    hand = [r for r in rows if "kind" not in r]
    item = next((str(r["item"]) for r in rows if r.get("kind") == "chunk"), "")
    spans = _spans(hand, item)
    at, rest = _boundaries(
        page,
        text,
        [
            (cast("int", r["currentStart"]), cast("int", r["currentEnd"]))
            for r in spans
        ],
    )
    style = STYLE + (FACTS_STYLE if hand else "")
    body = [
        f'<section id="s{s.number}"><span class="num">§{s.number}</span>'
        + _prose(s, defs, md, at)
        + (_code(s, first, used, at) if s.chunk else "")
        + "</section>"
        for s in page.sections
    ]
    parts = [
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}"
        f"</title><style>{style}</style>",
        _marks("\n".join(body) + rest, spans),
        _index(page, defs, used),
    ]
    if hand:
        parts.append(_notes(page, text, rows, item))
    return "\n".join(parts) + "\n"

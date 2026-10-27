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
"""

from __future__ import annotations

import ast
import html
import re

from markdown_it import MarkdownIt

from lit.lint import REF, definitions
from lit.web import USE, Page, Section, Tangled, is_file, norm

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


def _prose(s: Section, defs: dict[str, int], md: MarkdownIt) -> str:
    def link(m: re.Match[str]) -> str:
        name = m["name"]
        n = defs.get(name.split(".")[-1])
        shown = html.escape(name)
        return (
            f'<a href="#s{n}"><code>{shown}</code></a>'
            if n
            else (f"<code>{shown}</code>")
        )

    text = "\n".join(
        line.text if line.fenced else REF.sub(link, line.text)
        for line in s.prose
    )
    return str(md.render(text))


def _code(
    s: Section, first: dict[str, int], used: dict[str, list[int]]
) -> str:
    chunk = s.chunk
    assert chunk is not None
    rows: list[str] = []
    for text in chunk.body:
        m = USE.fullmatch(text)
        if m and norm(m["name"]) in first:
            name = norm(m["name"])
            n = first[name]
            rows.append(
                f'{html.escape(m["indent"])}<a class="use" href="#s{n}">'
                f"⟨{html.escape(name)} §{n}⟩</a>"
            )
        else:
            rows.append(html.escape(text))
    sign = "+≡" if chunk.plus else "≡"
    head = f"⟨{html.escape(chunk.name)} §{first[chunk.name]}⟩ {sign}"
    if is_file(chunk.name):
        foot = f"This is the file <code>{html.escape(chunk.name)}</code>."
    else:
        at = ", ".join(
            f'<a href="#s{n}">§{n}</a>' for n in used.get(chunk.name, [])
        )
        foot = f"This code is used in {at}."
    body = "\n".join(rows)
    return (
        f'<div class="chunk"><div class="head">{head}</div>'
        f'<pre>{body}</pre><div class="foot">{foot}</div></div>'
    )


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


def weave(page: Page, tangled: list[Tangled], title: str) -> str:
    """The page as one HTML document."""
    md = MarkdownIt("commonmark").enable("table")
    defs = defining(tangled, page)
    used = uses(page)
    first = _first(page)
    parts = [
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}"
        f"</title><style>{STYLE}</style>"
    ]
    for s in page.sections:
        parts.append(
            f'<section id="s{s.number}"><span class="num">§{s.number}</span>'
            + _prose(s, defs, md)
            + (_code(s, first, used) if s.chunk else "")
            + "</section>"
        )
    parts.append(_index(page, defs, used))
    return "\n".join(parts) + "\n"

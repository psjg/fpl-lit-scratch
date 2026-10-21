"""
What an editor wants to know about a source, as plain data: where it is
wrong (diagnostics) and what each word is (semantic tokens). No LSP
here, so the browser (Pyodide) and the language server share it.

Diagnostics are the interpreter's own: parse, desugar and elaborate, the
first refusal wins (the pipeline stops at one). Semantic tokens come from
the surface AST plus the names the program defines (`name : ins -- outs`
lines, the same `desugar.definition` the resolver uses), so a word that
names a definition is a `function` and the rest follow the shape the
affix pass read.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from fpl import trivia
from fpl.ast_surface import Enclosure, Line, Program, Text, Word
from fpl.desugar import definition
from fpl.driver import checked
from fpl.errors import FplError
from fpl.parse import parse

LEGEND_TYPES = ("variable", "function", "number", "namespace", "operator")
LEGEND_MODIFIERS = ("declaration",)
# The characters a token stops at: the grammar's TOKEN class (grammar.lark).
WORD = re.compile(r"[^\s\[\]()“”「」⟦⟧⟨⟩{}|⍝;]+")


@dataclass(frozen=True)
class Diagnostic:
    """
    One refusal: 0-based line and start column, 0-based end column.
    """

    line: int
    start: int
    end: int
    message: str


@dataclass(frozen=True)
class Token:
    """
    A highlighted run: 0-based line and column, length, an index into
    LEGEND_TYPES, a bit set over LEGEND_MODIFIERS.
    """

    line: int
    col: int
    length: int
    kind: int
    mods: int = 0


def _rows(source: str) -> list[str]:
    """
    The source's lines the way lex.Lines counts them: by `\\n` only (a
    form feed is a page separator, not a line break), without a `\\r`.
    """
    return [row.removesuffix("\r") for row in source.split("\n")]


def utf16(row: str, col: int) -> int:
    """
    A code-point column as the UTF-16 units LSP positions count.
    """
    return len(row[:col].encode("utf-16-le")) // 2


def diagnose(source: str) -> list[Diagnostic]:
    """
    The interpreter's refusal of this source as at most one diagnostic;
    empty when the program parses, resolves and checks.
    """
    try:
        checked(source)
    except FplError as failure:
        lines = _rows(source)
        row = min(max(failure.span.line - 1, 0), len(lines) - 1)
        col = max(failure.span.col - 1, 0)
        run = WORD.match(lines[row], col)
        end = run.end() if run else min(col + 1, len(lines[row]))
        return [Diagnostic(row, col, max(end, col + 1), failure.message)]
    return []


def _words(lines: tuple[Line, ...]) -> Iterator[Word]:
    for line in lines:
        for frame in line.frames:
            for cell in frame.cells:
                for item in cell.items:
                    yield from _item(item)
        yield from _words(line.block)


def _item(item: Word | Text | Enclosure) -> Iterator[Word]:
    match item:
        case Word():
            yield item
        case Enclosure():
            for frame in item.frames:
                for cell in frame.cells:
                    for inner in cell.items:
                        yield from _item(inner)
        case Text():
            for part in item.parts:
                if isinstance(part, Program):
                    yield from _words(part.lines)


def _defined(lines: tuple[Line, ...]) -> dict[tuple[int, int], str]:
    """
    Each `name : ins -- outs` line's head word, by position, and its name.
    """
    found: dict[tuple[int, int], str] = {}
    for line in lines:
        if trivia.head(line):
            try:
                got = definition(line)
            except FplError:
                got = None
            if got is not None:
                head = line.frames[0].cells[0].items[0]
                found[(head.span.line, head.span.col)] = got[0]
        found.update(_defined(line.block))
    return found


def tokens(source: str) -> list[Token]:
    """
    A semantic token for every word of a source that parses, in source
    order; none when it does not (the diagnostics say why).
    """
    try:
        program = parse(source)
    except FplError:
        return []
    heads = _defined(program.lines)
    names = set(heads.values())
    rows = _rows(source)
    out: list[Token] = []
    for word in _words(program.lines):
        row, col = word.span.line - 1, word.span.col - 1
        run = WORD.match(rows[row], col)
        if run is None:
            continue
        spelled = "/".join(word.body)
        if (word.span.line, word.span.col) in heads:
            kind, mods = LEGEND_TYPES.index("function"), 1
        elif word.kind == "number":
            kind, mods = LEGEND_TYPES.index("number"), 0
        elif word.kind == "modifier":
            kind, mods = LEGEND_TYPES.index("operator"), 0
        elif word.kind == "path":
            kind, mods = LEGEND_TYPES.index("namespace"), 0
        elif spelled in names:
            kind, mods = LEGEND_TYPES.index("function"), 0
        else:
            kind, mods = LEGEND_TYPES.index("variable"), 0
        out.append(Token(row, col, run.end() - col, kind, mods))
    out.sort(key=lambda t: (t.line, t.col))
    return out


def encode(found: list[Token]) -> list[int]:
    """
    LSP's relative encoding: five integers a token, line and start as
    deltas from the previous token (spec 3.17, semanticTokens).
    """
    data: list[int] = []
    line = col = 0
    for token in found:
        data += [
            token.line - line,
            token.col - (col if token.line == line else 0),
            token.length,
            token.kind,
            token.mods,
        ]
        line, col = token.line, token.col
    return data

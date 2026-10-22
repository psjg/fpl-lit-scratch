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

LEGEND_TYPES = (
    "variable",
    "function",
    "number",
    "namespace",
    "operator",
    "parameter",
)
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


def _head_words(line: Line) -> list[Word]:
    """
    The words of a definition line's first cell (`name : ins -- outs`).
    """
    return [w for w in line.frames[0].cells[0].items if isinstance(w, Word)]


def tokens(source: str) -> list[Token]:
    """
    A semantic token for every word of a source that parses, in source
    order; none when it does not (the diagnostics say why). A definition
    line's name is a `function` (declaration), the names before its `--`
    are `parameter`s (declaration), and inside its block a word spelled
    as a parameter is a `parameter` use, one spelled as a definition a
    `function` use.
    """
    try:
        program = parse(source)
    except FplError:
        return []
    rows = _rows(source)
    names = _defined_names(program.lines)
    out: list[Token] = []
    kinds = {k: LEGEND_TYPES.index(k) for k in LEGEND_TYPES}

    def put(word: Word, kind: str, mods: int = 0) -> None:
        row, col = word.span.line - 1, word.span.col - 1
        run = WORD.match(rows[row], col)
        if run is not None:
            out.append(Token(row, col, run.end() - col, kinds[kind], mods))

    def plain(word: Word, params: frozenset[str]) -> None:
        spelled = "/".join(word.body)
        if word.kind == "number":
            put(word, "number")
        elif word.kind == "modifier":
            put(word, "operator")
        elif word.kind == "path":
            put(word, "namespace")
        elif spelled in params:
            put(word, "parameter")
        elif spelled in names:
            put(word, "function")
        else:
            put(word, "variable")

    def walk(lines: tuple[Line, ...], params: frozenset[str]) -> None:
        for line in lines:
            inner = params
            got = _definition(line)
            if got is not None:
                head = _head_words(line)
                put(head[0], "function", 1)
                before = True
                for word in head[1:]:
                    spelled = "/".join(word.body)
                    if spelled in {":", "--"}:
                        before = before and spelled != "--"
                        put(word, "operator")
                    elif word.kind == "name" and before:
                        put(word, "parameter", 1)
                        inner = inner | {spelled}
                    else:
                        plain(word, params)
                rest = [
                    i for fr in line.frames for c in fr.cells for i in c.items
                ][len(head) :]
                for item in rest:
                    for word in _item(item):
                        plain(word, inner)
            else:
                for frame in line.frames:
                    for cell in frame.cells:
                        for item in cell.items:
                            for word in _item(item):
                                plain(word, params)
            walk(line.block, inner)

    walk(program.lines, frozenset())
    out.sort(key=lambda t: (t.line, t.col))
    return out


def _definition(line: Line) -> tuple[str, object] | None:
    try:
        return definition(line) if trivia.head(line) else None
    except FplError:
        return None


def _defined_names(lines: tuple[Line, ...]) -> set[str]:
    """
    The names the program defines, anywhere in it.
    """
    found: set[str] = set()
    for line in lines:
        got = _definition(line)
        if got is not None:
            found.add(got[0])
        found |= _defined_names(line.block)
    return found


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


def lsp_data(source: str) -> list[int]:
    """
    The document's semantic tokens as the integers LSP and Monaco
    send: positions in UTF-16 units, relative encoding.
    """
    rows = _rows(source)
    units = [
        Token(
            t.line,
            utf16(rows[t.line], t.col),
            utf16(rows[t.line], t.col + t.length) - utf16(rows[t.line], t.col),
            t.kind,
            t.mods,
        )
        for t in tokens(source)
    ]
    return encode(units)


@dataclass(frozen=True)
class Def:
    """
    A definition line: its name's position, its inputs, the last line of
    its block (0-based), and the line as written without its note.
    """

    name: str
    line: int
    col: int
    params: tuple[str, ...]
    last: int
    head: str


def _last(line: Line) -> int:
    return max([line.span.line - 1, *[_last(b) for b in line.block]])


def definitions(source: str) -> list[Def]:
    """
    Every definition line of a source that parses, in source order.
    """
    try:
        program = parse(source)
    except FplError:
        return []
    rows = _rows(source)
    found: list[Def] = []

    def walk(lines: tuple[Line, ...]) -> None:
        for line in lines:
            if _definition(line) is not None:
                words = _head_words(line)
                names = [w.body[0] for w in words[1:]]
                cut = names.index("--") if "--" in names else len(names)
                params = tuple(
                    n for n in names[:cut] if n != ":" and n.strip()
                )
                row = line.span.line - 1
                found.append(
                    Def(
                        words[0].body[0],
                        row,
                        words[0].span.col - 1,
                        params,
                        _last(line),
                        rows[row].split(";")[0].strip(),
                    )
                )
            walk(line.block)

    walk(program.lines)
    return found


def _word_at(rows: list[str], line: int, col: int) -> tuple[str, int] | None:
    """
    The word under (line, col), 0-based, with its start column.
    """
    if not 0 <= line < len(rows):
        return None
    for run in WORD.finditer(rows[line]):
        if run.start() <= col <= run.end():
            return run.group(), run.start()
    return None


def _target(
    source: str, line: int, col: int
) -> tuple[str, str, Def | None] | None:
    """
    What the word under the cursor is: ('function', name, its Def) or
    ('parameter', name, the Def whose block holds it).
    """
    rows = _rows(source)
    hit = _word_at(rows, line, col)
    if hit is None:
        return None
    text = hit[0]
    defs = definitions(source)
    for d in defs:
        if d.line <= line <= d.last and text in d.params:
            return "parameter", text, d
    for d in defs:
        if d.name == text:
            return "function", text, d
    return None


def hover(source: str, line: int, col: int) -> str | None:
    """
    Markdown for the word under the cursor: the definition line (its
    stack effect) of a defined name, or the owner of a parameter.
    """
    got = _target(source, line, col)
    if got is None:
        return None
    kind, name, d = got
    assert d is not None
    if kind == "function":
        return f"```fpl\n{d.head}\n```"
    return f"parameter `{name}` of `{d.name}`\n\n```fpl\n{d.head}\n```"


def goto(source: str, line: int, col: int) -> tuple[int, int, int] | None:
    """
    Where the word under the cursor is defined: (line, col, length).
    """
    got = _target(source, line, col)
    if got is None:
        return None
    kind, name, d = got
    assert d is not None
    if kind == "function":
        return d.line, d.col, len(name)
    row = _rows(source)[d.line]
    after = row.index(":", d.col) if ":" in row[d.col :] else d.col
    for run in WORD.finditer(row, after):
        if run.group() == name:
            return d.line, run.start(), len(name)
    return None


def complete(source: str, line: int) -> list[tuple[str, str, str]]:
    """
    The names in scope at a line: (label, kind, detail), defined names
    and the parameters of the definition holding the line.
    """
    defs = definitions(source)
    items = [(d.name, "function", d.head) for d in defs]
    for d in defs:
        if d.line < line <= d.last:
            items += [(p, "parameter", f"of {d.name}") for p in d.params]
    return items


def rename(
    source: str, line: int, col: int, new: str
) -> list[tuple[int, int, int, str]]:
    """
    The edits (line, col, length, text) that rename the word under the
    cursor everywhere its meaning reaches: a definition across the
    program, a parameter across its definition's block.
    """
    got = _target(source, line, col)
    if got is None:
        return []
    kind, name, d = got
    assert d is not None
    rows = _rows(source)
    want = LEGEND_TYPES.index(kind)
    edits = []
    for t in tokens(source):
        if t.kind != want or rows[t.line][t.col : t.col + t.length] != name:
            continue
        if kind == "parameter" and not d.line <= t.line <= d.last:
            continue
        edits.append((t.line, t.col, t.length, new))
    return edits


def serve(
    op: str, source: str, line: int = 0, col: int = 0, arg: str = ""
) -> str:
    """
    One entry point for a host that speaks JSON (the Pyodide page):
    positions in and out are 0-based UTF-16 units; the result is JSON.
    """
    import json

    rows = _rows(source)

    def to_cp(row: int, units: int) -> int:
        text = rows[row] if 0 <= row < len(rows) else ""
        count = 0
        for i, ch in enumerate(text):
            if count >= units:
                return i
            count += 2 if ord(ch) > 0xFFFF else 1
        return len(text)

    def span(row: int, c: int, n: int) -> list[int]:
        return [row, utf16(rows[row], c), utf16(rows[row], c + n)]

    col = to_cp(line, col)
    if op == "tokens":
        return json.dumps(lsp_data(source))
    if op == "diagnose":
        return json.dumps(
            [
                [*span(d.line, d.start, d.end - d.start), d.message]
                for d in diagnose(source)
            ]
        )
    if op == "hover":
        return json.dumps(hover(source, line, col))
    if op == "goto":
        hit = goto(source, line, col)
        return json.dumps(span(*hit) if hit else None)
    if op == "complete":
        return json.dumps(complete(source, line))
    if op == "rename":
        return json.dumps(
            [
                [*span(r, c, n), text]
                for r, c, n, text in rename(source, line, col, arg)
            ]
        )
    raise ValueError(op)

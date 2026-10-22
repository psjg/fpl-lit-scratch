"""
A tree-sitter grammar for FPL, generated from `fpl/grammar.lark` and the
tables of `fpl/lex.py` and `fpl/parse.py`:

    grammar.js     every rule of grammar.lark, translated from Lark's own
                   EBNF trees; terminals from `parser().terminals`; the
                   brackets that suspend newlines from FplIndenter
    src/scanner.c  scanner.c.in (hand-written: the indentation stack and
                   the line-break protocol) with its tables generated: the
                   counted pairs from lex.PAIRS, the note marks from the
                   NOTE terminal
    queries/highlights.scm  from the same tables as gen_highlight.py

Tree-sitter rejects rules that match the empty string, and grammar.lark
has them (`frame` may be empty: an empty enclosure is one empty frame).
`nonempty` rewrites such a rule to its non-empty part and every use of it
to `optional(...)`, so the tree has no empty nodes.

    PYTHONPATH=. python ide/gen_treesitter.py [--check]

--check regenerates in memory and fails when a tracked file differs.
"""

import json
import re
import sys
from pathlib import Path

from lark.load_grammar import GrammarBuilder

from fpl import lex
from fpl.parse import GRAMMAR, FplIndenter, parser
from ide.gen_highlight import shapes

HERE = Path(__file__).resolve().parent / "tree-sitter-fpl"
NAME = "fpl"
# The only hand-written naming: what each counted pair is called as a node.
PAIR_NODE = {"“": "string", "「": "raw_string", "⟦": "block_comment"}
# Terminals the scanner produces (the pre-lexer and the Indenter in Lark).
EXTERNAL = {
    "_NL": "_nl",
    "_INDENT": "_indent",
    "_DEDENT": "_dedent",
    "NOTE": "note",
}
NODE = {"TOKEN": "word"}

type Expr = tuple


def lark_rules() -> dict[str, tuple[Expr, bool]]:
    """
    Each rule of grammar.lark as (expression, inlined-by-`?`), in source
    order.
    """
    builder = GrammarBuilder()
    builder.load_grammar(GRAMMAR.read_text(), str(GRAMMAR))
    return {
        str(name): (_expr(d.tree), bool(d.options and d.options.expand1))
        for name, d in builder._definitions.items()  # noqa: SLF001
        if not d.is_term
    }


def _expr(tree) -> Expr:
    """
    Lark's EBNF tree as ('seq'|'choice'|'opt'|'rep'|'rep1', ...),
    ('sym', rule), ('tok', terminal) or ('lit', text).
    """
    kind = getattr(tree, "data", None)
    if kind == "expansions":
        alts = [_expr(c) for c in tree.children]
        return alts[0] if len(alts) == 1 else ("choice", *alts)
    if kind == "expansion":
        parts = [_expr(c) for c in tree.children]
        return parts[0] if len(parts) == 1 else ("seq", *parts)
    if kind == "value":
        return _expr(tree.children[0])
    if kind == "literal":
        return ("lit", str(tree.children[0])[1:-1])
    if kind == "expr":
        inner = _expr(tree.children[0])
        return (
            {"?": "opt", "*": "rep", "+": "rep1"}[str(tree.children[1])],
            inner,
        )
    name = type(tree).__name__
    if name == "NonTerminal":
        return ("sym", str(tree.name))
    if name == "Terminal":
        return ("tok", str(tree.name))
    raise SystemExit(f"grammar.lark construct not handled: {tree!r}")


def literal_of(name: str) -> str | None:
    """
    The text of a string terminal (`_BAR`, `LSQB`), else None.
    """
    for terminal in parser().terminals:
        if terminal.name == name and terminal.pattern.type == "str":
            return terminal.pattern.value
    return None


def _drop(expr: Expr, gone: str) -> Expr | None:
    """
    The expression without terminal `gone` (a newline in a bracket is
    whitespace to the Indenter), or None when nothing is left.
    """
    op = expr[0]
    if op == "tok":
        return None if expr[1] == gone else expr
    if op in {"sym", "lit"}:
        return expr
    kids = [k for k in (_drop(c, gone) for c in expr[1:]) if k is not None]
    if not kids:
        return None
    return (
        kids[0] if len(kids) == 1 and op in {"seq", "choice"} else (op, *kids)
    )


class Translator:
    """
    grammar.lark to grammar.js: names, terminals, the empty-rule rewrite.
    """

    def __init__(self) -> None:
        self.rules = lark_rules()
        opens = {literal_of(n) for n in FplIndenter.OPEN_PAREN_types}
        closes = {literal_of(n) for n in FplIndenter.CLOSE_PAREN_types}
        self.bracketed: set[str] = set()
        for name, (expr, inline) in self.rules.items():
            if (
                expr[0] == "seq"
                and self._text(expr[1]) in opens
                and self._text(expr[-1]) in closes
            ):
                self.bracketed.add(name)
                self.rules[name] = (_drop(expr, "_NL") or expr, inline)
        self.null = {n: False for n in self.rules}
        changed = True
        while changed:
            changed = False
            for name, (expr, _) in self.rules.items():
                if not self.null[name] and self.nullable(expr):
                    self.null[name] = changed = True

    @staticmethod
    def _text(e: Expr) -> str | None:
        return (
            e[1]
            if e[0] == "lit"
            else literal_of(e[1])
            if e[0] == "tok"
            else None
        )

    def nullable(self, e: Expr) -> bool:
        """Can `e` match the empty string?"""
        op = e[0]
        if op == "sym":
            return self.null[e[1]]
        if op in {"tok", "lit"}:
            return False
        if op in {"opt", "rep"}:
            return True
        if op == "rep1":
            return self.nullable(e[1])
        if op == "seq":
            return all(self.nullable(c) for c in e[1:])
        return any(self.nullable(c) for c in e[1:])

    def part(self, e: Expr) -> Expr:
        """`e` as the content of an optional or repetition."""
        return self.nonempty(e) if self.nullable(e) else self.fix(e)

    def use(self, e: Expr) -> Expr:
        """`e` where it may be absent: a nullable part becomes optional."""
        return ("opt", self.nonempty(e)) if self.nullable(e) else self.fix(e)

    def fix(self, e: Expr) -> Expr:
        """An expression with nullable children made optional."""
        op = e[0]
        if op in {"tok", "lit"}:
            return e
        if op == "sym":
            return ("opt", e) if self.null[e[1]] else e
        if op == "seq":
            return ("seq", *[self.use(c) for c in e[1:]])
        if op == "choice":
            return ("choice", *[self.fix(c) for c in e[1:]])
        return (op, self.part(e[1]))

    def nonempty(self, e: Expr) -> Expr:
        """`e` minus its empty match."""
        op = e[0]
        if op in {"tok", "lit", "sym"}:
            return e  # a rule is emitted in its non-empty form
        if op == "opt":
            return self.part(e[1])
        if op in {"rep", "rep1"}:
            return ("rep1", self.part(e[1]))
        if op == "choice":
            return (
                "choice",
                *[
                    self.nonempty(c) if self.nullable(c) else self.fix(c)
                    for c in e[1:]
                ],
            )
        alts: list[Expr] = []
        for i, c in enumerate(e[1:], 1):
            alts.append(
                ("seq", self.part(c), *[self.use(r) for r in e[i + 1 :]])
            )
            if not self.nullable(c):
                break
        return alts[0] if len(alts) == 1 else ("choice", *alts)


def regex(pattern: str) -> str:
    """A Python regex source as a JS regex literal."""
    for old, new in (
        ("/", "\\/"),
        ("\t", "\\t"),
        ("\x0c", "\\f"),
        ("\n", "\\n"),
        ("\r", "\\r"),
    ):
        pattern = pattern.replace(old, new)
    return f"/{pattern}/"


def js(e: Expr, hidden: dict[str, str]) -> str:
    """An expression as grammar.js source."""
    op = e[0]
    if op == "lit":
        return json.dumps(e[1], ensure_ascii=False)
    if op == "tok":
        if e[1] in EXTERNAL:
            return f"$.{EXTERNAL[e[1]]}"
        if e[1] == "TOKEN":  # the pre-lexer's placeholder is a TOKEN in Lark
            strings = ", ".join(
                f"$.{PAIR_NODE[o]}"
                for o in lex.PAIRS
                if PAIR_NODE[o] != "block_comment"
            )
            return f"choice($.{hidden[e[1]]}, {strings})"
        lit = literal_of(e[1])
        return (
            json.dumps(lit, ensure_ascii=False)
            if lit is not None
            else f"$.{hidden[e[1]]}"
        )
    if op == "sym":
        return f"$.{hidden.get(e[1], e[1])}"
    fn = {
        "seq": "seq",
        "choice": "choice",
        "opt": "optional",
        "rep": "repeat",
        "rep1": "repeat1",
    }[op]
    return f"{fn}({', '.join(js(c, hidden) for c in e[1:])})"


def grammar_js() -> str:
    """The whole grammar.js."""
    t = Translator()
    terms = {x.name: x for x in parser().terminals}
    hidden = {"start": "source_file"}
    hidden |= {n: "_" + n for n, (_, inline) in t.rules.items() if inline}
    for name, term in terms.items():
        if (
            name not in EXTERNAL
            and term.pattern.type == "re"
            and not name.startswith("__")
        ):
            hidden[name] = NODE.get(name, name.lower())
    out = [
        "// GENERATED by 01-bootstrap/ide/gen_treesitter.py from fpl/grammar.lark, lex.py, parse.py.",
        "// Do not edit: change the sources or the generator.",
        "module.exports = grammar({",
        f'  name: "{NAME}",',
        "  externals: ($) => [",
        "    $._nl,",
        "    $._inner_nl, // a newline inside a bracket: whitespace to the Indenter",
        "    $._indent,",
        "    $._dedent,",
        *[f"    $.{PAIR_NODE[o]}," for o in lex.PAIRS],
        "    $.note,",
        "  ],",
        f"  extras: ($) => [{regex(terms['__IGNORE_0'].pattern.value)}, $.block_comment, $._inner_nl],",
        "  rules: {",
    ]
    for name, (expr, _) in t.rules.items():
        body = (
            t.nonempty(expr)
            if t.null[name] and name != "start"
            else t.fix(expr)
        )
        out.append(f"    {hidden.get(name, name)}: ($) => {js(body, hidden)},")
    for name, node in hidden.items():
        if name in terms:
            out.append(
                f"    {node}: () => {regex(terms[name].pattern.value)},"
            )
    return "\n".join([*out, "  },", "});", ""])


def scanner_c() -> str:
    """scanner.c from scanner.c.in and the tables."""
    pairs = list(lex.PAIRS.items())
    symbols = [
        "NL",
        "INNER_NL",
        "INDENT",
        "DEDENT",
        *[PAIR_NODE[o].upper() for o, _ in pairs],
        "NOTE",
    ]
    cp = lambda ch: f"0x{ord(ch):04X}"  # noqa: E731
    block = next(o for o in lex.PAIRS if PAIR_NODE[o] == "block_comment")
    tables = (
        f"enum {{ {', '.join(symbols)} }};\n"
        "static const struct { int32_t open, close; int symbol; } PAIRS[] = {\n"
        + "".join(
            f"  {{{cp(o)}, {cp(c)}, {PAIR_NODE[o].upper()}}},\n"
            for o, c in pairs
        )
        + "};\n"
        f"#define BLOCK_OPEN {cp(block)}\n#define BLOCK_CLOSE {cp(lex.PAIRS[block])}"
    )
    note = {x.name: x.pattern.value for x in parser().terminals}["NOTE"]
    head = re.match(r"\((.+?)\)\[\^\n\]\*", note)
    if head is None:
        raise SystemExit(f"NOTE no longer opens with a mark group: {note}")
    body = ["  int32_t c = l->lookahead;"]
    for alt in head.group(1).split("|"):
        doubled = re.fullmatch(r"(.)\(\?!\1\)", alt)
        mark = doubled.group(1) if doubled else alt
        refuse = f"l->lookahead == '{mark}' ? -1 : 1" if doubled else "1"
        body.append(f"  if (c == {cp(mark)}) {{ next(l); return {refuse}; }}")
    body.append("  return 0;")
    text = (HERE / "scanner.c.in").read_text()
    text = text.replace("@TABLES@", tables).replace(
        "@NOTE_MARK@", "\n".join(body)
    )
    return (
        "/* GENERATED by ide/gen_treesitter.py from scanner.c.in; do not edit. */\n"
        + text.replace("@NAME@", NAME)
    )


def highlights() -> str:
    """highlights.scm from the lex tables."""
    sh = shapes()
    esc = lambda s: s.replace("\\", "\\\\")  # noqa: E731
    brackets = " ".join(
        f'"{b}"' for pair in lex.BRACKETS.items() for b in pair
    )
    return (
        "; GENERATED by ide/gen_treesitter.py; the shapes are lex.py's, as predicates.\n"
        "; The generic word comes first: a later pattern wins.\n"
        "(word) @variable\n(note) @comment\n(doc) @comment.documentation\n"
        "(block_comment) @comment\n(string) @string\n(raw_string) @string.special\n"
        f'[{brackets} "|"] @punctuation.bracket\n'
        f'((word) @number (#match? @number "^{esc(sh["number"])}$"))\n'
        f'((word) @operator (#match? @operator "^{esc(sh["mods"])}$"))\n'
        f'((word) @keyword (#match? @keyword "^(?:{esc(sh["sigil"])})"))\n'
        '((word) @module (#match? @module "/"))\n'
    )


def outputs() -> dict[Path, str]:
    """Every generated file and its text."""
    return {
        HERE / "grammar.js": grammar_js(),
        HERE / "src" / "scanner.c": scanner_c(),
        HERE / "queries" / "highlights.scm": highlights(),
    }


def main() -> None:
    """Write, or with --check compare."""
    bad = False
    for path, text in outputs().items():
        if "--check" in sys.argv:
            if not path.exists() or path.read_text() != text:
                print(f"stale: {path}")
                bad = True
        else:
            path.write_text(text)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

"""
Syntax highlighting derived from the FPL sources: one generator, two
targets (a Monaco Monarch definition and a TextMate grammar).

What is mechanical: the terminal regexes (TOKEN, NOTE, DOC) are read out
of `fpl/grammar.lark` through Lark itself, and the pairs, the sigils, the
modifier set and the number shape are read out of `fpl/lex.py`, so a
change to either source changes the highlighter. What is not: the
tokenizers below (which state a string pushes, which rule order wins)
are written by hand, because Monarch and TextMate are regex state
machines and the grammar is a context-free one.

    python ide/gen_highlight.py monarch  > ../assets/fpl-language.js
    cp ../assets/fpl-language.js fpl/fpl-language.js  # the pad's copy
    python ide/gen_highlight.py textmate > ide/fpl.tmLanguage.json
"""

import json
import re
import sys

from fpl import lex
from fpl.parse import parser

SCOPE = "source.fpl"


def terminals() -> dict[str, str]:
    """
    The regex source of every named terminal of the grammar.
    """
    return {t.name: t.pattern.to_regexp() for t in parser().terminals}


def delimiters() -> str:
    """
    The characters a TOKEN may not contain, as the inside of a regex
    class, read from the grammar's own TOKEN terminal.
    """
    token = terminals()["TOKEN"]
    inner = re.fullmatch(r"\(\?:\[\^(.*)\]\+\)|\[\^(.*)\]\+", token)
    if inner is None:
        msg = f"TOKEN no longer has the shape [^...]+: {token}"
        raise SystemExit(msg)
    return inner.group(1) or inner.group(2)


def shapes() -> dict[str, str]:
    """
    The regex (JS and Oniguruma compatible) of each token shape, from
    lex.py. Each is anchored by the caller.
    """
    sigil = lex.SHAPE.pattern.split(")?", 1)[0].lstrip("(")
    mods = lex.MODS
    return {
        "sigil": sigil,
        # a number with its modifiers, as lex.shape reads `5´`
        "number": f"(?:{sigil})?{lex.NUMBER.pattern}[{mods}]*",
        "mods": f"[{mods}]+",
    }


def monarch() -> dict:
    """
    A Monaco Monarch language definition.
    """
    d = delimiters()
    sh = shapes()
    word = f"[^{d}\\s]+"
    pairs = lex.PAIRS
    open_brackets = "".join(lex.BRACKETS)
    close_brackets = "".join(lex.BRACKETS.values())
    code = [
        [";;;;[^\\n]*", "comment.file"],
        [";;;[^\\n]*", "comment.section"],
        [";;[^\\n]*", "comment.doc"],
        ["(?:;|⍝)[^\\n]*", "comment"],
        ["“", {"token": "string.quote", "next": "@str"}],
        ["「", {"token": "string.quote", "next": "@raw"}],
        ["⟦", {"token": "comment.block", "next": "@block"}],
        [
            f"[{re.escape(open_brackets)}{re.escape(close_brackets)}]",
            "@brackets",
        ],
        ["\\|", "delimiter.bar"],
        ["\\t+", "white.tab"],
        ["[ \\f]+", "white"],
        [
            word,
            {
                "cases": {
                    # Monarch's `~` guard matches the whole token, anchored.
                    f"~{sh['number']}": "number",
                    f"~(?:{sh['sigil']}).*": "keyword.sigil",
                    f"~{sh['mods']}": "operator.modifier",
                    "~.*/.*": "type.path",
                    "@default": "identifier",
                }
            },
        ],
    ]
    return {
        "defaultToken": "",
        "tokenPostfix": ".fpl",
        "brackets": [
            {"open": o, "close": c, "token": "delimiter.bracket"}
            for o, c in lex.BRACKETS.items()
        ],
        "tokenizer": {
            "root": code,
            "str": [
                ["[^“”⟨]+", "string"],
                ["“", {"token": "string", "next": "@push"}],
                ["”", {"token": "string.quote", "next": "@pop"}],
                ["⟨", {"token": "delimiter.island", "next": "@island"}],
            ],
            "island": [
                ["⟨", {"token": "delimiter.island", "next": "@push"}],
                ["⟩", {"token": "delimiter.island", "next": "@pop"}],
                *[
                    r
                    for r in code
                    if r[0] not in ("\\|",) and "@brackets" != r[1]
                ],
            ],
            "raw": [
                ["[^「」]+", "string.raw"],
                ["「", {"token": "string.raw", "next": "@push"}],
                ["」", {"token": "string.quote", "next": "@pop"}],
            ],
            "block": [
                ["[^⟦⟧]+", "comment.block"],
                ["⟦", {"token": "comment.block", "next": "@push"}],
                ["⟧", {"token": "comment.block", "next": "@pop"}],
            ],
        },
        "_derived_from": {"pairs": pairs, "token": terminals()["TOKEN"]},
    }


def textmate() -> dict:
    """
    A TextMate grammar (VS Code, Shiki, GitHub linguist).
    """
    d = delimiters()
    sh = shapes()
    edge = f"(?<![^{d}\\s])"
    end = f"(?![^{d}\\s])"

    def pair(name: str, scope: str, o: str, c: str) -> dict:
        return {
            "name": scope,
            "begin": o,
            "end": c,
            "patterns": [{"include": f"#{name}"}]
            if name != "str"
            else [
                {"include": "#str"},
                {
                    "begin": "⟨",
                    "end": "⟩",
                    "name": "meta.island.fpl",
                    "patterns": [{"include": "$self"}],
                },
            ],
        }

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "FPL",
        "scopeName": SCOPE,
        "patterns": [{"include": "#code"}],
        "repository": {
            "code": {
                "patterns": [
                    {"match": ";;;;[^\\n]*", "name": "comment.line.file.fpl"},
                    {
                        "match": ";;;[^\\n]*",
                        "name": "comment.line.section.fpl",
                    },
                    {"match": ";;[^\\n]*", "name": "comment.line.doc.fpl"},
                    {
                        "match": "(?:;|⍝)[^\\n]*",
                        "name": "comment.line.note.fpl",
                    },
                    {"include": "#block"},
                    {"include": "#str"},
                    {"include": "#raw"},
                    {"match": "\\|", "name": "punctuation.separator.bar.fpl"},
                    {
                        "match": "[\\[\\]()⟨⟩{}]",
                        "name": "punctuation.section.fpl",
                    },
                    {
                        "match": f"{edge}{sh['number']}{end}",
                        "name": "constant.numeric.fpl",
                    },
                    {
                        "match": f"{edge}({sh['sigil']})([^{d}\\s]*)",
                        "captures": {
                            "1": {"name": "keyword.operator.sigil.fpl"},
                            "2": {"name": "variable.other.fpl"},
                        },
                    },
                    {
                        "match": f"{edge}{sh['mods']}{end}",
                        "name": "keyword.operator.modifier.fpl",
                    },
                    {
                        "match": f"{edge}[^{d}\\s]*/[^{d}\\s]*",
                        "name": "entity.name.type.path.fpl",
                    },
                    {
                        "match": f"{edge}[^{d}\\s]+",
                        "name": "variable.other.fpl",
                    },
                ]
            },
            "str": pair("str", "string.quoted.fpl", "“", "”"),
            "raw": pair("raw", "string.quoted.raw.fpl", "「", "」"),
            "block": pair("block", "comment.block.fpl", "⟦", "⟧"),
        },
    }


def main() -> None:
    """
    Print the target named on the command line.
    """
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "textmate":
        print(json.dumps(textmate(), ensure_ascii=False, indent=2))
    elif which == "monarch":
        body = json.dumps(monarch(), ensure_ascii=False, indent=2)
        print(
            "// GENERATED by 01-bootstrap/ide/gen_highlight.py from grammar.lark "
            "and lex.py; do not edit.\n"
            f"export const fplMonarch = {body};\n\n"
            "/** Register language id `fpl` with Monaco. */\n"
            "export function registerFpl(monaco) {\n"
            '  monaco.languages.register({ id: "fpl" });\n'
            '  monaco.languages.setMonarchTokensProvider("fpl", fplMonarch);\n'
            "}"
        )
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

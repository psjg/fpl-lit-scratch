"""
Differential test: Lark against the generated tree-sitter parser, on the
fixtures, on programs generated from the grammar's own shapes, and on
one-character mutations of the fixtures. Where both accept, the trees
must have the same shape (named nodes only, empty frames dropped); where
they disagree on acceptance the case is counted by kind and the first few
are printed.

    PYTHONPATH=. python ide/diff_treesitter.py [N] [SEED]

Exit 1 if any shape differs.
"""

import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lark import Token, Tree

from fpl.errors import FplError
from fpl.lex import prelex
from fpl.parse import _tree, parse

ROOT = Path(__file__).resolve().parents[2]
GRAMMAR = Path(__file__).with_name("tree-sitter-fpl")
NAMES = {"start": "source_file", "TOKEN": "word", "NOTE": "note", "DOC": "doc"}
POSITION = re.compile(r" ?\[\d+, \d+\] - \[\d+, \d+\]")


def lark_shape(source: str):
    """Lark's tree as nested lists, or None when the source is refused."""
    try:
        parse(source)
        tree = _tree(source, prelex(source))
    except FplError:
        return None
    return _norm(tree)


def _norm(node):
    if isinstance(node, Token):
        if node.type == "TOKEN" and node.value == "¶":
            return ["string"]
        return [NAMES[node.type]] if node.type in NAMES else None
    kids = [k for k in (_norm(c) for c in node.children) if k is not None]
    name = NAMES.get(node.data, str(node.data))
    return None if name in {"frame", "frames"} and not kids else [name, *kids]


def ts_shape(source: str, path: Path):
    """tree-sitter's tree as nested lists, or None on ERROR/MISSING."""
    path.write_text(source)
    out = subprocess.run(
        ["tree-sitter", "parse", str(path)],
        cwd=GRAMMAR,
        capture_output=True,
        text=True,
    ).stdout
    text = POSITION.sub(
        "",
        out.split("\n\n")[0]
        if "(source_file" not in out
        else out[out.index("(source_file") :],
    )
    text = text.split("\n/")[0]
    if "ERROR" in text or "MISSING" in text:
        return None
    stack: list[list] = [[]]
    for tok in re.findall(r"\(|\)|[\w]+", text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    return _prune(stack[0][0])


def _prune(node):
    name, *kids = node
    kids = [k for k in (_prune(c) for c in kids) if k is not None]
    if name == "block_comment":
        return None
    if name == "raw_string":
        name = "string"  # Lark's pre-lexer stands one placeholder for both
    return None if name in {"frame", "frames"} and not kids else [name, *kids]


WORDS = [
    "a",
    "swap",
    "x1",
    "q'",
    "42",
    "-3",
    "π",
    "5´",
    "->x",
    "$y",
    "#z",
    "../p/q",
    "a/b",
    "?",
    "--",
    ":",
    "+",
]


def generate(rng: random.Random, depth: int = 0) -> str:
    """A random program built from the grammar's shapes."""
    lines = []
    for _ in range(rng.randint(1, 4)):
        code = _code(rng, 2, "\t" * depth).strip(" \t")
        note = rng.choice(["", "", "; note"])
        lines.append(
            "\t" * depth
            + code
            + (" " if code and note else "")
            + (note if code else "")
        )
        if rng.random() < 0.5 and depth < 3:
            lines.append(generate(rng, depth + 1).rstrip("\n"))
        if rng.random() < 0.15:
            lines.append(
                rng.choice(
                    ["", "\t" * depth + ";; doc", "\f", "\t" * depth + "⟦ c ⟧"]
                )
            )
    return "\n".join(lines) + "\n"


def _code(rng: random.Random, room: int, ind: str) -> str:
    parts = []
    for _ in range(rng.randint(0, 5)):
        r = rng.random()
        if r < 0.5:
            parts.append(rng.choice(WORDS))
        elif r < 0.62:
            parts.append("|")
        elif r < 0.7 and not (parts and parts[-1] == "\t"):
            parts.append("\t")
        elif r < 0.78:
            parts.append(rng.choice(["“a ⟨b⟩ c”", "“x “y” z”", "「raw」"]))
        elif room:
            o, c = rng.choice(["[]", "()", "⟨⟩", "{}"])
            gap = rng.choice([" ", " ", "\n" + ind])
            inner = _code(rng, room - 1, ind).strip(" ")
            parts.append(
                o
                + gap
                + inner
                + (gap.strip(" ") + c if "\n" in gap else " " + c)
            )
    return " ".join(parts)


def mutate(rng: random.Random, source: str) -> str:
    """One random edit: delete, insert a structural character, or swap."""
    i = rng.randrange(len(source) + 1)
    kind = rng.random()
    if kind < 0.4 and i < len(source):
        return source[:i] + source[i + 1 :]
    return (
        source[:i] + rng.choice(list("[](){}⟨⟩|\t\n;“”「」⟦⟧ a")) + source[i:]
    )


def main() -> int:
    """Run the three corpora and print the table."""
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    fixtures = [
        p.read_text()
        for p in sorted(ROOT.glob("03-fpl/**/*.fpl"))
        + sorted(ROOT.glob("learn/**/*.fpl"))
    ]
    corpora = {
        "fixtures": fixtures,
        "generated": [generate(rng) for _ in range(n)],
        "mutated": [mutate(rng, rng.choice(fixtures)) for _ in range(n)],
    }
    scratch = Path(__import__("tempfile").mkdtemp())
    bad = 0
    for name, cases in corpora.items():
        # Lark's Indenter is stateful and the parser cached: Lark runs serially.
        larks = [lark_shape(case) for case in cases]
        with ThreadPoolExecutor(8) as pool:
            tss = list(
                pool.map(
                    lambda ic: ts_shape(ic[1], scratch / f"{name}{ic[0]}.fpl"),
                    enumerate(cases),
                )
            )
        results = list(zip(cases, larks, tss, strict=True))
        both = same = lark_only = ts_only = neither = 0
        shown = 0
        for case, lark, ts in results:
            if lark is not None and ts is not None:
                both += 1
                if lark == ts:
                    same += 1
                else:
                    bad += 1
                    if shown < 3:
                        shown += 1
                        print(
                            "SHAPE",
                            repr(case[:120]),
                            "\n  lark",
                            lark,
                            "\n  ts  ",
                            ts,
                        )
            elif lark is not None:
                lark_only += 1
                if shown < 3:
                    shown += 1
                    print("LARK-ONLY accepts", repr(case[:120]))
            elif ts is not None:
                ts_only += 1
                if shown < 3:
                    shown += 1
                    print("TS-ONLY accepts", repr(case[:120]))
            else:
                neither += 1
        print(
            f"{name:10} cases {len(cases):4}  both accept {both:4} same shape {same:4}  lark-only {lark_only:3}  ts-only {ts_only:3}  both refuse {neither:3}"
        )
    return 1 if bad else 0


sys.exit(main())

"""
Does tree-sitter agree with Lark? For each .fpl under 03-fpl and learn:
Lark parse ok/refused, tree-sitter ERROR-free or not, and the word count of
each side (they must be equal when both parse).

    PYTHONPATH=. python ide/measure_parity.py
"""

import re
import subprocess
from pathlib import Path

from fpl.errors import FplError
from fpl.parse import parse
from ide import analysis

ROOT = Path(__file__).resolve().parents[2]
GRAMMAR = Path(__file__).with_name("tree-sitter-fpl")


def ts_words(path: Path) -> tuple[bool, int]:
    """Tree-sitter: parsed without ERROR/MISSING, and its `word` leaves."""
    out = subprocess.run(
        ["tree-sitter", "parse", str(path)],
        cwd=GRAMMAR,
        capture_output=True,
        text=True,
    ).stdout
    return "ERROR" not in out and "MISSING" not in out, len(
        re.findall(r"\(word ", out)
    )


def main() -> None:
    """Print the table and totals."""
    both = same = lark_ok = ts_ok = 0
    files = sorted(ROOT.glob("03-fpl/**/*.fpl")) + sorted(
        ROOT.glob("learn/**/*.fpl")
    )
    for path in files:
        try:
            lark = len(list(analysis._words(parse(path.read_text()).lines)))
        except FplError:
            lark = None
        ok, n = ts_words(path)
        lark_ok += lark is not None
        ts_ok += ok
        if lark is not None and ok:
            both += 1
            same += lark == n
            if lark != n:
                print("word count differs", path.name, lark, n)
    print(
        f"files {len(files)}  lark ok {lark_ok}  tree-sitter ok {ts_ok}  both {both}  same word count {same}"
    )


main()

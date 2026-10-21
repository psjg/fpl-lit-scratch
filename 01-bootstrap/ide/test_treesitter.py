"""
The tree-sitter scanner nests indentation as Lark's Indenter does:
a level stack, siblings at one level, a dedent to a level no line opened
refused, a block comment alone on a line no block. Skipped without the
tree-sitter CLI.

    tree-sitter generate   (in ide/tree-sitter-fpl, once)
"""

import shutil
import subprocess
from pathlib import Path

import pytest

GRAMMAR = Path(__file__).with_name("tree-sitter-fpl")
pytestmark = pytest.mark.skipif(
    shutil.which("tree-sitter") is None
    or not (GRAMMAR / "src" / "parser.c").exists(),
    reason="needs the tree-sitter CLI and a generated parser",
)


def tree(source: str, tmp_path: Path) -> str:
    path = tmp_path / "t.fpl"
    path.write_text(source)
    return subprocess.run(
        ["tree-sitter", "parse", str(path)],
        cwd=GRAMMAR,
        capture_output=True,
        text=True,
    ).stdout


def test_two_tabs_open_one_level(tmp_path: Path) -> None:
    out = tree("a\n\t\tb\n\t\tc\n", tmp_path)
    assert out.count("(block") == 1 and "ERROR" not in out


def test_dedent_to_an_unopened_level_is_refused(tmp_path: Path) -> None:
    assert "ERROR" in tree("a\n\t\tb\n\tc\n", tmp_path)


def test_a_block_comment_line_opens_no_block(tmp_path: Path) -> None:
    assert "(block" not in tree("a\n\t⟦ c ⟧\nb\n", tmp_path)


def test_unclosed_bracket_is_an_error(tmp_path: Path) -> None:
    assert "ERROR" in tree("[ 1 2\n", tmp_path)

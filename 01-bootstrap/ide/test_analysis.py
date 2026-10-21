"""
The editor facts hold: diagnostics are the interpreter's refusals, tokens
are in order and inside the source, the encoding round-trips, and the
generated highlighters carry the sigils and modifiers lex.py defines.

    PYTHONPATH=. python -m pytest ide -q -p no:cacheprovider
"""

from pathlib import Path

import pytest

from fpl import lex
from ide import analysis, gen_highlight

EXAMPLES = sorted(
    (Path(__file__).resolve().parents[2] / "03-fpl").rglob("*.fpl")
)


def test_unclosed_bracket_is_one_diagnostic() -> None:
    found = analysis.diagnose("[ 1 2\n")
    assert [(d.line, d.start, d.message) for d in found] == [
        (0, 0, "[ never closed")
    ]


def test_unknown_word_points_at_the_word() -> None:
    (found,) = analysis.diagnose("foo bar\n")
    assert (found.line, found.start, found.end) == (0, 0, 3)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_tokens_stay_inside_the_source(path: Path) -> None:
    source = path.read_text()
    rows = source.splitlines()
    found = analysis.tokens(source)
    assert found == sorted(found, key=lambda t: (t.line, t.col))
    for token in found:
        assert token.col + token.length <= len(rows[token.line])


def test_encoding_is_relative() -> None:
    found = [
        analysis.Token(1, 4, 2, 0),
        analysis.Token(1, 9, 1, 1),
        analysis.Token(3, 2, 3, 2),
    ]
    assert analysis.encode(found) == [
        1,
        4,
        2,
        0,
        0,
        0,
        5,
        1,
        1,
        0,
        2,
        2,
        3,
        2,
        0,
    ]


def test_definitions_are_functions_with_the_declaration_bit() -> None:
    first = analysis.tokens("f : x -- y\n\tx\nf\n")[0]
    assert (first.kind, first.mods) == (
        analysis.LEGEND_TYPES.index("function"),
        1,
    )


def test_highlighters_read_lex_py() -> None:
    mon = str(gen_highlight.monarch())
    for mod in lex.MODS:
        assert mod in mon
    assert "→" in gen_highlight.shapes()["sigil"]


def test_a_form_feed_is_not_a_line_break() -> None:
    found = analysis.tokens("a\n\f\nb c\nd e\n")
    assert [(t.line, t.col) for t in found] == [(0, 0), (2, 0), (2, 2), (3, 0), (3, 2)]


def test_utf16_columns_count_astral_characters_twice() -> None:
    assert analysis.utf16("“😀” x", 4) == 5


def test_a_number_with_modifiers_is_still_a_number() -> None:
    assert lex.shape("5´")[1] == "number"
    assert "[´`¨˜⁼˙]*" in gen_highlight.shapes()["number"]

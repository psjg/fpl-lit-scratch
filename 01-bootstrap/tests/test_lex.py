"""
The pre-lexer keeps every code character's place in the source and every
string's interior.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fpl.ast_surface import Text
from fpl.errors import FplError, Span
from fpl.lex import PLACEHOLDER, Lines, Stashed, counted, prelex, shape
from fpl.parse import parse

PLAIN = st.text(alphabet="ab \t\n|[]“”「」⟦⟧;", max_size=30)


@given(PLAIN)
def test_every_code_character_comes_from_its_origin(source: str) -> None:
    try:
        lexed = prelex(source)
    except FplError:
        return
    assert len(lexed.origin) == len(lexed.code) + 1
    for char, at in zip(lexed.code, lexed.origin, strict=False):
        verbatim = at < len(source) and char == source[at]
        padded = char in " " + PLACEHOLDER and source[at] in "“「⟦"
        assert verbatim or padded or (char, at) == ("\n", len(source))


@given(st.text(alphabet=st.characters(exclude_characters="“”⟨"), max_size=20))
def test_a_string_keeps_its_interior(interior: str) -> None:
    item = parse(f"“{interior}”\n").lines[0].frames[0].cells[0].items[0]
    assert item == Text("str", (interior,) if interior else (), item.span)


def test_the_stash_holds_each_string_by_its_kind() -> None:
    assert prelex("“a” 「b」").stash == {
        0: Stashed("str", 1, 2, 0),
        3: Stashed("raw", 5, 6, 0),
    }


def test_an_opener_left_open_counts_to_none() -> None:
    """
    counted: an opener its own closer never balances before the end is
    None, not an offset; a nested opener of the same pair counts against
    the one closer.
    """
    assert counted("“a“b”", 0, "”", 5) is None


def test_a_string_placeholder_and_its_pad_keep_the_opener_offset() -> None:
    """
    Prelexed.origin: the placeholder a string becomes and the pad after
    it both map back to the string's opener; the closing newline and the
    end map to the source's end.
    """
    assert prelex("“ab”").origin == (0, 0, 4, 4)


def refusal(source: str) -> str:
    """
    The one error line prelex refuses source with, or "" when it accepts
    the source.
    """
    try:
        prelex(source)
    except FplError as error:
        return str(error)
    return ""


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("“a 「b” c」\n", "|- ! err/read/unopened 1:9 “」 closes nothing”"),
        ("“a”」\n", "|- ! err/read/unopened 1:4 “」 closes nothing”"),
        ("x “ab\n", "|- ! err/read/unclosed 1:3 ““ never closed”"),
        ("⟦ a\n", "|- ! err/read/unclosed 1:1 “⟦ never closed”"),
        ("a ]\n", "|- ! err/read/unopened 1:3 “] closes nothing”"),
        ("a\n\t b\n", "|- ! err/read/tabs 2:2 “indentation must be tabs”"),
        (
            "a\n\t\t[\n\tb ]\n",
            "|- ! err/read/dedent 3:2"
            " “dedent below line 2, but its [ is still open”",
        ),
        ("a\n\t[ b\n", "|- ! err/read/unclosed 2:2 “[ never closed”"),
        ("[ ⟦ ] ⟧ ]\n", ""),
        ("a ; ( b\n", ""),
        ("[\n  a ]\n", ""),
    ],
)
def test_prelex_refuses_at_the_place_in_the_source(
    source: str, expected: str
) -> None:
    """
    A refusal names the line and column of the source, not of the code;
    a bracket inside a comment, and spaces inside brackets, are fine.
    """
    assert refusal(source) == expected


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("a ⟦c⟧ b", "a   b\n"),
        ("⟦c⟧  a", "a\n"),
        ("\t⟦c⟧ a", "\ta\n"),
        ("a“b”", "a ¶ \n"),
    ],
)
def test_a_comment_leaves_a_space_or_nothing(source: str, code: str) -> None:
    """
    A block comment leaves one space between words, and nothing at the
    start of a line; a string after a word gets a space before it.
    """
    assert prelex(source).code == code


def test_a_string_counts_the_tabs_of_its_line() -> None:
    assert prelex("\t“b”").stash == {1: Stashed("str", 2, 3, 1)}


def test_an_offset_is_a_line_and_a_column() -> None:
    assert Lines("a\n\nb").span(2) == Span(2, 1)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("abc", ("", "name", ("abc",), "")),
        ("#x\u02d9", ("#", "name", ("x",), "\u02d9")),
        ("../a/b", ("../", "path", ("a", "b"), "")),
        ("1/2", ("", "path", ("1", "2"), "")),
        ("∞", ("", "number", ("∞",), "")),
        ("\u00b4", ("", "modifier", ("",), "\u00b4")),
        ("->f", ("->", "name", ("f",), "")),
        ("a\u00b4b", None),
    ],
)
def test_shape_cuts_a_token_in_three(
    token: str, expected: tuple[str, str, tuple[str, ...], str] | None
) -> None:
    assert shape(token) == expected

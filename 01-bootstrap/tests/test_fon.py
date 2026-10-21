"""
FON data is postfix and ASCII: it reads what it writes, in one spelling,
within its bounds, and refuses everything else in place, braces first.
"""

import math
import re
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fpl.errors import FplError
from fpl.fon import (
    BRACKETS,
    HEXFLT,
    Absent,
    Bool,
    Cell,
    Code,
    Dict,
    Flt,
    FonError,
    Hash,
    Json,
    Leaf,
    List,
    Num,
    Str,
    Sym,
    Tagged,
    Value,
    embed,
    read,
    write,
)
from fpl.multihash import BLAKE2B_256, Multihash, content

STRINGS = re.compile(r"""[#$]?"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'""")

name = st.from_regex(r"[A-Za-z][A-Za-z0-9/+-]{0,7}", fullmatch=True)
number = st.decimals(allow_nan=False, allow_infinity=False, places=3).map(
    lambda d: Num(Decimal(format(d, "f")))
)
digest = st.tuples(
    st.integers(0, 32), st.binary(min_size=32, max_size=32)
).map(
    lambda zeros_bytes: (
        bytes(zeros_bytes[0]) + zeros_bytes[1][zeros_bytes[0] :]
    )
)
ident = digest.map(lambda d: Multihash(BLAKE2B_256, d))
hashes = st.one_of(
    st.binary(max_size=32), st.binary(min_size=33, max_size=64)
).map(content)
floats = st.one_of(
    st.floats(allow_nan=False), st.sampled_from([math.nan, -math.nan])
).map(Flt.of)
leaf: st.SearchStrategy[Leaf] = st.one_of(
    st.just(Absent()),
    st.booleans().map(Bool),
    number,
    floats,
    st.one_of(name, st.text(max_size=8)).map(Sym),
    st.text(max_size=12).map(Str),
    st.text(max_size=12).map(lambda raw: Str(raw, raw=True)),
    st.one_of(name, st.text(max_size=8)).map(Cell),
    ident.map(Cell),
    hashes.map(Hash),
)
key: st.SearchStrategy[Leaf] = st.one_of(
    name.map(Sym), number, floats, st.text(max_size=8).map(Str)
)


def nested(inner: st.SearchStrategy[Value]) -> st.SearchStrategy[Value]:
    """
    Lists, tagged tuples (headed by a tag's name often), code and dicts
    of `inner`.
    """
    items = st.lists(inner, max_size=4).map(tuple)
    heads = st.one_of(name, st.sampled_from(["list", "dict", "1", "#a"]))
    fields = st.lists(st.one_of(heads.map(Sym), inner), max_size=4)
    entries = st.lists(
        st.tuples(key, inner), max_size=4, unique_by=lambda entry: entry[0]
    )
    return st.one_of(
        items.map(List),
        fields.map(lambda f: Tagged(tuple(f))),
        items.map(Code),
        entries.map(lambda e: Dict(tuple(e))),
    )


value: st.SearchStrategy[Value] = st.recursive(leaf, nested, max_leaves=12)
json: st.SearchStrategy[Json] = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=12),
    ),
    lambda inner: st.one_of(
        st.lists(inner, max_size=4),
        st.dictionaries(st.text(max_size=8), inner, max_size=4),
    ),
    max_leaves=12,
)


def refusal(document: str, **bounds: int) -> str:
    """
    The error line reading gives; the error is a FonError.
    """
    with pytest.raises(FonError) as caught:
        read(document, **bounds)
    return str(caught.value)


@given(value)
def test_read_after_write_is_the_identity(v: Value) -> None:
    """
    read ∘ write = id on every value, and write is idempotent on the
    text it gives.
    """
    written = write(v)
    assert read(written) == v
    assert write(read(written)) == written


@given(value)
def test_the_writer_writes_postfix_ascii(v: Value) -> None:
    """
    Written FON is one line of printable ASCII, and no brace or bracket
    stands in it outside a string's text.
    """
    written = write(v)
    assert re.fullmatch(r"[ -~]+", written)
    assert not set(STRINGS.sub("", written)) & set(BRACKETS)


@given(value, st.sampled_from(BRACKETS))
def test_a_brace_anywhere_outside_a_string_is_refused(
    v: Value, bracket: str
) -> None:
    """
    Braced FON never reads: a brace or bracket before or after a
    document is refused where it stands.
    """
    written = write(v)
    reason = f"{bracket} refused: FON is postfix, not braced"
    assert refusal(f"{bracket} {written}") == f"ERROR: 1:1 {reason}"
    end = len(written) + 2
    assert refusal(f"{written} {bracket}") == f"ERROR: 1:{end} {reason}"


def test_the_braced_documents_of_old_are_refused() -> None:
    """
    The token document and the session record the braced writer gave
    are refused at their first brace.
    """
    assert refusal(
        "{ 「source」 「1」 「tokens」 ⟨ ( 「TOKEN」 「1」 0 1 ) ⟩ }"
    ) == ("ERROR: 1:1 { refused: FON is postfix, not braced")
    assert refusal("1 ⟨ 2 ⟩") == (
        "ERROR: 1:3 ⟨ refused: FON is postfix, not braced"
    )
    assert refusal("“x”") == "ERROR: 1:1 “ refused: FON is postfix, not braced"


@given(json)
def test_json_embeds_and_reads_back(j: Json) -> None:
    """
    Every JSON value embeds and reads back, whatever its texts hold.
    """
    embedded = embed(j)
    assert read(write(embedded)) == embedded


@pytest.mark.parametrize("cell", ["a", "X", "x1", "a:b"])
def test_a_cell_that_opens_with_other_than_a_digit_is_a_name(
    cell: str,
) -> None:
    """
    $ then a name character other than a digit is a name.
    """
    assert read("$" + cell) == Cell(cell)
    assert write(Cell(cell)) == "$" + cell


@given(ident, hashes)
def test_fon_ids(i: Multihash, h: Multihash) -> None:
    """
    [law: fon-ids] FON reads and writes $ ids and & hashes in the
    decimal spelling as the same values, and the hex alias reads as the
    decimal value.
    """
    assert write(Cell(i)) == "$" + i.spelled()
    assert write(Hash(h)) == "&" + h.spelled()
    assert read(write(Cell(i))) == Cell(i)
    assert read(write(Hash(h))) == Hash(h)
    assert read("&" + h.raw().hex()) == Hash(h)


@pytest.mark.parametrize(
    ("v", "spelled"),
    [
        (Tagged((Sym("Add"), Num(Decimal(1)), Num(Decimal(2)))), "1 2 Add/2"),
        (Tagged((Sym("Nil"),)), "Nil/0"),
        (Tagged((Sym("X"),)), "X/0"),
        (Tagged((Sym("a/b"), Absent())), "_ a/b/1"),
        (Tagged((Sym("list"), Absent())), "#list _ tuple/2"),
        (Tagged((Sym("1"),)), "#1 tuple/1"),
        (Tagged((Sym("#a"),)), "##a tuple/1"),
        (Tagged((Str("T"), Num(Decimal(0)))), '"T" 0 tuple/2'),
        (Tagged(()), "tuple/0"),
        (List(()), "list/0"),
        (Code(()), "code/0"),
        (Dict(()), "dict/0"),
        (
            Dict(((Sym("a"), Num(Decimal(1))), (Sym("b"), Num(Decimal(2))))),
            "#a 1 #b 2 dict/2",
        ),
        (List((Code((Sym("dup"), Sym("+"))),)), "#dup #+ code/2 list/1"),
        (Str("a\"b'c\\"), r'"a\"b' + "'" + r'c\\"'),
        (Str("a\"b'c", raw=True), r"""'a"b\'c'"""),
        (Str("\n\t\r\x00é😀"), r'"\n\t\u{d}\u{0}\u{e9}\u{1f600}"'),
        (Str("{ [ ( ⟨"), r'"{ [ ( \u{27e8}"'),
        (Str("\U0010ffff"), r'"\u{10ffff}"'),
        (Sym("a b"), '#"a b"'),
        (Sym(""), '#""'),
        (Sym("x"), "#x"),
        (Cell("x"), "$x"),
        (Cell("1x"), '$"1x"'),
        (Cell(""), '$""'),
        (Num(Decimal("2.50")), "2.50"),
        (Num(Decimal("-3")), "-3"),
        (Absent(), "_"),
        (Bool(True), "true"),
        (Bool(False), "false"),
    ],
)
def test_each_value_has_one_postfix_spelling(v: Value, spelled: str) -> None:
    assert write(v) == spelled
    assert read(spelled) == v


@pytest.mark.parametrize(
    ("document", "error"),
    [
        ("#a 1 #a 2 dict/2", "ERROR: 1:6 repeated key #a"),
        ("1 list/0 2 dict/1", "ERROR: 1:3 a dict key is a leaf"),
        ("dict/0 1 dict/1", "ERROR: 1:1 a dict key is a leaf"),
        ("1 list/2", "ERROR: 1:3 list/2 takes 2 values, the stack holds 1"),
        ("#k dict/1", "ERROR: 1:4 dict/1 takes 2 values, the stack holds 1"),
        ("Add/1", "ERROR: 1:1 Add/1 takes 1 values, the stack holds 0"),
        ("#Add 1 tuple/2", "ERROR: 1:8 non-canonical spelling tuple/2"),
        ('#"a"', "ERROR: 1:1 non-canonical spelling"),
        ('$"a"', "ERROR: 1:1 non-canonical spelling"),
        (r'"\u{41}"', "ERROR: 1:1 non-canonical spelling"),
        (r'"\u{0e9}"', "ERROR: 1:1 non-canonical spelling"),
        (r'"\'"', "ERROR: 1:1 non-canonical spelling"),
        (r'"\q"', "ERROR: 1:2 malformed escape"),
        (r'"\u{E9}"', "ERROR: 1:2 malformed escape"),
        (r'"\u{110000}"', "ERROR: 1:2 malformed escape"),
        ('"\\', "ERROR: 1:2 malformed escape"),
        ('"a', 'ERROR: 1:1 " never closed'),
        ("1 'a", "ERROR: 1:3 ' never closed"),
        ('"a"X', "ERROR: 1:4 a string ends its token"),
        ('"é"', "ERROR: 1:2 U+00E9 refused in a string: escape it"),
        ('"a\nb"', "ERROR: 1:3 U+000A refused in a string: escape it"),
        ("#é", "ERROR: 1:2 U+00E9 refused: FON is printable ASCII"),
        ("#a\x0c", "ERROR: 1:3 U+000C refused: FON is printable ASCII"),
        ('x"y', 'ERROR: 1:2 " refused inside a word'),
        ("#a]", "ERROR: 1:3 ] refused: FON is postfix, not braced"),
        ("x", "ERROR: 1:1 unknown word x"),
        ("a/01", "ERROR: 1:1 unknown word a/01"),
        ("/0", "ERROR: 1:1 unknown word /0"),
        ("a/", "ERROR: 1:1 unknown word a/"),
        ("#", "ERROR: 1:1 unknown word #"),
        ("$", "ERROR: 1:1 unknown word $"),
        ("&", "ERROR: 1:1 unknown word &"),
        ("&zz", "ERROR: 1:1 malformed hash reference &zz"),
        ("&abcdef", "ERROR: 1:1 malformed hash reference &abcdef"),
        ("&45600:01", "ERROR: 1:1 malformed hash reference &45600:01"),
        (
            "&b22020" + "0" * 64,
            "ERROR: 1:1 malformed hash reference &b22020" + "0" * 64,
        ),
        ("&7:1", "ERROR: 1:1 malformed hash reference &7:1"),
        ("&0:33:0", "ERROR: 1:1 malformed hash reference &0:33:0"),
        ("&0:1:256", "ERROR: 1:1 malformed hash reference &0:1:256"),
        ("$0:0:0", "ERROR: 1:1 malformed identity $0:0:0"),
        ("$1x", "ERROR: 1:1 malformed identity $1x"),
        ("_ $45600:01 list/2", "ERROR: 1:3 malformed identity $45600:01"),
        ("01", "ERROR: 1:1 non-canonical number 01"),
        ("1e5", "ERROR: 1:1 non-canonical number 1e5"),
        ("1/2", "ERROR: 1:1 non-canonical number 1/2"),
        ("0x0.8p0", "ERROR: 1:1 non-canonical number 0x0.8p0"),
        ("0x1p-2000", "ERROR: 1:1 non-canonical number 0x1p-2000"),
        ("0x0p5", "ERROR: 1:1 non-canonical number 0x0p5"),
        ("-0x0p-0", "ERROR: 1:1 non-canonical number -0x0p-0"),
        (
            "0x0.0000000000001p-1022",
            "ERROR: 1:1 non-canonical number 0x0.0000000000001p-1022",
        ),
        ("_\n0x1p2000", "ERROR: 2:1 float out of range 0x1p2000"),
        ("a" * 4097, "ERROR: 1:1 token too long"),
    ],
)
def test_the_profile_refuses_in_place(document: str, error: str) -> None:
    assert refusal(document) == error


def test_a_refusal_names_its_offset() -> None:
    """
    FonError is an FplError, placed by line and column, that also
    carries the offset into the text.
    """
    with pytest.raises(FplError) as caught:
        read("1 2\n3 }")
    assert isinstance(caught.value, FonError)
    assert (str(caught.value), caught.value.offset) == (
        "ERROR: 2:3 } refused: FON is postfix, not braced",
        6,
    )


@pytest.mark.parametrize(
    ("document", "error"),
    [
        ("\n}", "ERROR: 2:1 }"),
        ("_\n_\n}", "ERROR: 3:1 }"),
        ("\n\n _ }", "ERROR: 3:4 }"),
    ],
)
def test_a_refusal_counts_lines_from_the_start(
    document: str, error: str
) -> None:
    """
    The line is one more than the newlines before the offset, the
    column counts from the last of them.
    """
    assert refusal(document).startswith(error + " refused")


def test_nesting_is_bounded_at_the_constructor() -> None:
    document = "_" + " list/1" * 70
    assert refusal(document) == f"ERROR: 1:{2 + 7 * 64 + 1} nesting too deep"
    assert refusal("list/0 list/1", max_depth=1) == (
        "ERROR: 1:8 nesting too deep"
    )
    assert read("list/0", max_depth=1) == List(())


def test_the_bounds_are_parameters() -> None:
    assert refusal("_\nabcd", max_token=3) == "ERROR: 2:1 token too long"
    assert refusal("abc", max_size=2) == "ERROR: 1:3 input too large"
    assert read("_ _", max_size=3) == List((Absent(), Absent()))
    assert read("#" + "a" * 4095) == Sym("a" * 4095)
    assert read('"' + "a" * 10 + '"', max_token=3) == Str("a" * 10)


@pytest.mark.parametrize(
    ("x", "spelled"),
    [
        (12.0, "0x1.8p3"),
        (-0.0, "-0x0p0"),
        (5e-324, "0x1p-1074"),
        (math.inf, "inf"),
        (-math.inf, "-inf"),
        (math.nan, "nan"),
        (-math.nan, "-nan"),
    ],
)
def test_a_float_is_its_bits(x: float, spelled: str) -> None:
    assert write(Flt.of(x)) == spelled
    assert read(spelled) == Flt.of(x)


@pytest.mark.parametrize(
    ("subnormal", "spelled"),
    [
        ("0x0.0000000000001p-1022", "0x1p-1074"),
        ("-0x0.0000000000001p-1022", "-0x1p-1074"),
        ("0x0.0000000000003p-1022", "0x1.8p-1073"),
        ("0x0.0123456789abcp-1022", "0x1.23456789abcp-1030"),
        ("0x0.8p-1022", "0x1p-1023"),
        ("0x0.fffffffffffffp-1022", "0x1.ffffffffffffep-1023"),
    ],
)
def test_a_subnormal_is_written_normalised(
    subnormal: str, spelled: str
) -> None:
    """
    A subnormal is written 0x1[.hex]p<exp> like every other nonzero
    float, its exponent below binary64's -1022, and reads back as
    exactly the float it was written from.
    """
    x = float.fromhex(subnormal)
    assert write(Flt.of(x)) == spelled
    back = read(spelled)
    assert isinstance(back, Flt)
    assert back.value.hex() == x.hex()
    assert back == Flt.of(x)


@given(st.floats(allow_nan=False, allow_subnormal=True))
def test_a_float_has_one_spelling(x: float) -> None:
    """
    Over the whole binary64 range, subnormals included, the written
    spelling reads back as the float and writes again as itself.
    """
    spelled = write(Flt.of(x))
    assert read(spelled) == Flt.of(x)
    assert write(read(spelled)) == spelled


@given(st.from_regex(HEXFLT, fullmatch=True))
def test_a_hex_float_reads_only_as_it_is_written(spelled: str) -> None:
    """
    Every token of hex float shape is refused in place or reads back to
    itself: no second spelling of a float, and no float beyond binary64,
    gets past the reader.
    """
    try:
        outcome = write(read(spelled))
    except FplError as refused:
        outcome = str(refused)
    assert outcome in {
        spelled,
        f"ERROR: 1:1 non-canonical number {spelled}",
        f"ERROR: 1:1 float out of range {spelled}",
    }


def test_the_reader_is_inert() -> None:
    """
    Names, references, tuples and code are data; nothing is resolved or
    called, and whitespace between tokens is free.
    """
    assert read(
        "#class \"x\" dict/1 'r' $c &0:3:6382179 $45600:0 #s p/6"
    ) == Tagged(
        (
            Sym("p"),
            Dict(((Sym("class"), Str("x")),)),
            Str("r", raw=True),
            Cell("c"),
            Hash(Multihash(0, b"abc")),
            Cell(Multihash(BLAKE2B_256, bytes(32))),
            Sym("s"),
        )
    )
    assert read("#dup #+ #;  code/3") == Code((Sym("dup"), Sym("+"), Sym(";")))
    assert read("  #a\n\t_\r\n") == List((Sym("a"), Absent()))
    assert read("") == List(())


def test_json_keys_are_symbols_where_they_are_names() -> None:
    assert embed({"name": "Ada", "a b": None, "1": [1.5, True]}) == Dict(
        (
            (Sym("name"), Str("Ada")),
            (Str("a b"), Absent()),
            (Sym("1"), List((Num(Decimal("1.5")), Bool(True)))),
        )
    )
    assert embed({"": None, "é": None}) == Dict(
        ((Str(""), Absent()), (Str("é"), Absent()))
    )

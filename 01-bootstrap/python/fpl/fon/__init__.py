"""
# 01.01.02 FON

FON, FPL Object Notation, is the restricted and inert subset of FPL that
writes a value out for the wire and reads it back
([ADR-0003](../../02-docs/02.05-project/adr/ADR-0003-fon-is-an-fpl-subset.md)).
It is postfix: a document is a stream of tokens read left to right on a
stack. A literal pushes a value; a constructor pops the values it is
built from and pushes what it builds, so `1 2 Add/2` is the tuple headed
by `Add` with the fields 1 and 2. It is lexically printable ASCII. This
page is normative: the reader and writer below are FON, and the seed's
`fpl/fon.py` is the same code. There is no braced FON; a brace or a
bracket outside a string's text is refused.

## Lexical grammar

```text document = *space [ token *( 1*space token ) ] *space space    =
SP / HT / CR / LF token    = string / word string   = [ "#" / "$" ]
DQUOTE *( dchar / escape ) DQUOTE / SQUOTE *( schar / escape ) SQUOTE
dchar    = printable ASCII but DQUOTE and the backslash schar    =
printable ASCII but SQUOTE and the backslash escape   = the backslash,
then one of: the backslash, n, t, DQUOTE, SQUOTE, or u{ 1*6 lowercase
hex digits } word     = 1*namechar namechar = printable ASCII but SP,
DQUOTE, SQUOTE, ( ) [ ] { } ```

A string is followed by whitespace or the end. Printable ASCII is U+0020
to U+007E; every other character of a text, newline and tab included, is
written as an escape: `\n`, `\t`, or the code point in lowercase hex
without leading zeros, as in \\u{e9} for é and \\u{0} for NUL. `\\` is
the backslash, and the string's own quote is escaped the same way: `"say
\"hi\""`.

## Literals

| Token | Value | |---|---| | `"text"` | `Str`, text whose interpolation
is kept as text | | `'raw'` | `Str` with `raw`, raw text | | `#name`,
`#"any text"` | `Sym`, a symbol; the quoted form only when the name is
not a word | | `$name`, `$"any text"` | `Cell` naming by name; the
quoted form when the name is not a word or opens with a digit | |
`$<code>:<n>` | `Cell` naming by hash, the multihash's decimal spelling
| | `&<multihash>` | `Hash`, a reference by content; the hex alias reads
too | | `_` | `Absent` | | `true`, `false` | `Bool` | | `-12`, `0`,
`2.50` | `Num`, an exact decimal: no `+`, no leading zeros, no exponent
| | `0x1.8p3`, `-0x0p0`, `inf`, `-inf`, `nan`, `-nan` | `Flt`, a
binary64 by its bits, C99 hex |

## Constructors

A constructor is a word `name/arity`, the arity a decimal without
leading zeros.

| Token | Pops | Pushes | |---|---|---| | `list/n` | n values | `List`
of them | | `code/n` | n values | `Code`, opaque to the reader | |
`tuple/n` | n values | `Tagged`, the first its head | | `dict/n` | 2n
values, key and value in turn | `Dict`; keys are leaves, distinct, in
order | | `Name/k` | k values | `Tagged` headed by `#Name`, then the k
fields |

A word that is neither a literal nor a constructor is refused. What is
left on the stack is the document's value: one value is itself, none or
several a `List` of them.

## One spelling per value

`write` gives each value one spelling, and `read` accepts only that one:
a number out of canonical form, a quoted name that has a bare spelling,
an escape where the character stands for itself, `tuple/n` for a tuple
whose head a tag can spell, and so on, are refused in place. Only the
whitespace between tokens is free; the writer puts one space.

| Value | FON | |---|---| | the tuple headed by `Add` with 1 and 2 | `1
2 Add/2` | | the empty list, tuple, code, dict | `list/0`, `tuple/0`,
`code/0`, `dict/0` | | a dict from `a` to 1 and `b` to 2 | `#a 1 #b 2
dict/2` | | code holding `dup +`, in a list | `#dup #+ code/2 list/1` |
| a tuple headed by the symbol `list`, a constructor's name | `#list _
tuple/2` | | a tuple headed by the raw text `TOKEN` | `'TOKEN' '1' 0 1
tuple/4` | | the symbol `a b`, the name `1x` | `#"a b"`, `$"1x"` | | the
text `say "hi"` and a newline | `"say \"hi\"\n"` |

A token document, as `fpl source | fpl lex` writes it for `1 2 +`,
begins `'source' '1 2 +\n' 'code'` and ends `list/4 dict/5`.

## Refusals

Every refusal is a `FonError`, an `FplError` placed at the line and
column where it starts and carrying the offset into the text: a brace or
bracket (`{ refused: FON is postfix, not braced`), a character outside
printable ASCII, a quote inside a word, an unclosed string, a malformed
escape, a constructor with too few values below it, a dict key that is
not a leaf or repeats, an unknown word, a number or hash out of form,
nesting deeper than `max_depth`, a word longer than `max_token`, a text
longer than `max_size`. The reader never evaluates, resolves or
constructs typed objects.

FON, FPL Object Notation: the inert, postfix, ASCII subset of FPL that
writes a value out and reads it back, within bounds and canonically.

A document is a stream of tokens between whitespace, read left to right
on a stack. A literal pushes its value: an exact decimal, a float as
C99 hex or inf, -inf, nan, -nan, _ for absence, true and false, #name a
symbol, $name or $<code>:<n> a reference by identity, &<multihash> a
reference by content (fpl/multihash.py, the hex alias read too), "text"
and 'raw text'. A constructor pops what it builds from and pushes the
result: n values then list/n a list, code/n opaque code, tuple/n a
tagged tuple, 2n values then dict/n a dict of n keys and values in
turn, and k values then Name/k the tagged tuple headed by #Name, so
1 2 Add/2 is ( Add 1 2 ). One value left on the stack is the document's
value; none or several are a List of them.

The reader never evaluates, resolves or constructs typed objects, and
accepts each value in one spelling only, the one `write` gives; only
the amount of whitespace between tokens is free. It refuses every brace
and bracket, the braced FON's included, and every character outside
printable ASCII but in a string's escapes. Depth, token length and
input size are parameters.
"""

import math
import re
import struct
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import assert_never

from fpl.arrow import Pass
from fpl.errors import FplError, Span
from fpl.multihash import Multihash, spelling

SPACE = re.compile(r"[ \t\r\n]*")
WORD = re.compile(r"[^ \t\r\n]*")
NAME = re.compile(r"[!#-&*-Z\\^-z|~]+")
STRANGER = re.compile(r"[^!#-&*-Z\\^-z|~]")
PLAIN = {'"': r" !#-\[\]-~", "'": r" -&(-\[\]-~"}
LITERAL = {quote: re.compile(f"[{chars}]*") for quote, chars in PLAIN.items()}
ESCAPED = {quote: re.compile(f"[^{chars}]") for quote, chars in PLAIN.items()}
SHORT = {"\\": "\\", "n": "\n", "t": "\t", '"': '"', "'": "'"}
ESCAPES = {char: "\\" + letter for letter, char in SHORT.items()}
CODEPOINT = re.compile(r"\\u\{([0-9a-f]{1,6})\}")
BRACKETS = "{}()[]⟨⟩“”「」⟦⟧"
NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
NUMERIC = re.compile(r"-?(0x|[0-9])")
HEXFLT = re.compile(r"-?0x(0|1)(\.[0-9a-f]*[1-9a-f])?p-?(0|[1-9][0-9]*)")
ARITY = re.compile(r"0|[1-9][0-9]*")
CONTAINERS = ("list", "code", "tuple", "dict")


class FonError(FplError):
    """
    A document refused: the reason, at the line and column of the
    character it starts at, and that character's offset in the text.
    """

    def __init__(self, text: str, offset: int, message: str) -> None:
        line = text.count("\n", 0, offset) + 1
        super().__init__(
            Span(line, offset - text.rfind("\n", 0, offset)), message
        )
        self.offset = offset


def _quoted(text: str, quote: str) -> str:
    r"""
    text between quotes: printable ASCII as itself, but for the quote
    and the backslash, which are escaped, as are newline (\n) and tab
    (\t); every other character is \u{<hex>}, lowercase hex without
    leading zeros.
    """
    return (
        quote
        + ESCAPED[quote].sub(
            lambda found: ESCAPES.get(found[0], f"\\u{{{ord(found[0]):x}}}"),
            text,
        )
        + quote
    )


@dataclass(frozen=True)
class Absent:
    """
    _ : nothing here.
    """

    def written(self) -> str:
        """
        Canonical FON.
        """
        return "_"


@dataclass(frozen=True)
class Bool:
    """
    true or false, a kind apart from numbers.
    """

    value: bool

    def written(self) -> str:
        """
        Canonical FON.
        """
        return "true" if self.value else "false"


@dataclass(frozen=True)
class Num:
    """
    An exact decimal: no +, no leading zeros, no exponent.
    """

    value: Decimal

    def written(self) -> str:
        """
        Canonical FON.
        """
        return format(self.value, "f")


@dataclass(frozen=True)
class Flt:
    """
    An IEEE binary64 float, held as its bit pattern so that every float,
    nan and -0.0 included, equals only itself; written as C99 %a hex,
    exact.
    """

    bits: int

    @classmethod
    def of(cls, value: float) -> "Flt":
        """
        The float's bit pattern.
        """
        return cls(int(struct.unpack("<q", struct.pack("<d", value))[0]))

    @property
    def value(self) -> float:
        """
        The float the bits spell.
        """
        return float(struct.unpack("<d", struct.pack("<q", self.bits))[0])

    def written(self) -> str:
        """
        Canonical FON: nan, -nan, inf, -inf, [-]0x0p0, or
        [-]0x1[.hex]p<exp> with trailing zero hex digits dropped. A
        subnormal is normalised like every other nonzero float, its
        exponent below -1022: the smallest is 0x1p-1074, not float.hex's
        0x0.0000000000001p-1022, so that each float has one spelling.
        """
        x = self.value
        sign = "-" if math.copysign(1, x) < 0 else ""
        if math.isnan(x):
            return sign + "nan"
        if math.isinf(x):
            return sign + "inf"
        if x == 0:
            return sign + "0x0p0"
        fraction, biased = (
            self.bits & ((1 << 52) - 1),
            (self.bits >> 52) & 0x7FF,
        )
        exponent = biased - 1023
        if biased == 0:
            top = fraction.bit_length() - 1
            fraction, exponent = (
                (fraction - (1 << top)) << (52 - top),
                top - 1074,
            )
        digits = f"{fraction:013x}".rstrip("0")
        return f"{sign}0x1{'.' if digits else ''}{digits}p{exponent}"


@dataclass(frozen=True)
class Sym:
    """
    A symbol, any text; not resolved.
    """

    name: str

    def written(self) -> str:
        """
        Canonical FON: #name when the name is a run of name characters,
        else #"name".
        """
        bare = NAME.fullmatch(self.name)
        return "#" + (self.name if bare else _quoted(self.name, '"'))


@dataclass(frozen=True)
class Cell:
    """
    $name, or $<code>:<n> naming by hash: a reference by identity; not
    followed.
    """

    name: str | Multihash

    def written(self) -> str:
        """
        Canonical FON: $ then the hash's decimal spelling, or the name,
        quoted when it is not a run of name characters or opens with a
        digit, as a hash does.
        """
        if isinstance(self.name, Multihash):
            return "$" + self.name.spelled()
        bare = NAME.fullmatch(self.name) and self.name[0] not in "0123456789"
        return "$" + (self.name if bare else _quoted(self.name, '"'))


@dataclass(frozen=True)
class Hash:
    """
    &<multihash>: a reference by content, the bytes themselves up to 32;
    not followed.
    """

    ref: Multihash

    def written(self) -> str:
        """
        Canonical FON: the decimal spelling.
        """
        return "&" + self.ref.spelled()


@dataclass(frozen=True)
class Str:
    """
    "…" text, interpolation kept as text, or '…' raw text.
    """

    text: str
    raw: bool = False

    def written(self) -> str:
        """
        Canonical FON.
        """
        return _quoted(self.text, "'" if self.raw else '"')


@dataclass(frozen=True)
class List:
    """
    n values then list/n.
    """

    items: tuple["Value", ...]

    def written(self) -> str:
        """
        Canonical FON; the empty list is list/0.
        """
        return _built(self.items, f"list/{len(self.items)}")


@dataclass(frozen=True)
class Tagged:
    """
    A tagged tuple; its head is data, never called.
    """

    items: tuple["Value", ...]

    def written(self) -> str:
        """
        Canonical FON: the fields then Name/k when the head is a symbol
        a tag can spell, else every item then tuple/n.
        """
        head = self.items[0] if self.items else None
        if isinstance(head, Sym) and _tag(head.name):
            fields = self.items[1:]
            return _built(fields, f"{head.name}/{len(fields)}")
        return _built(self.items, f"tuple/{len(self.items)}")


@dataclass(frozen=True)
class Code:
    """
    n values then code/n: code, opaque to the reader.
    """

    items: tuple["Value", ...]

    def written(self) -> str:
        """
        Canonical FON.
        """
        return _built(self.items, f"code/{len(self.items)}")


type Leaf = Absent | Bool | Num | Flt | Sym | Cell | Hash | Str


@dataclass(frozen=True)
class Dict:
    """
    Keys and values in turn, then dict/n: keys literal and distinct, in
    the order written.
    """

    entries: tuple[tuple[Leaf, "Value"], ...]

    def written(self) -> str:
        """
        Canonical FON.
        """
        flat = tuple(item for entry in self.entries for item in entry)
        return _built(flat, f"dict/{len(self.entries)}")


type Value = Leaf | List | Tagged | Code | Dict
type Json = bool | int | float | str | list["Json"] | dict[str, "Json"] | None

CONSTANTS: dict[str, Leaf] = {
    "_": Absent(),
    "true": Bool(True),
    "false": Bool(False),
    "inf": Flt.of(math.inf),
    "-inf": Flt.of(-math.inf),
    "nan": Flt.of(math.nan),
    "-nan": Flt.of(-math.nan),
}


def _built(values: tuple[Value, ...], constructor: str) -> str:
    """
    The values, then the constructor that pops them, between single
    spaces.
    """
    return " ".join([*(value.written() for value in values), constructor])


class _RefusedError(Exception):
    """
    A token the profile refuses, before it is placed in the text.
    """


@dataclass(frozen=True)
class Make:
    """
    A constructor token, name/arity: list, code, tuple or dict, else a
    tag naming its tuple's head.
    """

    name: str
    arity: int

    def width(self) -> int:
        """
        How many values it pops: two per entry for a dict.
        """
        return 2 * self.arity if self.name == "dict" else self.arity

    def build(self, items: tuple[Value, ...]) -> Value:
        """
        What it makes of the values it popped; a dict is made apart,
        where its keys can be placed. A tuple whose head a tag spells is
        refused: Name/k is its one spelling.
        """
        if self.name == "list":
            return List(items)
        if self.name == "code":
            return Code(items)
        if self.name != "tuple":
            return Tagged((Sym(self.name), *items))
        if items and isinstance(items[0], Sym) and _tag(items[0].name):
            raise _RefusedError(f"non-canonical spelling tuple/{self.arity}")
        return Tagged(items)


def _hash(text: str) -> Hash:
    """
    &<multihash>, in decimal or the hex alias, inline bytes allowed.
    """
    try:
        return Hash(spelling(text, inline=True))
    except ValueError:
        raise _RefusedError(f"malformed hash reference &{text}") from None


def _cell(text: str) -> Cell:
    """
    $name, or $<code>:<n> when it opens with a digit; no hex alias,
    which would read as a name, and no inline bytes, which are content,
    not identity.
    """
    if text[0] not in "0123456789":
        return Cell(text)
    if ":" in text:
        try:
            return Cell(spelling(text, inline=False))
        except ValueError:
            pass
    raise _RefusedError(f"malformed identity ${text}")


def _hexflt(token: str) -> Flt:
    """
    A hex float, read only in the spelling Flt.written gives it: a
    second spelling of the same bits (0x0.8p0 for 0x1p-1, 0x0p5 for
    0x0p0) or one that rounds or underflows (0x1p-2000) is refused, so
    that write ∘ read is the identity on what reads, as it is for
    decimals; past binary64 (0x1p2000) is out of range.
    """
    try:
        flt = Flt.of(float.fromhex(token))
    except OverflowError:
        raise _RefusedError(f"float out of range {token}") from None
    if flt.written() != token:
        raise _RefusedError(f"non-canonical number {token}")
    return flt


SIGILS: dict[str, Callable[[str], Leaf]] = {"$": _cell, "&": _hash, "#": Sym}


def word(token: str) -> Leaf | Make:
    """
    What a token of name characters spells: a literal, or a constructor
    name/arity. A number or hash out of canonical form is refused, and
    so is a word that is neither.
    """
    constant = CONSTANTS.get(token)
    if constant is not None:
        return constant
    if HEXFLT.fullmatch(token):
        return _hexflt(token)
    if NUMBER.fullmatch(token):
        return Num(Decimal(token))
    if NUMERIC.match(token):
        raise _RefusedError(f"non-canonical number {token}")
    sigil = SIGILS.get(token[0]) if len(token) > 1 else None
    return _constructor(token) if sigil is None else sigil(token[1:])


def _constructor(token: str) -> Make:
    """
    name/arity, the arity a decimal without leading zeros; any other
    word is unknown.
    """
    name, slash, arity = token.rpartition("/")
    if not (slash and name and ARITY.fullmatch(arity)):
        raise _RefusedError(f"unknown word {token}")
    return Make(name, int(arity))


def _tag(name: str) -> bool:
    """
    Whether name/k reads back as a tag headed by #name, so that the
    tuple is written that way.
    """
    if name in CONTAINERS or not NAME.fullmatch(name):
        return False
    try:
        return word(name + "/0") == Make(name, 0)
    except _RefusedError:
        return False


def _refusal(char: str) -> str:
    """
    Why a character may not stand in a word.
    """
    if char in BRACKETS:
        return f"{char} refused: FON is postfix, not braced"
    if char in "\"'":
        return f"{char} refused inside a word"
    return f"U+{ord(char):04X} refused: FON is printable ASCII"


def _word(text: str, start: int, end: int, max_token: int) -> Leaf | Make:
    """
    The word text[start:end], refused in place: a character no word
    holds, a word longer than max_token, or one `word` refuses.
    """
    token = text[start:end]
    stranger = STRANGER.search(token)
    if stranger is not None:
        raise FonError(text, start + stranger.start(), _refusal(stranger[0]))
    if len(token) > max_token:
        raise FonError(text, start, "token too long")
    try:
        return word(token)
    except _RefusedError as refusal:
        raise FonError(text, start, str(refusal)) from None


def _escape(text: str, at: int) -> tuple[str, int]:
    r"""
    The character the escape at text[at] stands for, and the offset past
    it: \\ \n \t \" \' or \u{<hex>} up to 10ffff; whether it was the
    canonical one is judged with the whole string.
    """
    short = SHORT.get(text[at + 1 : at + 2])
    if short is not None:
        return short, at + 2
    found = CODEPOINT.match(text, at)
    if found is None or int(found[1], 16) > 0x10FFFF:
        raise FonError(text, at, "malformed escape")
    return chr(int(found[1], 16)), found.end()


def _body(text: str, start: int, quote: str) -> tuple[str, int]:
    """
    The text of the string whose quote is at start, and the offset past
    its closing quote. A character outside printable ASCII must be
    escaped.
    """
    parts: list[str] = []
    at = start + 1
    while True:
        end = _past(LITERAL[quote], text, at)
        parts.append(text[at:end])
        at = end
        if at == len(text):
            raise FonError(text, start, f"{quote} never closed")
        if text[at] == quote:
            return "".join(parts), at + 1
        if text[at] != "\\":
            raise FonError(
                text,
                at,
                f"U+{ord(text[at]):04X} refused in a string: escape it",
            )
        char, at = _escape(text, at)
        parts.append(char)


def _string(text: str, start: int) -> tuple[Leaf, int]:
    """
    The string token at start, "text", 'raw', #"symbol" or $"name", and
    the offset past it. Whitespace must follow it, and it must be
    spelled as `write` spells its value.
    """
    sigil = text[start] if text[start] in "#$" else ""
    quote = text[start + len(sigil)]
    body, end = _body(text, start + len(sigil), quote)
    value: Leaf = (
        Sym(body)
        if sigil == "#"
        else Cell(body)
        if sigil
        else Str(body, quote == "'")
    )
    if end < len(text) and text[end] not in " \t\r\n":
        raise FonError(text, end, "a string ends its token")
    if value.written() != text[start:end]:
        raise FonError(text, start, "non-canonical spelling")
    return value, end


def _past(pattern: re.Pattern[str], text: str, at: int) -> int:
    """
    The offset past the run of `pattern`, starred, that starts at `at`.
    """
    run = pattern.match(text, at)
    assert run is not None
    return run.end()


def _tokens(text: str, max_token: int) -> Iterator[tuple[int, Leaf | Make]]:
    """
    Each token's offset and what it spells, left to right.
    """
    at = _past(SPACE, text, 0)
    while at < len(text):
        item: Leaf | Make
        if text[at] in "\"'" or text[at : at + 2] in ('#"', '$"'):
            item, end = _string(text, at)
        else:
            end = _past(WORD, text, at)
            item = _word(text, at, end, max_token)
        yield at, item
        at = _past(SPACE, text, end)


@dataclass(frozen=True)
class _Held:
    """
    A value on the reader's stack, the offset of the token that pushed
    it, and how deeply constructors nest in it.
    """

    value: Value
    offset: int
    depth: int


def _dict(text: str, held: list[_Held]) -> Dict:
    """
    Keys and values in turn; a key that is not a leaf, or one given
    twice, is refused where it was pushed.
    """
    entries: dict[Leaf, Value] = {}
    for key, value in zip(held[::2], held[1::2], strict=True):
        if isinstance(key.value, List | Tagged | Code | Dict):
            raise FonError(text, key.offset, "a dict key is a leaf")
        if key.value in entries:
            raise FonError(
                text, key.offset, f"repeated key {key.value.written()}"
            )
        entries[key.value] = value.value
    return Dict(tuple(entries.items()))


def _made(
    text: str, stack: list[_Held], offset: int, make: Make, max_depth: int
) -> _Held:
    """
    What the constructor at offset makes of the values it pops off the
    stack: too few values, or a result nested deeper than max_depth, is
    refused at the constructor.
    """
    width = make.width()
    if width > len(stack):
        raise FonError(
            text,
            offset,
            f"{make.name}/{make.arity} takes {width} values,"
            f" the stack holds {len(stack)}",
        )
    taken = stack[len(stack) - width :]
    del stack[len(stack) - width :]
    depth = 1 + max((held.depth for held in taken), default=0)
    if depth > max_depth:
        raise FonError(text, offset, "nesting too deep")
    if make.name == "dict":
        return _Held(_dict(text, taken), offset, depth)
    try:
        value = make.build(tuple(held.value for held in taken))
    except _RefusedError as refusal:
        raise FonError(text, offset, str(refusal)) from None
    return _Held(value, offset, depth)


def read(
    text: str,
    max_depth: int = 64,
    max_token: int = 4096,
    max_size: int = 1 << 24,
) -> Value:
    """
    The value a FON document spells: one value is itself, several or
    none a List of them. Linear and total: every refusal is a FonError
    inside the text, bounds included. A string's length is bounded by
    max_size alone.
    """
    if len(text) > max_size:
        raise FonError(text, max_size, "input too large")
    stack: list[_Held] = []
    for offset, item in _tokens(text, max_token):
        stack.append(
            _made(text, stack, offset, item, max_depth)
            if isinstance(item, Make)
            else _Held(item, offset, 0)
        )
    values = tuple(held.value for held in stack)
    return values[0] if len(values) == 1 else List(values)


def write(value: Value) -> str:
    """
    Canonical FON for a value, the text `read` gives it back from: one
    line of printable ASCII, every value spellable.
    """
    return value.written()


def embed(json: Json) -> Value:
    """
    A JSON value as FON: null is absence, a number an exact decimal, an
    object a Dict keyed by symbols where the key is a run of name
    characters, else by text.
    """
    match json:
        case list():
            return List(tuple(embed(item) for item in json))
        case dict():
            return Dict(
                tuple((_key(key), embed(item)) for key, item in json.items())
            )
        case _:
            return _scalar(json)


def _scalar(json: bool | float | str | None) -> Leaf:
    """
    A JSON scalar as FON.
    """
    match json:
        case None:
            return Absent()
        case bool():
            return Bool(json)
        case int() | float():
            return Num(Decimal(repr(json)))
        case str():
            return Str(json)
        case _:
            assert_never(json)


def _key(name: str) -> Leaf:
    """
    A JSON key as a symbol when it is a run of name characters, else as
    text.
    """
    return Sym(name) if NAME.fullmatch(name) else Str(name)


fon = Pass("fon", read)

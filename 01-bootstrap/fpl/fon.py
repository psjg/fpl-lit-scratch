"""Read and write FON, the inert, postfix, ASCII subset of FPL.

A FON document is a stream of tokens between whitespace, read left to
right on a stack. A literal pushes its value: an exact decimal, a float
as C99 hex or ``inf``, ``-inf``, ``nan``, ``-nan``, ``_`` for absence,
``true`` and ``false``, ``#name`` a symbol, ``$name`` or ``$<code>:<n>``
a reference by identity, ``&<multihash>`` a reference by content
(:mod:`fpl.multihash`, the hex alias read too), ``"text"`` and ``'raw
text'``. A constructor pops what it builds from and pushes the result:
``n`` values then ``list/n`` a list, ``code/n`` opaque code, ``tuple/n``
a tagged tuple, ``2n`` values then ``dict/n`` a dict of ``n`` keys and
values in turn, and ``k`` values then ``Name/k`` the tagged tuple headed
by ``#Name``, so ``1 2 Add/2`` is ``( Add 1 2 )``. One value left on the
stack is the document's value; none or several are a :class:`List` of
them.

:func:`read` never evaluates, resolves or constructs typed objects. It
accepts each value in one spelling only, the one :func:`write` gives;
only the amount of whitespace between tokens is free. It refuses every
brace and bracket, the braced FON's included, and every character
outside printable ASCII except in a string's escapes. Depth, token
length and input size are parameters. :func:`embed` turns parsed JSON
into a :data:`Value`.
"""

import math
import re
import struct
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import assert_never

from fpl.errors import FplError, Span
from fpl.multihash import Multihash, spelling

#: Whitespace between tokens, possibly none.
SPACE = re.compile(r"[ \t\r\n]*")
#: A run of non-whitespace: the extent of a word token.
WORD = re.compile(r"[^ \t\r\n]*")
#: A run of the characters a name, tag or bare symbol may hold.
NAME = re.compile(r"[!#-&*-Z\\^-z|~]+")
#: One character that may not stand in a word.
STRANGER = re.compile(r"[^!#-&*-Z\\^-z|~]")
#: Per quote character, the character class a string holds unescaped.
PLAIN = {'"': r" !#-\[\]-~", "'": r" -&(-\[\]-~"}
#: Per quote character, a run of unescaped characters.
LITERAL = {quote: re.compile(f"[{chars}]*") for quote, chars in PLAIN.items()}
#: Per quote character, one character that must be escaped in that
#: string.
ESCAPED = {quote: re.compile(f"[^{chars}]") for quote, chars in PLAIN.items()}
#: The letter after a backslash, mapped to the character it escapes.
SHORT = {"\\": "\\", "n": "\n", "t": "\t", '"': '"', "'": "'"}
#: The inverse of :data:`SHORT`: a character to its two-character
#: escape.
ESCAPES = {char: "\\" + letter for letter, char in SHORT.items()}
#: A ``\u{<hex>}`` escape, one to six lowercase hex digits.
CODEPOINT = re.compile(r"\\u\{([0-9a-f]{1,6})\}")
#: Brackets refused with a pointed message; FON is postfix.
BRACKETS = "{}()[]⟨⟩“”「」⟦⟧"
#: The canonical exact decimal.
NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
#: The start of any number-like word, canonical or not.
NUMERIC = re.compile(r"-?(0x|[0-9])")
#: The canonical hex float, as :meth:`Flt.written` spells it.
HEXFLT = re.compile(r"-?0x(0|1)(\.[0-9a-f]*[1-9a-f])?p-?(0|[1-9][0-9]*)")
#: A constructor's arity: a decimal without leading zeros.
ARITY = re.compile(r"0|[1-9][0-9]*")
#: Constructor names that build the container they name, not a tagged
#: tuple.
CONTAINERS = ("list", "code", "tuple", "dict")


class FonError(FplError):
    """A document refused, with the reason and where it starts.

    The position is the line and column of the offending character and
    its offset in the text.
    """

    tag = "err/fon"

    def __init__(self, text: str, offset: int, message: str) -> None:
        """Refuse *text* at *offset* with *message*.

        Args:
            text: The document, to derive the line and column from.
            offset: Offset in *text* of the character the refusal starts
                at.
            message: The reason.
        """
        line = text.count("\n", 0, offset) + 1
        super().__init__(
            Span(line, offset - text.rfind("\n", 0, offset)), message
        )
        #: Offset in the text of the character the refusal starts at.
        self.offset = offset


def _quoted(text: str, quote: str) -> str:
    r"""Quote *text* the one canonical way.

    Printable ASCII stands for itself, except the quote and the
    backslash, which are escaped, as are newline (``\n``) and tab
    (``\t``). Every other character is ``\u{<hex>}``, lowercase hex
    without leading zeros.
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
    """The value ``_``: nothing here."""

    def written(self) -> str:
        """Return the canonical FON."""
        return "_"


@dataclass(frozen=True)
class Bool:
    """``true`` or ``false``, a kind apart from numbers."""

    #: The truth value.
    value: bool

    def written(self) -> str:
        """Return the canonical FON."""
        return "true" if self.value else "false"


@dataclass(frozen=True)
class Num:
    """An exact decimal: no ``+``, no leading zeros, no exponent."""

    #: The number, exact.
    value: Decimal

    def written(self) -> str:
        """Return the canonical FON."""
        return format(self.value, "f")


@dataclass(frozen=True)
class Flt:
    """An IEEE binary64 float, held as its bit pattern.

    Two floats are equal when their bits are: ``nan`` equals ``nan``
    and ``-0.0`` differs from ``0.0``. It is written as C99 ``%a`` hex,
    exact.
    """

    #: The 64 bits of the float as a signed integer.
    bits: int

    @classmethod
    def of(cls, value: float) -> "Flt":
        """Return the float's bit pattern as a :class:`Flt`."""
        return cls(int(struct.unpack("<q", struct.pack("<d", value))[0]))

    @property
    def value(self) -> float:
        """The float the bits spell."""
        return float(struct.unpack("<d", struct.pack("<q", self.bits))[0])

    def written(self) -> str:
        """Return the canonical FON.

        That is ``nan``, ``-nan``, ``inf``, ``-inf``, ``[-]0x0p0``, or
        ``[-]0x1[.hex]p<exp>`` with trailing zero hex digits dropped. A
        subnormal is normalised like every other nonzero float, with its
        exponent below -1022: the smallest is ``0x1p-1074``, where
        :meth:`float.hex` gives ``0x0.0000000000001p-1022``.

        Examples:
            >>> Flt.of(1.5).written()
            '0x1.8p0'
            >>> Flt.of(5e-324).written()
            '0x1p-1074'
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
    """A symbol, any text; it is not resolved."""

    #: The symbol's text.
    name: str

    def written(self) -> str:
        """Return the canonical FON.

        That is ``#name`` when the name is a run of name characters,
        else ``#"name"``.
        """
        bare = NAME.fullmatch(self.name)
        return "#" + (self.name if bare else _quoted(self.name, '"'))


@dataclass(frozen=True)
class Cell:
    """A reference by identity, ``$name`` or ``$<code>:<n>``."""

    #: The name, or the multihash that names it by hash.
    name: str | Multihash

    def written(self) -> str:
        """Return the canonical FON.

        That is ``$`` then the hash's decimal spelling, or the name,
        quoted when it is not a run of name characters or opens with a
        digit, as a hash does.
        """
        if isinstance(self.name, Multihash):
            return "$" + self.name.spelled()
        bare = NAME.fullmatch(self.name) and self.name[0] not in "0123456789"
        return "$" + (self.name if bare else _quoted(self.name, '"'))


@dataclass(frozen=True)
class Hash:
    """A reference by content, ``&<multihash>``; not followed.

    Contents up to 32 bytes may be given inline in the multihash.
    """

    #: The multihash of the referenced content.
    ref: Multihash

    def written(self) -> str:
        """Return the canonical FON: ``&`` and the decimal spelling."""
        return "&" + self.ref.spelled()


@dataclass(frozen=True)
class Str:
    """Text: ``"…"`` with interpolation kept as text, or ``'…'`` raw."""

    #: The characters of the string.
    text: str
    #: Whether the string was written with single quotes.
    raw: bool = False

    def written(self) -> str:
        """Return the canonical FON."""
        return _quoted(self.text, "'" if self.raw else '"')


@dataclass(frozen=True)
class List:
    """A list: ``n`` values then ``list/n``."""

    #: The elements, in order.
    items: tuple["Value", ...]

    def written(self) -> str:
        """Return the canonical FON; the empty list is ``list/0``."""
        return _built(self.items, f"list/{len(self.items)}")


@dataclass(frozen=True)
class Tagged:
    """A tagged tuple; its head is data and is never called."""

    #: The head, then the fields.
    items: tuple["Value", ...]

    def written(self) -> str:
        """Return the canonical FON.

        That is the fields then ``Name/k`` when the head is a symbol a
        tag can spell, else every item then ``tuple/n``.
        """
        head = self.items[0] if self.items else None
        if isinstance(head, Sym) and _tag(head.name):
            fields = self.items[1:]
            return _built(fields, f"{head.name}/{len(fields)}")
        return _built(self.items, f"tuple/{len(self.items)}")


@dataclass(frozen=True)
class Code:
    """Opaque code: ``n`` values then ``code/n``, not read into."""

    #: The values the constructor popped.
    items: tuple["Value", ...]

    def written(self) -> str:
        """Return the canonical FON."""
        return _built(self.items, f"code/{len(self.items)}")


#: A value that holds no other value; the only kinds a :class:`Dict` key
#: may be.
type Leaf = Absent | Bool | Num | Flt | Sym | Cell | Hash | Str


@dataclass(frozen=True)
class Dict:
    """Keys and values in turn, then ``dict/n``.

    Keys are leaves, distinct, and kept in the order written.
    """

    #: The key and value pairs, in the order written.
    entries: tuple[tuple[Leaf, "Value"], ...]

    def written(self) -> str:
        """Return the canonical FON."""
        flat = tuple(item for entry in self.entries for item in entry)
        return _built(flat, f"dict/{len(self.entries)}")


#: Any FON value.
type Value = Leaf | List | Tagged | Code | Dict
#: The values :func:`json.loads` returns, as :func:`embed` takes them.
type Json = bool | int | float | str | list["Json"] | dict[str, "Json"] | None

#: The words that spell a fixed literal.
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
    return " ".join([*(value.written() for value in values), constructor])


class _RefusedError(Exception):
    """A token the profile refuses, before it is placed in the text."""


@dataclass(frozen=True)
class Make:
    """A constructor token ``name/arity``.

    The name is ``list``, ``code``, ``tuple`` or ``dict``, else a tag
    naming the head of the tuple it builds.
    """

    #: The constructor name.
    name: str
    #: The count after the slash: values, or entries for a dict.
    arity: int

    def width(self) -> int:
        """Return how many values it pops: two per entry for a dict."""
        return 2 * self.arity if self.name == "dict" else self.arity

    def build(self, items: tuple[Value, ...]) -> Value:
        """Return what it makes of the *items* it popped.

        A dict is made apart, in ``_dict``, where its keys can be
        placed.

        Raises:
            _RefusedError: A ``tuple/n`` whose head is a symbol a tag
                can spell; ``Name/k`` is its one spelling.
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
    """Return the :class:`Hash` for ``&<multihash>``, after the ``&``.

    The multihash is in decimal or the hex alias, inline bytes allowed.

    Raises:
        _RefusedError: *text* is not a multihash spelling.
    """
    try:
        return Hash(spelling(text, inline=True))
    except ValueError:
        raise _RefusedError(f"malformed hash reference &{text}") from None


def _cell(text: str) -> Cell:
    """Return the :class:`Cell` for ``$name`` or ``$<code>:<n>``.

    The part after ``$`` is a hash when it opens with a digit. A hash
    has no hex alias, which would read as a name, and no inline bytes,
    which are content, not identity.

    Raises:
        _RefusedError: *text* opens with a digit but is not a decimal
            hash.
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
    """Return the :class:`Flt` a hex float token spells.

    Only the spelling :meth:`Flt.written` gives is read. A second
    spelling of the same bits (``0x0.8p0`` for ``0x1p-1``, ``0x0p5`` for
    ``0x0p0``) or one that rounds or underflows (``0x1p-2000``) is
    refused, so that write after read is the identity on what reads, as
    it is for decimals.

    Raises:
        _RefusedError: *token* is beyond binary64 (``0x1p2000``) or not
            canonical.
    """
    try:
        flt = Flt.of(float.fromhex(token))
    except OverflowError:
        raise _RefusedError(f"float out of range {token}") from None
    if flt.written() != token:
        raise _RefusedError(f"non-canonical number {token}")
    return flt


#: Maps a leading sigil to the function that reads the rest of the word.
SIGILS: dict[str, Callable[[str], Leaf]] = {"$": _cell, "&": _hash, "#": Sym}


def word(token: str) -> Leaf | Make:
    """Return what a token of name characters spells.

    That is a literal, or a constructor ``name/arity``.

    Args:
        token: A non-empty run of name characters, without quotes.

    Raises:
        _RefusedError: *token* is a number or hash out of canonical
            form, or is neither a literal nor a constructor.

    Examples:
        >>> word("0x1.8p0")
        Flt(bits=4609434218613702656)
        >>> word("Add/2")
        Make(name='Add', arity=2)
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
    """Return the :class:`Make` for ``name/arity``.

    Raises:
        _RefusedError: *token* is not ``name/arity`` with the arity a
            decimal without leading zeros.
    """
    name, slash, arity = token.rpartition("/")
    if not (slash and name and ARITY.fullmatch(arity)):
        raise _RefusedError(f"unknown word {token}")
    return Make(name, int(arity))


def _tag(name: str) -> bool:
    """Return whether ``name/k`` reads back as a tag headed ``#name``.

    Only then is a tuple with that head written that way.
    """
    if name in CONTAINERS or not NAME.fullmatch(name):
        return False
    try:
        return word(name + "/0") == Make(name, 0)
    except _RefusedError:
        return False


def _refusal(char: str) -> str:
    """Return why *char* may not stand in a word."""
    if char in BRACKETS:
        return f"{char} refused: FON is postfix, not braced"
    if char in "\"'":
        return f"{char} refused inside a word"
    return f"U+{ord(char):04X} refused: FON is printable ASCII"


def _word(text: str, start: int, end: int, max_token: int) -> Leaf | Make:
    """Return what the word ``text[start:end]`` spells, or refuse.

    Raises:
        FonError: The word holds a character no word holds, is longer
            than *max_token*, or is refused by :func:`word`.
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
    r"""Decode the escape at ``text[at]``.

    Returns:
        The character the escape stands for, and the offset past it. The
        escapes are ``\\``, ``\n``, ``\t``, ``\"``, ``\'`` and
        ``\u{<hex>}`` up to ``10ffff``. Whether it was the canonical one
        is judged with the whole string.

    Raises:
        FonError: The escape is malformed or beyond ``10ffff``.
    """
    short = SHORT.get(text[at + 1 : at + 2])
    if short is not None:
        return short, at + 2
    found = CODEPOINT.match(text, at)
    if found is None or int(found[1], 16) > 0x10FFFF:
        raise FonError(text, at, "malformed escape")
    return chr(int(found[1], 16)), found.end()


def _body(text: str, start: int, quote: str) -> tuple[str, int]:
    """Decode the string whose opening *quote* is at ``text[start]``.

    Returns:
        The text of the string, and the offset past its closing quote.

    Raises:
        FonError: The string is never closed, holds a character outside
            printable ASCII unescaped, or holds a bad escape (from
            :func:`_escape`).
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
    """Read the string token at *start*.

    The token is ``"text"``, ``'raw'``, ``#"symbol"`` or ``$"name"``.

    Returns:
        The value, and the offset past the token.

    Raises:
        FonError: Non-whitespace follows the token, it is not spelled as
            :func:`write` spells its value, or the string is refused by
            :func:`_body`.
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
    """Return the offset past the run of *pattern* that starts at *at*.

    *pattern* must be starred, so that it matches at *at* even for an
    empty run.
    """
    run = pattern.match(text, at)
    assert run is not None
    return run.end()


def _tokens(text: str, max_token: int) -> Iterator[tuple[int, Leaf | Make]]:
    """Yield each token's offset and what it spells, left to right.

    Raises:
        FonError: A token is refused by :func:`_string` or
            :func:`_word`.
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
    """A value on the reader's stack."""

    value: Value
    # The offset of the token that pushed it.
    offset: int
    # How deeply constructors nest in it.
    depth: int


def _dict(text: str, held: list[_Held]) -> Dict:
    """Build a :class:`Dict` from keys and values in turn.

    Raises:
        FonError: A key is not a leaf, or is given twice; raised at the
            offset where the key was pushed.
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
    """Pop the values *make* takes off *stack* and return what it makes.

    *offset* is where the constructor token stands in *text*.

    Raises:
        FonError: The stack holds too few values, the result nests
            deeper than *max_depth*, or :meth:`Make.build` or ``_dict``
            refuses.
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
    """Return the value a FON document spells.

    One value is itself; several or none are a :class:`List` of them.
    The cost is linear in the size of *text*, and every refusal is a
    :exc:`FonError` at a position in the text, the bounds included.

    Args:
        text: The document.
        max_depth: Deepest nesting of constructors allowed.
        max_token: Longest word allowed, in characters. A string's
            length is bounded by *max_size* alone.
        max_size: Longest *text* allowed, in characters.

    Raises:
        FonError: *text* is longer than *max_size*, or any token or
            constructor is refused (from :func:`_tokens` and
            :func:`_made`).

    Examples:
        >>> write(read("1 2 Add/2"))
        '1 2 Add/2'
        >>> read("1 2")
        List(items=(Num(value=Decimal('1')), Num(value=Decimal('2'))))
        >>> read("01")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        FonError: 1:1: non-canonical number 01
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
    r"""Return the canonical FON for *value*.

    The text is one line of printable ASCII, and :func:`read` gives
    *value* back from it.

    Examples:
        >>> write(List((Num(Decimal("1")), Str("a\nb"))))
        '1 "a\\nb" list/2'
    """
    return value.written()


def embed(json: Json) -> Value:
    """Return a JSON value as FON.

    Null is :class:`Absent` and a number an exact :class:`Num`. An
    object is a :class:`Dict` keyed by symbols where the key is a run of
    name characters, else by text.

    Examples:
        >>> write(embed({"a": [1, None, True], "b c": 2.5}))
        '#a 1 _ true list/3 "b c" 2.5 dict/2'
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
    """Return a JSON scalar as FON."""
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
    """Return a JSON key as a symbol if it is a run of name characters.

    Any other key is returned as text.
    """
    return Sym(name) if NAME.fullmatch(name) else Str(name)

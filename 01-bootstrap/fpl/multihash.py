"""Spell multihashes in decimal and read them back.

A digest is written ``<code>:<n>``, with *n* the digest read as a
big-endian number; bytes held inline are written ``0:<len>:<n>``. The
lower-case hex of the raw multihash is accepted as an alias.
:func:`content` and :func:`hashed` build a :class:`Multihash`,
:meth:`Multihash.spelled` writes it, and :func:`spelling` reads either
form. Only code ``0`` (inline, at most 32 bytes) and ``45600``
(blake2b-256) are known; every other code is refused (HOLES.md:
log-hash-stand-in).
"""

import hashlib
import re
from dataclasses import dataclass

#: Code of digests that hold the content bytes themselves.
INLINE = 0
#: Code of a blake2b digest of 32 bytes.
BLAKE2B_256 = 45600
#: Digest lengths each known code allows, in bytes.
LENGTHS: dict[int, range] = {INLINE: range(33), BLAKE2B_256: range(32, 33)}
#: One decimal numeral: ASCII digits, no leading zero.
NUMERAL = re.compile(r"0|[1-9][0-9]*")
#: Lower-case hex, whole bytes only.
HEX = re.compile(r"(?:[0-9a-f]{2})+")


def _leb128(n: int) -> bytes:
    r"""Encode *n* as minimal unsigned LEB128.

    Examples:
        >>> _leb128(300)
        b'\xac\x02'
    """
    out = bytearray()
    while n >= 0x80:
        out.append(n & 0x7F | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


@dataclass(frozen=True)
class Multihash:
    """A self-describing digest.

    The *code* names how *digest* was made from the content.
    """

    #: Hash function code; a key of :data:`LENGTHS` for values that
    #: :func:`spelling` accepts.
    code: int
    #: The digest bytes, or the content itself when *code* is
    #: :data:`INLINE`.
    digest: bytes

    def spelled(self) -> str:
        r"""Return the decimal spelling.

        Inline digests carry their length, ``0:<len>:<n>``, because
        leading zero bytes are lost in *n*; others are ``<code>:<n>``.

        Examples:
            >>> Multihash(INLINE, b"\x00a").spelled()
            '0:2:97'
        """
        n = int.from_bytes(self.digest, "big")
        return (
            f"0:{len(self.digest)}:{n}"
            if self.code == INLINE
            else f"{self.code}:{n}"
        )

    def raw(self) -> bytes:
        r"""Return ``varint(code) + varint(length) + digest``.

        These are the bytes the hex alias spells.

        Examples:
            >>> Multihash(INLINE, b"ab").raw()
            b'\x00\x02ab'
        """
        return _leb128(self.code) + _leb128(len(self.digest)) + self.digest


def hashed(data: bytes) -> Multihash:
    """Return the blake2b-256 multihash of *data*.

    Examples:
        >>> hashed(b"").code
        45600
    """
    return Multihash(
        BLAKE2B_256, hashlib.blake2b(data, digest_size=32).digest()
    )


def content(data: bytes) -> Multihash:
    """Return the ``&`` of *data*.

    Up to 32 bytes the digest is the bytes themselves (:data:`INLINE`);
    longer data gets its :func:`hashed` digest.

    Examples:
        >>> content(b"ab")
        Multihash(code=0, digest=b'ab')
        >>> content(bytes(33)).code
        45600
    """
    return Multihash(INLINE, data) if len(data) <= 32 else hashed(data)


def _checked(code: int, length: int, inline: bool) -> None:
    """Check a code and digest length, and if inline bytes may stand.

    Raises:
        ValueError: *code* is not in :data:`LENGTHS` (line 123),
            *length* is not allowed for *code* (line 125), or *code* is
            :data:`INLINE` while *inline* is false (line 127).
    """
    lengths = LENGTHS.get(code)
    if lengths is None:
        raise ValueError(f"unknown multihash code {code}")
    if length not in lengths:
        raise ValueError(f"digest length {length} is wrong for code {code}")
    if code == INLINE and not inline:
        raise ValueError("inline bytes cannot stand for an identity")


def _numerals(parts: list[str]) -> list[int]:
    """Convert decimal numerals to integers.

    Raises:
        ValueError: A part does not match :data:`NUMERAL` (line 137).
    """
    if not all(NUMERAL.fullmatch(part) for part in parts):
        raise ValueError("malformed decimal multihash")
    return [int(part) for part in parts]


def _decimal(parts: list[str], inline: bool) -> Multihash:
    """Read the parts of ``<code>:<n>`` or ``0:<len>:<n>``.

    Raises:
        ValueError: The parts are not in one of those shapes (lines 137,
            158), the code is unknown (line 156), or *n* does not fit in
            the length (line 161). Errors of :func:`_numerals` and
            :func:`_checked` pass through.
    """
    match _numerals(parts):
        case [0, length, n]:
            code = INLINE
        case [code, n] if code != INLINE and code in LENGTHS:
            length = LENGTHS[code].start
        case [code, _] if code != INLINE:
            raise ValueError(f"unknown multihash code {code}")
        case _:
            raise ValueError("malformed decimal multihash")
    _checked(code, length, inline)
    if n.bit_length() > 8 * length:
        raise ValueError(f"number too large for {length} bytes")
    return Multihash(code, n.to_bytes(length, "big"))


def _varint(raw: bytes, at: int) -> tuple[int, int]:
    """Read the minimal unsigned LEB128 number at offset *at*.

    Returns:
        The number and the offset after it.

    Raises:
        ValueError: The number has a trailing zero byte (line 181), or
            *raw* ends before it is complete (line 183).
    """
    value = 0
    for offset in range(at, len(raw)):
        byte = raw[offset]
        value |= (byte & 0x7F) << 7 * (offset - at)
        if byte < 0x80:
            if byte == 0 and offset > at:
                raise ValueError("non-minimal varint")
            return value, offset + 1
    raise ValueError("varint cut short")


def _hex(text: str, inline: bool) -> Multihash:
    """Read hex of ``varint(code) + varint(length) + digest``.

    Raises:
        ValueError: *text* does not match :data:`HEX` (line 195), the
            digest is not *length* bytes (line 201; trailing bytes
            included). Errors of :func:`_varint` and :func:`_checked`
            pass through.
    """
    if not HEX.fullmatch(text):
        raise ValueError("malformed hex multihash")
    raw = bytes.fromhex(text)
    code, at = _varint(raw, 0)
    length, at = _varint(raw, at)
    _checked(code, length, inline)
    if len(raw) - at != length:
        raise ValueError(f"digest length differs from {length}")
    return Multihash(code, raw[at:])


def spelling(text: str, *, inline: bool) -> Multihash:
    r"""Return the multihash a decimal spelling or its hex alias names.

    Text with a ``:`` is read as decimal, other text as hex.

    Args:
        text: The spelling to read.
        inline: Whether inline (code ``0``) digests are allowed.

    Raises:
        ValueError: *text* is malformed (lines 137, 158, 195), has an
            unknown code (lines 123, 156), a digest of the wrong length
            (lines 125, 201), inline bytes while *inline* is false (line
            127), a number too large for its length (line 161), or a
            non-minimal or cut-short varint (lines 181, 183).

    Examples:
        >>> spelling("0:2:97", inline=True)
        Multihash(code=0, digest=b'\x00a')
        >>> spelling("0:2:97", inline=False)
        Traceback (most recent call last):
            ...
        ValueError: inline bytes cannot stand for an identity
    """
    return (
        _decimal(text.split(":"), inline)
        if ":" in text
        else _hex(text, inline)
    )

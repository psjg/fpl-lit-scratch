"""
The tangled FON, `python/fpl/fon`, is the seed's postfix FON: it reads
what the seed writes and writes it back byte for byte, refuses braces,
and the stages speak it over the pipe.
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st
from lit import fpl, lit
from test_fon import STRINGS, value

from fpl.fon import BRACKETS, Value, write

ECHO = """
import sys
from fpl.fon import read, write
for line in sys.stdin.read().splitlines():
    print(write(read(line)))
"""


@settings(max_examples=3)
@given(st.lists(value, min_size=20, max_size=40))
def test_the_tangled_fon_reads_and_writes_as_the_seed(
    values: list[Value],
) -> None:
    """
    Every document the seed writes is one line; the tangled reader reads
    it and the tangled writer gives the same line back.
    """
    lines = "".join(write(v) + "\n" for v in values).encode()
    result = lit(ECHO, stdin=lines)
    assert result.returncode == 0, result.stderr
    assert result.stdout == lines


def test_the_tangled_reader_refuses_braced_fon() -> None:
    result = lit(
        "from fpl.fon import FonError, read\n"
        "try:\n"
        "    read('{ 「source」 「1」 }')\n"
        "except FonError as error:\n"
        "    print(error, error.offset)\n"
    )
    assert result.stdout == (
        b"ERROR: 1:1 { refused: FON is postfix, not braced 0\n"
    )


def test_the_stages_speak_postfix_ascii() -> None:
    """
    `fpl source | fpl lex` writes one line of printable ASCII with no
    brace outside a string, each a document tagged with its
    representation; `fpl lex` refuses braced input.
    """
    source = fpl("source", stdin=b"1 2 +\n")
    assert source.stdout == b'"1 2 +\\n" Source/1\n'
    lexed = fpl("lex", stdin=source.stdout)
    assert lexed.returncode == 0, lexed.stderr
    document = lexed.stdout.decode()
    assert re.fullmatch(r"[ -~]+\n", document)
    assert not set(STRINGS.sub("", document)) & set(BRACKETS)
    assert document.startswith('"1 2 +\\n" "1 2 +\\n\\n" ')
    assert document.endswith(" Tokens/1\n")
    braced = fpl("lex", stdin="「1 2 +\n」\n".encode())
    assert (braced.returncode, braced.stderr.decode()) == (
        1,
        "not FON: 「 refused: FON is postfix, not braced\n",
    )

"""
The parse note, read from the tangled tree.
"""

from lit import lit


def test_parse_reads_a_string_with_an_island() -> None:
    code = (
        "from fpl.lex import lex\n"
        "from fpl.parse import parse\n"
        "parse(lex('\\u201ca \\u27e81 2 +\\u27e9 b\\u201d\\n'))\n"
        "print('ok')\n"
    )
    done = lit(code)
    assert done.returncode == 0, done.stderr.decode()
    assert done.stdout == b"ok\n"

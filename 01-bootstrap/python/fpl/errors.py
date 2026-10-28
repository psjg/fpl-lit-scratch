"""Define the errors of a running program, each at a source position.

:class:`FplError` carries a :class:`Span` and a message and prints as
one ``ERROR: line:col message`` line; :meth:`FplError.render` adds the
source line with a caret. :class:`FailError` and
:class:`UnresolvedError` are its two subclasses.
"""

from dataclasses import dataclass
from typing import override


@dataclass(frozen=True)
class Span:
    """A position in the source, counted from 1 as an editor counts."""

    #: Line number, 1 for the first line.
    line: int
    #: Column number, 1 for the first character of the line.
    col: int


class FplError(Exception):
    """A failure of the program being run, not of the interpreter."""

    def __init__(self, span: Span, message: str) -> None:
        """Store the position and the message.

        Args:
            span: Where in the source the failure is.
            message: What failed, without the position.
        """
        super().__init__(message)
        #: Where in the source the failure is.
        self.span = span
        #: What failed, without the position.
        self.message = message

    @override
    def __str__(self) -> str:
        """Return the one line an ``.expected`` file holds for an error.

        The format is fixed by ``.agents/CONVENTIONS.md``.

        Returns:
            ``ERROR: <line>:<col> <message>``.

        Examples:
            >>> str(FplError(Span(2, 3), "bad"))
            'ERROR: 2:3 bad'
        """
        return f"ERROR: {self.span.line}:{self.span.col} {self.message}"

    def render(self, source: str) -> str:
        r"""Return the error line, the source line it is in and a caret.

        Args:
            source: The full program text the span refers to.

        Returns:
            :meth:`__str__`, a newline, the source line, a newline and a
            caret under the column. A column past the end of the line
            puts the caret one past its last character. A line outside
            *source* gives :meth:`__str__` alone.

        Examples:
            >>> print(FplError(Span(2, 3), "bad").render("a\nbcd\n"))
            ERROR: 2:3 bad
            bcd
              ^
            >>> FplError(Span(9, 1), "bad").render("a")
            'ERROR: 9:1 bad'
        """
        lines = source.splitlines()
        if not 1 <= self.span.line <= len(lines):
            return str(self)
        text = lines[self.span.line - 1]
        caret = " " * (min(self.span.col, len(text) + 1) - 1) + "^"
        return f"{self}\n{text}\n{caret}"


class FailError(FplError):
    """A match found no fitting row, or a guard's ``+fail`` hit."""


class UnresolvedError(FplError):
    """A word no definition or builtin names, reported at the word.

    Raised both for an unknown word and for one that the language's
    examples call but nothing runs yet. The ``.expected`` files of the
    latter still hold the skeleton's blanket refusal, which
    ``tests/test_conformance.py`` keeps.
    """

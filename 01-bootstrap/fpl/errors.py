"""Define the errors of a running program, each at a source position.

:class:`FplError` carries a :class:`Span` and a message and prints as
one ``ERROR: line:col message`` line; :meth:`FplError.render` adds the
source line with a caret. Each subclass names what went wrong by its
:attr:`~FplError.tag`, a path under ``err/`` that a fail judgment
``|- ! err/<tag>`` matches; the catalog is
``02-docs/02.03-reference/02.03.01-errors.md``. The tag is printed
nowhere yet.
"""

from dataclasses import dataclass
from typing import ClassVar, override


@dataclass(frozen=True)
class Span:
    """A position in the source, counted from 1 as an editor counts."""

    #: Line number, 1 for the first line.
    line: int
    #: Column number, 1 for the first character of the line.
    col: int


class FplError(Exception):
    """A failure of the program being run, not of the interpreter."""

    #: What went wrong, as a path under ``err/``; a subclass names a
    #: path under its parent's.
    tag: ClassVar[str] = "err"

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

    tag = "err/no-row"


class UnresolvedError(FplError):
    """A word that nothing runs, reported at the word.

    The parent of :class:`NoEvaluatorError` and
    :class:`UnknownWordError`.
    """

    tag = "err/unresolved"


class NoEvaluatorError(UnresolvedError):
    """What the language's examples use and nothing here runs yet.

    The ``.expected`` files of those examples still hold the skeleton's
    blanket refusal, which ``tests/test_conformance.py`` keeps.
    """

    tag = "err/unresolved/no-evaluator"


class UnknownWordError(UnresolvedError):
    """A word no definition or builtin names."""

    tag = "err/unresolved/unknown-word"


class OutOfGasError(FplError):
    """A run line took every step its fuel allows."""

    tag = "err/out-of-gas"


class StackError(FplError):
    """The stack does not hold what a word takes."""

    tag = "err/stack"


class CheckError(FplError):
    """A check ``L |- R`` or a closing fail judgment did not hold.

    The message starts with ``check failed:``.
    """

    tag = "err/check"

    def __init__(self, span: Span, reason: str) -> None:
        """Store the position and the reason, after ``check failed:``.

        Args:
            span: The line of the check.
            reason: Why the check failed.

        Examples:
            >>> str(CheckError(Span(1, 1), "why"))
            'ERROR: 1:1 check failed: why'
        """
        super().__init__(span, f"check failed: {reason}")


class UnequalError(CheckError):
    """The two sides of ``L |- R`` left different stacks."""

    tag = "err/check/unequal"

    def __init__(self, span: Span, left: str, right: str) -> None:
        """Store the two stacks, each as the line that prints it.

        Args:
            span: The line of the check.
            left: What ``L`` left, printed.
            right: What ``R`` left, printed.

        Examples:
            >>> str(UnequalError(Span(3, 1), "2", "3"))
            'ERROR: 3:1 check failed: 2 is not 3'
        """
        super().__init__(span, f"{left} is not {right}")


class UnmatchedFailError(CheckError):
    """The program failed, with another tag or message than judged."""

    tag = "err/check/unmatched-fail"


class NoFailError(CheckError):
    """The program passed where its closing judgment says it fails."""

    tag = "err/check/no-fail"

"""Define the errors of a running program, each at a source position.

:class:`FplError` carries a :class:`Span` and a message and prints as
one ``ERROR: line:col message`` line; :meth:`FplError.render` adds the
source line with a caret. Each subclass names what went wrong by its
:attr:`~FplError.tag`, a path under ``err/`` that a fail judgment
``|- ! err/<tag>`` matches; the catalog is
``02-docs/02.03-reference/02.03.01-errors.md``. The tag is printed
nowhere yet.

Errors are grouped by what went wrong, not by the pass that finds it:
``stack underflow`` is :class:`UnderflowError` whether the types or the
run see it first. No module raises :class:`FplError` itself; a new
error is a new subclass at its place in the tree.
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
            :meth:`__str__`, a newline and the :func:`excerpt` of
            *source* at the span; :meth:`__str__` alone when the excerpt
            is empty.

        Examples:
            >>> print(FplError(Span(2, 3), "bad").render("a\nbcd\n"))
            ERROR: 2:3 bad
            bcd
              ^
            >>> FplError(Span(9, 1), "bad").render("a")
            'ERROR: 9:1 bad'
        """
        shown = excerpt(source, self.span)
        return f"{self}\n{shown}" if shown else str(self)


def excerpt(source: str, span: Span) -> str:
    r"""Return the source line a span is in, a newline and a caret.

    Args:
        source: The full text the span refers to.
        span: The position to mark.

    Returns:
        The line and a caret under the column. A column past the end of
        the line puts the caret one past its last character. A line
        outside *source* gives the empty string.

    Examples:
        >>> print(excerpt("a\nbcd\n", Span(2, 9)))
        bcd
           ^
        >>> excerpt("a", Span(9, 1))
        ''
    """
    lines = source.splitlines()
    if not 1 <= span.line <= len(lines):
        return ""
    text = lines[span.line - 1]
    return f"{text}\n{' ' * (min(span.col, len(text) + 1) - 1)}^"


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


class GoalError(UnresolvedError):
    """A hole whose code is neither written nor inferred."""

    tag = "err/unresolved/goal"


class OutOfGasError(FplError):
    """A run line took every step its fuel allows."""

    tag = "err/out-of-gas"


class StackError(FplError):
    """The stack does not hold what a word takes."""

    tag = "err/stack"


class UnderflowError(StackError):
    """Fewer values than a word, a binder or a match takes."""

    tag = "err/stack/underflow"

    def __init__(self, span: Span) -> None:
        """Build the error with the message ``stack underflow``.

        Args:
            span: The word, binder or match that took too many values.

        Examples:
            >>> str(UnderflowError(Span(1, 3)))
            'ERROR: 1:3 stack underflow'
        """
        super().__init__(span, "stack underflow")


class ReadError(FplError):
    """Text that does not read as code: the program is never run."""

    tag = "err/read"


class UnclosedError(ReadError):
    """An opener with no closer before the text ends."""

    tag = "err/read/unclosed"


class UnopenedError(ReadError):
    """A closer with no opener before it."""

    tag = "err/read/unopened"


class MismatchedError(ReadError):
    """A closer that does not close the latest opener."""

    tag = "err/read/mismatched"


class TabsError(ReadError):
    """A line indented with spaces outside brackets."""

    tag = "err/read/tabs"


class StrayDedentError(ReadError):
    """A dedent to a level that no line or open bracket holds."""

    tag = "err/read/dedent"


class TooDeepError(ReadError):
    """Nesting deeper than the reader's recursion reaches."""

    tag = "err/read/too-deep"


class ModifierError(ReadError):
    """A token that ends in a modifier, so names no word."""

    tag = "err/read/modifier"


class CommentError(ReadError):
    """A comment where comments cannot stand."""

    tag = "err/read/comment"


class UnexpectedError(ReadError):
    """Input the grammar does not take at its position."""

    tag = "err/read/unexpected"


class NumberError(ReadError):
    """A numeral the reader does not take."""

    tag = "err/read/number"


class TooLongError(NumberError):
    """A numeral of more digits than a number holds."""

    tag = "err/read/number/too-long"


class FormError(FplError):
    """A line or an enclosure of the wrong shape for its place."""

    tag = "err/form"


class RowError(FormError):
    """A match row that is not its patterns and at most a body."""

    tag = "err/form/row"


class MatchError(FormError):
    """A match with no rows."""

    tag = "err/form/match"


class PatternError(FormError):
    """A constructor pattern of another count than the constructor."""

    tag = "err/form/pattern"


class DictError(FormError):
    """A dict whose key repeats or whose value is not one value."""

    tag = "err/form/dict"


class EffectError(FormError):
    """A body that leaves another count than its effect line."""

    tag = "err/form/effect"


class ClauseError(FormError):
    """Clauses of one arity group that disagree on kinds or counts."""

    tag = "err/form/clause"


class CheckFormError(FormError):
    """A check or a fail judgment where none can stand."""

    tag = "err/form/check"


class AmbiguousError(FplError):
    """A name or call that more than one definition answers."""

    tag = "err/ambiguous"


class AmbiguousClauseError(AmbiguousError):
    """Two clauses that both fit some input none of them names."""

    tag = "err/ambiguous/clause"


class AmbiguousCallError(AmbiguousError):
    """A call that two clauses both fit, found at run time."""

    tag = "err/ambiguous/call"


class AmbiguousQueryError(AmbiguousError):
    """A query on a path with more than one part to answer it."""

    tag = "err/ambiguous/query"


class WrongTypeError(FplError):
    """An operand of the wrong kind for the word that takes it."""

    tag = "err/type"


class NotNumberError(WrongTypeError):
    """A word that takes a number, or a count, was given another."""

    tag = "err/type/number"


class NotQuotationError(WrongTypeError):
    """A word that takes a quotation was given another value."""

    tag = "err/type/quotation"


class NotListError(WrongTypeError):
    """A word that takes a list or a strand was given another."""

    tag = "err/type/list"


class NotInvertibleError(WrongTypeError):
    """A word in a pattern that cannot run backwards."""

    tag = "err/type/invertible"


class ShapeError(FplError):
    """Operands of the right kinds and the wrong sizes."""

    tag = "err/shape"


class UnequalStrandsError(ShapeError):
    """Two strands of different lengths, neither of length one."""

    tag = "err/shape/unequal-strands"


class EmptyFoldError(ShapeError):
    """A fold or a reduction over no items."""

    tag = "err/shape/empty-fold"


class EachError(ShapeError):
    """A step that leaves other than the one value it must."""

    tag = "err/shape/each"


class TooLargeError(FplError):
    """An arithmetic result of more digits than a number holds."""

    tag = "err/too-large"


class RecursionDepthError(FplError):
    """A run nested deeper than Python's stack, not the fuel, allows."""

    tag = "err/recursion"


class PrintError(FplError):
    """A value nested deeper than the printer reaches."""

    tag = "err/print"


class SessionError(FplError):
    """A session input that does not start at the left margin."""

    tag = "err/session"


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

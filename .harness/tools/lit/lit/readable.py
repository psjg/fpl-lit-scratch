"""The reader check: does the prose alone teach what the tests assert?

The page is stripped of its code; each chunk leaves only its name, as
``⟨Name⟩``, where the code stood. The facts are the module's tests, read
mechanically: every ``assert L == R`` and ``assert L is None`` in a test
function becomes the question "what is ``L``?" with ``R`` as its
answer, once per row of a ``pytest.mark.parametrize`` table. A fact is
kept only when a reader of the page could answer it, and the answer
can be judged: every name in it is bound by the page's code, is a
builtin, or is a helper of the test file whose docstring says what it
does, quoted with the question; and the expected value is literals,
containers and calls of the page's records.
Facts over a test's local variables (a Hypothesis draw, say) are
dropped.

A model reads the stripped page and the questions, and answers each
with a Python expression; it does so three times by default, and the
score is the mean, since one reply of a small model varies (measured,
2026-10-27: 0.71 and 0.50 on the same page, one minute apart). An
answer is right when it evaluates to the expected value, where only
literals and data classes that run no code of their own are evaluated.
The score is the fraction right; the page passes at or above a
threshold.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import itertools
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import override

from lit.web import Page

MODEL = "haiku"
THRESHOLD = 0.7
RUNS = 3
ANSWER = re.compile(r"\s*(?P<n>\d+)\s*[:.)]\s*(?P<expr>.*?)\s*")
PROMPT = """\
Below is one chapter of a program's documentation, with its code taken
out: each ⟨Name⟩ marks where a piece of code stood. Answer every
question from the chapter alone. Reply with one line per question and
nothing else, in the form

<number>: <Python expression>

with no explanation, no backticks and no working.
where the expression is the value as Python would print it (a string
in quotes, a tuple in parentheses, None, a call such as Name(1, 2) for
an object). If the chapter does not tell, write <number>: ?

=== CHAPTER ===
{chapter}
=== QUESTIONS ===
{questions}
"""


@dataclass(frozen=True)
class Fact:
    """A question from one assertion, where it is, and its answer."""

    anchor: str
    question: str
    expected: str


def chapter(page: Page, text: str, examples: bool = True) -> str:
    """The page's prose with each chunk's code replaced by its name."""
    lines = text.split("\n")
    keep: set[int] = set()
    for s in page.sections:
        if examples:
            keep |= {p.number for p in s.prose}
        else:
            keep |= {p.number for p in s.prose if not p.fenced}
    out: list[str] = []
    for s in page.sections:
        out += [lines[p.number - 1] for p in s.prose if p.number in keep]
        if s.chunk is not None:
            out.append(f"⟨{s.chunk.name}⟩")
    return "\n".join(out)


def _rows(fn: ast.FunctionDef) -> list[dict[str, ast.expr]]:
    """The parameter rows of a test, one empty row if not a table."""
    tables: list[list[dict[str, ast.expr]]] = []
    for deco in fn.decorator_list:
        match deco:
            case ast.Call(
                func=ast.Attribute(attr="parametrize"),
                args=[ast.Constant(value=str() as spec), values, *_],
            ):
                params = [p.strip() for p in spec.split(",")]
            case ast.Call(
                func=ast.Attribute(attr="parametrize"),
                args=[ast.Tuple(elts=elts) | ast.List(elts=elts), values, *_],
            ):
                params = [ast.literal_eval(e) for e in elts]
            case _:
                continue
        tables.append(_table(params, values))
    return [
        {k: v for row in combo for k, v in row.items()}
        for combo in itertools.product(*tables)
    ]


def _table(params: list[str], values: ast.expr) -> list[dict[str, ast.expr]]:
    """One parametrize table's rows, each a name to its value's tree."""
    if not isinstance(values, ast.List | ast.Tuple):
        return []
    if len(params) == 1:
        return [{params[0]: v} for v in values.elts]
    return [
        dict(zip(params, v.elts, strict=True))
        for v in values.elts
        if isinstance(v, ast.Tuple) and len(v.elts) == len(params)
    ]


class _Subst(ast.NodeTransformer):
    """Put a row's values in place of the test's parameters."""

    def __init__(self, row: dict[str, ast.expr]) -> None:
        self.row = row

    @override
    def visit_Name(self, node: ast.Name) -> ast.expr:
        """A parameter becomes its value; other names stay."""
        return self.row.get(node.id, node)


def _free(tree: ast.expr) -> set[str]:
    """The names an expression reads."""
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _locals(fn: ast.FunctionDef) -> set[str]:
    """A test's parameters and the names it assigns."""
    stored = {
        n.id
        for n in ast.walk(fn)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }
    return stored | {a.arg for a in fn.args.args}


def _helpers(module: ast.Module) -> dict[str, str]:
    """The test file's helpers that say what they do: name to doc."""
    out: dict[str, str] = {}
    for node in module.body:
        doc = (
            ast.get_docstring(node)
            if isinstance(node, ast.FunctionDef)
            else None
        )
        if doc and isinstance(node, ast.FunctionDef):
            out[node.name] = " ".join(doc.split("\n\n")[0].split())
    return out


def _assertions(fn: ast.FunctionDef) -> list[tuple[int, ast.expr, ast.expr]]:
    """Each ``L == R`` or ``L is None`` asserted in a test."""
    out: list[tuple[int, ast.expr, ast.expr]] = []
    for node in ast.walk(fn):
        match node:
            case ast.Assert(
                test=ast.Compare(
                    left=left, ops=[ast.Eq()], comparators=[right]
                )
            ):
                out.append((node.lineno, left, right))
            case ast.Assert(
                test=ast.Compare(
                    left=left,
                    ops=[ast.Is()],
                    comparators=[ast.Constant(value=None) as right],
                )
            ):
                out.append((node.lineno, left, right))
            case _:
                pass
    return out


def facts(path: str, source: str, known: set[str]) -> list[Fact]:
    """The facts of one test file a reader of the page could answer."""
    module = ast.parse(source)
    helpers = _helpers(module)
    allowed = known | set(dir(builtins)) | set(helpers)
    out: list[Fact] = []
    for fn in module.body:
        if not (
            isinstance(fn, ast.FunctionDef) and fn.name.startswith("test")
        ):
            continue
        local = _locals(fn)
        for line, left, right in _assertions(fn):
            for row in _rows(fn):
                usable = allowed - (local - set(row))
                fact = _fact(row, left, right, usable, helpers)
                if fact is not None:
                    out.append(Fact(f"{path}:{line}", *fact))
    return out


def _fact(
    row: dict[str, ast.expr],
    left: ast.expr,
    right: ast.expr,
    allowed: set[str],
    helpers: dict[str, str],
) -> tuple[str, str] | None:
    """A question and its answer, or None when no reader could tell."""
    lhs = _Subst(row).visit(ast.parse(ast.unparse(left), mode="eval")).body
    rhs = _Subst(row).visit(ast.parse(ast.unparse(right), mode="eval")).body
    free = _free(lhs) | _free(rhs)
    if not free <= allowed or not plain(rhs):
        return None
    notes = [
        f" Here `{h}` is: {helpers[h]}" for h in sorted(free & set(helpers))
    ]
    question = f"What is `{ast.unparse(lhs)}`?" + "".join(notes)
    return question, ast.unparse(rhs)


def prompt(text: str, items: list[Fact]) -> str:
    """The one prompt: the chapter and the numbered questions."""
    questions = "\n".join(f"{n}. {f.question}" for n, f in enumerate(items, 1))
    return PROMPT.format(chapter=text, questions=questions)


SAFE = (
    ast.Expression,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.Call,
    ast.keyword,
    ast.Name,
    ast.Load,
    ast.UnaryOp,
    ast.USub,
)


def plain(tree: ast.AST) -> bool:
    """Whether a tree is literals, containers, minus and named calls."""
    return all(
        isinstance(node, SAFE)
        and not (
            isinstance(node, ast.Call) and not isinstance(node.func, ast.Name)
        )
        for node in ast.walk(tree)
    )


def records(space: dict[str, object]) -> dict[str, type]:
    """The data classes a namespace holds that run no code of their own.

    A dataclass's ``__init__`` only stores its fields; one with a
    ``__post_init__`` runs more, and any other class may run anything
    (``Popen`` would run a command), so neither is a record.
    """
    return {
        k: v
        for k, v in space.items()
        if isinstance(v, type)
        and dataclasses.is_dataclass(v)
        and not hasattr(v, "__post_init__")
    }


def value(text: str, space: dict[str, object]) -> object:
    """The value of an answer built of literals and records.

    Only literals, containers, a minus sign, and calls of the records
    in ``space`` are evaluated, with no builtins: an answer is a
    model's text, and nothing else of it runs. Anything more raises
    ValueError.
    """
    tree = ast.parse(text, mode="eval")
    kinds = records(space)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    if not plain(tree) or not names <= set(kinds):
        raise ValueError(text)
    code = compile(tree, "<answer>", "eval")
    return eval(code, {"__builtins__": {}}, kinds)


def same(expected: str, got: str, space: dict[str, object]) -> bool:
    """Whether an answer is the expected value.

    An answer that is no expression is read as the text of a string,
    since a model often leaves the quotes off a message.
    """
    want = value(expected, space)
    try:
        return bool(want == value(got, space))
    except (ValueError, SyntaxError, TypeError):
        return isinstance(want, str) and want == got.strip()


def answer(text: str) -> str:
    """The expression of an answer line: its last code span, if any.

    Asked for a bare expression, a model still often explains it and
    quotes the value in backticks last; that value is the answer.
    """
    spans = re.findall(r"`([^`]+)`", text)
    return spans[-1] if spans else text


def score(
    items: list[Fact], reply: str, space: dict[str, object]
) -> list[tuple[Fact, str, bool]]:
    """Each fact, the answer given to it, and whether it is right."""
    said: dict[int, str] = {}
    for line in reply.splitlines():
        if m := ANSWER.fullmatch(line):
            said.setdefault(int(m["n"]), answer(m["expr"]))
    return [
        (f, said.get(n, "?"), same(f.expected, said.get(n, "?"), space))
        for n, f in enumerate(items, 1)
    ]


def ask(text: str, command: list[str]) -> str:
    """The model's reply to a prompt, run in an empty directory.

    The command reads the prompt on stdin. It runs where there is
    nothing to read, so that the page is all it knows, and without
    extended thinking: the reader is meant to be a quick one, and with
    thinking the CLI took over 100 s for 28 questions (measured,
    2026-10-27) against 15 s without.
    """
    with tempfile.TemporaryDirectory() as empty:
        run = subprocess.run(
            command,
            input=text,
            capture_output=True,
            text=True,
            cwd=empty,
            env=os.environ | {"MAX_THINKING_TOKENS": "0"},
            check=True,
            timeout=900,
        )
    return run.stdout


SYSTEM = (
    "You answer questions about a document you are given. Reply with"
    " exactly one line per question, '<number>: <Python expression>',"
    " and nothing else."
)


def claude(model: str) -> list[str]:
    """The headless Claude CLI, with no tools and no settings.

    Its own system prompt, that of a coding agent, is replaced by one
    that asks for the answer lines alone: with the default one, Haiku
    worked through the questions in prose and two runs of three gave no
    line the score could read (measured, 2026-10-27).
    """
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--tools",
        "",
        "--safe-mode",
        "--system-prompt",
        SYSTEM,
        "--output-format",
        "text",
    ]


def tests_for(page: Page, root: Path) -> list[Path]:
    """The default tests: ``tests/test_<stem>.py`` per Python file."""
    stems = {
        Path(c.name).stem for c in page.chunks() if c.name.endswith(".py")
    }
    return sorted(
        root / "tests" / f"test_{s}.py"
        for s in stems
        if (root / "tests" / f"test_{s}.py").is_file()
    )

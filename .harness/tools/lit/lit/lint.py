"""The lint: the prose and the code of a page agree.

Prose names code in the form of an Emacs docstring, a backtick, the
name, an apostrophe: `prelex' or `Lines.span'. Three rules hold:

- **lit-unknown**: every such reference names something the tangled
  code binds (a definition, a field, a parameter, an import);
- **lit-unmentioned**: every constant (an upper-case module name) and
  every public name (a definition, method or field whose name has no
  leading underscore) is referenced in the prose of the section whose
  chunk defines it, unless the page's front matter allows it with
  ``lit-allow: [NAME, ...]``;
- **lit-example**: every ``pycon`` fence of the prose is a doctest,
  run against the namespace of the page's first Python file, and must
  pass.

A reference inside a fence is not read, so an example may quote code
freely. The module is executed from its fresh tangle, never from the
file on disk, so the lint judges the page even when the file drifted.
"""

from __future__ import annotations

import ast
import doctest
import linecache
import re
import sys
import types
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast, override

from lit.web import Finding, Page, Section, Tangled

REF = re.compile(r"`(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)'")
CONSTANT = re.compile(r"_*[A-Z][A-Z0-9_]*")


@dataclass(frozen=True)
class Defined:
    """A name the prose must mention, qualified, and its line."""

    name: str
    qualified: str
    line: int


def public(name: str) -> bool:
    """A constant, or a name without a leading underscore."""
    return not name.startswith("_") or CONSTANT.fullmatch(name) is not None


def _targets(node: ast.stmt) -> list[str]:
    """The plain names a definition or assignment statement binds."""
    match node:
        case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
            return [node.name]
        case ast.Assign():
            return [
                n.id
                for t in node.targets
                for n in ast.walk(t)
                if isinstance(n, ast.Name)
            ]
        case ast.AnnAssign(target=ast.Name(id=name)):
            return [name]
        case _:
            return []


def definitions(tree: ast.Module) -> list[Defined]:
    """The names the module and its classes define, in order."""
    out: list[Defined] = []
    for node in tree.body:
        out += [Defined(n, n, node.lineno) for n in _targets(node)]
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                out += [
                    Defined(n, f"{node.name}.{n}", sub.lineno)
                    for n in _targets(sub)
                ]
    return out


def required(tree: ast.Module) -> list[Defined]:
    """The module's constants and public names, and their classes'."""
    return [d for d in definitions(tree) if public(d.name)]


def bound(tree: ast.Module) -> set[str]:
    """Every name the module binds anywhere, imports included."""
    out: set[str] = set()
    for node in ast.walk(tree):
        match node:
            case (
                ast.FunctionDef(name=n)
                | ast.AsyncFunctionDef(name=n)
                | ast.ClassDef(name=n)
                | ast.arg(arg=n)
            ):
                out.add(n)
            case ast.Name(id=n, ctx=ast.Store()):
                out.add(n)
            case ast.Attribute(attr=n, ctx=ast.Store()):
                out.add(n)
            case ast.alias(name=n, asname=a):
                out.add(a or n.split(".")[0])
            case _:
                pass
    return out


def refs(section: Section) -> Iterator[tuple[int, str]]:
    """Each reference in a section's unfenced prose, with its line."""
    for line in section.prose:
        if not line.fenced:
            for m in REF.finditer(line.text):
                yield line.number, m["name"]


def imported(tree: ast.Module) -> set[str]:
    """The names the module's imports bind."""
    return {
        a.asname or a.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for a in node.names
    }


def code_names(
    tangled: list[Tangled],
) -> tuple[set[str], dict[tuple[str, int], Defined]]:
    """What the Python files bind, and what they owe the prose, by line.

    What they bind holds the plain names, each ``Class.member`` the
    module defines, and each import as a prefix, ``re.`` for ``re``:
    a reference into an imported module is not checked past it. A name
    the two files of one page both define from the same chunk line is
    owed once.
    """
    known: set[str] = set()
    owed: dict[tuple[str, int], Defined] = {}
    for t in tangled:
        if t.name.endswith(".py"):
            tree = ast.parse(t.text)
            known |= bound(tree) | {d.qualified for d in definitions(tree)}
            known |= {f"{n}." for n in imported(tree)}
            for d in required(tree):
                owed.setdefault((d.qualified, t.origin[d.line - 1]), d)
    return known, owed


def resolves(name: str, known: set[str]) -> bool:
    """Whether a reference names what the code binds."""
    head = name.split(".", maxsplit=1)[0]
    return name in known or ("." in name and f"{head}." in known)


def names(page: Page, tangled: list[Tangled]) -> list[Finding]:
    """lit-unknown and lit-unmentioned over the page's Python files."""
    known, owed = code_names(tangled)
    out: list[Finding] = []
    said: dict[int, set[str]] = {}
    for s in page.sections:
        for line, name in refs(s):
            said.setdefault(s.number, set()).add(name)
            if not resolves(name, known):
                message = f"`{name}' names nothing the code binds"
                out.append(Finding(page.path, line, "lit-unknown", message))
    for (qualified, line), d in sorted(owed.items(), key=lambda i: i[0][1]):
        heard = said.get(page.section_of(line), set())
        if d.name in page.allow or heard & {d.name, qualified}:
            continue
        message = (
            f"`{d.name}' is defined here but its section's prose never"
            f" names it -- write `{d.name}' in the prose before the chunk,"
            " or add it to lit-allow"
        )
        out.append(Finding(page.path, line, "lit-unmentioned", message))
    return out


def dotted(name: str) -> str:
    """The module a file path is: ``fpl/lex.py`` is ``fpl.lex``."""
    return name.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def load(t: Tangled, root: Path) -> dict[str, object]:
    """Execute a fresh tangle as its module; its namespace.

    The module is registered under its own name while it runs, as an
    import would, and the previous entry is put back after; ``root``
    is on the path so that its imports resolve. The fresh text is put
    in the line cache, so that a traceback quotes it, not the file.
    """
    name = dotted(t.name)
    path = root / t.name
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    if path.name == "__init__.py":
        module.__package__ = name
        module.__path__ = [str(path.parent)]
    had = name in sys.modules
    saved = sys.modules.get(name)
    sys.modules[name] = module
    sys.path.insert(0, str(root))
    lines = [line + "\n" for line in t.lines]
    linecache.cache[str(path)] = (len(t.text), None, lines, str(path))
    try:
        exec(compile(t.text, str(path), "exec"), module.__dict__)
    finally:
        sys.path.remove(str(root))
        if had:
            # None is a valid entry (an import that must fail);
            # typeshed does not say so. It is put back as found.
            sys.modules[name] = cast("types.ModuleType", saved)
        else:
            del sys.modules[name]
    return dict(module.__dict__)


class _Runner(doctest.DocTestRunner):
    """A doctest runner that keeps each failure as a finding."""

    def __init__(self, path: str, line: int) -> None:
        super().__init__(verbose=False)
        self.path, self.line = path, line
        self.findings: list[Finding] = []

    def _add(self, example: doctest.Example, message: str) -> None:
        at = self.line + 1 + example.lineno
        self.findings.append(Finding(self.path, at, "lit-example", message))

    @override
    def report_failure(
        self,
        out: object,
        test: doctest.DocTest,
        example: doctest.Example,
        got: str,
    ) -> None:
        """Keep a wrong output: what was expected, what came."""
        want, came = example.want.strip(), got.strip()
        self._add(example, f"expected {want!r}, got {came!r}")

    @override
    def report_unexpected_exception(
        self,
        out: object,
        test: doctest.DocTest,
        example: doctest.Example,
        exc_info: tuple[type[BaseException], BaseException, object],
    ) -> None:
        """Keep an exception no example expected."""
        self._add(example, f"raised {exc_info[1]!r}")


def examples(page: Page, tangled: list[Tangled], root: Path) -> list[Finding]:
    """lit-example: each pycon fence, run as a doctest."""
    fences = [e for s in page.sections for e in s.examples]
    module = next((t for t in tangled if t.name.endswith(".py")), None)
    if not fences:
        return []
    if module is None:
        line = fences[0].line
        message = "an example, and no Python file to run it in"
        return [Finding(page.path, line, "lit-example", message)]
    try:
        space = load(module, root)
    except Exception as error:  # noqa: BLE001 -- any failure is a finding
        message = f"{module.name} does not load: {error!r}"
        return [Finding(page.path, 1, "lit-example", message)]
    out: list[Finding] = []
    parser = doctest.DocTestParser()
    for fence in fences:
        test = parser.get_doctest(
            fence.text, dict(space), page.path, page.path, fence.line
        )
        runner = _Runner(page.path, fence.line)
        runner.run(test, out=lambda _: None)
        out += runner.findings
    return out

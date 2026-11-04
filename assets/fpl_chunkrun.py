"""
Run one edited chunk of a literate page under Pyodide, as lit's
lit-example runs the page's examples (lit/lint.py: load and _Runner).

The page's code is a package unpacked under a root. The edited chunk
takes the place of its tangled lines in the file it tangles to, at
their indent, so a chunk that is part of a function runs as that
function; the module is imported fresh, and each example of the page
(a pycon fence) is run as a doctest against a copy of it. The file is
put back after. The root's modules are in sys.modules for the run
only: the playground's own package of the same name (the walker) is
set aside and put back after.
"""

import doctest
import importlib
import io
import json
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path


def dotted(root: str, path: str) -> tuple[str, Path]:
    """
    The module `path` (a repo path, 01-bootstrap/fpl/lex.py) is under
    `root`, and its file there: its leading directories dropped until
    it is a file there.
    """
    parts = path.split("/")
    while parts and not Path(root, *parts).is_file():
        parts.pop(0)
    if not parts:
        raise ImportError(f"{path} is not in the page's code")
    name = "/".join(parts).removesuffix(".py").removesuffix("/__init__")
    return name.replace("/", "."), Path(root, *parts)


def splice(text: str, orig: str, src: str, first: int) -> str:
    """
    `text` with the lines that read `orig` at some indent, nearest to
    line `first`, read as `src` at that indent.
    """
    lines, old = text.split("\n"), orig.split("\n")
    for i in sorted(range(len(lines)), key=lambda i: abs(i + 1 - first)):
        pad = lines[i].removesuffix(old[0])
        if pad.strip() or not lines[i].endswith(old[0]):
            continue
        got = lines[i:i + len(old)]
        if got == [pad + x if x else x for x in old]:
            new = [pad + x if x else x for x in src.split("\n")]
            return "\n".join(lines[:i] + new + lines[i + len(old):])
    raise LookupError("dit blok staat anders in de code van de pagina")


class _Runner(doctest.DocTestRunner):
    """Keeps each example's source, what it wanted and what came."""

    def __init__(self) -> None:
        super().__init__(verbose=False)
        self.seen: list[dict] = []

    def _keep(self, example, got: str, ok: bool) -> None:
        self.seen.append({"src": example.source.rstrip("\n"),
                          "want": example.want.rstrip("\n"),
                          "got": got.rstrip("\n"), "ok": ok})

    def report_success(self, out, test, example, got):
        self._keep(example, got, True)

    def report_failure(self, out, test, example, got):
        self._keep(example, got, False)

    def report_unexpected_exception(self, out, test, example, exc_info):
        line = traceback.format_exception_only(*exc_info[:2])[-1]
        self._keep(example, line, False)


def run(root: str, path: str, src: str, examples: list[str],
        orig: str, first: int) -> str:
    """
    JSON {ok, out, examples}: `ok` whether the module ran with `src` in
    the place of `orig` (the chunk as tangled, from line `first`), `out`
    its stdout and, if it raised, the traceback from the module on;
    `examples` one list per fence of {src, want, got, ok}, empty when
    the module did not run.
    """
    name, file = dotted(root, path)
    top = name.split(".")[0]
    ours = lambda k: k == top or k.startswith(top + ".")
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if ours(k)}
    text = file.read_text(encoding="utf-8")
    sys.path.insert(0, root)
    nopyc, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    importlib.invalidate_caches()
    buf, ok, done = io.StringIO(), True, []
    try:
        file.write_text(splice(text, orig, src, first), encoding="utf-8")
        with redirect_stdout(buf):
            module = importlib.import_module(name)
        parser = doctest.DocTestParser()
        for ex in examples:
            test = parser.get_doctest(ex, dict(module.__dict__),
                                      path, path, 0)
            runner = _Runner()
            runner.run(test, out=lambda _: None)
            done.append(runner.seen)
    except Exception as e:  # noqa: BLE001 -- any failure is the output
        ok = False
        # from the module's own frame on: the import machinery is no news
        tb = e.__traceback__
        while tb and tb.tb_frame.f_code.co_filename != str(file):
            tb = tb.tb_next
        buf.writelines(traceback.format_exception(type(e), e, tb))
    finally:
        file.write_text(text, encoding="utf-8")
        sys.dont_write_bytecode = nopyc
        sys.path.remove(root)
        for k in [k for k in sys.modules if ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return json.dumps({"ok": ok, "out": buf.getvalue(), "examples": done})

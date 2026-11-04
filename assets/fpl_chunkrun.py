"""
Run one edited chunk of a literate page under Pyodide, as lit's
lit-example runs the page's examples (lit/lint.py: load and _Runner).

The page's code is a package unpacked under a root. The module a chunk
tangles to is imported fresh from there, the edited chunk is executed
into that module's namespace, so that the module's own functions call
the edited definitions, and each example of the page (a pycon fence)
is run as a doctest against a copy of it. The root's modules are in
sys.modules for the run only: the playground's own package of the same
name (the walker) is set aside and put back after.
"""

import doctest
import importlib
import io
import json
import linecache
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path


def dotted(root: str, path: str) -> str:
    """
    The module `path` (a repo path, 01-bootstrap/fpl/lex.py) is under
    `root`: its leading directories dropped until it is a file there.
    """
    parts = path.split("/")
    while parts and not Path(root, *parts).is_file():
        parts.pop(0)
    if not parts:
        raise ImportError(f"{path} is not in the page's code")
    name = "/".join(parts).removesuffix(".py").removesuffix("/__init__")
    return name.replace("/", ".")


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


def run(root: str, path: str, src: str, examples: list[str]) -> str:
    """
    JSON {ok, out, examples}: `ok` whether the chunk ran, `out` its
    stdout and, if it raised, the traceback; `examples` one list per
    fence of {src, want, got, ok}, empty when the chunk did not run.
    """
    name = dotted(root, path)
    top = name.split(".")[0]
    ours = lambda k: k == top or k.startswith(top + ".")
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if ours(k)}
    sys.path.insert(0, root)
    importlib.invalidate_caches()
    buf, ok, done = io.StringIO(), True, []
    where = f"<{path}>"
    linecache.cache[where] = (len(src), None, src.splitlines(True), where)
    try:
        module = importlib.import_module(name)
        with redirect_stdout(buf):
            # running the reader's chunk is the point
            exec(compile(src, where, "exec"), module.__dict__)  # noqa: S102
        parser = doctest.DocTestParser()
        for text in examples:
            test = parser.get_doctest(text, dict(module.__dict__),
                                      where, where, 0)
            runner = _Runner()
            runner.run(test, out=lambda _: None)
            done.append(runner.seen)
    except Exception as e:  # noqa: BLE001 -- any failure is the output
        ok = False
        # from the chunk's frame on: this module's own is no news
        buf.writelines(traceback.format_exception(
            type(e), e, e.__traceback__.tb_next))
    finally:
        sys.path.remove(root)
        for k in [k for k in sys.modules if ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return json.dumps({"ok": ok, "out": buf.getvalue(), "examples": done})

"""Serve a pad as one local web page: ``python -m fpl pad [FILE]``.

The page (``pad.html`` and the files :data:`PAGE` names beside this
module) is the whole interface; it needs no network beyond this
server. ``fpl-language.js`` is the playground's tokenizer, a copy of
``assets/fpl-language.js`` that a test keeps equal; the pad colours
its cells with it (``editors.js``), or with Monaco from its CDN when
the page is opened as ``/?editor=monaco`` (``monaco.js``, the one
route that needs the network). The site's ``/pad/`` page runs
the same files on :mod:`fpl.pad` under Pyodide instead
(``assets/fpl-pad.js``). The server holds one pad in
memory and changes it only through :mod:`fpl.pad`; it is a WSGI
application (:func:`app`) on :mod:`wsgiref`, which serves one request
at a time, so turns never overlap.

Routes, answered with the pad as JSON (:func:`shown`: the cells, each
with its bar and turns, the buffer, and where the caret goes), but for
``/preview``:

- ``GET /`` the page, ``GET /<file>`` for each file of :data:`PAGE`;
  ``GET /pad`` the pad.
- ``POST /buffer`` with ``{"text": buffer, "cursor": offset}``:
  :func:`fpl.pad.synced`, the caret as :func:`fpl.pad.caret` puts it.
- ``POST /reset``: an empty pad; ``POST /pad``: the pad as it is.
- ``POST /preview`` with ``{"text": buffer, "cursor": offset}``:
  :func:`fpl.pad.preview`, answered ``{"ghost": {"line", "kind",
  "text"}}``, or ``{"ghost": null}``; the pad is unchanged.

A ``POST`` body may carry ``"indent"``, the string each result line is
set in by (:func:`fpl.pad.transcript`); the page asks for a tab when
opened as ``/?results=indented``. A preview leaves the indent be.

A ``FILE`` seeds the pad: each input :func:`fpl.repl.inputs` finds in
it becomes a cell, evaluated before the page opens.
"""

import json
import sys
import webbrowser
from argparse import ArgumentParser
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from wsgiref.simple_server import make_server
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from fpl.pad import (
    Cell,
    buffer,
    caret,
    context,
    preview,
    replayed,
    synced,
)
from fpl.repl import Tty, inputs
from fpl.session import Context

#: The content type of each kind of file the page is made of.
KINDS = {
    "html": "text/html; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
}
#: The files of the page by path, and their content types.
PAGE = {"/": ("pad.html", KINDS["html"])} | {
    f"/{name}": (name, KINDS[name.rsplit(".", 1)[1]])
    for name in (
        "pad.js",
        "pad.css",
        "editors.js",
        "monaco.js",
        "highlight.js",
        "fpl-language.js",
    )
}


def seeded(text: str, ctx: Context, tty: Tty) -> tuple[Cell, ...]:
    """Return the pad whose cells are the inputs of *text*."""
    lines = iter(text.splitlines())
    sources = [t.rstrip("\n") for t in inputs(lambda _on: next(lines, None))]
    return replayed((), sources, ctx, tty)


class Pad:
    """The pad a server holds, and the changes a request can ask for."""

    def __init__(
        self, cells: tuple[Cell, ...], ctx: Context, tty: Tty | None = None
    ) -> None:
        """Hold *cells*, changed later under *ctx*.

        *tty* gives the clocks of the bars; the wall clock when None.
        """
        self.cells = cells
        self.ctx = ctx
        self.tty = tty if tty is not None else Tty()
        #: What the page sets result lines in by; the last request's.
        self.indent = ""

    def change(
        self, route: str, body: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Carry out a ``POST`` route; None when there is none.

        A preview leaves the pad, its indent included, as it was.

        Returns:
            The answer: the pad as :func:`shown` gives it, the caret
            where it goes after the change; for ``/preview``, the
            ghost.

        Raises:
            KeyError: The body lacks a field the route needs.
            TypeError: A field has the wrong type.
            ValueError: A cursor is not a number.
        """
        if route == "/preview":
            return self._previewed(body)
        self.indent = str(body.get("indent", ""))
        match route:
            case "/buffer":
                text, cursor = str(body["text"]), int(body["cursor"])
                self.cells = synced(self.cells, text, self.ctx, self.tty)
                at = caret(text, cursor, self.cells, self.tty, self.indent)
                return shown(self, at)
            case "/reset":
                self.cells = ()
                return shown(self, self.end())
            case "/pad":
                return shown(self, self.end())
            case _:
                return None

    def _previewed(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Answer ``/preview``: the ghost of the cell at the cursor."""
        text, cursor = str(body["text"]), int(body["cursor"])
        g = preview(self.cells, text, cursor, self.ctx, self.tty)
        if g is None:
            return {"ghost": None}
        return {"ghost": {"line": g.line, "kind": g.kind, "text": g.text}}

    def end(self) -> int:
        """Return the end of the buffer, where the caret rests first."""
        return len(buffer(self.cells, self.tty, self.indent))


def shown(pad: Pad, at: int) -> dict[str, Any]:
    """Return the pad as the page reads it: the cells without logs.

    ``buffer`` is the pad as text (:func:`fpl.pad.buffer`), ``caret``
    where the page puts the caret in it, *at*.
    """
    return {
        "cells": [
            {
                "source": cell.source,
                "status": cell.status,
                "bar": cell.bar,
                "turns": list(cell.turns),
                "changes": list(cell.changes),
            }
            for cell in pad.cells
        ],
        "buffer": buffer(pad.cells, pad.tty, pad.indent),
        "caret": at,
    }


#: An answer: the HTTP status line, the content type, the body.
type Answer = tuple[str, str, bytes]
#: The answer to a path no route takes.
MISSING: Answer = ("404 Not Found", "text/plain", b"not found\n")


def answered(pad: Pad, method: str, path: str, body: bytes) -> Answer:
    """Answer one request on *pad*, changing it for a ``POST``."""
    if method == "GET" and path in PAGE:
        name, kind = PAGE[path]
        return "200 OK", kind, (Path(__file__).parent / name).read_bytes()
    if method != "POST":
        return _json(shown(pad, pad.end())) if path == "/pad" else MISSING
    try:
        answer = pad.change(path, json.loads(body or b"{}"))
    except (ValueError, KeyError, TypeError) as error:
        return "400 Bad Request", "text/plain", f"{error!r}\n".encode()
    return MISSING if answer is None else _json(answer)


def _json(answer: dict[str, Any]) -> Answer:
    """Return *answer* as the body of a ``200`` answer."""
    return "200 OK", "application/json", json.dumps(answer).encode()


def app(pad: Pad) -> WSGIApplication:
    """Return the WSGI application that serves *pad*."""

    def serve(environ: WSGIEnvironment, start: StartResponse) -> list[bytes]:
        size = int(environ.get("CONTENT_LENGTH") or 0)
        status, kind, data = answered(
            pad,
            environ["REQUEST_METHOD"],
            environ["PATH_INFO"],
            environ["wsgi.input"].read(size),
        )
        length = str(len(data))
        start(status, [("Content-Type", kind), ("Content-Length", length)])
        return [data]

    return serve


def main(argv: list[str], env: Mapping[str, str]) -> int:
    """Serve a pad until interrupted, and open it in a browser.

    Args:
        argv: ``[FILE] [--port N] [--no-browser]``; port 0 picks a free
            one.
        env: Where the provenance of each input comes from.

    Returns:
        0 when interrupted.

    Raises:
        SystemExit: argparse refuses *argv*.
        OSError: *FILE* cannot be read, or the port cannot be bound.
    """
    parser = ArgumentParser(prog="python -m fpl pad")
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    ctx, tty = context(env), Tty()
    cells = seeded(args.file.read_text(), ctx, tty) if args.file else ()
    server = make_server("127.0.0.1", args.port, app(Pad(cells, ctx, tty)))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"fpl pad: {url} (Ctrl-C stops)", file=sys.stderr)
    try:
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

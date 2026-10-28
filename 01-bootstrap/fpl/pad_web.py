"""Serve a pad as one local web page: ``python -m fpl pad [FILE]``.

The page (``pad.html`` and the files :data:`PAGE` names beside this
module) is the whole interface; it needs no network beyond this
server. ``fpl-language.js`` is the playground's tokenizer, a copy of
``assets/fpl-language.js`` that a test keeps equal; the pad colours
its cells with it (``editors.js``). The site's ``/pad/`` page runs
the same files on :mod:`fpl.pad` under Pyodide instead
(``assets/fpl-pad.js``). The server holds one pad in
memory and changes it only through :mod:`fpl.pad`; it is a WSGI
application (:func:`app`) on :mod:`wsgiref`, which serves one request
at a time, so turns never overlap.

Routes, all answered with the pad as JSON (:func:`shown`: the cells,
each with its bar and turns, and the bar of the cell to come):

- ``GET /`` the page, ``GET /<file>`` for each file of :data:`PAGE`;
  ``GET /pad`` the pad.
- ``POST /run`` with ``{"index": i, "source": text}``:
  :func:`fpl.pad.run`.
- ``POST /remove`` with ``{"index": i}``: :func:`fpl.pad.removed`.
- ``POST /reset``: an empty pad.

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

from fpl.pad import Cell, bar, context, removed, replayed, run
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

    def change(self, route: str, body: Mapping[str, Any]) -> bool:
        """Carry out a ``POST`` route; False when there is none.

        Raises:
            KeyError: The body lacks a field the route needs.
            IndexError: The index names no cell.
            TypeError: A field has the wrong type.
        """
        match route:
            case "/run":
                self.cells = run(
                    self.cells,
                    body["index"],
                    str(body["source"]),
                    self.ctx,
                    self.tty,
                )
            case "/remove":
                self.cells = removed(
                    self.cells, body["index"], self.ctx, self.tty
                )
            case "/reset":
                self.cells = ()
            case _:
                return False
        return True


def shown(pad: Pad) -> dict[str, Any]:
    """Return the pad as the page reads it: the cells without logs.

    ``bar`` is the phrase bar of the cell the page offers next, as the
    REPL prints a bar before it reads.
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
        "bar": bar(pad.cells, pad.tty),
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
    if method == "POST":
        try:
            found = pad.change(path, json.loads(body or b"{}"))
        except (ValueError, KeyError, IndexError, TypeError) as error:
            return "400 Bad Request", "text/plain", f"{error!r}\n".encode()
        if not found:
            return MISSING
    elif path != "/pad":
        return MISSING
    return "200 OK", "application/json", json.dumps(shown(pad)).encode()


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

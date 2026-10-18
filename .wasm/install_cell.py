"""Shared install cell for JupyterLite notebooks (direct wheel URLs)."""

from __future__ import annotations

import json
from pathlib import Path

# Walker last so a partial failure is obvious. deps=False — list every wheel.
WHEEL_GLOBS = (
    "lark-*.whl",
    "icontract-*.whl",
    "asttokens-*.whl",
    "typing_extensions-*.whl",
    "six-*.whl",
    "comm-*.whl",
    "fpl_walker-*.whl",
)


def wheel_names(pypi: Path) -> list[str]:
    names: list[str] = []
    for pattern in WHEEL_GLOBS:
        found = sorted(pypi.glob(pattern))
        if found:
            names.append(found[-1].name)
    if not any(n.startswith("fpl_walker-") for n in names):
        raise FileNotFoundError(f"no fpl_walker wheel in {pypi}")
    return names


def install_cell(pypi: Path) -> dict:
    wheels = wheel_names(pypi)
    # Code runs in the Pyodide *worker*, so `location` is the worker
    # script URL — not the lab page. Climb to the werkbank root via
    # `/extensions/`, then fetch `/pypi/<wheel>`.
    body = (
        "from js import location\n"
        "import micropip\n"
        "\n"
        '_path = location.pathname\n'
        '_root = _path.split("/extensions/")[0] if "/extensions/" in _path else _path.rsplit("/", 1)[0]\n'
        '_pypi = location.origin + _root + "/pypi/"\n'
        "_wheels = [\n"
        + "".join(f"    {w!r},\n" for w in wheels)
        + "]\n"
        "await micropip.install([_pypi + w for w in _wheels], deps=False)\n"
        "import fpl\n"
        "fpl\n"
    )
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"tags": ["fpl-walker-install"]},
        "outputs": [],
        "source": body.splitlines(keepends=True),
    }


def write_start_here(content: Path, pypi: Path) -> None:
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# FPL workbench\n",
                    "\n",
                    "Installs the local **`fpl-walker`** wheels from `/pypi/` "
                    "(import name stays `fpl`).\n",
                    "Kernel → Restart Kernel if a cell spinner sticks after an error.\n",
                ],
            },
            install_cell(pypi),
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    'fpl.run.default.src("""\n',
                    "double : n -- n\n",
                    "    dup +\n",
                    "\n",
                    "2 double\n",
                    '""")\n',
                ],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python (Pyodide)",
                "language": "python",
                "name": "python",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    # New filename when the install strategy changes — JupyterLite keeps
    # browser-local copies of same-path notebooks in IndexedDB.
    path = content / "00-install.ipynb"
    path.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8")
    for stale_name in ("start-here.ipynb", "try.ipynb"):
        stale = content / stale_name
        if stale.exists():
            stale.unlink()
    # Also bump a copy so a stuck IndexedDB entry is easy to dodge.
    (content / "00-install-v2.ipynb").write_text(
        json.dumps(nb, indent=1) + "\n", encoding="utf-8"
    )

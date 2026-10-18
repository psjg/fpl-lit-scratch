#!/usr/bin/env python3
"""Export 01-bootstrap marimo .md modules to JupyterLite content/*.ipynb."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from install_cell import install_cell, write_start_here


def marimo_mds(bootstrap: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(bootstrap.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---") and "\nengine: marimo\n" in text.split("---", 2)[1]:
            out.append(path)
    return out


def export_one(md: Path, dest: Path, install: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uvx",
            "--from",
            "marimo",
            "--with",
            "nbformat",
            "marimo",
            "export",
            "ipynb",
            str(md),
            "-o",
            str(dest),
            "-f",
        ],
        check=True,
    )
    nb = json.loads(dest.read_text(encoding="utf-8"))
    cells = nb.get("cells", [])
    if cells and cells[0].get("metadata", {}).get("tags") == ["fpl-walker-install"]:
        cells[0] = install
    else:
        cells.insert(0, install)
    nb["cells"] = cells
    dest.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    top = Path(__file__).resolve().parents[1]
    bootstrap = top / "01-bootstrap"
    content = top / ".wasm" / "lite" / "content"
    pypi = top / ".wasm" / "lite" / "pypi"
    install = install_cell(pypi)
    write_start_here(content, pypi)

    tree = content / "01-bootstrap"
    if tree.exists():
        for p in tree.rglob("*.ipynb"):
            p.unlink()
    mds = marimo_mds(bootstrap)
    if not mds:
        print("export_modules: no marimo modules under 01-bootstrap", file=sys.stderr)
        return 1
    for md in mds:
        rel = md.relative_to(top).with_suffix(".ipynb")
        print(f"export {rel}")
        export_one(md, content / rel, install)
    print(f"export_modules: {len(mds)} notebooks → {content / '01-bootstrap'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

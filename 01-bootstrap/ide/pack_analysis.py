"""
Pack what the playground needs to run ide/analysis.py under Pyodide: the
bootstrap `fpl` package and `ide/analysis.py`, as one zip the page
unpacks (the playground's own `fpl` is the tangled walker, so the
bootstrap one cannot be installed beside it).

    PYTHONPATH=. python ide/pack_analysis.py <out.zip>
"""

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPL = HERE.parent / "fpl"


def main(out: str) -> None:
    """
    Write the zip.
    """
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(FPL.glob("*.py")) + [FPL / "grammar.lark"]:
            z.write(path, f"fpl/{path.name}")
        z.write(HERE / "__init__.py", "ide/__init__.py")
        z.write(HERE / "analysis.py", "ide/analysis.py")


main(sys.argv[1])

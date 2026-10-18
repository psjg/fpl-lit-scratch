"""Write the Quarto homepage from the checkout README.

The README stays a Marimo notebook. Quarto does not run a ``{.marimo}`` fence.
This writes ``index.qmd`` with those fences dropped, and replaces the
"Try it in Marimo" section with an iframe to the Marimo-wasm export at
``try/index.html`` (built into ``.site/try/``). ``index.qmd`` is generated.
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONT = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_FENCE = re.compile(
    r"^```python \{\.marimo([^}]*)\}\n(.*?)^```\n?",
    re.MULTILINE | re.DOTALL,
)
_TRY = re.compile(
    r"^## Try it in Marimo\n.*\Z",
    re.MULTILINE | re.DOTALL,
)

_HEADER = """---
title: FPL
execute:
  enabled: false
---
"""

_IFRAME = """\
## Try it in the browser

Edit a cell and run it. The walker runs in Pyodide via Marimo-wasm.

```{=html}
<iframe
  src="try/index.html"
  title="FPL try notebook"
  style="width:100%;height:42rem;border:1px solid #dee2e6;border-radius:0.25rem;"
  loading="lazy"
></iframe>
```
"""


def qmd(readme: str) -> str:
    """Return the Quarto page for one Marimo README."""
    body = _FRONT.sub("", readme, count=1)
    body = _FENCE.sub("", body)
    body = _TRY.sub(_IFRAME, body).strip() + "\n"
    return _HEADER + "\n" + body


def main() -> None:
    """Read the checkout ``README.md`` and write ``index.qmd`` beside it."""
    root = Path(__file__).resolve().parent.parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    (root / "index.qmd").write_text(qmd(readme), encoding="utf-8")


if __name__ == "__main__":
    main()

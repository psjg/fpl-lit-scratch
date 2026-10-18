"""Write the Quarto homepage from the checkout README.

The README stays a Marimo notebook. Quarto does not run ``{.marimo}`` fences.
This writes ``index.qmd`` with those fences dropped, and replaces the
"Try it in Marimo" section with editable ``{.python .live}`` fences that
``assets/fpl-live.js`` runs in Pyodide. ``index.qmd`` is generated.
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
include-after-body:
  - text: |
      <script type="module" src="assets/fpl-live.js"></script>
---
"""

# Browser has no checkout files; keep examples self-contained (same as .wasm/try.py).
_LIVE = """\
## Try it in the browser

Edit a block and press play. Runs in Pyodide with this site's `fpl-walker` wheel.

For a full editor, shareable `#c=` links, and graded katas, open the
[Playground](try/index.html) or [Katas](try/kata.html).

```{.python .live}
frames = "\\n".join(
    [
        ";;; ── frames ──",
        "1 | 1 2 3 +\\t; 2 3 4",
        "1 2 3 +\\t; [1‿2‿3 +]",
        "2 | 3 +\\t; 5",
        "1 | 1 2 3 [-] swap-args\\t; 1 2 3 - 1",
    ]
)
fpl.run.default.src(frames)
```

```{.python .live}
fpl.run.default.src(\"\"\"
double : n -- n
    dup +

2 double
\"\"\")
```

```{.python .live}
fpl.run.default.src(\"\"\"
4 double
\"\"\")
```
"""


def qmd(readme: str) -> str:
    """Return the Quarto page for one Marimo README."""
    body = _FRONT.sub("", readme, count=1)
    body = _FENCE.sub("", body)
    body = _TRY.sub(_LIVE, body).strip() + "\n"
    return _HEADER + "\n" + body


def main() -> None:
    """Read the checkout ``README.md`` and write ``index.qmd`` beside it."""
    root = Path(__file__).resolve().parent.parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    (root / "index.qmd").write_text(qmd(readme), encoding="utf-8")


if __name__ == "__main__":
    main()

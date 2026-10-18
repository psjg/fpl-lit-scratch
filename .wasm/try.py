# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fpl-walker",
#   "lark",
#   "icontract",
#   "marimo",
# ]
# [tool.uv.sources]
# fpl-walker = { path = "wheels/fpl_walker-0.0.0-py3-none-any.whl" }
# ///

"""Browser try-notebook for the walker. Exported with marimo html-wasm.

File paths from the checkout are not in the browser, so examples are inlined.
"""

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import fpl

    return (fpl,)


@app.cell
def _(fpl):
    frames = "\n".join(
        [
            ";;; ── frames ──",
            "1 | 1 2 3 +\t; 2 3 4",
            "1 2 3 +\t; [1‿2‿3 +]",
            "2 | 3 +\t; 5",
            "1 | 1 2 3 [-] swap-args\t; 1 2 3 - 1",
        ]
    )
    fpl.run.default.src(frames)
    return


@app.cell
def _(fpl):
    fpl.run.default.src(
        """
double : n -- n
    dup +

2 double
"""
    )
    return


@app.cell
def _(fpl):
    fpl.run.default.src(
        """
4 double
"""
    )
    return


if __name__ == "__main__":
    app.run()

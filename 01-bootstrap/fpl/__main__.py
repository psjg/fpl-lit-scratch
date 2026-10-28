"""Command line that runs one FPL file: ``python -m fpl file.fpl``.

The entry point is :func:`main`, which reads the file, calls
:func:`fpl.driver.run` and reports an :exc:`fpl.errors.FplError` as one
line.
"""

import sys
from functools import partial
from pathlib import Path

from fpl.driver import run
from fpl.errors import FplError


def main(argv: list[str]) -> int:
    """Run the file named in *argv*; print its output or its error line.

    Goals go to stderr before anything runs. The error line goes to
    stdout, where an ``.expected`` file compares it; the source line and
    the caret under the column go to stderr.

    Args:
        argv: The command-line arguments after the program name; exactly
            one is expected, the path of the ``.fpl`` file.

    Returns:
        ``0`` if the file ran, ``1`` if it raised :exc:`FplError`, ``2``
        if *argv* does not hold exactly one path.

    Raises:
        OSError: The file cannot be read, raised by
            :meth:`pathlib.Path.read_text`.
        UnicodeDecodeError: The file is not valid in the default
            encoding.
    """
    if len(argv) != 1:
        print("usage: python -m fpl <file.fpl>", file=sys.stderr)
        return 2
    source = Path(argv[0]).read_text()
    try:
        print(run(source, partial(print, file=sys.stderr)), end="")
    except FplError as error:
        print(error)
        shown = error.render(source).partition("\n")[2]
        if shown:
            print(shown, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""`fpl <file>` runs in-process. `fpl <stage>` is one filter."""

import sys

from fpl.cli import dispatch

if __name__ == "__main__":
    sys.exit(dispatch(sys.argv[1:]))

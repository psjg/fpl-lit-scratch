"""
Run the literate tree, `python/fpl`, from a test.

The tests import the seed walker, `fpl/`, and the tangled package is
also named `fpl`, so one interpreter cannot hold both. These helpers
reach the tangled tree in a child interpreter whose path holds
`python/` and nothing else: PYTHONPATH is replaced, not extended, and
PYTHONSAFEPATH keeps the working directory off it, so the seed can
never answer in its place.
"""

import os
import subprocess
import sys
from pathlib import Path

BOOTSTRAP = Path(__file__).resolve().parents[1]
PYTHON = BOOTSTRAP / "python"
TANGLE = BOOTSTRAP / "tangle.py"
TIMEOUT = 60


def env() -> dict[str, str]:
    """
    The environment of a child that sees only the tangled package.
    """
    return os.environ | {"PYTHONSAFEPATH": "1", "PYTHONPATH": str(PYTHON)}


def run(
    args: list[str], stdin: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    """
    Run `args` under that environment; stdout and stderr are captured.
    """
    return subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        env=env(),
        timeout=TIMEOUT,
        check=False,
    )


def lit(code: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    """
    Run `code` with `python -c` against the tangled package.
    """
    return run([sys.executable, "-c", code], stdin)


def fpl(*args: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    """
    Run `python -m fpl args` against the tangled package.
    """
    return run([sys.executable, "-m", "fpl", *args], stdin)

"""The ruff of the lanes, for every test that checks a tangle.

`lit check' holds each tangled Python file to ruff, which it finds
beside the interpreter or on PATH. The tests run in lit's own
environment, which holds no ruff, so the harness's environment (the
one `make venv' syncs, whose ruff the lanes run) goes first on PATH.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

HARNESS_BIN = Path(__file__).resolve().parents[3] / ".venv" / "bin"


@pytest.fixture(autouse=True)
def lanes_ruff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the harness's environment first on PATH."""
    path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{HARNESS_BIN}{os.pathsep}{path}")

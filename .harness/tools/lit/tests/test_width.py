"""The overlay's code keeps 80 columns.

assets/fpl-annot.js and assets/fpl-annot.css are read by people in a
terminal and side by side in review, so no line of either is wider than
80 characters. The lines over are named with their numbers, so the
failure says where to wrap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ASSETS = Path(__file__).parents[4] / "assets"
WIDTH = 80


@pytest.mark.parametrize("name", ["fpl-annot.js", "fpl-annot.css"])
def test_no_line_is_wider_than_80(name: str) -> None:
    """Every line of the file fits in WIDTH characters."""
    lines = (ASSETS / name).read_text(encoding="utf-8").splitlines()
    over = [n for n, line in enumerate(lines, 1) if len(line) > WIDTH]
    assert over == [], f"{name}: lines over {WIDTH} columns: {over}"

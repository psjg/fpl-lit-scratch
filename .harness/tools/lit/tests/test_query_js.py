"""The overlay's query block answers the cases facts.query answers.

assets/fpl-annot.js holds the query language between two markers, with
nothing from outside them; node runs that block on the shared cases,
tests/query_cases.json. Without node on the path the test is skipped,
and says so.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
JS = HERE.parents[3] / "assets" / "fpl-annot.js"
RUN = """
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const block = src.split("/* query: begin")[1].split("/* query: end */")[0];
const body = block.slice(block.indexOf("*/") + 2);
const QUERY = new Function(body + "; return QUERY;")();
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = cases.cases.map((c) => {
  try { return { ids: QUERY.query(cases.rows, c.q) }; }
  catch (e) { return { error: e.message }; }
});
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not on the path"
)
def test_overlay_query_answers_the_shared_cases() -> None:
    """Each case: the same ids, or the same error message."""
    cases = json.loads((HERE / "query_cases.json").read_text())["cases"]
    got = subprocess.run(
        ["node", "-e", RUN, str(JS), str(HERE / "query_cases.json")],
        capture_output=True,
        text=True,
        check=True,
    )
    for case, answer in zip(cases, json.loads(got.stdout), strict=True):
        want = (
            {"error": case["error"]}
            if "error" in case
            else {"ids": case["ids"]}
        )
        assert answer == want, case["q"]

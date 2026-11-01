"""The overlay's query block answers the cases facts.query answers.

assets/fpl-annot.js holds the query language between two markers, with
nothing from outside them; node runs that block on the shared cases,
tests/query_cases.json (a case may carry rows of its own), and on rows
built here, which facts.query must answer alike. Without node on the
path the tests are skipped, and say so.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from support import CASES, EDGELESS, PAIRS, chain_rows

from lit import facts

HERE = Path(__file__).parent
JS = HERE.parents[3] / "assets" / "fpl-annot.js"
RUN = """
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const block = src.split("/* query: begin")[1].split("/* query: end */")[0];
const body = block.slice(block.indexOf("*/") + 2);
const QUERY = new Function(body + "; return QUERY;")();
const asked = JSON.parse(fs.readFileSync(0, "utf8"));
const out = asked.map((c) => {
  try { return { ids: QUERY.query(c.rows, c.q) }; }
  catch (e) { return { error: e.message }; }
});
process.stdout.write(JSON.stringify(out));
"""

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not on the path"
)


def node(asked: list[dict[str, object]]) -> list[dict[str, object]]:
    """The overlay's answer to each ``{rows, q}``: ids or an error."""
    got = subprocess.run(
        ["node", "-e", RUN, str(JS)],
        input=json.dumps(asked),
        capture_output=True,
        text=True,
        check=True,
    )
    return cast_answers(json.loads(got.stdout))


def cast_answers(value: object) -> list[dict[str, object]]:
    """Node's printed list of answers, as the type checker sees it."""
    assert isinstance(value, list)
    return value


def python(rows: list[facts.Row], q: str) -> dict[str, object]:
    """facts.query's answer to `q`, shaped as `node` shapes one."""
    try:
        return {"ids": facts.query(rows, q)}
    except ValueError as e:
        return {"error": str(e)}


def test_overlay_query_answers_the_shared_cases() -> None:
    """Each case: the same ids, or the same error message."""
    cases = CASES["cases"]
    asked = [
        {"rows": c.get("rows", CASES["rows"]), "q": c["q"]} for c in cases
    ]
    for case, answer in zip(cases, node(asked), strict=True):
        want = (
            {"error": case["error"]}
            if "error" in case
            else {"ids": case["ids"]}
        )
        assert answer == want, case["q"]


def test_overlay_bare_terms_answer_as_one_edge() -> None:
    """``has:R`` as ``has:R+1``, and ``gives:R`` so for a relation, here
    too, on the shared rows and on rows that bear no edge."""
    asked = [
        {"rows": rows, "q": q}
        for rows in (CASES["rows"], EDGELESS)
        for bare, one in PAIRS
        for q in (bare, one)
    ]
    answers = node(asked)
    for i in range(0, len(asked), 2):
        assert answers[i] == answers[i + 1], asked[i]["q"]


def test_overlay_walks_a_long_chain_as_facts_does() -> None:
    """A chain longer than a reader's call stack: the same answer."""
    rows = chain_rows(1500)
    for q in ("layer:span has:supports+1100", "gives:supports+1400"):
        assert node([{"rows": rows, "q": q}]) == [python(rows, q)], q

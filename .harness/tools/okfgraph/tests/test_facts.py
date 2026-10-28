"""The fact layer on a fixture bundle: IRIs, quiet gates, findings.

Rows files are JSON strings written into a temporary directory, never
committed as files: the walk would load them into the real bundle.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pyoxigraph as ox
from okfgraph.bundle import BASE, build
from okfgraph.gate import Finding, findings, gates, tsv
from okfgraph.project import FACT, PREFIXES
from test_gate import CLEAN, write

XSD = PREFIXES["xsd"]
PAGE = BASE + "pass/lower.md"
LEDGER = BASE + "pass/lower.decisions.tsv"

HAND: list[dict[str, object]] = [
    {
        "id": "s-1",
        "item": "pass/lower.md",
        "start": 4,
        "end": 8,
        "text": "type",
        "labels": ["reason", "PSJ"],
        "note": "",
        "targets": ["s-2", "L-I4", "pass/evaluate.md#s-9"],
        "commit": "1977936",
        "createdAt": 1761652800000,
    },
    {"id": "f-1", "note": "a fact about a row", "targets": ["s-1"]},
]

# The generated layer in the row shape of `lit facts`: kind, labels,
# targets, codeHash, state.
BUILT: list[dict[str, object]] = [
    {
        "id": "s-2",
        "item": "pass/lower.md",
        "start": 0,
        "end": 3,
        "text": "---",
        "kind": "chunk",
        "labels": ["Lower", "root"],
        "codeHash": "0123456789abcdef",
        "targets": [],
    },
    {
        "id": "L-I4",
        "item": "pass/lower.decisions.tsv",
        "start": 0,
        "end": 5,
        "text": "tabs",
        "kind": "ledger",
        "labels": ["indent", "PSJ"],
        "note": "",
        "targets": [],
    },
    {
        "id": "s-1",
        "item": "pass/lower.md",
        "start": 4,
        "end": 8,
        "text": "type",
        "state": "vers",
        "targets": ["s-2"],
    },
]

FACTS = {
    "pass/lower.facts.json": json.dumps(HAND),
    "build/facts/lower.json": json.dumps(BUILT),
}

NOTE = "---\ntype: Note\n---\n"

# One sidecar per breakage, beside a page of its own: f/<name>.md.
BROKEN = {
    "space": '[{"id": "a b", "text": "x"}, {"id": "ok", "text": "y"}]',
    "twice": '[{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]',
    "empty": "[]",
    "object": '{"id": "a"}',
    "json": "[",
    "noid": '[{"text": "x"}]',
    "scalar": "[5]",
    "item": '[{"id": "a", "item": 5}]',
    "targets": '[{"id": "a", "targets": "b"}]',
    "target": '[{"id": "a", "text": "x", "targets": ["b c"]}]',
    "nested": '[{"id": "a", "more": {"k": 1}}]',
    "syntax": '[{"id": "a", "start": {"@id": 5}}]',
}

DETAIL = {
    "space": "2 rows, 1 nodes: an id twice, or no IRI",
    "twice": "2 rows, 1 nodes: an id twice, or no IRI",
    "empty": "no rows",
    "object": "not a JSON array",
    "json": "json: Expecting value: line 1 column 2 (char 1)",
    "noid": "row 1: no string id",
    "scalar": "row 1: no string id",
    "item": "row 1: item is no path",
    "targets": "row 1: targets is no list of ids",
    "target": "1 targets, 0 edges: a target is no IRI",
    "nested": "1 rows, 2 nodes: an id twice, or no IRI",
    "syntax": "json-ld: @id value must be a string",
}


def keys(root: Path) -> set[str]:
    found: list[Finding] = list(findings(build(root), gates()))
    return {f.key for f in found}


def objects(store: ox.Store, s: str, p: str) -> set[object]:
    found = store.quads_for_pattern(ox.NamedNode(s), ox.NamedNode(p), None)
    return {q.object for q in found}


def test_rows_name_exact_iris(tmp_path: Path) -> None:
    store = build(write(tmp_path, CLEAN | FACTS)).store
    s1 = PAGE + "#s-1"
    assert objects(store, s1, FACT + "source") == {ox.NamedNode(PAGE)}
    assert objects(store, s1, FACT + "target") == {
        ox.NamedNode(PAGE + "#s-2"),
        ox.NamedNode(LEDGER + "#L-I4"),
        ox.NamedNode(BASE + "pass/evaluate.md#s-9"),
    }
    start = ox.Literal("4", datatype=ox.NamedNode(XSD + "integer"))
    assert objects(store, s1, FACT + "start") == {start}
    assert objects(store, s1, FACT + "note") == {ox.Literal("")}
    assert objects(store, s1, FACT + "label") == {
        ox.Literal("reason"),
        ox.Literal("PSJ"),
    }
    at = "2025-10-28T12:00:00Z"  # as oxigraph normalises it
    stamp = ox.Literal(at, datatype=ox.NamedNode(XSD + "dateTime"))
    assert objects(store, s1, FACT + "createdAt") == {stamp}
    # The generated layer adds the state to the hand row's node.
    assert objects(store, s1, FACT + "state") == {ox.Literal("vers")}
    # A target and the row it names meet on one IRI: the ledger span.
    kind = objects(store, LEDGER + "#L-I4", FACT + "kind")
    assert kind == {ox.Literal("ledger")}
    assert objects(store, PAGE + "#f-1", FACT + "source") == set()


def test_facts_keep_the_gates_quiet(tmp_path: Path) -> None:
    plain = build(write(tmp_path / "plain", CLEAN))
    root = write(tmp_path / "facts", CLEAN | FACTS)
    g = build(root)
    assert keys(root) == keys(tmp_path / "plain") == set()
    added = len(g.store) - len(plain.store)
    nodes = {
        q.subject
        for q in g.store
        if q.predicate.value.startswith(FACT) and "#" in q.subject.value
    }
    assert added > 0
    assert len(nodes) == len({str(r["id"]) for r in HAND + BUILT})


def test_each_breakage_is_a_fact_load_finding(tmp_path: Path) -> None:
    files = {f"f/{name}.md": NOTE for name in BROKEN}
    files |= {f"f/{name}.facts.json": rows for name, rows in BROKEN.items()}
    files |= {
        "f/gone.facts.json": "[]",
        "build/facts/nowhere.json": "[]",
        "a/twin.md": NOTE,
        "b/twin.md": NOTE,
        "build/facts/twin.json": "[]",
    }
    root = write(tmp_path, CLEAN | files)
    nopage = "fact-load: no one page of this name"
    assert keys(root) == {
        f"f/{name}.facts.json: fact-load: {detail}"
        for name, detail in DETAIL.items()
    } | {
        f"f/gone.facts.json: {nopage}",
        f"build/facts/nowhere.json: {nopage}",
        f"build/facts/twin.json: {nopage}",
    }


def git(root: Path, *args: str) -> str:
    env = os.environ | {"GIT_CONFIG_GLOBAL": os.devnull}
    hush = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false"]
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org"]
    cmd = ["git", "-C", str(root), *hush, *who, *args]
    out = subprocess.run(cmd, check=True, capture_output=True, env=env)
    return out.stdout.decode().strip()


def test_as_of_names_the_commit(tmp_path: Path) -> None:
    root = write(tmp_path / "git", CLEAN | FACTS)
    git(root, "init", "-q")
    git(root, "add", "-f", *CLEAN, "pass/lower.facts.json")
    git(root, "commit", "-q", "-m", "fixture")
    g = build(root)
    sha = ox.Literal(git(root, "rev-parse", "HEAD"))
    assert objects(g.store, "urn:okf:build", FACT + "asOf") == {sha}
    # build/facts is in no index: it is read from disk by name.
    kind = objects(g.store, LEDGER + "#L-I4", FACT + "kind")
    assert kind == {ox.Literal("ledger")}
    assert keys(root) == set()
    bare = build(write(tmp_path / "bare", CLEAN | FACTS)).store
    assert objects(bare, "urn:okf:build", FACT + "asOf") == set()


def test_fact_stats_counts_by_kind_and_state(tmp_path: Path) -> None:
    g = build(write(tmp_path, CLEAN | FACTS))
    text = Path(__file__).parents[1] / "okfgraph/queries/fact-stats.rq"
    rows = tsv(g, text.read_text()).splitlines()
    assert rows == [
        "?kind\t?state\t?n",
        '"-"\t"-"\t1',
        '"-"\t"vers"\t1',
        '"chunk"\t"-"\t1',
        '"ledger"\t"-"\t1',
    ]

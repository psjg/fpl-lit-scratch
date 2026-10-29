"""The fact queries on a fixture page with one planted defect each.

The page ``q/two.md`` has five chunk spans (``Out`` nested in ``Lex``,
as no fence is, to see the smallest one win), two definitions, one
paragraph and a ledger of two decisions, all in a generated layer
written by hand below. Its sidecar holds three hand spans and seven
rows about rows. Rows files are JSON strings written into a temporary
directory, never committed as files: the walk would load them into the
real bundle.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyoxigraph as ox
from okfgraph.bundle import BASE, build
from okfgraph.gate import Finding, findings, gates, queries, tsv
from okfgraph.project import FACT, PREFIXES
from test_gate import CLEAN, write

PAGE = "q/two.md"


def chunk(name: str, start: int, end: int, *labels: str) -> dict[str, object]:
    return {
        "id": f"chunk:{name}:1",
        "item": PAGE,
        "start": start,
        "end": end,
        "kind": "chunk",
        "labels": [name, *labels],
        "targets": [],
    }


def span(sid: str, start: int, end: int, **more: object) -> dict[str, object]:
    return {"id": sid, "item": PAGE, "start": start, "end": end} | more


def ledger(sid: str, decision: str, reason: str) -> dict[str, object]:
    row = span(sid, 0, len(decision), text=decision, note=reason)
    return row | {"item": "q/two.decisions.tsv", "kind": "ledger"}


# The generated layer, and in it the located copies of the hand spans.
BUILT: list[dict[str, object]] = [
    chunk("Lex", 10, 60),
    chunk("Out", 30, 50),
    chunk("Root", 100, 150, "root", "skeleton"),
    chunk("Name", 160, 190, "skeleton"),
    chunk("Tail", 192, 198),
    span(
        "def:lex",
        165,
        168,
        kind="definition",
        labels=["lex"],
        targets=["chunk:Name:1"],
    ),
    span(
        "def:hidden",
        110,
        116,
        kind="definition",
        labels=["hidden"],
        targets=["chunk:Root:1"],
    ),
    span("p:1", 0, 9, kind="paragraph", text="it calls `lex' first"),
    ledger("L-A1", "indent with tabs", ""),
    ledger("L-B2", "pair brackets", "one rule"),
    {
        "id": "s-in",
        "state": "verplaatst",
        "currentStart": 35,
        "currentEnd": 40,
    },
    {"id": "s-out", "state": "vers", "currentStart": 92, "currentEnd": 96},
    {"id": "s-gone", "state": "stale"},
]

HAND: list[dict[str, object]] = [
    # Written outside every chunk, located inside Out (and Lex).
    span("s-in", 95, 99, commit="c1", labels=["claim"], note="in Out"),
    span("s-out", 92, 96, commit="c1"),  # outside every chunk
    span("s-gone", 200, 205, commit="c0"),  # its text is gone
    {"id": "r-1", "labels": ["supports"], "targets": ["s-in", "s-out"]},
    {"id": "f-2", "note": "about the relation", "targets": ["r-1"]},
    {"id": "f-gone", "note": "rests on a stale span", "targets": ["s-gone"]},
    {"id": "loop", "targets": ["loop"]},
    {"id": "old", "note": "an older reading", "targets": ["r-1"]},
    {"id": "sup", "labels": ["supersedes"], "targets": ["old"]},
    {"id": "why", "labels": ["because"], "targets": ["L-A1", "L-Z99"]},
]

FILES = CLEAN | {
    PAGE: "---\ntype: Note\n---\n",
    "q/two.facts.json": json.dumps(HAND),
    "build/facts/two.json": json.dumps(BUILT),
}


def report(root: Path, name: str) -> list[list[str]]:
    text = next(q.text for q in queries() if q.name == name)
    lines = tsv(build(root), text).splitlines()
    return [line.split("\t") for line in lines[1:]]


def iri(name: str) -> str:
    return f'"{name}"' if "#" in name else f'"{PAGE}#{name}"'


def test_a_hand_span_lies_in_its_smallest_chunk(tmp_path: Path) -> None:
    # s-in: written at 95, located at 35 in Out, which Lex holds too.
    assert report(write(tmp_path, FILES), "fact-about-chunk") == [
        [iri("s-gone"), "", "", "", iri("f-gone")],
        [iri("s-in"), iri("chunk:Out:1"), '"claim"', '"in Out"', iri("r-1")],
        [iri("s-out"), "", "", "", iri("r-1")],
    ]


def test_a_chain_runs_through_a_relation_to_its_spans(
    tmp_path: Path,
) -> None:
    # old is superseded: it starts no chain, but sup reaches through it.
    tsv_ = "q/two.decisions.tsv#"
    hops = [
        ("f-2", "r-1", "r-1"),
        ("f-2", "r-1", "s-in"),
        ("f-2", "r-1", "s-out"),
        ("f-gone", "s-gone", "s-gone"),
        ("loop", "loop", "loop"),
        ("r-1", "s-in", "s-in"),
        ("r-1", "s-out", "s-out"),
        ("sup", "old", "old"),
        ("sup", "old", "r-1"),
        ("sup", "old", "s-in"),
        ("sup", "old", "s-out"),
    ]
    assert report(write(tmp_path, FILES), "fact-chain") == [
        [iri(f), iri(via), iri(x), '"-"'] for f, via, x in hops
    ] + [
        [iri("why"), iri(tsv_ + "L-A1"), iri(tsv_ + "L-A1"), '"ledger"'],
        [iri("why"), iri(tsv_ + "L-Z99"), iri(tsv_ + "L-Z99"), '"-"'],
    ]


def test_a_row_on_a_stale_span_is_stale_by_dependency(
    tmp_path: Path,
) -> None:
    free = ["", "", "", "false"]
    assert report(write(tmp_path, FILES), "fact-still-true") == [
        [iri("f-2"), '"-"', *free],
        [iri("f-gone"), '"-"', "", "", "", "true"],
        [iri("loop"), '"-"', *free],
        [iri("old"), '"-"', *free],
        [iri("r-1"), '"-"', *free],
        [iri("s-gone"), '"stale"', '"c0"', "", "", "false"],
        [iri("s-in"), '"verplaatst"', '"c1"', "35", "40", "false"],
        [iri("s-out"), '"vers"', '"c1"', "92", "96", "false"],
        [iri("sup"), '"-"', *free],
        [iri("why"), '"-"', *free],
    ]


def test_a_decision_without_a_reason_is_reported(tmp_path: Path) -> None:
    rows = report(write(tmp_path, FILES), "fact-decision-unreasoned")
    l_a1 = iri("q/two.decisions.tsv#L-A1")
    assert rows == [[l_a1, '"indent with tabs"', iri("why")]]


def test_a_chunk_no_span_and_no_prose_touches(tmp_path: Path) -> None:
    # Lex and Out hold s-in, Name's `lex' is quoted; Root is root and
    # skeleton both, and root wins; hidden is quoted nowhere.
    assert report(write(tmp_path, FILES), "fact-chunk-untouched") == [
        [iri("chunk:Tail:1"), '"body"'],
        [iri("chunk:Root:1"), '"root"'],
    ]


def test_a_cycle_and_an_unknown_decision_are_findings(
    tmp_path: Path,
) -> None:
    g = build(write(tmp_path, FILES))
    found: list[Finding] = list(findings(g, gates()))
    assert {f.key for f in found} == {
        f"{PAGE}: fact-cycle: loop reaches itself through targets",
        f"{PAGE}: fact-cites-unknown: why cites q/two.decisions.tsv#L-Z99",
    }


def test_current_offsets_are_integers(tmp_path: Path) -> None:
    store = build(write(tmp_path, FILES)).store
    s_in = ox.NamedNode(BASE + PAGE + "#s-in")
    at = ox.NamedNode(FACT + "currentStart")
    xsd = ox.NamedNode(PREFIXES["xsd"] + "integer")
    found = {q.object for q in store.quads_for_pattern(s_in, at, None)}
    assert found == {ox.Literal("35", datatype=xsd)}

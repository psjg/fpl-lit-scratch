"""okfgraph: the repository as an OKF bundle, as RDF, queried in SPARQL.

    okfgraph graph  [--out build/okf.ttl]  write the graph as Turtle
    okfgraph check  [--baseline F]         run the gates
    okfgraph report [NAME ...]             print report queries as TSV

Every command takes ``--root DIR`` (the bundle, default ``.``),
``--base IRI`` (the node base, default the repository's page on the
forge) and ``--exclude PATH`` (repeatable: a path prefix that is not
bundle). Timings go to stderr.

``check`` prints each finding as ``path: rule: detail -- remedy``. A
baseline lists the known findings (their ``path: rule: detail`` keys,
one per line, ``#`` comments allowed): those are counted, not judged,
and a key no gate produces any more is reported as stale, so the file
can only shrink. Exit 0: no finding outside the baseline and none
stale; 1: some; 2: usage.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pyoxigraph as ox

from okfgraph.bundle import BASE, Graph, build
from okfgraph.gate import findings, gates, queries, tsv
from okfgraph.project import PREFIXES


def parser() -> argparse.ArgumentParser:
    """The command line: a command, its names, and the options."""
    ap = argparse.ArgumentParser(
        prog="okfgraph",
        description="Project an OKF bundle onto RDF and check it.",
    )
    ap.add_argument("command", choices=["graph", "check", "report"])
    ap.add_argument("names", nargs="*", help="report: the queries to print")
    ap.add_argument("--root", type=Path, default=Path())
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--out", type=Path, default=Path("build/okf.ttl"))
    ap.add_argument("--baseline", type=Path)
    return ap


def say(text: str) -> None:
    """Print ``text`` to stderr, where timings and counts go."""
    print(text, file=sys.stderr)


def graph(g: Graph, out: Path) -> int:
    """Write the graph to ``out`` as Turtle; exit 0."""
    out.parent.mkdir(parents=True, exist_ok=True)
    g.store.dump(
        str(out),
        format=ox.RdfFormat.TURTLE,
        from_graph=ox.DefaultGraph(),
        prefixes=PREFIXES,
    )
    say(f"okfgraph: {g.notes} notes, {len(g.store)} triples -> {out}")
    return 0


def check(g: Graph, baseline: Path | None) -> int:
    """Print the findings outside ``baseline``; exit 1 on any."""
    known: set[str] = set()
    if baseline:
        lines = (line.strip() for line in baseline.read_text().splitlines())
        known = {line for line in lines if line and not line.startswith("#")}
    found = list(findings(g, gates()))
    new = [f for f in found if f.key not in known]
    stale = sorted(known - {f.key for f in found})
    for f in new:
        print(f"{f.key} -- {f.remedy}")
    for key in stale:
        print(f"{baseline}: stale: {key} -- no gate finds it; delete it")
    old = len(found) - len(new)
    say(f"okfgraph check: {len(new)} new, {old} known, {len(stale)} stale")
    return 1 if new or stale else 0


def report(g: Graph, names: list[str]) -> int:
    """Print the reports ``names`` (all if none) as TSV; 2 on a typo."""
    reports = {q.name: q for q in queries() if not q.rule}
    if unknown := [n for n in names if n not in reports]:
        have = ", ".join(reports)
        say(f"okfgraph report: no {', '.join(unknown)} (have: {have})")
        return 2
    for name in names or list(reports):
        print(f"# {name}\n{tsv(g, reports[name].text)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Build the graph under ``--root``, run the command, time it."""
    a = parser().parse_args(argv)
    t0 = time.perf_counter()
    g = build(a.root.resolve(), a.base, a.exclude)
    if a.command == "graph":
        rc = graph(g, a.out)
    elif a.command == "check":
        rc = check(g, a.baseline)
    else:
        rc = report(g, a.names)
    ms = (time.perf_counter() - t0) * 1000
    say(f"okfgraph: build {g.seconds * 1000:.0f} ms, total {ms:.0f} ms")
    return rc


if __name__ == "__main__":
    sys.exit(main())

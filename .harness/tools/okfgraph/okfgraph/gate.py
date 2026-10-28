"""The queries over a projected bundle, and the gate that judges it.

Each ``queries/*.rq`` is a SPARQL SELECT. A query whose header names a
rule is a gate::

    # rule: okf-untyped
    # remedy: give the note frontmatter with a non-empty `type`
    SELECT ?path ?detail WHERE { ... }

and selects one row per finding: the bundle path, then what is wrong
there. A query without a ``# rule:`` line is a report, printed on
request and never judged. A finding prints as
``path: rule: detail -- remedy``; ``path: rule: detail`` is its key,
and a baseline file holds the keys that are known, one per line.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable

import pyoxigraph as ox

from okfgraph.bundle import Graph
from okfgraph.project import PREFIXES

HEADER = re.compile(r"^#\s*(rule|remedy):\s*(.+?)\s*$", re.M)


@dataclass(frozen=True, slots=True)
class Query:
    """One ``.rq`` file: name, text, and for a gate rule and remedy."""

    name: str
    text: str
    rule: str = ""
    remedy: str = ""

    @classmethod
    def read(cls, file: Traversable) -> Query:
        """The query in ``file``; its header gives rule and remedy."""
        text = file.read_text()
        head = dict(HEADER.findall(text))
        name = file.name.removesuffix(".rq")
        return cls(name, text, head.get("rule", ""), head.get("remedy", ""))


@dataclass(frozen=True, slots=True)
class Finding:
    """One gate row: where, which rule, what, and how to clear it."""

    path: str
    rule: str
    detail: str
    remedy: str

    @property
    def key(self) -> str:
        """``path: rule: detail``, the line a baseline holds."""
        return f"{self.path}: {self.rule}: {self.detail}"


def queries() -> list[Query]:
    """The queries shipped beside this module, in file-name order."""
    files = resources.files("okfgraph").joinpath("queries").iterdir()
    rqs = sorted((f for f in files if f.name.endswith(".rq")), key=str)
    return [Query.read(f) for f in rqs]


def gates() -> list[Query]:
    """The queries that are gates: those whose header names a rule."""
    return [q for q in queries() if q.rule]


def select(graph: Graph, text: str) -> ox.QuerySolutions:
    """Run one SELECT with the okf prefixes and ``b:`` the base."""
    prefixes = PREFIXES | {"b": graph.base}
    res = graph.store.query(text, prefixes=prefixes)
    if not isinstance(res, ox.QuerySolutions):
        raise TypeError("a query of okfgraph must be a SELECT")
    return res


def tsv(graph: Graph, text: str) -> str:
    """A report query's result as TSV, header row included."""
    out = io.BytesIO()
    select(graph, text).serialize(out, format=ox.QueryResultsFormat.TSV)
    return out.getvalue().decode()


def value(term: object) -> str:
    """A result cell as text; an unbound one as ``-``."""
    if isinstance(term, (ox.Literal, ox.NamedNode, ox.BlankNode)):
        return term.value
    return "-"


def findings(graph: Graph, rules: list[Query]) -> Iterator[Finding]:
    """Every finding of the gates in ``rules``, query then row order."""
    for q in rules:
        for row in select(graph, q.text):
            yield Finding(value(row[0]), q.rule, value(row[1]), q.remedy)

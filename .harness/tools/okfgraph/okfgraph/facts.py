"""The functional core of the fact layer: rows of facts in, quads out.

A rows file is a JSON array of rows in the shape of the annotation
program (``id``, ``item``, ``start``, ``end``, ``text``, ``labels``,
``note``, ``createdAt``, ``updatedAt``) plus ``targets`` (ids of other
rows) and ``commit``. Two kinds of file hold them: a hand-written
sidecar ``<page>.facts.json`` beside its page, and the generated layer
``build/facts/<page stem>.json``. Both are read against their page and
over ``facts.jsonld``, whose ``@vocab`` puts every key under ``fact:``.

The JSON-LD processor resolves nothing here: with the page as base, a
bare id would become a sibling path and ``item`` a doubled one
(measured on pyoxigraph 0.5.11). So every row is rewritten first, and
one rule turns both an ``id`` and each of its ``targets`` into a node,
so a target and the row it names meet on one IRI:

==============  ================================================
written         node
==============  ================================================
``s-1``         ``<base><page>#s-1``: a row of this page
``L-I4``        ``<base><page stem>.decisions.tsv#L-I4``: a row
                of the page's decisions ledger
``p.md#s-1``    ``<base>p.md#s-1``: a row of another page
==============  ================================================

``item`` is a bundle path and becomes ``<base><item>``; a timestamp in
epoch milliseconds becomes an ``xsd:dateTime``. Every other key is
kept as it is: an unknown key is a ``fact:`` literal.

pyoxigraph drops a row whose id is no IRI, and a target that is none,
without an error, and merges two rows with one id. So the loader
counts: one node per row, one ``fact:target`` triple per distinct
target of a row. A miss, an empty file or a file that does not parse
is a ``fact-load`` finding on ``<urn:okf:facts:<path>>``, never a node
with ``okf:path``, so the gates over the bundle stay quiet.
"""

from __future__ import annotations

import datetime as dt
import json
from functools import cache
from importlib import resources
from typing import cast
from urllib.parse import quote

import pyoxigraph as ox

from okfgraph.project import FACT, okf

TARGET = ox.NamedNode(FACT + "target")
STAMPS = ("createdAt", "updatedAt")

type Row = dict[str, object]


@cache
def context() -> object:
    """The ``@context`` of ``facts.jsonld``, spliced into every file."""
    text = resources.files("okfgraph").joinpath("facts.jsonld").read_text()
    return json.loads(text)["@context"]


def node(name: str, page: str, base: str) -> str:
    """The IRI of the row ``name`` as written on ``page``."""
    if "#" in name:
        path, _, frag = name.partition("#")
    elif name.startswith("L-"):
        path, frag = page.removesuffix(".md") + ".decisions.tsv", name
    else:
        path, frag = page, name
    return f"{base}{quote(path)}#{frag}"


def fault(data: object) -> str:
    """What makes decoded JSON no array of rows, or ``""``."""
    if not isinstance(data, list):
        return "not a JSON array"
    for n, r in enumerate(cast("list[object]", data), 1):
        row = cast("Row", r) if isinstance(r, dict) else {}
        targets = row.get("targets", [])
        if not isinstance(row.get("id"), str):
            return f"row {n}: no string id"
        if not isinstance(row.get("item", ""), str):
            return f"row {n}: item is no path"
        if not isinstance(targets, list) or not all(
            isinstance(t, str) for t in cast("list[object]", targets)
        ):
            return f"row {n}: targets is no list of ids"
    return ""


def doc(row: Row, page: str, base: str) -> Row:
    """One row rewritten to absolute IRIs; ``fault`` passed on it."""
    out = dict(row, id=node(cast("str", row["id"]), page, base))
    if isinstance(item := row.get("item"), str):
        out["item"] = base + quote(item)
    targets = cast("list[str]", row.get("targets", []))
    out["targets"] = [node(t, page, base) for t in targets]
    for key in STAMPS:
        if isinstance(ms := row.get(key), int):
            at = dt.datetime.fromtimestamp(ms / 1000, dt.UTC)
            out[key] = at.isoformat(timespec="milliseconds")
    return out


def rows_to_jsonld(rows: list[Row], page: str, base: str) -> bytes:
    """The rows of ``page`` as one JSON-LD document, context inline.

    pyoxigraph loads no ``@context`` by reference (it has no document
    loader), so the context is spliced in as a dict.
    """
    graph = [doc(r, page, base) for r in rows]
    return json.dumps({"@context": context(), "@graph": graph}).encode()


def count(rows: list[Row], triples: list[ox.Quad]) -> str:
    """What the parse lost of ``rows``, or ``""``."""
    nodes = len({t.subject for t in triples})
    edges = sum(1 for t in triples if t.predicate == TARGET)
    want = sum(len(set(cast("list[str]", r.get("targets", [])))) for r in rows)
    if not triples:
        return "no rows"
    if nodes != len(rows):
        return f"{len(rows)} rows, {nodes} nodes: an id twice, or no IRI"
    if edges != want:
        return f"{want} targets, {edges} edges: a target is no IRI"
    return ""


def read(text: str, page: str, base: str) -> tuple[str, list[ox.Quad]]:
    """A rows file's quads, or what is wrong with it."""
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as e:
        return f"json: {e}", []
    if err := fault(data):
        return err, []
    rows = cast("list[Row]", data)
    try:
        body = rows_to_jsonld(rows, page, base)
        parsed = ox.parse(body, format=ox.RdfFormat.JSON_LD, base_iri=base)
        quads = [ox.Quad(t.subject, t.predicate, t.object) for t in parsed]
    except SyntaxError as e:
        return f"json-ld: {e}", []
    return count(rows, quads), quads


def refuse(path: str, detail: str) -> list[ox.Quad]:
    """The ``fact-load`` finding on the rows file at ``path``."""
    n = ox.NamedNode("urn:okf:facts:" + quote(path))
    return [
        ox.Quad(n, okf("factsFile"), ox.Literal(path)),
        ox.Quad(n, okf("factsError"), ox.Literal(detail)),
    ]


def load_facts(
    store: ox.Store, path: str, text: str, page: str, base: str
) -> int:
    """Load the rows file ``path`` of ``page``; its triples, or 0.

    A file that does not load whole adds nothing but its finding.
    """
    detail, quads = read(text, page, base)
    store.extend(refuse(path, detail) if detail else quads)
    return 0 if detail else len(quads)

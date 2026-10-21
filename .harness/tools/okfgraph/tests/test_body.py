"""Typed edges in the body: inline fields and link titles.

Two forms, both plain CommonMark that renders as an ordinary link:

- an inline field, ``key:: [text](path.md)`` as a line or list item,
  or bracketed inside prose, ``[key:: [text](path.md)]``;
- a link title, ``[text](path.md "key")``.

Only a key the context declares an edge is typed; any other is listed
by the ``l-body-undeclared`` report. The fixture is written to a
temporary directory, like ``test_gate``'s.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from okfgraph.__main__ import main
from okfgraph.bundle import BASE, build
from okfgraph.gate import select, value
from test_gate import keys, md, write

BODY = "https://fpl-org.github.io/okf/body#"
OKF = "https://fpl-org.github.io/okf#"

CLEAN = {
    "index.md": '---\nokf_version: "0.2"\n---\n',
    "notes.md": "---\ntype: Note\n---\n",
    "adr/ADR-0001-walk.md": md("""
        ---
        type: ADR
        status: stable
        superseded-by: ADR-0002
        ---
        - superseded-by:: [ADR-0002](ADR-0002-cbpv.md)
        """),
    "adr/ADR-0002-cbpv.md": md("""
        ---
        type: ADR
        status: draft
        supersedes: [ADR-0001]
        related: [ADR-0003]
        affects: [../pass/title.md]
        ---
        - supersedes:: [ADR-0001](ADR-0001-walk.md)
        - related:: [ADR-0003](ADR-0003-jets.md), [Notes](../notes.md)

        Prose with [affects:: [Lower](../pass/lower.md)] inside, and
        a field in code: `supersedes:: [gone](../gone.md)`. A wrapped
        [related:: [long
        label](../pass/wrap.md)] keeps its field.

        ```
        supersedes:: [fenced](../fenced.md)
        ```

        \\[affects:: [Esc](../pass/esc.md)\\] stays a plain link, as does
        [affects:: [Half](../pass/half.md)\\] whose bracket never closes.

        [T](../pass/title.md "affects") [R](../pass/r.md "  Related ")
        [P](../pass/prose.md "The walk, superseded")
        [Q](../pass/quote.md 'He said "related"')
        [S](../pass/s.md (related))
        ![fig](../pass/fig.png "related")

        - std:: [x](../pass/lower.md)
        - Key Words:: [y](../pass/lower.md)
        - related:: none, a field without a link
        - related:: [RFC](https://example.org/rfc), [v6](http://[::1)
        """),
    "adr/ADR-0003-jets.md": "---\ntype: ADR\nstatus: draft\n---\n",
    "pass/lower.md": "---\ntype: Pass\n---\n",
    "pass/esc.md": "---\ntype: Pass\n---\n",
    "pass/wrap.md": "---\ntype: Pass\n---\n",
    "pass/half.md": "---\ntype: Pass\n---\n",
    "pass/title.md": "---\ntype: Pass\n---\n",
    "pass/r.md": "---\ntype: Pass\n---\n",
    "pass/prose.md": "---\ntype: Pass\n---\n",
    "pass/quote.md": "---\ntype: Pass\n---\n",
    "pass/s.md": "---\ntype: Pass\n---\n",
    "pass/fig.png": "",
}

BROKEN = {
    "adr/ADR-0004-mix.md": md("""
        ---
        type: ADR
        status: draft
        related: [ADR-0003]
        affects: [../pass/lower.md, ../pass/r.md]
        ---
        - supersedes:: [ADR-0003](ADR-0003-jets.md)
        - related:: [Gone](gone.md)
        - affects:: [R](../pass/r.md)
        - related:: [ghost](urn:okf:id:ghost)

        [t](missing.md "affects")
        """),
}


def triples(root: Path) -> set[tuple[str, str, str]]:
    every = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
    res = select(build(root), every)
    return {(value(r[0]), value(r[1]), value(r[2])) for r in res}


def test_clean_body_edges_pass(tmp_path: Path) -> None:
    assert keys(write(tmp_path, CLEAN)) == set()


def test_both_forms_project_typed_edges(tmp_path: Path) -> None:
    rows = triples(write(tmp_path, CLEAN))
    cbpv = BASE + "adr/ADR-0002-cbpv.md"
    typed = {
        (p.removeprefix(BODY), o)
        for s, p, o in rows
        if s == cbpv and p.startswith(BODY)
    }
    assert typed == {
        ("supersedes", BASE + "adr/ADR-0001-walk.md"),
        ("related", BASE + "adr/ADR-0003-jets.md"),
        ("related", BASE + "notes.md"),
        ("affects", BASE + "pass/lower.md"),
        ("affects", BASE + "pass/title.md"),
        ("related", BASE + "pass/r.md"),
        ("related", BASE + "pass/s.md"),
        ("related", BASE + "pass/wrap.md"),
        ("related", "https://example.org/rfc"),
    }
    walk = BASE + "adr/ADR-0001-walk.md"
    assert (walk, BODY + "superseded-by", cbpv) in rows
    # A typed body edge is a body link too: the untyped graph sees it.
    links = {o for s, p, o in rows if s == cbpv and p == OKF + "linksTo"}
    assert BASE + "pass/esc.md" in links
    assert BASE + "pass/half.md" in links
    assert not {o for _, _, o in rows if o.endswith(("gone.md", "fenced.md"))}


def test_undeclared_relations_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write(tmp_path, CLEAN)
    assert main(["report", "--root", str(root), "l-body-undeclared"]) == 0
    out = capsys.readouterr().out.splitlines()
    cbpv = '"adr/ADR-0002-cbpv.md"'
    assert out[2:-1] == [
        f'{cbpv}\t"field"\t"Key Words -> ../pass/lower.md"',
        f'{cbpv}\t"field"\t"std -> ../pass/lower.md"',
        f'{cbpv}\t"title"\t"He said \\"related\\" -> ../pass/quote.md"',
        f'{cbpv}\t"title"\t"The walk, superseded -> ../pass/prose.md"',
    ]


def test_body_gates_fire(tmp_path: Path) -> None:
    got = keys(write(tmp_path, CLEAN | BROKEN))
    mix, jets = "adr/ADR-0004-mix.md", "adr/ADR-0003-jets.md"
    assert {
        f"{mix}: edge-disagree: body supersedes, frontmatter related {jets}",
        f"{mix}: body-dangling: related {BASE}adr/gone.md",
        f"{mix}: body-dangling: affects {BASE}adr/missing.md",
        f"{mix}: body-dangling: related urn:okf:id:ghost",
        f"{mix}: edge-without-link: affects pass/lower.md",
        f"{jets}: supersede-pair: no superseded-by {mix}",
    } == got

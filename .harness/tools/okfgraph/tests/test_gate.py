"""The gates on a fixture bundle: clean passes, each breakage fires.

The test writes the fixture into a temporary directory; it is never
committed as files, so the repository's own bundle holds no broken ADR.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest
from okfgraph.__main__ import main
from okfgraph.bundle import BASE, build
from okfgraph.gate import Finding, findings, gates, select, value

OKF = "https://fpl-org.github.io/okf#"
REL = "https://fpl-org.github.io/okf/rel#"


def md(text: str) -> str:
    return dedent(text).lstrip("\n")


CLEAN = {
    "index.md": md("""
        ---
        okf_version: "0.2"
        ---
        * [ADRs](adr/README.md) - decisions
        """),
    "adr/README.md": md("""
        ---
        type: Readme
        title: ADRs
        description: The decisions.
        ---
        See [index](index.md).
        """),
    "adr/index.md": "* [ADR-0001](ADR-0001-walk.md)\n",
    "adr/ADR-0001-walk.md": md("""
        ---
        type: ADR
        title: ADR-0001 Walk
        status: stable
        date: 2026-10-01
        superseded-by: ADR-0002
        affects: [../pass/evaluate.md]
        ---
        Superseded by [ADR-0002](ADR-0002-cbpv.md).
        Affects [Evaluate](../pass/evaluate.md).
        """),
    "adr/ADR-0002-cbpv.md": md("""
        ---
        type: ADR
        title: ADR-0002 CBPV
        status: draft
        rejected: false
        supersedes: [ADR-0001]
        related: [/adr/README.md]
        affects:
          - ../pass/evaluate.md
          - "[Lower](../pass/lower.md)"
        ---
        Supersedes [ADR-0001](ADR-0001-walk.md). Affects
        [Evaluate](../pass/evaluate.md) and [Lower](../pass/lower.md).
        Related: [ADRs](/adr/README.md). See [it](https://example.org/s).

        `[no edge](ADR-0001-walk.md)`, ![a figure](fig.png), [up](#top).
        """),
    "adr/fig.png": "",
    "README.md": "---\ntype: Readme\n---\n[Home](./), [top](/), [p](pass/)\n",
    "pass/evaluate.md": "---\ntype: Pass\n---\nUp: [pass](./), [root](../).\n",
    "pass/lower.md": md("""
        ---
        type: Pass
        see: "[Evaluate](evaluate.md?view=1)"
        related: [evaluate.md#top]
        ---
        [Evaluate](evaluate.md)
        """),
    "pass/log.md": "# Log\n",
}

BROKEN = {
    "adr/ADR-0003-jets.md": md("""
        ---
        type: ADR
        status: proposed
        supersedes: [ADR-0001]
        related: [ADR-0009]
        affects: [../pass/optimize.md]
        ---
        Supersedes ADR-0001 in prose only. See [ADR-0002](ADR-0002-cbpv.md),
        [[Lower]] and [up](../../x.md).
        """),
    "pass/index.md": "---\ntitle: no\n---\n# Pass\n",
    "pass/bare.md": "No frontmatter.\n",
    "pass/open.md": "---\ntype: Pass\n",
    "pass/list.md": "---\n- a\n---\n",
    "pass/bad.md": "---\nx: : :\n---\n",
    "pass/yaml.md": "---\na: [\n---\n",
    "pass/empty.md": "---\n---\n",
    "pass/listed.md": '---\ntype: [Pass]\n"@id": x\n---\n[q](?x)\n',
    "pass/odd.md": '---\ntype: Oddity\nnested: {"@type": 5}\n---\n',
    "pass/a/same.md": md("""
        ---
        type: Note
        id: twin
        related: [twin]
        ---
        [twin](../b/same.md)
        """),
    "pass/b/same.md": "---\ntype: Note\nid: twin\n---\n",
    "pass/edges.md": md("""
        ---
        type: Note
        related: ["", "#x", "../../../out.md", "urn:x:y"]
        ---
        [y](urn:x:y)
        """),
}


def write(root: Path, files: dict[str, str]) -> Path:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    return root


def keys(root: Path, exclude: tuple[str, ...] = ()) -> set[str]:
    found: list[Finding] = list(
        findings(build(root, exclude=exclude), gates())
    )
    return {f.key for f in found}


def test_clean_fixture_passes(tmp_path: Path) -> None:
    root = write(tmp_path, CLEAN)
    assert keys(root) == set()
    assert main(["check", "--root", str(root)]) == 0


def test_broken_fixture_fires_each_rule(tmp_path: Path) -> None:
    got = keys(write(tmp_path, CLEAN | BROKEN))
    adr = "adr/ADR-0003-jets.md"
    gone = BASE + "pass/optimize.md"
    assert {
        f"adr/ADR-0001-walk.md: supersede-pair: no superseded-by {adr}",
        f"{adr}: edge-without-link: affects {gone}",
        f"{adr}: edge-without-link: supersedes adr/ADR-0001-walk.md",
        f"{adr}: edge-without-link: related urn:okf:id:ADR-0009",
        f"{adr}: dangling: related urn:okf:id:ADR-0009",
        f"{adr}: dangling: affects {gone}",
        f"{adr}: dangling: linksOutside ../x.md",
        f"{adr}: wikilink: Lower",
        f"{adr}: status-enum: status proposed",
        "pass/index.md: okf-index-frontmatter: frontmatter ok",
        "pass/bare.md: okf-untyped: frontmatter none",
        "pass/open.md: okf-untyped: frontmatter invalid: unclosed frontmatter",
        "pass/list.md: okf-untyped: frontmatter invalid: "
        "frontmatter is a list",
        "pass/bad.md: okf-untyped: frontmatter invalid: "
        "mapping values are not allowed here",
        "pass/yaml.md: okf-untyped: frontmatter invalid: "
        "while parsing a flow node",
        "pass/empty.md: okf-untyped: frontmatter ok",
        "pass/odd.md: type-unknown: type Oddity",
        "pass/listed.md: okf-untyped: frontmatter ok: ['Pass']",
        "pass/a/same.md: dangling: related urn:okf:id:twin",
        "pass/edges.md: dangling: related urn:okf:outside:../../out.md",
    } <= got
    assert not [k for k in got if "pass/odd.md: okf-untyped" in k]
    assert not [k for k in got if "%23x" in k or "urn:x:y" in k]


def test_typed_edges_and_links_project(tmp_path: Path) -> None:
    g = build(write(tmp_path, CLEAN))
    every = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
    rows = {(value(r[0]), value(r[1]), value(r[2])) for r in select(g, every)}
    cbpv, lower = BASE + "adr/ADR-0002-cbpv.md", BASE + "pass/lower.md"
    assert {
        (cbpv, REL + "supersedes", BASE + "adr/ADR-0001-walk.md"),
        (cbpv, REL + "affects", lower),
        (cbpv, REL + "related", BASE + "adr/README.md"),
        (lower, REL + "see", BASE + "pass/evaluate.md"),
        (cbpv, OKF + "embeds", BASE + "adr/fig.png"),
        (cbpv, OKF + "linksToExternal", "https://example.org/s"),
        (BASE + "adr/fig.png", OKF + "path", "adr/fig.png"),
        (lower, REL + "related", BASE + "pass/evaluate.md"),
        (BASE + "pass/evaluate.md", OKF + "linksTo", BASE + "pass"),
        (BASE + "pass/evaluate.md", OKF + "linksTo", BASE),
        (BASE + "README.md", OKF + "linksTo", BASE),
        (BASE, OKF + "path", ""),
    } <= rows
    # Four targets: the code span is no edge, nor is the #anchor.
    assert len({r for r in rows if r[:2] == (cbpv, OKF + "linksTo")}) == 4


def test_json_ld_error_is_reported(tmp_path: Path) -> None:
    root = write(tmp_path, {"n.md": '---\ntype: Note\nx: {"@id": 5}\n---\n'})
    res = select(build(root), "SELECT ?e { ?n okf:frontmatterError ?e }")
    assert [value(r[0]).startswith("json-ld:") for r in res] == [True]
    assert [k.split(": ")[:2] for k in keys(root)] == [
        ["n.md", "frontmatter-error"]
    ]


def test_git_walk_takes_the_index(tmp_path: Path) -> None:
    extra = {"scratch.md": "untracked\n", "gone.md": "x\n"}
    root = write(tmp_path, CLEAN | extra)
    git = ["git", "-C", str(root)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-f", *CLEAN, "gone.md"], check=True)
    (root / "gone.md").unlink()
    assert keys(root) == set()


def test_exclude_drops_a_subtree(tmp_path: Path) -> None:
    root = write(tmp_path, CLEAN | {"skip/broken.md": "x\n"})
    assert keys(root) != set()
    assert keys(root, exclude=("skip/",)) == set()


def test_baseline_known_new_and_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write(tmp_path / "b", CLEAN | {"bare.md": "x\n", "other.md": "y\n"})
    base = tmp_path / "baseline"
    bare = "bare.md: okf-untyped: frontmatter none"
    other = "other.md: okf-untyped: frontmatter none"
    argv = ["check", "--root", str(root), "--baseline", str(base)]
    base.write_text(f"# known\n{bare}\n\n")
    assert main(argv) == 1
    assert capsys.readouterr().out.startswith(f"{other} -- give the note")
    base.write_text(f"{bare}\n{other}\n")
    assert main(argv) == 0
    (root / "bare.md").unlink()
    assert main(argv) == 1
    assert f"stale: {bare}" in capsys.readouterr().out


def test_graph_writes_turtle(tmp_path: Path) -> None:
    root = write(tmp_path / "b", CLEAN)
    out = tmp_path / "out" / "okf.ttl"
    assert main(["graph", "--root", str(root), "--out", str(out)]) == 0
    text = out.read_text()
    assert "@prefix okf: <https://fpl-org.github.io/okf#> ." in text
    assert f"<{BASE}adr/ADR-0002-cbpv.md>" in text


def test_report_prints_tsv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write(tmp_path, CLEAN)
    assert main(["report", "--root", str(root), "c-adr"]) == 0
    out = capsys.readouterr().out
    assert '"adr/ADR-0001-walk.md"\t"superseded"\t"affects"' in out
    assert '"adr/ADR-0002-cbpv.md"\t"draft"\t"supersedes"' in out
    assert main(["report", "--root", str(root)]) == 0
    assert "# z-stats" in capsys.readouterr().out
    assert main(["report", "--root", str(root), "nope"]) == 2


def test_an_unbound_cell_reads_as_a_dash() -> None:
    assert value(None) == "-"


def test_a_query_must_select(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        select(build(write(tmp_path, CLEAN)), "ASK { ?s ?p ?o }")

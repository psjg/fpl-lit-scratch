---
type: Readme
title: okfgraph
description: The repository as one OKF bundle, projected onto an RDF graph and checked with SPARQL.
---

# okfgraph

The whole repository is one [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle (v0.2). This tool reads it and writes a symbolic graph of it, so the bundle can be
queried with SPARQL and checked by a gate, with no Obsidian plugin and no wikilinks.

    make graph       # build/okf.ttl, the bundle as Turtle
    make okf-check   # the gates; a finding prints as `path: rule: detail -- remedy`
    uv run --project .harness/tools/okfgraph okfgraph report c-adr   # one report, as TSV

## The design

OKF links are untyped (§6.1: the kind of an edge lives in the prose around it). The typed
edges live in frontmatter, which is their source of truth; each one is also written as a
relative link in the body, the projection that GitHub, Obsidian and any OKF reader can follow.
A body link can carry the edge's type itself, in one of two forms; gates check that the
frontmatter and the body agree.

- **Frontmatter** is read as JSON-LD over [context.jsonld](okfgraph/context.jsonld). A key the
  context types `"@type": "@id"` (`supersedes`, `superseded-by`, `related`, `affects`) is an
  edge; a key whose value is a quoted markdown link is an edge typed by the key; every other
  key is a literal. An edge value is a bare id (`ADR-0003`), a path (relative, or `/`-absolute
  from the bundle root) or a quoted link `"[x](y.md)"`.
- **Body links** are parsed with a CommonMark parser (markdown-it-py), so a link in a code
  span is no edge, and become untyped `okf:linksTo` edges; images become `okf:embeds`.
- **Typed body links** are body links that say which edge they are. A typed body link is
  still a body link (`okf:linksTo`, or `okf:linksToExternal` for a URL), and also a `body:<key>` edge (`…/okf/body#`) when the context
  declares `key` an edge; the two forms:

  | Form | Written | Read by |
  | --- | --- | --- |
  | inline field | `- supersedes:: [ADR-0003](ADR-0003-jets.md)`, a line or list item, several links allowed; or bracketed in prose, `[affects:: [Lower](lower.md)]` | okfgraph; it is Dataview's `key::` field syntax, which Breadcrumbs builds edges from (not checked here: whether either types a markdown-link value) |
  | link title | `[ADR-0003](ADR-0003-jets.md "supersedes")` | only okfgraph |

  The pinned Typed Graph CLI (0.6.0) reads neither form: its bundle holds no `key::` parser,
  so `make okf-check-tg` sees a typed body link as a plain link, which is all it needs.
  Both render as plain markdown: on GitHub or any CommonMark reader the field form is a line
  of text with a link in it, the title form a link with a tooltip. Write form 1: the key is
  visible in the rendered page and other tools can read it. Form 2 is invisible in the render, so
  a reader cannot see the edge's kind; it is read for prose that cannot hold a field line.
  A key is normalised as Dataview does (trimmed, lower case, inner spaces a `-`), which is
  the spelling of the frontmatter key. A field or title the context does not declare (`std::`,
  a title that is prose, `"see the old design"`) types nothing; report `l-body-undeclared`
  lists them. A field in a code span or fence is no field, an escaped `\[` opens no bracket,
  and a field value that is no link (`supersedes:: none`) is no edge. Not read as a field: a
  bold key (`**key**::`), a key not starting with an ASCII letter, a line break between `::`
  and the link; the link then stays an untyped body link.
- **The walk** is the git index: tracked and staged files. An untracked scratch file is not
  bundle; a new note is, once `git add` sees it.
- **Node IRIs** are the bundle path under a base, by default the repository's page on the
  forge (`https://github.com/fpl-org/fpl/blob/main/`, prefix `b:` in queries), so a node
  opens in a browser. The vocabulary lives under
  `https://fpl-org.github.io/okf#` (`okf:`), with `…/okf/type#` for types, `…/okf/key#` for
  literal keys, `…/okf/rel#` for frontmatter edges and `…/okf/body#` for typed body links. Both namespaces are proposals until the maintainer
  confirms them.

The [code](okfgraph/README.md) is a functional core (`project.py`: one note in, its quads out)
and a thin shell (`bundle.py` reads the disk, `gate.py` runs the queries).

## Types

`type` is required on every note but `index.md` and `log.md` (OKF §11). The vocabulary is the
set of terms `context.jsonld` maps to `cls:<Name>`; the gate `type-unknown` refuses any other.

| Type | For |
| --- | --- |
| `Readme` | a folder's page (`README.md`) |
| `AgentDoc` | instructions for agents: `AGENTS.md`, `CLAUDE.md`, `.agents/*`, `.claude/**` |
| `Note` | a note: explanation, how-to, a project note |
| `ADR` | an architecture decision record (`02-docs/02.05-project/adr/`) |
| `Spec` | a specification: the language spec, a feature's `spec.md` |
| `Design` | the language design note |
| `Roadmap` | the roadmap |
| `Pass`, `Repr`, `Composition`, `Lab` | the walker's literate notes (`01-bootstrap/`) |
| `Kata` | an exercise of the playground (`learn/kata/*/prompt.md`) |

An ADR keeps OKF's `status` (`draft`, `stable`, `deprecated`). Its decision state is derived,
not written: `rejected: true` makes it rejected, a `superseded-by` superseded, else its
`status` stands (report `c-adr`). `c-adr` and `supersede-pair` read an edge from the
frontmatter or a typed body link alike.

## Gates and reports

A query whose header holds `# rule:` and `# remedy:` is a gate; the others are reports.

| Query | Rule | Fires when |
| --- | --- | --- |
| `a-untyped` | `okf-untyped` | a note has no frontmatter, a broken one, or no `type` |
| `a2-index-frontmatter` | `okf-index-frontmatter` | an `index.md` below the root has frontmatter |
| `a3-frontmatter-error` | `frontmatter-error` | a typed note's frontmatter fails to read as JSON-LD |
| `d-supersede-pair` | `supersede-pair` | `supersedes` is not answered by `superseded-by`, or back |
| `e-edge-without-link` | `edge-without-link` | a frontmatter edge has no body link to the same target (typed or plain) |
| `f-dangling` | `dangling` | an edge or link names no file of the bundle, or climbs out of it |
| `j-edge-disagree` | `edge-disagree` | a typed body link names a target the frontmatter names under another key |
| `k-body-dangling` | `body-dangling` | a typed body link names no file of the bundle (`f-dangling` then stays quiet on that target) |
| `g-wikilink` | `wikilink` | a body holds a `[[wikilink]]` |
| `h-status-enum` | `status-enum` | `status` is not `draft`, `stable` or `deprecated` |
| `i-type-unknown` | `type-unknown` | `type` is not in the vocabulary |
| `b-into`, `c-adr`, `l-body-undeclared`, `z-stats` | report | edges into a note, ADR states and edges, undeclared body relations, counts |

`make check` runs `make okf-check` first, so every gate blocks. To bring in a new rule
before the bundle meets it, `okfgraph check --baseline FILE` tolerates the findings FILE
lists and fails on any other; a listed finding no gate produces any more fails too, so a
baseline can only shrink (the migration to full conformance started from 94 findings and
ended at none). `make okf-check` uses `.harness/tools/okfgraph/baseline` while it exists.
[Typed Graph](https://www.npmjs.com/package/@typedgraph/cli)'s `okf check` (`make okf-check-tg`,
pinned) is an independent second checker of the OKF rules; it does not read dot-folders.

The tests build a fixture bundle in a temporary directory, a clean one and one broken in
every way a gate knows, so the repository holds no broken note. The OKF index is
[index.md](index.md).

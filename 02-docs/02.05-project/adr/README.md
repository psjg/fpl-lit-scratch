---
type: Readme
title: ADRs
---

Architecture decision records: one decision per file, named `ADR-NNNN-<slug>.md`
(four digits, starting at `ADR-0001`). A number is an identity, not a position: it is
never reused or renumbered. A decision that changes is not edited away; a new ADR
replaces it. The frontmatter carries the edges (`supersedes`, `superseded-by`, `related`,
`affects`); because OKF links are untyped, each edge is also written in the body as a field
line whose value is a relative link, `- supersedes:: [ADR-0003](ADR-0003-<slug>.md)`.
GitHub renders it as a list item with a link and follows the link; okfgraph reads the key,
in Dataview's field syntax, as the edge's type. `make okf-check` refuses a frontmatter edge with
no body link to its target, a field whose key disagrees with the frontmatter for that target,
and a field whose link goes nowhere ([the forms](../../../.harness/tools/okfgraph/README.md#the-design)).

An ADR keeps OKF's `status` (`draft`, `stable`, `deprecated`); its decision state is derived,
never written: `rejected: true` makes it rejected, a `superseded-by` superseded, and otherwise
`status` stands (`stable` is accepted).

Start a new one by copying [ADR-0000-template.md](ADR-0000-template.md) to the next free number.

The OKF index is [index.md](index.md).

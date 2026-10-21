---
title: ADRs
---

Architecture decision records: one decision per file, named `ADR-NNNN-<slug>.md`
(four digits, starting at `ADR-0001`). A number is an identity, not a position: it is
never reused or renumbered. A decision that changes is not edited away; a new ADR
replaces it. The frontmatter carries the edges (`supersedes`, `superseded-by`, `related`,
`affects`); because OKF links are untyped, each edge is also written as a relative link in
the body, so Obsidian and GitHub follow it, and `make okf-check` refuses one without the other.

An ADR keeps OKF's `status` (`draft`, `stable`, `deprecated`); its decision state is derived,
never written: `rejected: true` makes it rejected, a `superseded-by` superseded, and otherwise
`status` stands (`stable` is accepted).

Start a new one by copying [ADR-0000-template.md](ADR-0000-template.md) to the next free number.

The OKF index is [index.md](index.md).

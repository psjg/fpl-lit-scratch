---
title: ADRs
---

Architecture decision records: one decision per file, named `ADR-NNNN-<slug>.md`
(four digits, starting at `ADR-0001`). A number is an identity, not a position: it is
never reused or renumbered. A decision that changes is not edited away; a new ADR
replaces it. The frontmatter carries the edges (`status`, `supersedes`, `superseded-by`, `related`); because OKF links are untyped, each edge is also written as a relative link in the body, so Obsidian and GitHub follow it.

Start a new one by copying [ADR-0000-template.md](ADR-0000-template.md) to the next free number.

The OKF index is [index.md](index.md).

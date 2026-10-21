---
type: ADR
title: "ADR-0000 <title>"
description: "<one sentence: what was decided>"
tags:
  - adr
status: draft     # OKF: draft | stable | deprecated; accepted = stable
rejected: false   # true when the decision was considered and turned down
date: YYYY-MM-DD
deciders:
  - "<name>"
supersedes: []     # e.g. [ADR-0003]
superseded-by:     # e.g. ADR-0009; set, it makes this ADR superseded
related: []        # other ADRs or notes, by id or relative path
affects: []        # passes, notes, scripts the decision touches, by relative path
drivers: []        # forces that decide it, one short phrase each
options:           # considered alternatives; exactly one has chosen: true
  - name: "<option>"
    chosen: true
    pros: []
    cons: []
  - name: "<option>"
    chosen: false
    pros: []
    cons: []
---

# ADR-0000 <title>

<!-- Each frontmatter edge is also a line here, `key:: [text](path)`: a relative link
     GitHub renders and follows, typed by its key for okfgraph (Dataview's field syntax).
     `make okf-check` holds the two together (.harness/tools/okfgraph/README.md). A key with
     several targets takes one line per target. Replace `none` with the links, e.g.:
- supersedes:: [ADR-0003](ADR-0003-<slug>.md)
- affects:: [01.02.10 Evaluate](../../../01-bootstrap/01.02-pass/01.02.10-evaluate.md)
-->

- supersedes:: none
- superseded-by:: none
- related:: none
- affects:: none

## Context

What forces the decision: the problem, the constraints, what is known.

## Decision

What we do, in one or two sentences: the chosen option and why it beats the others on the drivers.

## Consequences

What becomes easier, what becomes harder, what is now refused.

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

<!-- Every edge in the frontmatter is also a relative link here, so the untyped OKF
     graph and GitHub can follow it; the edge kind lives in prose. `make okf-check` holds
     the two together. For example:
     Supersedes: [ADR-0003](ADR-0003-<slug>.md). Affects: [01.02.10 Evaluate](../../../01-bootstrap/01.02-pass/01.02.10-evaluate.md). -->

Supersedes: none. Superseded by: none. Affects: none.

## Context

What forces the decision: the problem, the constraints, what is known.

## Decision

What we do, in one or two sentences: the chosen option and why it beats the others on the drivers.

## Consequences

What becomes easier, what becomes harder, what is now refused.

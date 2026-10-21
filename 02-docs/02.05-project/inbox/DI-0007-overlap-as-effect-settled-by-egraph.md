---
type: Note
title: "DI-0007 Overlap as an effect, settled by the e-graph"
description: "overlapping rows carry a choice effect; the e-graph discharges it where rows provably agree"
status: stable
date: 2026-10-05
related: []
---

# DI-0007 Overlap as an effect, settled by the e-graph

## His words

> we hebben koka effecten en E-graph capabilities ... poetst het misschien niet helemaal weg

## Context

Agent framing (a prior): a non-exhaustive match carries `+fail`; overlapping rows carry a choice effect (`+choose`, or the design doc's `select`); a disjoint exhaustive match is pure and total. This is the determinism lattice of the Mercury reference manual: det = none, semidet = +fail, multi = +choose, nondet = both. A handler picks the policy: first-match in a word, all answers in a space. The e-graph plays the confluence check of "Overlapping and Order-Independent Patterns" (ESOP 2014, doi 10.1007/978-3-642-54833-8_6): where it proves overlapping rows agree, the choice effect goes away; where it cannot (guards, unprovable equalities), the effect stays in the type. To read: "The Algebra of Patterns" (ECOOP 2025, arXiv 2504.18920).

## Options and outcome

Decided in direction together with DI-0008.

## Related

- related:: [ADR-0012](../adr/ADR-0012-pipeline-is-a-computation-graph.md)


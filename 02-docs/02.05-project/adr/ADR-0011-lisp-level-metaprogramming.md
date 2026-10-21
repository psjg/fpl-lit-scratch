---
type: ADR
title: "ADR-0011 FPL aims to match or surpass Lisp in metaprogramming"
description: "Metaprogramming at the level of Lisp and Kernel's $vau operatives, or beyond, is a design goal; the compiler architecture must not cap it."
tags:
  - adr
status: stable
rejected: false
date: 2026-10-21
deciders:
  - "psjg"
supersedes: []
superseded-by:
related:
  - ADR-0008-object-language-dependent-cbpv.md
  - ADR-0010-first-class-staging.md
affects:
  - ../../../02-docs/02.04-explanation/design.md
  - ../../../01-bootstrap/01.02-pass/01.02.04-expand.md
  - ../../../03-fpl/OLD/03.01-features/draft2/examples/03-operatives-thunks.fpl
drivers:
  - "programs that manipulate programs, syntax, environments and evaluation"
  - "a goal stated by the maintainer, not a feature to trade away for compiler speed"
  - "static types, dependent types, effects and separate compilation must still hold"
options:
  - name: "Lisp/Kernel level or beyond, operatives included, through first-class staging"
    chosen: true
    pros:
      - "operatives receive unevaluated syntax and an environment and decide how to evaluate"
      - "macros, passes and operatives become one family: Syntax<A> to Syntax<B>, with context or environment"
      - "syntax objects can be richer than cons lists: scopes, binding identity, types, spans, provenance"
    cons:
      - "unrestricted run-time $vau defeats static analysis and optimisation (the fexpr problem)"
      - "needs a staging discipline that keeps evaluation behaviour visible at the call site"
  - name: "Hygienic macros only (Scheme, Rust)"
    chosen: false
    pros:
      - "well understood; easy to analyse"
    cons:
      - "below the stated goal: no operatives, no first-class environments"
  - name: "No user metaprogramming beyond functions"
    chosen: false
    pros:
      - "simplest compiler"
    cons:
      - "contradicts the goal outright"
---

# ADR-0011 FPL aims to match or surpass Lisp in metaprogramming

Supersedes: none. Superseded by: none.
Related: [ADR-0008 Dependent CBPV](ADR-0008-object-language-dependent-cbpv.md),
[ADR-0010 First-class staging](ADR-0010-first-class-staging.md).
Affects: [Design](../../../02-docs/02.04-explanation/design.md),
[01.02.04 Expand](../../../01-bootstrap/01.02-pass/01.02.04-expand.md),
[draft2 operatives example](../../../03-fpl/OLD/03.01-features/draft2/examples/03-operatives-thunks.fpl).

## Context

The maintainer's ambition for FPL is to match Lisp in metaprogramming, or surpass it, naming
Kernel's `$vau` operatives. The question was whether the pass pipeline of
[ADR-0001](ADR-0001-passes-are-pipeable-filters.md) keeps that possible. It does: the
capability that matters is whether running programs can manipulate syntax, environments and
evaluation, and a pipeline of passes does not prevent that.

The cost sits elsewhere. When an operative may evaluate an operand twice, never, or in another
environment, the call site no longer tells the compiler how the arguments are evaluated. That
was the historical problem with fexprs, which Kernel answers by making operatives and
applicatives orthogonal. For a language with dependent types, effects, optimisation and
separate compilation, unrestricted run-time `$vau` everywhere is not free.

## Decision

Metaprogramming at Lisp's level or beyond, operatives included, is a design goal of FPL. The
route to it is first-class staging ([ADR-0010](ADR-0010-first-class-staging.md)): when a
transformation runs is part of what it is, so an operative is a staged computation over syntax
and an environment, not an escape from the type and effect system.

## Consequences

- Under dependent CBPV ([ADR-0008](ADR-0008-object-language-dependent-cbpv.md)) an operative
  can receive syntax and an environment as values, while the choice to evaluate is a
  computation; the thunk, force and return boundaries are where stages meet. This is the
  intended reading and is not designed in detail.
- The tree has only sketches: the draft2 example `03-operatives-thunks.fpl` gives operatives
  thunks and an environment, not syntax, and names `lift`, `reify` and `reflect` as
  stage-creating words behind a `../meta` that does not exist. `01.02.04-expand.md` is a
  signature page; the walker has no macro expander of its own.
- Binding identity in the representation (ABTs, [ADR-0003](ADR-0003-fon-is-an-fpl-subset.md))
  is what lets transformations be hygienic without guessing names.
- Open: node identity, effect and dependency discovery, and how dynamic staging avoids
  dependencies nobody can see.

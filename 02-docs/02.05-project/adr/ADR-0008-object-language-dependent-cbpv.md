---
type: ADR
title: "ADR-0008 FPL's object language is dependent call-by-push-value"
description: "The core that elaboration and lowering target is a dependent CBPV calculus, with the value/computation split as a load-bearing distinction."
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
  - ADR-0010-first-class-staging.md
  - ADR-0011-lisp-level-metaprogramming.md
affects:
  - ../../../01-bootstrap/01.03-repr/01.03.07-core.md
  - ../../../01-bootstrap/01.03-repr/01.03.06-elaborated.md
  - ../../../01-bootstrap/01.02-pass/01.02.06-elaborate.md
  - ../../../01-bootstrap/01.02-pass/01.02.07-lower.md
  - ../../../01-bootstrap/01.02-pass/01.02.08-normalize.md
  - ../../../README.md
drivers:
  - "a small formal core under a rich surface language"
  - "value/computation polarity gives staging and effects a natural place"
  - "dependent types make elaboration the bridge from surface to core"
options:
  - name: "Dependent CBPV"
    chosen: true
    pros:
      - "values and computations apart; thunk, force and return as the staging boundaries"
      - "macros and passes can be typed as computations over syntax values"
    cons:
      - "elaboration carries most of the work: implicit arguments, metavariables, polarity"
      - "nothing of it is implemented yet"
  - name: "Simply typed CBPV, the README's default object theory"
    chosen: false
    pros:
      - "simpler checker"
    cons:
      - "no types that depend on values"
  - name: "A call-by-value core"
    chosen: false
    pros:
      - "familiar"
    cons:
      - "staging and operatives need special cases in the core"
---

# ADR-0008 FPL's object language is dependent call-by-push-value

Supersedes: none. Superseded by: none.
Related: [ADR-0010 First-class staging](ADR-0010-first-class-staging.md),
[ADR-0011 Lisp-level metaprogramming](ADR-0011-lisp-level-metaprogramming.md).
Affects: [01.03.07 Core](../../../01-bootstrap/01.03-repr/01.03.07-core.md),
[01.03.06 Elaborated](../../../01-bootstrap/01.03-repr/01.03.06-elaborated.md),
[01.02.06 Elaborate](../../../01-bootstrap/01.02-pass/01.02.06-elaborate.md),
[01.02.07 Lower](../../../01-bootstrap/01.02-pass/01.02.07-lower.md),
[01.02.08 Normalize](../../../01-bootstrap/01.02-pass/01.02.08-normalize.md),
[README](../../../README.md).

## Context

The README describes FPL as two-level, with a pluggable object theory whose default is
call-by-push-value (Levy 2003). Elaboration was explained as the step that fills in implicit
semantic information (names, implicit arguments, coercions, metavariables, effects) and
translates surface syntax into a precise core. With that, the maintainer settled the object
language: it becomes dependent CBPV.

## Decision

The core that the compiler targets is dependent CBPV. Elaboration establishes the semantic
information the core needs, roughly `Γ ⊢ surface ⇝ core : A`; lowering reifies the
elaborated term into the core.

## Consequences

- The pass and representation pages state it: `01.02.07-lower.md` is `Elaborated -> Core`
  into the dependent-CBPV core, and `01.03.07-core.md` says the core later splits into
  `Core.Value` and `Core.Comp` and that this trial keeps one sort.
- `expand` does not go to Core: the chain is
  `Syntax -resolve-> Resolved -expand-> Expanded -elaborate-> Elaborated -lower-> Core`.
- The working walker (`01.02.10-evaluate.md`, `01-bootstrap/fpl/eval.py`) is a stack machine
  over untyped sorts, not CBPV. That is the bootstrap, not a contradiction; the core pages
  have no body yet, and nothing implements dependent types.
- `README.md` still names plain CBPV as the default object theory; when it is next edited it
  should say dependent CBPV.
- Which normalisation is needed for definitional equality, and which is optional
  whole-program work, is not yet said: `01.02.08-normalize.md` and `01.02.09-optimize.md`
  are separate signature pages.

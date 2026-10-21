---
type: ADR
title: "ADR-0010 Staging is first-class: the compiler is an FPL library"
description: "The compiler and the evaluator are reachable from FPL itself, as a nanopass library of ordinary values; the bootstrap only decides that Python/Lark runs them first."
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
  - ADR-0001-passes-are-pipeable-filters.md
  - ADR-0008-object-language-dependent-cbpv.md
  - ADR-0011-lisp-level-metaprogramming.md
  - ADR-0012-pipeline-is-a-computation-graph.md
affects:
  - ../../../02-docs/02.04-explanation/design.md
  - ../../../01-bootstrap/01.04-compose/01.04.01-pass.md
  - ../../../01-bootstrap/01.04-compose/01.04.04-build.md
  - ../../../01-bootstrap/python/fpl/arrow.py
drivers:
  - "metaprogramming at Lisp's level or beyond (ADR-0011)"
  - "macros, passes and operatives are one family of transformations"
  - "compile-time code is the same language as run-time code"
  - "the pipeline may be extended from the language"
options:
  - name: "The compiler and evaluator are an FPL library; staging is first-class"
    chosen: true
    pros:
      - "a program can call, compose and extend passes like any other value"
      - "function, macro, operative, elaborator, optimiser pass and code generator become variants of one staged model"
      - "nothing in the compiler is special syntax; the bootstrap is only the first host"
    cons:
      - "node identity, effect and dependency discovery, and dynamic staging without hidden dependencies are hard and open"
      - "the compiler's own interfaces become language surface that must stay stable"
  - name: "Fixed compiler phases with a macro layer on top"
    chosen: false
    pros:
      - "the conventional route; easy to optimise and analyse"
    cons:
      - "metaprogramming stops at the macro expander"
  - name: "The compiler as a separate actor reached through an API (Jai's Compiler module and message loop)"
    chosen: false
    pros:
      - "a clear boundary; build programs react to compiler events"
    cons:
      - "the compiler stays a special object the language talks to, not one built from it"
---

# ADR-0010 Staging is first-class: the compiler is an FPL library

Supersedes: none. Superseded by: none.
Related: [ADR-0001 Pipeable filters](ADR-0001-passes-are-pipeable-filters.md),
[ADR-0008 Dependent CBPV](ADR-0008-object-language-dependent-cbpv.md),
[ADR-0011 Lisp-level metaprogramming](ADR-0011-lisp-level-metaprogramming.md),
[ADR-0012 The pipeline is a computation graph](ADR-0012-pipeline-is-a-computation-graph.md).
Affects: [Design](../../../02-docs/02.04-explanation/design.md),
[01.04.01 Pass](../../../01-bootstrap/01.04-compose/01.04.01-pass.md),
[01.04.04 Build](../../../01-bootstrap/01.04-compose/01.04.04-build.md),
[python/fpl/arrow.py](../../../01-bootstrap/python/fpl/arrow.py).

## Context

The pass architecture of [ADR-0001](ADR-0001-passes-are-pipeable-filters.md) is close to
Nanopass: many small passes over explicit intermediate languages. The question was whether
it limits the metaprogramming FPL aims for ([ADR-0011](ADR-0011-lisp-level-metaprogramming.md)).
It does not, if the staging itself is made first-class: a transformation says what it maps
(syntax to syntax, syntax to core, syntax and environment to a value) and when it runs
(parse, elaboration, compile, link, load or run time). The maintainer confirmed that this is
the idea: the compiler and the evaluator should be addressable from the language itself, as
a nanopass library.

`02-docs/02.04-explanation/design.md` ("Which extension mechanism") names three answers to
"how does a user extend the language": the compiler as a library (Forth), code as data
(Lisp) and objects in a live image (Smalltalk), and warns that taking all three means three
mechanisms. This ADR takes the first for the compiler and the evaluator. Whether code as
data and the image fold into the same mechanism stays the open question of `design.md`.

## Decision

The compiler and the evaluator are an FPL library. Passes are ordinary FPL values that a
program can call, compose and extend; the pipeline itself is a value, and a program may
build its own (`parse >> expand >> elaborate >> my_pass >> lower`). The bootstrap only
decides that the Python/Lark walker runs the passes first.

## Consequences

- `Pass[A, B]` in `01-bootstrap/python/fpl/arrow.py` (`01.04.01-pass.md`) is the bootstrap
  form of a pass. There is no FPL-level pass form or pipeline value yet, and nothing in
  `03-fpl/` reflects the compiler.
- Compile-time evaluation need not go through the optimising backend: a cheap evaluator for
  meta-computation beside an optimising route for release (as Jai interprets `#run` code as
  bytecode) is compatible with this decision and not yet designed.
- A typed staging model (one `Transform<A, B, Stage, Effects>` of which function, macro,
  operative, elaborator, optimiser pass, partial evaluator and code generator are variants)
  is the proposed shape. It is not ratified
  ([02.05.06 Pipeline open questions](../notes/02.05.06-pipeline-open-questions.md)).
- The composition `>>` must stay visible as structure for a program to inspect or extend a
  pipeline; see [ADR-0012](ADR-0012-pipeline-is-a-computation-graph.md).

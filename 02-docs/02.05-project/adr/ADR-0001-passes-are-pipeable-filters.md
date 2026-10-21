---
type: ADR
title: "ADR-0001 Every pass also runs alone as a pipeable filter"
description: "Each compiler stage is a transformation between two named representations that can run on its own, read stdin and write stdout, so stages compose as a shell pipeline."
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
  - ADR-0002-fon-is-the-stage-protocol.md
  - ADR-0004-native-abts-fon-at-boundaries.md
  - ADR-0006-one-fpl-executable.md
  - ADR-0012-pipeline-is-a-computation-graph.md
affects:
  - ../../../01-bootstrap/01.04-compose/01.04.01-pass.md
  - ../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md
  - ../../../01-bootstrap/01.02-pass/README.md
  - ../../../01-bootstrap/01.05-labs/01.05.01-pipeline.md
drivers:
  - "composition: a stage should be usable like a Unix filter"
  - "each stage testable and inspectable on its own"
  - "a Python/Lark stage can be swapped for an FPL one without changing its neighbours"
options:
  - name: "Separate stages, each runnable alone and pipeable"
    chosen: true
    pros:
      - "`fpl source < f | fpl lex | fpl parse` shows every intermediate"
      - "a stage can be replaced, tested or run in another process"
      - "the same Pass value serves the in-process chain and the filter"
    cons:
      - "every representation needs a lossless serial form"
      - "a process start per stage when used as a pipe"
  - name: "One in-process frontend with internal modules"
    chosen: false
    pros:
      - "no serialisation work"
      - "simplest bootstrap"
    cons:
      - "intermediates are invisible from outside"
      - "stages couple through shared Python objects"
  - name: "Library only, no per-stage entry point"
    chosen: false
    pros:
      - "passes still compose with >>"
    cons:
      - "no shell workflow; inspection needs a notebook or a debugger"
---

# ADR-0001 Every pass also runs alone as a pipeable filter

Supersedes: none. Superseded by: none.
Related: [ADR-0002 FON is the stage protocol](ADR-0002-fon-is-the-stage-protocol.md),
[ADR-0004 Native ABTs, FON at boundaries](ADR-0004-native-abts-fon-at-boundaries.md),
[ADR-0006 One fpl executable](ADR-0006-one-fpl-executable.md),
[ADR-0012 The pipeline is a computation graph](ADR-0012-pipeline-is-a-computation-graph.md).
Affects: [01.04.01 Pass](../../../01-bootstrap/01.04-compose/01.04.01-pass.md),
[01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md),
[01.02 Passes](../../../01-bootstrap/01.02-pass/README.md),
[01.05.01 Pipeline lab](../../../01-bootstrap/01.05-labs/01.05.01-pipeline.md).

## Context

The maintainer wants the stages of the compiler and of the bootstrap walker to be separate
programs that can be piped: composition in the Unix sense. The walker is a Python/Lark
program, so the question was whether Python and Lark allow it. They do: Lark is a library,
and where the process boundaries go is the author's choice. The one condition is that each
intermediate representation can be written out and read back, not passed as a Python object.

Feeding Lark a token stream produced elsewhere is a less common route than letting Lark lex
and parse in one go. The walker took that route anyway: `lex` and `parse` are separate, and
`parse` replays the lexed tokens (`01.02.02-parse.md`).

## Decision

Every compiler stage is a transformation `Pass[A, B]` between two named representations
(the `01.03-repr` pages). It composes in-process with `>>`, and it can also run alone as a
filter that reads its input on stdin and writes its output on stdout, with diagnostics on
stderr. The representations lead; a pass is named after the arrow between two of them.

## Consequences

- The pass pages under `01-bootstrap/01.02-pass/` and the representation pages under
  `01-bootstrap/01.03-repr/` are the unit of the design. The arrows (`Source -lex-> Tokens`,
  `Elaborated -lower-> Core`) are stated on the pass pages.
- A `>>` chain orders passes; it is not the semantics (`01.04.04-build.md`). Resolve, expand
  and elaborate may interleave later without breaking this decision.
- The shell route is a way to run the same passes, not a second implementation. Today, after
  `parse`, the filters send rendered source text and re-parse it, and the pipeline lab shows
  only the in-process half.
- Each pass is meant to be a pure transformation; purity is not stated as a rule or checked.
- How the shell route relates to other ways of running the passes is
  [ADR-0012](ADR-0012-pipeline-is-a-computation-graph.md) (draft): it would become one
  interpreter of the composition among several.

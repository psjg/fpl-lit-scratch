---
type: ADR
title: "ADR-0009 Keep information as long as possible; strip only in an optimising release build"
description: "Passes carry source, syntax, names, types, provenance and comments forward by default; only an explicit optimising build (an -O1..-O4 style level) may shake them out at the end."
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
  - ADR-0004-native-abts-fon-at-boundaries.md
affects:
  - ../../../01-bootstrap/01.04-compose/01.04.04-build.md
  - ../../../01-bootstrap/01.02-pass/01.02.09-optimize.md
  - ../../../01-bootstrap/01.02-pass/01.02.11-codegen.md
  - ../../../01-bootstrap/01.03-repr/01.03.07-core.md
drivers:
  - "the REPL, an image, tooling and debugging need the information"
  - "reconstructing debug information after the fact is worse than keeping it"
  - "a release build may still want a small executable"
options:
  - name: "Keep everything by default; an explicit optimising level strips at the end"
    chosen: true
    pros:
      - "one rich representation serves REPL, image, tooling and debugging"
      - "stripping is a late, separate pass"
    cons:
      - "larger intermediates; every pass must carry what it does not use"
  - name: "Drop information as soon as a pass no longer needs it"
    chosen: false
    pros:
      - "small, simple intermediates"
    cons:
      - "debug data must be rebuilt from side tables, often lossily"
  - name: "Separate debug and release pipelines"
    chosen: false
    pros:
      - "each tuned for its use"
    cons:
      - "two pipelines that drift apart"
---

# ADR-0009 Keep information as long as possible; strip only in an optimising release build

Supersedes: none. Superseded by: none.
Related: [ADR-0004 Native ABTs, FON at boundaries](ADR-0004-native-abts-fon-at-boundaries.md).
Affects: [01.04.04 Build](../../../01-bootstrap/01.04-compose/01.04.04-build.md),
[01.02.09 Optimize](../../../01-bootstrap/01.02-pass/01.02.09-optimize.md),
[01.02.11 Codegen](../../../01-bootstrap/01.02-pass/01.02.11-codegen.md),
[01.03.07 Core](../../../01-bootstrap/01.03-repr/01.03.07-core.md).

## Context

The maintainer wants to hold as much state as possible for as long as possible. An optimising
release build may shake it all out at the end, when the user asks for that and explicitly does
not want a debug build: a pass in the manner of `-O1` to `-O4`.

## Decision

The default build keeps the information the passes produce. Only an explicit optimising
release level strips it, as late passes before the executable.

## Consequences

- Passes should be information-monotone where they can: a lowered node keeps its source
  origin, surface origin, comments and docs, type, effect, symbol identity, and expansion and
  optimisation provenance. That list is the reading of this decision, not yet a checked rule.
- Core nodes carry a `Span` today (`01-bootstrap/python/fpl/ast_core.py`, with
  `compare=False`), and comments are kept by `01-bootstrap/fpl/trivia.py`. There are no
  stable node identities, no expansion or optimisation provenance, and no source-to-core
  mapping tables.
- There is no build flag: no `--debug`, no `-O` level, no strip pass. `optimize` and `codegen`
  are signature pages.

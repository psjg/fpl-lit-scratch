---
type: ADR
title: "ADR-0005 The boundary operation is fonify, its inverse defonify"
description: "The trip from a native object to FON bytes is called fonify and the way back defonify; the stdio wrapper reads defonify >> stage >> fonify."
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
  - ../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md
  - ../../../01-bootstrap/01.01-boundary/README.md
drivers:
  - "the formula at the boundary should read plainly"
  - "one name for the whole trip to the wire"
options:
  - name: "fonify / defonify"
    chosen: true
    pros:
      - "reads as 'make this into FON'"
      - "defonify >> stage >> fonify reads better than fon.decode >> stage >> fon.encode"
    cons:
      - "sounds like phon- (sound, phone), and telecom products named Fonify exist"
  - name: "fon.encode / fon.decode"
    chosen: false
    pros:
      - "conventional codec vocabulary"
    cons:
      - "encode and decode are also the words for bytes-to-text decoding"
  - name: "to_fon / from_fon for object to FON value, encode / decode for FON value to bytes"
    chosen: false
    pros:
      - "names the materialisation and transport levels apart"
    cons:
      - "four names where the seed needs two"
  - name: "fonify / unfonify"
    chosen: false
    pros:
      - "obvious inverse"
    cons:
      - "reads less well than defonify"
---

# ADR-0005 The boundary operation is fonify, its inverse defonify

Supersedes: none. Superseded by: none.
Related: [ADR-0004 Native ABTs, FON at boundaries](ADR-0004-native-abts-fon-at-boundaries.md).
Affects: [01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md),
[01.01 Boundary](../../../01-bootstrap/01.01-boundary/README.md).

## Context

[ADR-0004](ADR-0004-native-abts-fon-at-boundaries.md) puts a FON decode and encode around a
stage at a process boundary. The maintainer proposed calling the operation `fonify` and asked
whether the name carries a double meaning. It does (phon-, and a few telecom products), and
the telecom sense fits: fonify makes a value fit to go over the wire.

## Decision

`fonify` is the whole trip from a native object to FON bytes on the wire; `defonify` is its
inverse. The stdio wrapper is `defonify >> stage >> fonify`.

## Consequences

- The tree uses the names: `fonify_text`, `defonify_text`, `fonify_tokens` and
  `defonify_tokens` in `01.01.03-pipe.md`, whose description reads
  "defonify >> stage >> fonify, except at the two ends".
- The finer split (`to_fon` / `from_fon` for object to FON value, `encode` / `decode` for
  FON value to bytes) is not made. The FON module exposes `read` and `write` for text. If the
  materialisation and transport levels get their own code, they can take those names without
  changing this decision.
- `stdio = Pass("stdio", lambda stage: stage)` in the pipe page is an identity placeholder;
  the boundary logic lives in the stage-aware `_run`. The formula is not yet one generic,
  type-driven wrapper.

---
type: ADR
title: "ADR-0002 FON is the protocol between stages"
description: "A stage run as a filter reads FON on stdin and writes FON on stdout; the only exceptions are the two ends, source and render."
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
  - ADR-0003-fon-is-an-fpl-subset.md
  - ADR-0004-native-abts-fon-at-boundaries.md
affects:
  - ../../../01-bootstrap/01.01-boundary/01.01.02-fon.md
  - ../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md
  - ../../../01-bootstrap/01.01-boundary/01.01.01-source.md
  - ../../../01-bootstrap/01.01-boundary/01.01.04-render.md
drivers:
  - "the pipe needs one stable, canonical representation"
  - "Python stages and later FPL stages must speak the same protocol"
  - "canonical bytes give content addressing and caching"
options:
  - name: "FON, FPL's own object notation"
    chosen: true
    pros:
      - "the protocol is part of the language, not a foreign format"
      - "canonical FON gives one byte form per object, so a hash is an identity"
      - "a stage written in FPL needs no foreign codec"
    cons:
      - "a FON codec is needed for every representation"
  - name: "JSON or S-expressions"
    chosen: false
    pros:
      - "off the shelf; every language reads them"
    cons:
      - "a second notation beside FPL's own"
      - "no canonical form or content references of FPL's kind"
  - name: "Python objects (pickle)"
    chosen: false
    pros:
      - "no codec work"
    cons:
      - "ties the protocol to Python; an FPL stage could not read it"
---

# ADR-0002 FON is the protocol between stages

Supersedes: none. Superseded by: none.
Related: [ADR-0001 Pipeable filters](ADR-0001-passes-are-pipeable-filters.md),
[ADR-0003 FON is an FPL subset](ADR-0003-fon-is-an-fpl-subset.md),
[ADR-0004 Native ABTs, FON at boundaries](ADR-0004-native-abts-fon-at-boundaries.md).
Affects: [01.01.02 FON](../../../01-bootstrap/01.01-boundary/01.01.02-fon.md),
[01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md),
[01.01.01 Source](../../../01-bootstrap/01.01-boundary/01.01.01-source.md),
[01.01.04 Render](../../../01-bootstrap/01.01-boundary/01.01.04-render.md).

## Context

Once stages are pipeable ([ADR-0001](ADR-0001-passes-are-pipeable-filters.md)), the design
question is what travels over stdin and stdout. A stable, canonical representation there
turns the stages into real Unix programs rather than modules that happen to share a process.
The maintainer proposed FON, FPL Object Notation.

## Decision

FON is the protocol between stages. A stage run as a filter reads `FON<A>` on stdin and
writes `FON<B>` on stdout. The two ends are adapters, not compiler passes: `source` turns raw
bytes into `FON<Source>`, `render` turns a FON value into text for a person.

FON is the serialisation language; the representations are the schemas carried in it
(`FON<Tokens>`, `FON<Syntax>`, `FON<Core>`). FON is not itself a compiler IR.

## Consequences

- The tree holds this for `source`, `lex` and `render`: `fonify_tokens` and `defonify_tokens`
  in `01.01.03-pipe.md` round-trip a token stream. After `parse` the filters still send a
  FON string of rendered source, not `FON<Syntax>`.
- Canonical `written()` forms and `&multihash` content references exist in the FON codec.
  The chain canonical FON, bytes, hash, identity is not yet stated as a rule.
- Schema-over-FON exists in fact (the token document is a FON `Dict`), but no page states
  it as a principle.
- FON never evaluates, resolves names or type-checks; `01.01.02-fon.md` states this and
  `01-bootstrap/tests/test_fon.py` checks it.

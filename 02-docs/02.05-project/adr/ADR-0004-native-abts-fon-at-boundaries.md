---
type: ADR
title: "ADR-0004 Native ABTs within an address space, FON only across a boundary"
description: "Passes composed in one process hand native ABTs to each other; a representation is materialised as FON only where it crosses a process or other serialisation boundary."
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
  - ADR-0002-fon-is-the-stage-protocol.md
  - ADR-0003-fon-is-an-fpl-subset.md
  - ADR-0005-fonify-defonify.md
affects:
  - ../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md
  - ../../../01-bootstrap/01.04-compose/01.04.02-run.md
  - ../../../01-bootstrap/01.04-compose/01.04.01-pass.md
  - ../../../01-bootstrap/index.md
drivers:
  - "in-process composition must not pay a serialisation tax"
  - "processes must not share a runtime ABI"
  - "a pass should know nothing of FON"
  - "no infinite regress: the codec must not need the compiler"
options:
  - name: "Native ABTs in-process; FON only at a serialisation boundary"
    chosen: true
    pros:
      - "fast in-process chains: ABT to ABT with identities, types and provenance intact"
      - "Unix composition without a shared ABI"
      - "a pass is a plain A to B function; the wrapper does the FON work"
    cons:
      - "two ways to run the same chain, which tests must keep equal"
  - name: "FON between every pair of stages, also in-process"
    chosen: false
    pros:
      - "one path; every boundary always exercised"
    cons:
      - "encode and decode cost at every step"
      - "in-memory identity and caches lost at each step"
  - name: "Native objects across processes too (pickle, shared memory)"
    chosen: false
    pros:
      - "no codec per representation"
    cons:
      - "ties processes to one runtime and one language"
---

# ADR-0004 Native ABTs within an address space, FON only across a boundary

Supersedes: none. Superseded by: none.
Related: [ADR-0001 Pipeable filters](ADR-0001-passes-are-pipeable-filters.md),
[ADR-0002 FON is the stage protocol](ADR-0002-fon-is-the-stage-protocol.md),
[ADR-0003 FON is an FPL subset](ADR-0003-fon-is-an-fpl-subset.md),
[ADR-0005 fonify and defonify](ADR-0005-fonify-defonify.md).
Affects: [01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md),
[01.04.02 Run](../../../01-bootstrap/01.04-compose/01.04.02-run.md),
[01.04.01 Pass](../../../01-bootstrap/01.04-compose/01.04.01-pass.md),
[01-bootstrap index](../../../01-bootstrap/index.md).

## Context

An earlier proposal put FON between all stages. The maintainer asked for something else:
when passes are composed within one address space they should just hand ABTs to each other,
and only when they run as a Unix pipeline should the representation be materialised as FON
over the pipe. That replaced the FON-everywhere proposal.

The maintainer then asked whether translating to FON between stages is an infinite regress:
FON is FPL, so reading it seems to need the FPL compiler. It is not, because the codec sits
below the compiler pipeline, in the transport layer, and bottoms out in bytes
(`write(2)`, `read(2)`). Reading FON needs only a small decoder for the FON subset, not the
compiler, as reading JSON needs no JavaScript engine. The real circle is the bootstrap one
(compiler in FPL, FON codec in FPL, compiler uses FON), broken in the usual way by a seed:
the Python/Lark walker.

## Decision

Program representations stay native objects within an address space and are materialised as
FON only when they cross a serialisation boundary: a process, a machine, persistent storage,
a socket, a cache. At the process boundary a stage runs as

    defonify >> stage >> fonify

except at the two ends (`source` only fonifies, `render` only defonifies). A pass knows
nothing of FON. `>>` is the composition operator in both places.

## Consequences

- `fpl run <file>` runs `lex >> parse >> desugar >> elaborate >> evaluate` in one process with
  no FON in between (`01.04.02-run.md`; "ABTs stay in this process" in
  `01-bootstrap/python/fpl/__main__.py`).
- Each filter needs a lossless FON codec for its input and output representation. Only text
  and tokens have one. After `parse` the tree contradicts this decision: the filters render
  the program back to source text and the next stage re-lexes and re-parses it
  ([TD-0006](../techdebt/TD-0006-pipe-reparses-rendered-text.md)).
- The two routes must give the same result. A test that compares the in-process chain with
  the piped one, per boundary, would check it; none exists yet
  ([TD-0007](../techdebt/TD-0007-pipeline-lab-missing-fon-cell.md)).
- The three levels (semantic passes; materialisation, object to FON value; transport, FON
  value to bytes) and the small materialisation kernel that ends the regress are not written
  down as such. The FON module's `read` and `write` beside the pipe's `fonify_*` and
  `defonify_*` have that shape without the names.

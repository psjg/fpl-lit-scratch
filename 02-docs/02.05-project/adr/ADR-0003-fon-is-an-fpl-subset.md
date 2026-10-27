---
type: ADR
title: "ADR-0003 FON is an FPL subset that materialises native ABTs"
description: "FPL's native program representation is an abstract binding tree; FON is the restricted subset of FPL that writes those objects out for the rest of the world, as an ASCII postfix stream."
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
  - ADR-0010-first-class-staging.md
affects:
  - ../../../01-bootstrap/01.01-boundary/01.01.02-fon.md
  - ../../../01-bootstrap/index.md
  - ../../../README.md
drivers:
  - "FPL terms are ABTs natively; text is only needed to talk to the outside"
  - "a FON reader must not need the compiler (no regress, see ADR-0004)"
  - "FON should be easy to push over a wire"
options:
  - name: "FON is a restricted, inert subset of FPL"
    chosen: true
    pros:
      - "one notation: every FON document is FPL text"
      - "postfix reads left to right on a stack: a small decoder, easy in C or FPL"
      - "the same objects can be read by FPL code without a foreign parser"
    cons:
      - "the subset must be specified and kept inert"
  - name: "FON as a format separate from FPL syntax"
    chosen: false
    pros:
      - "can be tuned for the wire alone"
    cons:
      - "two notations to keep in step"
  - name: "FON as the compiler's internal representation"
    chosen: false
    pros:
      - "no translation step"
    cons:
      - "confuses the wire form with the object; binding structure would live in text"
---

# ADR-0003 FON is an FPL subset that materialises native ABTs

- supersedes:: none
- superseded-by:: none
- related:: [ADR-0002 FON is the stage protocol](ADR-0002-fon-is-the-stage-protocol.md)
- related:: [ADR-0004 Native ABTs, FON at boundaries](ADR-0004-native-abts-fon-at-boundaries.md)
- related:: [ADR-0010 First-class staging](ADR-0010-first-class-staging.md)
- affects:: [01.01.02 FON](../../../01-bootstrap/01.01-boundary/01.01.02-fon.md)
- affects:: [01-bootstrap index](../../../01-bootstrap/index.md)
- affects:: [README](../../../README.md)

## Context

The maintainer's statement: FON is a subset of FPL that is easier to push over the wire.
FPL should have an abstract binding tree (ABT) natively; a textual materialisation is needed
only to deal with the rest of the world. Because FON is a subset of FPL, it is also a
pseudo-binary, ASCII, postfix format.

The README already says terms are ABTs, and `01-bootstrap/index.md` says that inside one
process the values are ABTs and FON is only the wire.

## Decision

FPL's native program representation is the ABT. FON is a restricted, inert subset of FPL
that writes FPL objects out and reads them back. It is a materialisation, not the
representation itself. Like FPL, it is postfix: a stream of objects and constructors that
decodes left to right on a stack (`1 2 Add/2`, the constructor naming its arity), lexically ASCII.

## Consequences

- Four layers stay apart: the ABT (in-memory program), the FPL object model (values of the
  language), FON (the textual materialisation), and a possible later packed or binary FON
  carrying the same abstract value. Only the first split is written down today, in
  `01-bootstrap/index.md`.
- The seed FON in `01.01.02-fon.md` is the postfix stream this decision describes: the reader
  and writer in `01-bootstrap/python/fpl/fon/__init__.py` decode tokens left to right on a
  stack, a literal pushes a value and a constructor `name/arity` pops its fields and pushes
  what it builds. There is no braced FON; a brace or bracket outside a string is refused
  ([TD-0009](../techdebt/TD-0009-seed-fon-braced-not-postfix.md), deprecated: resolved).
- Binding-aware ABTs (hygiene, alpha-equivalence and substitution in the representation) are
  the intent; the walker's AST in `01-bootstrap/python/fpl/ast_surface.py` carries spans but
  no binding structure yet.

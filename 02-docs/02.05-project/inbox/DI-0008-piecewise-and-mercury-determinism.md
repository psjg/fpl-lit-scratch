---
type: Note
title: "DI-0008 `piecewise` and Mercury's determinism semantics"
description: "correctness by construction by default; pull Mercury determinism into FPL; `piecewise` for the disjoint form"
status: stable
date: 2026-10-05
related: []
---

# DI-0008 `piecewise` and Mercury's determinism semantics

## His words

> Correctness by construction by default (die wel ergonomisch getracked geloosened kan worden)

## Context

Decided in direction. Further words: "laten we die mercury semantiek FPL intrekken!!! meer cutting edge research unified"; effect names floated: `+multiple` (or `+multi`), `+fail`, `+nondet`. `piecewise` is the word for the disjoint exhaustive form ("drukt ook precies de semantiek uit"); it is total and pure by construction while `match` carries its effects. Agda's case split is "correct maar lelijk"; the guarded if...fi: "blijkt die Edsger toch nog steeds altijd gewoon gelijk te hebben". A research workflow on the sources was run.

## Options and outcome

Decided: `piecewise` exists; `match` carries effects. Not yet in design.md (spec-guarded).

## Related

- related:: [design](../../02.04-explanation/design.md)


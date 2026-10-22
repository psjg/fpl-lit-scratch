---
type: Note
title: "DI-0009 piecewise as the default for top-level overloading"
description: "must overload clauses be disjoint, or does \"most specific wins\" stay as a tracked loosening"
status: draft
date: 2026-10-05
related: []
---

# DI-0009 piecewise as the default for top-level overloading

## His words

> misschien veel te moeilijk nu

## Context

Several definitions of one word with patterns in their heads (the dispatch of feature 09). Dispatch already refuses an ambiguous call and crossing clauses whose meet is not a clause (Julia's ambiguity rule), and orders by specificity not by text, so moving clauses changes nothing. Mercury's committed choice (cc_multi) as the reading of "first match" is a handler, not a separate semantics: "sick en het onderzoeken waard". He liked the Julia parallel.

## Options and outcome

Left as a future item. Open: tracked loosening versus mandatory disjointness.

## Related

- related:: [spec](../../02.03-reference/spec.md)


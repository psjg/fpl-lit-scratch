---
type: Note
title: The seed FON is braced, not the postfix stream FON is decided to be
description: "FON is decided to be an ASCII postfix subset of FPL, decoded left to right on a stack; the seed FON is a braced data profile read by a Lark LALR grammar, and no page says which of the two is normative."
tags: [bootstrap, fon]
status: draft
date: 2026-10-21
found-in: [01-bootstrap/01.01-boundary/01.01.02-fon.md, 01-bootstrap/python/fpl/fon/__init__.py]
related:
  - ../adr/ADR-0003-fon-is-an-fpl-subset.md
closed-by:
---

Contradicts [ADR-0003](../adr/ADR-0003-fon-is-an-fpl-subset.md): FON is a subset of FPL and
therefore postfix.

## Symptom

The token document `fpl lex` writes is nested brackets:
`{ 「source」 … 「tokens」 ⟨ ( 「TOKEN」 「1」 0 1 ) … ⟩ … }`. A postfix form of the same
value would end each constructor after its fields (`1 2 Add`).

## Cause

`01.01.02-fon.md` is "the seed's FON reader and writer": an inert, braced profile with
`⟨⟩ {} () []` and a Lark LALR grammar. It was written before the postfix decision, and the
page does not say whether the braced form is only the seed's.

## Remedy

Either state on `01.01.02-fon.md` that the braced form is the seed FON and not the eventual
one, so it does not become normative by use, or write the postfix FON and move the codecs to
it. Which one is the maintainer's call; until then new codecs
([TD-0006](TD-0006-pipe-reparses-rendered-text.md)) carry the same risk.

## How to reproduce

Run `fpl source` and then `fpl lex` on any file and read the output; or read the grammar in
`01-bootstrap/01.01-boundary/01.01.02-fon.md`.

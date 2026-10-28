---
type: Note
title: "DI-0063 Escapes in FPL strings: only the code-point escape?"
description: "the pre-lexer has one code-point escape and no short escapes; whether FPL strings get tab and newline escapes or keep raw strings is a design decision"
status: draft
date: 2026-10-28
related: []
---

# DI-0063 Escapes in FPL strings: only \u{XXXX}?

## His words

> bedoel je nou dat we geen '\t' en '\n' in FPL hebben? dat is toch een beetje whack?

## Context

A note on web F, line 4406, in the annotation round of 2026-10-28. The pre-lexer's escape design
has no recorded reason anywhere: the bootstrap decodes `\u{XXXX}` and nothing shorter, and the
page offers raw strings in `「 」` for the rest. The question is whether FPL strings get the
usual short escapes (`\t`, `\n`, `\\`, `\"`) or stay with one code-point escape plus raw
strings. A decision for the maintainer, not for the literate rewrite of the lexer, which
describes what the bootstrap does.

## Options and outcome

Open. A design decision, not taken.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)

## Decision 2026-10-28

The maintainer chose to add short escapes (`\n`, `\t`, `\\` and a fixed small set) beside
`\u{XXXX}`. The pre-lexer and the string reader change accordingly. The spec change itself is
his and still to come; this item stays open until it lands.

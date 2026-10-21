---
type: Note
title: "DI-0032 Lossless FON of Syntax, and seed FON versus wire FON"
description: "next milestone: defonify(fpl source | fpl lex | fpl parse) == parse(lex(source)) at every boundary"
status: draft
date: 2026-10-19
related: []
---

# DI-0032 Lossless FON of Syntax, and seed FON versus wire FON

## His words

> (agent audit, no quote)

## Context

An audit of the literate draft found that the stdio pass is the identity and later passes pass rendered FON text that downstream re-lexes. Next milestone (a prior): lossless FON of Syntax (later Core), plus a second cell asserting native equals piped; mark the current braced FON as seed FON, not the postfix wire format he described. Pipeline terminology was proposed: decoder, lexer, parser, elaborator, evaluator (avoid scanner, reader, tokenizer, frontend, "interpreter" as a phase).

## Options and outcome

Open; belongs to the literate-draft design, not the bootstrap. Ask before touching either.

## Related

- related:: [02.05.06 pipeline open questions](../notes/02.05.06-pipeline-open-questions.md)
- related:: [ADR-0004](../adr/ADR-0004-native-abts-fon-at-boundaries.md)


---
type: Note
title: "DI-0061 The nanopass composition operator used fractally inside a pass"
description: "the operator that composes passes in the pipeline may also compose the stages inside one pass, so that one operator holds at every level"
status: draft
date: 2026-10-28
related: []
---

# DI-0061 The nanopass composition operator used fractally inside a pass

## His words

> Als dit zo is dan kunnen we de nanopass compositie operator `>>` [uit het pijplijnontwerp] toch ook op dit niveau fractaal gebruiken... niet?

## Context

A note in the annotation round of 2026-10-28, on the sentence "The whole picture is a pipeline.
`pairs` walks the source once ...". The pre-lexer's stages (pairs, escapes, indentation, shape)
would compose with the same `>>` that the pass pipeline uses (`pass_compose`, ADR-0012). The
operator is the composition operator from the pipeline design conversation. Taken up as
ADR-0014 (draft), which says when a stage may be composed and what to measure first.

## Options and outcome

Open. Drafted as ADR-0014.

## Related

- related:: [DI-0055 Documents as views over the semantic graph](DI-0055-documents-as-views-over-the-graph.md)
- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)

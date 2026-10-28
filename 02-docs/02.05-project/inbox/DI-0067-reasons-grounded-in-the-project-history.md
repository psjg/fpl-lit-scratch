---
type: Note
title: "DI-0067 Reasons grounded in the project's history"
description: "before a page is written, a step collects the recorded reasons behind each decision of the module, so the page argues from sources"
status: draft
date: 2026-10-28
related: []
---

# DI-0067 Reasons grounded in the project's history

## His words

> ik weet niet of je de chatlogs die ik met agents heb gehad hebt kunnen minen maar daar werd dit ook als reden gegeven … dan wordt het dus niet alleen de full mambo van H maar ook kijken naar de chat traces JSONL's om gronding te geven in een redenvoering

## Context

From web H, line 631, in the annotation round of 2026-10-28. For the pre-lexer this was done
once: a ledger of 65 decisions, each with the reason found, where it was found, and whether
it holds. It shows that the LALR reason given on one page is unsupported and that a remembered
performance reason is absent from the mined sessions, while textbooks do support others
(thain, p. 76; siek-python, p. 54). Proposal: a `fpl:lit:reasons` step that builds such a
ledger per module before its page is written. Repo text cites decisions and dates, never the
conversations themselves.

## Options and outcome

Open. Proposal; not implemented.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)

---
type: Note
title: "DI-0023 REPL results as checked claims, not comments"
description: "a result is a claim (`|= 5`) that re-running checks; start with the ASCII spellings"
status: stable
date: 2026-10-08
related: []
---

# DI-0023 REPL results as checked claims, not comments

## His words

> we starten met de ascii varianten

## Context

On "everything the REPL writes is a comment": "ik zou zeggen ja..! vgm deden sommige lisps het ook zo... maar we kunnen het nog beter doen... wij hebben namelijk `|=` & `|-`". So `2 | 3 +` then `|= 5`: a transcript is fixture and oracle in one and `.expected` files become redundant. Errors as FPL data: "zelfs errors zouden we homoiconisch terug kunnen geven... niet?"; stderr in comment form: "daar heb je een goed punt". Decided 09:52: the REPL writes `|=` (and `|-` where a derivation is meant); the glyph forms come later, if at all. Open: one word with two spellings goes against DI-0013; measure token cost first.

## Options and outcome

Decided: ASCII first. The turnstile glyph question is reopened in DI-0041.

## Related

- related:: [02.04.02 turnstiles](../../02.04-explanation/inspiration/02.04.02-turnstiles.md)
- related:: [02.04.03 judgments](../../02.04-explanation/inspiration/02.04.03-judgments.md)
- related:: [02.05.05 REPL phrase costs](../notes/02.05.05-repl-phrase-costs.md)


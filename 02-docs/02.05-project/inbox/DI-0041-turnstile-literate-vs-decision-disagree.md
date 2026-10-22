---
type: Note
title: "DI-0041 Turnstiles: the literate draft and the 10-08 decision disagree"
description: "which turnstile prints a REPL value: `|-` or `|=`?"
status: draft
date: 2026-10-21
related: []
---

# DI-0041 Turnstiles: the literate draft and the 10-08 decision disagree

## His words

> (see DI-0023 for his decision of 10-08)

## Context

The literate worktree prints every REPL result as `|-`; `|=`, `-|`, `=|` are unwired. His decision of 10-08 and FPL's own examples go the other way: `|=` for a semantic claim or check, `|-` for a derivation. Measured on main: `|` is a self-delimiting bar, so `2 | 3 + |= 5` fails with `unknown word: =` and `2 | 3 + |- 5` silently opens a frame; his remembered "space-delimited word" is not what the grammar does. Bears on the transcript-fixture idea in the test plan.

## Options and outcome

Open for him: the glyph for a value, comment versus checked claim, and the lexer route (space-delimited `|` or `|=`/`|-` terminals).

## Related

- related:: [02.04.02 turnstiles](../../02.04-explanation/inspiration/02.04.02-turnstiles.md)
- related:: [02.04.03 judgments](../../02.04-explanation/inspiration/02.04.03-judgments.md)
- related:: [02.05.05 REPL phrase costs](../notes/02.05.05-repl-phrase-costs.md)


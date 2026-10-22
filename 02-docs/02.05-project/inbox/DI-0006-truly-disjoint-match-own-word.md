---
type: Note
title: "DI-0006 A truly disjoint match as a word of its own"
description: "opt-in disjointness check with an exempt wildcard row, superseded by `piecewise`"
status: deprecated
date: 2026-10-05
related: []
---

# DI-0006 A truly disjoint match as a word of its own

## His words

> ik wil het

## Context

An opt-in check with an exempt final wildcard row felt "zeer lelijk" to him. By their English, `case` and `match` read as sequential trial, so the order-independent form, whose rows must be disjoint, may deserve its own word. Function and relation (space) readings coincide exactly when rows are disjoint. Precedents: definition by cases (piecewise: disjoint and exhaustive), guarded `if ... fi` (order-free; overlap means nondeterminism), Agda's case split. Name candidates: `split`, `cases`, `piecewise`; decide by first-contact eval and token count.

## Options and outcome

Superseded the same day: see DI-0007 (overlap as an effect) and DI-0008 (`piecewise` chosen).

## Related

- none yet

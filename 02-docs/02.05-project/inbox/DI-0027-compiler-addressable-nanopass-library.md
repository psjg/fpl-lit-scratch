---
type: Note
title: "DI-0027 The compiler addressable from the language (a nanopass library)"
description: "first-class staging: the compiler is an FPL library of typed passes"
status: stable
date: 2026-10-17
related: []
---

# DI-0027 The compiler addressable from the language (a nanopass library)

## His words

> de staging zelf first-class maken: dat is idd de idee ik wil de compiler / evaluator aanspreekbaar maken in de taal zelf (als een nanopass library)

## Context

Passes: parse, resolve, elaborate, lower, evaluate; user passes insertable; macro, operative, elaborator and optimiser as variants of one staged transform. Unrestricted runtime operatives everywhere are no free lunch for types, effects and optimisation. Jai's compile-time code in the same language was the contrast; FPL goes further by composing the compiler of ordinary passes.

## Options and outcome

Decided; recorded as ADR-0010 and ADR-0011. The tension with static analysis stays open.

## Related

- related:: [ADR-0010](../adr/ADR-0010-first-class-staging.md)
- related:: [ADR-0011](../adr/ADR-0011-lisp-level-metaprogramming.md)


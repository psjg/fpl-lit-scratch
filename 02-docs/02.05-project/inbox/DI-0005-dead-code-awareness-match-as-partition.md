---
type: Note
title: "DI-0005 Dead-code awareness early, and `match` as a partition"
description: "unreachable rows should be noticed early; is `match` ordered trial or a partition?"
status: draft
date: 2026-10-05
related: []
---

# DI-0005 Dead-code awareness early, and `match` as a partition

## His words

> het is handig als we deadcode awareness al vroeg in FPL kunnen werken

## Context

Raised by the 09 conflict, where a row after `_` never runs. C's `switch/case` and ML's `match` are false friends: C's is order-dependent (a jump table or goto, surrounded by UB); ML's is modelled as a strict partition, though it is first-match too and the redundancy check is what makes it feel like one. Inside a space an FPL `match` is a relation (a disjunction of rows). He said his "order independent" claim was a deliberate probe: "als AGDA het doet dan willen we dat dus". Agda's `--exact-split` checks that each clause holds as a definitional equality, with CATCHALL exemptions; it is not merely a ban on overlap. A Fable 5.1 and a GPT-6 consult ran on it.

## Options and outcome

Filed as #115 (unreachable-row warning). The partition question continues in DI-0006 to DI-0008.

## Related

- related:: [spec](../../02.03-reference/spec.md)


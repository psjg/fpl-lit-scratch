---
type: Note
title: "DI-0002 Bounded by default, plus usage accounting"
description: "finite default fuel and deadline, an explicit UNBOUNDED sentinel, and per-evaluation usage reports"
status: stable
date: 2026-10-05
related: []
---

# DI-0002 Bounded by default, plus usage accounting

## His words

> fantastisch voorstel, neem dat mee

## Context

Decided and recorded on #112. Pieces: fuel and deadline get finite defaults; unbounded is an explicit UNBOUNDED sentinel, and a quality gate refuses it outside a few call sites; defaults come from measured maxima; every evaluation reports the steps and wall time it used (`--stats`); the REPL log keeps fuel spent in the hashed record and wall time as an observation event; the tests collect a usage table.

## Options and outcome

Decided for the walker. For FPL itself: budgets and their use as log events.

## Related

- related:: [02.05.05 REPL phrase costs](../notes/02.05.05-repl-phrase-costs.md)


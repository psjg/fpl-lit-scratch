---
type: Note
title: "DI-0001 Realtime deadlines beside fuel"
description: "a wall-clock deadline as a second, monotone-decreasing counter beside fuel"
status: draft
date: 2026-10-02
related: []
---

# DI-0001 Realtime deadlines beside fuel

## His words

> we kunnen FUEL trouwens ook combineren met realtime deadlines. aka... this should finish within this wall clock time... (het wordt dan een andere parallele monotoon aflopende discrete teller, moet kunnen met een Lamport klok.) -- Dat is dus voor FPL zelf niet voor deze interpreter zooi.

## Context

Raised on the step-bound (fuel) work. It fits the design principle that time is causality: a deadline is a capability whose readings are log events. The walker side (a per-test timeout, a `deadline` beside `fuel`, `--deadline`) is filed as #112; the language side is open.

## Options and outcome

Open: how a deadline is expressed in FPL (a capability, an effect, a handler) and how its readings enter the hashed log as observation events.

## Related

- related:: [design](../../02.04-explanation/design.md)
- related:: [spec](../../02.03-reference/spec.md)


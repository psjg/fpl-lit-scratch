---
type: Note
title: "DI-0018 A binary word over one strand acts as scan, reduce or map"
description: "`1 2 3 4 | +` should behave like a fold"
status: draft
date: 2026-10-06
related: []
---

# DI-0018 A binary word over one strand acts as scan, reduce or map

## His words

> je zou willen dat het zou werken als een scan / reduce (fold L \/ R) / map anyway

## Context

From the first REPL session: `1 2 3 4 | +` gave `1 2 3 4 [ + ]`, and `[ + ] each` underflowed the stack; `[+] fold` and `[+] scan` do work. Note the "L \/ R": left and right folds both.

## Options and outcome

Open.

## Related

- related:: [spec](../../02.03-reference/spec.md)


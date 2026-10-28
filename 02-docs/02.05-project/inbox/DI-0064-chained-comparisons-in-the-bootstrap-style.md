---
type: Note
title: "DI-0064 Chained comparisons in the bootstrap style"
description: "write `a <= x <= b` as one chain, not as two comparisons joined by and; a style rule for the bootstrap and a candidate lint"
status: draft
date: 2026-10-28
related: []
---

# DI-0064 Chained comparisons in the bootstrap style

## His words

> kan dit niet een volle <= chain?

## Context

A note on web F, line 5143, in the annotation round of 2026-10-28, on
`if not 0 <= value <= 0x10FFFF or 0xD800 <= value <= 0xDFFF:`. A style rule for the code side
of the pages and the bootstrap, and a candidate for a lint (ruff or one of our own) so it is
checked rather than remembered.

## Options and outcome

Open. Proposal; not implemented.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)

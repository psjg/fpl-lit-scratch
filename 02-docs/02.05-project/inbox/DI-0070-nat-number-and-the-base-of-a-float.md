---
type: Note
title: "DI-0070 nat, number, and the base of a float"
description: "the sort a result line names, whether ℕ gets its own sort now, and floats written in a power-of-two base rather than with a decimal point"
status: draft
date: 2026-10-29
related: []
---

# DI-0070 nat, number, and the base of a float

## His words

> waar komt de string numbers vandaan. Kunnen we dat net maken, NAT, als in het wiskundige begrip van de natural numbers?

> twee spanningen... aan een kant degelijke software engineering aan de andere kant zo vroeg mogelijk richting jusitheid gaan

> ander ding ik wil geen decimal points doen iig niet in de normalisatie van FPL of FON het zou denk ik correcter zijn als we floating point etc in een notatie base van een tweemacht doen

> we kunnen ook gewoon dat hele stuk inspringen? idk

## Context

Said in the pad, reading `|- 2 : number`. The name is the sort `Kind.NUMBER = "number"` of `fpl/types.py`, "an int or a decimal": the lexer takes `1.5`, `∞` and `π` as numbers too, so `nat` for that sort would say too much.

## Options and outcome

Open.

- The sort: (a) rename to `nat` now, and `1.5 : nat` lies; (b) two sorts, `nat` for `0 1 2 …` and `number` for the rest, which the elaborator must tell apart, with `3 2 -` on `nat` an open question (ℕ is not closed under subtraction); (c) keep `number` until the type system distinguishes ℕ.
- Floats: no decimal point in the normal form of FPL or FON; a notation in a power-of-two base (hex floats, as `0x1.8p0`), exact where a decimal is not. Bears on the lexer's NUMBER shape and on FON (the hex-float decision of 2026-10-05).
- The last line is about the pad's layout: set the whole cell in (text and results), as BQNPad sets its input in; FPL reads a leading tab as a body line, so the pad would have to write and strip that indent itself.

## Related

- related:: [DI-0069](DI-0069-the-space-before-a-comment-as-part-of-its-token.md)
- related:: [DI-0013](DI-0013-one-spelling-per-value.md)

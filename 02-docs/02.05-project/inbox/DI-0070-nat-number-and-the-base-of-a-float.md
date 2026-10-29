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

> nat

> het moet gewoon een tweemacht zijn hexfloat is daar een vorm van binair voor je bitmasks en octaal en idk hoe mensne base32 en base64 doen zou ook mogen ik wou sws een arbitraire base notatie syntax weet je nog?

> nee vriend gewoon een wit stuk er naast thats all....

## Context

Said in the pad, reading `|- 2 : number`. The name is the sort `Kind.NUMBER = "number"` of `fpl/types.py`, "an int or a decimal": the lexer takes `1.5`, `∞` and `π` as numbers too, so `nat` for that sort would say too much.

## Options and outcome

Decided 2026-10-29: `nat`, as the small form of (b): a sort of its own for the literals `0 1 2 …`, rising to `number` wherever a number is asked; `3 2 -` on `nat` stays open. The float notation: any power-of-two base, hex float one form of it, binary for bit masks, octal, base32 and base64 to be looked at; he had asked for an arbitrary-base notation before. The last line was a layout remark, answered by a white margin beside the buffer, no indent.

- The sort: (a) rename to `nat` now, and `1.5 : nat` lies; (b) two sorts, `nat` for `0 1 2 …` and `number` for the rest, which the elaborator must tell apart, with `3 2 -` on `nat` an open question (ℕ is not closed under subtraction); (c) keep `number` until the type system distinguishes ℕ.
- Floats: no decimal point in the normal form of FPL or FON; a notation in a power-of-two base (hex floats, as `0x1.8p0`), exact where a decimal is not. Bears on the lexer's NUMBER shape and on FON (the hex-float decision of 2026-10-05).
- The last line is about the pad's layout: set the whole cell in (text and results), as BQNPad sets its input in; FPL reads a leading tab as a body line, so the pad would have to write and strip that indent itself.

## Related

- related:: [DI-0069](DI-0069-the-space-before-a-comment-as-part-of-its-token.md)
- related:: [DI-0013](DI-0013-one-spelling-per-value.md)

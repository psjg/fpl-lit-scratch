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

> kan je het plan weer opnieuw oppakken en Nat1 en Nat0 uitsplitsen? die hebben gewoon zuivere bijectie tussen elkaar (hilberts hotel) maar ik vermoed dat dat wederom wat ambiguiteit gaat oplossen

> misschien ook NNAT of -NAT idk wat wiskundigen het best siert en dan is INT gewoon NAT U -NAT

> those are going to be the rationals

> wat doen we met de negatieven van nat1 en nat0: nat1 U neg1 U {0} is een keurige dekking op Int neg0 U nat0 is dat niet...

> misschien moeten types wel met een hoofdletter geschreven worden? dat houdt ons consistent met andere functionele wiskundigere meer CT georienteerde talen

> maak ze allemaal met hoofdletter

## Context

Said in the pad, reading `|- 2 : number`. The name is the sort `Kind.NUMBER = "number"` of `fpl/types.py`, "an int or a decimal": the lexer takes `1.5`, `∞` and `π` as numbers too, so `nat` for that sort would say too much.

## Options and outcome

Decided 2026-10-29: `nat`, as the small form of (b): a sort of its own for the literals `0 1 2 …`, rising to `number` wherever a number is asked; `3 2 -` on `nat` stays open. The float notation: any power-of-two base, hex float one form of it, binary for bit masks, octal, base32 and base64 to be looked at; he had asked for an arbitrary-base notation before. The last line was a layout remark, answered by a white margin beside the buffer, no indent.

Decided 2026-10-29, final: the naturals get a sort of their own and the literals partition the integers: `Nat1` (1 2 ...), `Zero` (0) and `Neg1` (-1 -2 ...). Above them sit the covers `Nat0 = Nat1 ∪ Zero` and `Neg0 = Neg1 ∪ Zero`, then `Int`, then `Rat` (reserved: a name only, no literal, no arrow) and `Number` (decimals and everything numeric). A sort rises one way and never falls; `Value` stays the unknown sort. Every sort name is capitalised: `Nat1 Zero Neg1 Nat0 Neg0 Int Rat Number Text Symbol Value`. A divisor of sort `Nat1` is never zero, which DI-0072 uses. Open: whether `1 | 2 +` is `Nat1` or `Number`; `Number` is kept for now.

- The sort: (a) rename to `nat` now, and `1.5 : nat` lies; (b) two sorts, `nat` for `0 1 2 …` and `number` for the rest, which the elaborator must tell apart, with `3 2 -` on `nat` an open question (ℕ is not closed under subtraction); (c) keep `number` until the type system distinguishes ℕ.
- Floats: no decimal point in the normal form of FPL or FON; a notation in a power-of-two base (hex floats, as `0x1.8p0`), exact where a decimal is not. Bears on the lexer's NUMBER shape and on FON (the hex-float decision of 2026-10-05).
- The last line is about the pad's layout: set the whole cell in (text and results), as BQNPad sets its input in; FPL reads a leading tab as a body line, so the pad would have to write and strip that indent itself.

## Related

- related:: [DI-0069](DI-0069-the-space-before-a-comment-as-part-of-its-token.md)
- related:: [DI-0013](DI-0013-strict-readers-one-value-one-spelling.md)
- related:: [DI-0072](DI-0072-the-division-family.md)

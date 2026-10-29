---
type: Note
title: "DI-0072 The division family"
description: "div, mod, rem, floor and ceiling words, the jump to the rationals, and how the number system stays open to roots and rings"
status: draft
date: 2026-10-29
related: []
---

# DI-0072 The division family

## His words

> hoe moelijk is het om de rationals alvast uit te bouwen?

> ik zou willen dat er een `div` en een `mod` en misschien een `rem` woord dan bijkomen … misschien ook `floor` `ceilling` `floordiv` `ceilingdiv`? idk een div die expliciet binnen de gehele getallen blijft en een die van gehelge getallen naar een rational kan springen?

> of misschien willen we mod onder N toevoegen... als ring dan? hmm willen we dat nu al? idk … we hebben nog geen CT spul om deze hogere structuren uit te rekene … wat zouden we moeten doen met wortels en complexe getallen? wat doen we met `i j k l m` ik zou die natuurlijk symbolisch willen houden 2 sqrt blijft gewoon 2 sqrt zegmaar ... dit is scope creep... maar het is wel goed om na te denken hoe dit getallen systeem in de toekomst netjes kan blijven

> mijn onderbuik zegt dat C waarschijnlijk wel logisch is als je de logica van de machine volgt maar op een of andere manier later terugkomt om met je te fucken

> ok ik weet dat ik hiermee heilige wiskundigen huisjes omver werp maar die 0 moet ook een plaats … dus er moet misschien een nat1 en een nat0 zijn.. dan is div ook gesloten onder nat1 en hebben we gewoon zuivere bijectie tussen die twee (hilberts hotel)

> ER IS ECHTER EEN HELE GOEDE REDEN OM DIV 0 als waar vast te houden die we een soort van kunnen lezen bij crockford boekhoudkundigen en accounts hebben er weet ik zeker ook een mening over

> zijn dat dan onze eerste afhankelijke / dependent types?

## Context

Said in the pad after the sorts of DI-0070 were fixed. The elaborator now has `Nat1`, `Zero`, `Neg1`, `Nat0`, `Neg0`, `Int` and a reserved `Rat`; the words that divide are still missing. Each integer word costs one `partial(arithmetic, ...)` entry in `fpl/eval.py`, one arrow in `ARROWS` and tests; the rational jump touches the ten or so `Decimal` sites plus FON.

## Options and outcome

Open: recorded now, built after his choice. Defaults in bold.

- Integer division pair: **floored `div`/`mod`** (Knuth, Concrete Mathematics section 3.4: mod takes the divisor's sign, `x mod 0 = x`; Python's `//` and `%`), or Euclidean (Boute 1992, ACM TOPLAS 14(2): the remainder is always at least 0, ranked best, floored second, truncated last), or truncated (C; `rem` is that remainder's name). `rem` only if both conventions should sit side by side.
- `floor` and `ceiling`: unary, `Number` to `Int`. `floordiv` and `ceilingdiv`: the two rounding divisions as words; `div` an alias of `floordiv`.
- The jump to the rationals: one word (`/`? `ratio`?) from `Int Int` to `Rat` through `fractions.Fraction`. It needs the `Rat` printer and a canonical FON spelling (the hex-float decision of 2026-10-05), so it is its own commit after the literal question: FON refuses `1/2` today and `/` is a path separator in the lexer.
- Sorts: `Nat0 Nat1 div` is `Nat0`, `Int Nat1 div` is `Int`, `Nat0 Nat1 mod` is `Nat0`; a `Nat1` divisor is never zero. `1 2 div = 0`, so `div` is not closed on `Nat1` (only `+` and `times` are). ISO 80000-2 has 0 in the naturals.
- Division by zero: he wants it held as a value on purpose, with Crockford's position still to be read (open); accountants will have a view as well.
- Structure for later: (1) a literal gets the smallest sort that holds it; (2) sorts rise one way; (3) a word with no rewrite stays a term (`2 sqrt` stays `2 sqrt`, `i j k` are symbols), so roots, complex numbers and the integers mod n enter as sorts whose values are terms. `mod n` is a value-indexed sort, which would be the first dependent type; parked until sorts take arguments.

## Related

- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)

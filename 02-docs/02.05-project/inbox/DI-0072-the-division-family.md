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

> wat als we varianten maken zoals kdiv (knuth div) en bdiv (bautediv)... die kunnen we samengaan onder hetzelfde typesysteem toch? worden gewoon andere woorden en andere functies dan...

> ja dat wil ik dat is wat ik eigenlijk bedoelde voeg pdiv toe

> dit past ook mooi bij onze totale / fuel / complexiteits ambities

> ja wacht even tenzij die waarde track waar het gebeurde... maar ok misschien heb je gelijk

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

2026-10-29, late morning, decided for the integers (floor, ceiling and the jump to the rationals stay open):

- Four pairs, not one: `kdiv`/`kmod` (floored, Knuth), `bdiv`/`bmod` (Euclidean, Boute), `tdiv`/`tmod` (truncated, C) and `pdiv`/`pmod` (Euclidean, total at zero). His words: "wat als we varianten maken zoals kdiv (knuth div) en bdiv (bautediv)... die kunnen we samengaan onder hetzelfde typesysteem toch? worden gewoon andere woorden en andere functies dan...". They share the type system: each pair is one `Cases` table of result sorts, so the choice of convention is the choice of a word and nothing else. A bare `div` and `mod` stay unbuilt; no convention is the default.
- Why the conventions cannot be one word: mirror symmetry (`(-a) div d = -(a div d)`) and a remainder that is never negative exclude each other. Take -7 and 2. Mirror symmetry forces q = -3, as 7 div 2 = 3. The identity a = d q + r then gives r = -7 - 2 * (-3) = -1, which is below 0. Truncation keeps the mirror and gives up r >= 0; the Euclidean pair keeps r >= 0 and gives up the mirror (q = -4, r = 1); the floored pair keeps the divisor's sign on r and gives up both.
- `pdiv`/`pmod` are the Euclidean pair made total: `a pdiv 0 = 0` and `a pmod 0 = a`, so a = d q + r holds for every d, zero included. Their sorts are those of `bdiv` and `bmod` plus the rows (Int, Zero) to Zero for `pdiv` and (X, Zero) to X for `pmod`, the dividend's own sort. They refuse nothing at elaboration. His words: "ja dat wil ik dat is wat ik eigenlijk bedoelde voeg pdiv toe".
- The other six words do not fire at a zero divisor and the term stays, as a value: `7 0 kdiv` leaves one value that prints as `7 0 kdiv`, so a run never fails on it and the operands and the word stay visible. His words: "dit past ook mooi bij onze totale / fuel / complexiteits ambities". On a value that only says "division by zero" he first wanted the place kept: "ja wacht even tenzij die waarde track waar het gebeurde... maar ok misschien heb je gelijk". The stuck term is that value: it holds the operands, the word and the span where it happened. It is no number, so arithmetic on it is refused (`arithmetic on a non-number`); its sort is `Value` until it gets a sort of its own. A strand with a zero item sticks the whole application: one term holding both operands as they were. This answers the open line above on division by zero as a value; Crockford's position is still unread.
- Sources now in hand: Boute, "The Euclidean definition of the functions div and mod", ACM TOPLAS 14(2), 1992 (the ranking: Euclidean best, floored second, truncated last); Leijen, "Division and Modulus for Computer Scientists", 2001 (his remarks that Knuth's floored definition is from TAOCP, 1972, and that Ada's `mod` fails the division conditions); R6RS section 11.7.4, whose `div` and `mod` are the Euclidean pair, and `div0` and `mod0` the centred pair.

## Related

- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)

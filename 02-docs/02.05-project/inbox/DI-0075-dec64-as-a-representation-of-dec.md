---
type: Note
title: "DI-0075 DEC64 as a representation of Dec"
description: "what Crockford's DEC64 is, what it costs as the bounded target form of the Dec sort (range, exactness, the refusal Dec relies on) and what it gains over Decimal; a representation under 02.04.13, not a new sort"
status: draft
date: 2026-10-29
related: []
---

# DI-0075 DEC64 as a representation of Dec

## His words

> hebben we crockfords dec64 in de taal zitten

After the first version of this note (replies in the same chat, 13:07):

> draai die assembly man

> ik voel eigenlijk weinig voor die trap cool dat het kan maar het fuckt met de totaliteit en correctness by construction als we het kunnen voorkomen met design dan graag zolang mogelijk afhouden

> ik zou ze plugable naast elkaar willen hebben net zoals iEEE747 whatever floating point ook iets is wat plugable is en dan aan de voorwaarden kan voldoen

On the planner choosing and the program pinning a plug as the exception (09:59):

> precies als er ambiguiteit is dan kan de compiler helpen dat gat kleiner te maken (dit is een hole) en je kant het dicht specificeren door te zeggen wat voor soort plug het wordt om dat gat te dichten

## Context

Asked in a side chat on 2026-10-29, after [DI-0074](DI-0074-a-discrete-basis-dec-rat-and-the-slash-literal.md)
leaned on a `Dec` sort. The answer to the question as asked is no: a grep of the repository for
`dec64` finds the word nowhere before this note. What follows is what DEC64 is, read from
Crockford's own pages, and what it would be to us. Measured on this machine (Python 3.13.15,
libmpdec 4.0.1) unless marked a prior.

**What DEC64 is**, from [crockford.com/dec64.html](https://www.crockford.com/dec64.html) (dated
2020-06-09) and [dec64.obj.html](https://www.crockford.com/dec64.obj.html), the header
`dec64.h` on [GitHub](https://github.com/douglascrockford/DEC64) (2025-12-14):

- One 64-bit word: a 56-bit two's-complement coefficient in the high end, an 8-bit exponent in the
  low byte. `value = coefficient * 10^exponent`. Coefficient −36_028_797_018_963_968 thru
  36_028_797_018_963_967 (±2^55, about 3.6e16, so 16 digits always, 17 mostly); exponent −127 thru
  127. Extremes 3.6028797018963967E+143 and 1.0E-127.
- Not normalised: "Normalization is not required, and is usually not desired." Exponent 0 is a
  plain integer shifted left 8 bits, so integer addition is one machine add with an overflow check
  (his x64 fast path is five instructions).
- 255 zeros (any exponent), all equal; no negative zero.
- `nan` is exponent −128; "The result of division by zero is `nan`. `nan` is also the result of
  operations that produce results that are too large to be represented. `nan` is equal to itself."
  The other 2^56 coefficients under exponent −128 are free payload (object pointers), two are
  `true` and `false`. The reference functions always return the one normal `nan`, `DEC64_NULL`.
- Rounding is a total rule, not a trap: "Rounding is to the nearest value. Ties are rounded away
  from zero." There is no inexact flag, no status, no context.
- Two zero rules that break strictness: `0 × n`, `0 ÷ n`, `0 mod n` are zero "even if n is nan".
  Any other operation with a `nan` operand is `nan`; `n ÷ 0` is `nan` for every n except 0.
- What it cannot represent: a third (`1/3` rounds), more than 17 significant digits, magnitude
  above about 3.6e143, below 1e-127 (a number that small is not an error, it rounds to 0), infinity,
  and a distinct "undefined" (division by zero and overflow are the same `nan`).
- His claim for it: "`DEC64` is intended to be the only number type in the next generation of
  application programming languages", and "eliminating the performance justification for a separate
  `int` type and avoiding the terrible errors that can result from `int` truncation."

**Measured: a model of the spec** (20 lines of Python on `int` and `Fraction`: build the exact
result, round to the nearest, ties away, pick the lowest exponent at which the coefficient fits,
`nan` when none does) and then the reference assembly itself. Crockford's `dec64.s` (ARM64, dated
2024-04-09, written for Microsoft's assembler) was converted mechanically to clang syntax (labels,
`global`, `dcq`, comments, two addressing forms; no instruction changed), assembled on this arm64
Mac and driven from C through `dec64.h`. On 3012 cases (twelve named ones and 3000 random money
pairs) the assembly and the model give the same value in every one, `nan` included, so the
table below is the assembly's behaviour, with the conversion as my own and unreviewed. Run directly
on the assembly: `0 × nan` and `0 ÷ nan` return 0, `5 ÷ nan` and `nan + 1` return `nan`, and
`dec64_new(1, -128)` returns 0, a silent underflow. The upstream test program was not run.
Model and assembly against `Decimal` at precision 8192 with `Inexact` trapped:

| case | DEC64 model | `Decimal` |
|---|---|---|
| `0.1 + 0.2` | `30000000000000000e-17`, equals 0.3 | `0.3` |
| `1/3` | `33333333333333333e-17`, silently rounded | `Inexact` |
| `1/0` | `nan` | `DivisionByZero` |
| 2^30 × 2^30 = 2^60 | `11529215046068470e2`, not 2^60 | `1152921504606846976` |
| 2^28 × 2^28 = 2^56 | `7205759403792794e1`, not 2^56 | `72057594037927936` |
| literal 2^55 | `3602879701896397e1` | exact |
| 36028797018963967e127 × 10 | `nan` | exact |
| `0 × nan`, `nan + 1` | `0`, `nan` | n/a |
| literal 0.123456789012345678 | rounded to 17 digits | exact |
| literal 1e-128 | `0`, no error | exact |

Money-like grid, 1000 random pairs per operation (amounts of 1 to 14 integer digits and two
decimals; division by 3, 7, 12 or 360): addition differs from `Decimal` in 0 of 1000 and never
gives `nan`; multiplication differs in 581 (the product needs more than 17 digits, DEC64 rounds,
`Decimal` is exact); division differs in 788 (785 of them are the cases where `Decimal` raises
`Inexact`). So DEC64 is exact where the result fits 17 digits and is silently wrong in the last
digit where it does not, the very event `Decimal` makes loud.

**What the walker does today** (read, not assumed). `DIGITS = 4096` ([ast_core.py:32](../../../01-bootstrap/fpl/ast_core.py))
bounds a numeral and the integer part of a result; [eval.py:63](../../../01-bootstrap/fpl/eval.py)
turns it into `LIMIT = 10**DIGITS` and `arithmetic` raises `number too large` at it
([eval.py:853](../../../01-bootstrap/fpl/eval.py)). A search for `Inexact`, `traps` and
`getcontext` in `fpl/` finds nothing: the trap DI-0074 describes is a measured property of
`Decimal`, not code in this checkout, because `÷` is not a walker word yet. So the refusal Dec
relies on is a design to build, and DEC64 is a design question before it is a dependency. He does not want the trap
(quote above): a trap makes `÷` partial at run time, which costs totality and correctness by
construction. Note that `LIMIT` above is a refusal of the same kind, a bound met at run time; it is
the one the walker already has.

## Options and outcome

1. **Representation or new sort.** [02.04.13](../../02.04-explanation/02.04.13-numbers-ml-library.md)
   answers Crockford's one-number-type with "one specification with representations chosen per
   obligation". DEC64 fits that rule as one representation of the `Dec` sort for a target that
   needs a fixed word. It is not a sort: it has a `nan` and rounds, both of which the kernel
   excludes. The kernel stays discrete and
   unbounded; DEC64 is below it. Prior: representation.
2. **The obligation a DEC64 target must discharge, by design and not by trap.** `Dec` closes under
   `+ − ×`; `÷` leaves ℤ[1/10] and rises to `Rat` (DI-0074), so no division ever has to fail on
   `Dec`. DEC64 differs in four places, and each is an obligation on the choice of the
   representation, checked before the program runs, not a check inside it: (a) a result must fit
   55 bits of coefficient and exponents −127..127, which a static bound on the operands decides
   (a width per value, as the digits of a coefficient add under `×` and the larger plus one under
   `+`), and a program whose bounds do not fit is given another representation; (b) the one `nan`
   (division by zero and overflow alike) never arises, because no operation on a value in range
   leaves the range once (a) holds, and `÷` by a Nat1 divisor cannot be zero (DI-0074 point 3);
   (c) `0 × nan` is 0 (measured), harmless when no `nan` is ever formed; (d) literals and results
   under 1e-127 or past 17 digits do not occur, for the same reason. If that holds, DEC64's own
   rounding is never exercised, and what is left of DEC64 is the layout and the integer fast
   path. Prior, not measured: that the bounds can be tracked cheaply enough in the planner; the
   range-typed `Dec` this asks for is a design question for 02.04.13.
3. **What it gains over `Decimal`** (measured where marked). A fixed word, fixed layout and no
   allocation: `Decimal` is a heap object with a context (precision, rounding, traps) a
   compiled target has to ship (libmpdec); DEC64 has no context at all, one rounding rule, so the
   same bits give the same answer on every machine (Crockford: conversion to text is "free of the
   complexities that binary floating formats must wrestle with"). The integer path is a plain add
   (his 5-instruction fast path, a prior for speed; the measured 62 ns per `Decimal` add is in
   DI-0074). Conversion of a Nat1 or Int that fits 55 bits is a shift.
4. **What it costs.** Range: 55 bits of integer against `DIGITS = 4096` decimal digits, a factor
   of about 10^4080 in the largest integer; `Int` beyond 3.6e16 has no DEC64 form, and 2^60
   already rounds (table). Exactness is the narrowest here: 16 to 17 digits, so the product of two
   money amounts of 9 digits each already overflows the coefficient. The refusal costs a check per
   operation (a wide multiply and a range test), which the five-instruction path does not have.
5. **IEEE decimal64, read from the standard.** The text is ISO/IEC 60559:2020, which is IEEE Std
   754-2019 (his own copy; the standard is sold, resellers list it at roughly €89 to €268 by
   edition and are not checked against the shops). Clause numbers are the standard's.
   - Table 3.6: decimal64 is 64 bits, `p` = 16 digits, `emax` = 384 (and `emin` = 1 − `emax`, clause
     3.3), so exponents run to about ±384 against DEC64's ±127; a 13-bit combination field and a
     50-bit trailing significand. A NOTE says implementations choose binary or decimal encoding of
     the significand and the standard does not say how that choice is communicated.
   - 3.5.1: a value has a cohort of representations `(s, q, c)` and `(s, q + 1, c / 10)`; zero has
     one representation per exponent. This is DEC64's "not normalised" and its 255 zeros, said
     with more care (and with a sign on zero, which DEC64 does not have).
   - Exceptional cases give flags and non-stop results: five status flags (inexact, underflow,
     overflow, divideByZero, invalid; clause 7). Division of a finite non-zero by zero is `∞`
     with the divideByZero flag (7.3), `0 ÷ 0` and `∞ ÷ ∞` are invalid and give a quiet NaN
     (7.2), overflow and inexact results are rounded under the rounding-direction attribute. DEC64
     has one `nan` for all of it and no flags.
   - The same family as DEC64: Cowlishaw's earlier [proposal](https://www.speleotrove.com/mfc/files/cowlishaw2001-decimal-specification.pdf)
     (2001) and [slides](https://www.speleotrove.com/decimal/decArith16-charts.pdf) (2003) state
     the idea both share: integers have exponent 0, equal exponents need no alignment, and without
     rounding the operations are integer operations. The 2001 proposal is not the final format
     (52-bit integer, 11-bit exponent, 13 to 15 digits).
   Consequence for FPL: the flags are the trap he does not want, so what IEEE decimal64 adds over
   DEC64 is range and `∞`, not something the kernel can use; what it shares with DEC64 is the
   rounded-by-default result, which point 2 keeps out by the static bound. Both are plugs with the
   same obligation (the program's values stay inside the plug's range and digits). Which one a
   target prefers is a question for a target, with a measurement.
6. **His answer, 13:07: pluggable, side by side.** DEC64 is one plug among several for the `Dec`
   sort, as IEEE binary floating point is one for a smooth sort: each representation states the
   conditions under which it implements the sort (range, exactness, which operations are total),
   and a target takes the one whose conditions the program meets. That is 02.04.13's rule applied
   to `Dec`, and it removes the question of whether FPL has DEC64: it has a slot, and DEC64
   would be filled when a compiled target needs a fixed word. The plugs named so far: the walker's
   bignum `Decimal` (conditions: `DIGITS`), DEC64, IEEE decimal64 (prior), a scaled `int` (Q
   format, DI-0074). The shape of a plug's interface (its conditions as proof obligations, how a
   program says which plug it wants or leaves it to the planner) is not designed here.

7. **Who picks the plug: the hole.** The planner picks by the static bound (point 2); where the
   bound does not decide, the choice is a hole in the sense of
   [02.04.07](../../02.04-explanation/02.04.07-principles-and-privileges.md), not a default. The
   compiler narrows it: it states which plugs still satisfy the bounds it could compute (DEC64
   only if the coefficient stays under 2^55, the bignum always, and so on), and the author closes
   it by naming the kind of plug, not necessarily one plug (a fixed-width decimal, an exact one).
   That makes A (the program pins) and B (the planner picks) the two ends of one mechanism: B
   leaves no hole when the bound decides, A closes the hole by hand.

   **Proposed closure (mine, for him to confirm).** The hole takes the three fields of 02.04.07
   section 1.1. *Depends:* the static bound of point 2 on coefficient digits and exponent, per
   value. *Default in force:* the smallest plug whose conditions the bound satisfies; where the
   bound is unknown, the exact plug (the bignum), which is total, so an unknown bound costs speed
   and never correctness. *Closes by:* the author naming a kind, by the obligation that
   separates the plugs and not by their names:
   - `exact`: unbounded digits, no range obligation (the walker's `Decimal`, `DIGITS` aside);
   - `fixed`: a fixed word, its range an obligation discharged by the bound (DEC64, decimal64);
   - `scaled`: a fixed word with a static scale, a decimal Q format, the cheapest and the
     narrowest (DI-0074).
   Naming one plug (`DEC64`) is a pin and a dispensatie: it closes the hole to a single plug, and
   if the bound does not fit that plug the build fails before it runs, never at run time. What a
   closed hole records, in the log and in the interface hash (02.04.07, where profiles are part of the interface hash): the kind or
   pin, the bounds the compiler computed, and the plug chosen. Not closed by this: the surface
   spelling of the three kinds, and whether `fixed` may be left to the planner to split between
   DEC64 and decimal64.

8. **Von Neumann's argument, read.** From Burks, Goldstine and von Neumann, *Preliminary
   discussion of the logical design of an electronic computing instrument* (IAS, 1946; read in the
   HTML transcription taken from von Neumann's Collected Works, 1963, hosted at
   [MIT CSAIL](https://people.csail.mit.edu/ledlie/resources/papers/1963/neuman63.html), so
   the edition is the Collected Works', not checked against the 1946 or 1947 print; the Deep Blue
   and IAS copies exist but blocked a download).
   - Section 5.3 names the two reasons for a floating decimal point (keep the significant digits
     of a sum or product; free the operator from choosing scale factors) and answers: the time
     spent on scale factors is "a very small percentage" of the time to prepare a problem; the
     first reason is "somewhat illusory", since a floating word spends storage that could carry
     more digits; and long precision, built from fixed multiples of the word length, is harder
     with a floating point.
   - Section 6.6.7 reframes the choice: it is not built in or unused, it is built in or
     programmed from the operations the machine has. A floating point also repeats a scale factor
     in every number, where one factor often serves a whole set of numbers; it can be programmed
     out of shifts when needed.
   What it says to this note: DEC64 and decimal64 put one exponent in every number, which is the
   redundancy he names; the `scaled` kind is his one scale factor per set; the `exact` kind is
   his long precision built from primitives (limbs of integers); and a floating plug is
   something programmed out of the others when a target asks, not a basis. Where we differ: he
   leaves the scale analysis to the programmer, and here the planner computes the bound.

Outcome: the pluggable reading and the hole as the way to choose are his; the interface of a plug,
the kinds of plug and the static bound of point 2 are open. No code was written; the model and the converted assembly live outside the repository.

## Related

- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
- related:: [DI-0072](DI-0072-the-division-family.md)
- related:: [DI-0074](DI-0074-a-discrete-basis-dec-rat-and-the-slash-literal.md)
- related:: [02.04.13 numbers, ML and the library](../../02.04-explanation/02.04.13-numbers-ml-library.md)

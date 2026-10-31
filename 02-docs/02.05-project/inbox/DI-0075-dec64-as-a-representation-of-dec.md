---
type: Note
title: "DI-0075 DEC64, and plugs for the Dec sort"
description: "DEC64 read from Crockford and run on his assembly; IEEE decimal64 read from the standard; von Neumann on scale factors; Dec gets pluggable representations (exact, fixed, scaled), chosen by the planner from a static bound, with a hole where the bound does not decide, and no run-time trap"
status: draft
date: 2026-10-29
related: []
---

# DI-0075 DEC64, and plugs for the Dec sort

## His words

> hebben we crockfords dec64 in de taal zitten

On running the reference assembly, and on the trap:

> draai die assembly man

> ik voel eigenlijk weinig voor die trap cool dat het kan maar het fuckt met de totaliteit en correctness by construction als we het kunnen voorkomen met design dan graag zolang mogelijk afhouden

On what DEC64 should be to the language:

> ik zou ze plugable naast elkaar willen hebben net zoals iEEE747 whatever floating point ook iets is wat plugable is en dan aan de voorwaarden kan voldoen

On who picks the plug (2026-10-31):

> precies als er ambiguiteit is dan kan de compiler helpen dat gat kleiner te maken (dit is een hole) en je kant het dicht specificeren door te zeggen wat voor soort plug het wordt om dat gat te dichten

On the kinds of plug: whether `scaled` is a kind of its own, and whether a kind "may round, provided I see it" is missing:

> van zichzelf

> hoe zou je dat voor je zien dat lijkt me heel veel error trap slingeren

## Context

Asked in a side chat on 2026-10-29, after [DI-0074](DI-0074-a-discrete-basis-dec-rat-and-the-slash-literal.md)
leaned on a `Dec` sort. The answer to the question as asked is no: a search of the repository for
`dec64` finds the word nowhere before this note. Everything below is read from a source or measured
on this machine (Python 3.13.15, libmpdec 4.0.1, arm64) unless marked a prior.

**What DEC64 is**, from [crockford.com/dec64.html](https://www.crockford.com/dec64.html) (2020-06-09),
[dec64.obj.html](https://www.crockford.com/dec64.obj.html) and the header `dec64.h` on
[GitHub](https://github.com/douglascrockford/DEC64) (2025-12-14):

- One 64-bit word: a 56-bit two's-complement coefficient in the high end, an 8-bit exponent in the
  low byte, `value = coefficient * 10^exponent`. The coefficient runs from −2^55 to 2^55 − 1
  (about 3.6e16: 16 digits always, 17 mostly), the exponent from −127 to 127.
- Not normalised. Exponent 0 is a plain integer shifted left 8 bits, so integer addition is one
  machine add with an overflow check (his x64 fast path is five instructions).
- 255 zeros, all equal; no negative zero.
- `nan` is exponent −128. Division by zero gives `nan`, and so does a result too large to represent.
  The other coefficients under −128 are free payload (object pointers), two reserved as `true` and
  `false`; the reference functions always return the one normal `nan`.
- Rounding is a total rule, not a trap: to the nearest, ties away from zero. There is no inexact
  flag, no status, no context.
- Two zero rules break strictness: `0 × n`, `0 ÷ n` and `0 mod n` are zero even when `n` is `nan`;
  any other operation with a `nan` operand is `nan`.
- It cannot represent a third, more than 17 significant digits, magnitudes above about 3.6e143 or
  below 1e-127 (a smaller one rounds to 0 without an error), infinity, or a difference between
  "undefined" and "too large".
- His claim for it: it "is intended to be the only number type in the next generation of
  application programming languages".

**Measured.** A model of that spec (20 lines of Python on `int` and `Fraction`: build the exact
result, round to the nearest, ties away, take the lowest exponent at which the coefficient fits,
`nan` when none does), then Crockford's own ARM64 assembly `dec64.s` (2024-04-09, written for
Microsoft's assembler), converted mechanically to clang syntax (labels, `global`, `dcq`, comments,
two addressing forms; no instruction changed), assembled on this Mac and driven from C through
`dec64.h`. On 3012 cases (twelve named and 3000 random money pairs) the assembly and the model give
the same value in every one, `nan` included. The conversion is mine and unreviewed, and the
upstream test program was not run. Directly on the assembly: `0 × nan` and `0 ÷ nan` return 0,
`5 ÷ nan` and `nan + 1` return `nan`, and a construction under 1e-127 returns 0. Against `Decimal`
at precision 8192 with `Inexact` trapped:

| case | DEC64 (model and assembly) | `Decimal` |
|---|---|---|
| `0.1 + 0.2` | `30000000000000000e-17`, equals 0.3 | `0.3` |
| `1/3` | `33333333333333333e-17`, silently rounded | `Inexact` |
| `1/0` | `nan` | `DivisionByZero` |
| 2^30 × 2^30 = 2^60 | `11529215046068470e2`, not 2^60 | `1152921504606846976` |
| 2^28 × 2^28 = 2^56 | `7205759403792794e1`, not 2^56 | `72057594037927936` |
| literal 2^55 | `3602879701896397e1` | exact |
| 36028797018963967e127 × 10 | `nan` | exact |
| literal 0.123456789012345678 | rounded to 17 digits | exact |
| literal 1e-128 | `0`, no error | exact |

On 1000 random pairs per operation (amounts of 1 to 14 integer digits and two decimals; division
by 3, 7, 12 or 360), addition differs from `Decimal` in 0, multiplication in 581 (the product needs
more than 17 digits, DEC64 rounds, `Decimal` is exact) and division in 788 (785 of them where
`Decimal` raises `Inexact`). DEC64 is exact where the result fits 17 digits and wrong in the last
digit where it does not, silently: the event `Decimal` makes loud.

**What the walker does today.** `DIGITS = 4096` ([ast_core.py:32](../../../01-bootstrap/fpl/ast_core.py))
bounds a numeral and the integer part of a result; [eval.py:63](../../../01-bootstrap/fpl/eval.py)
makes it `LIMIT = 10**DIGITS` and `arithmetic` raises `number too large` at it
([eval.py:853](../../../01-bootstrap/fpl/eval.py)). A search for `Inexact`, `traps` and
`getcontext` in `fpl/` finds nothing: the `Inexact` trap in DI-0074 is a measured property of
`Decimal`, not code here, because `÷` is not a walker word yet. `LIMIT` is a run-time refusal of
the kind he does not want; it is the one the walker already has.

## Options and outcome

1. **A representation, not a sort.** [02.04.13](../../02.04-explanation/02.04.13-numbers-ml-library.md)
   answers Crockford's one number type with "one specification with representations chosen per
   obligation". DEC64 is one representation of the `Dec` sort for a target that needs a fixed
   word. It is not a sort: it has a `nan` and it rounds, both of which the kernel excludes. The
   kernel stays discrete and unbounded; DEC64 is below it.

2. **No trap; the bound is static.** He wants `÷` and every other operation total, correct by
   construction. `Dec` closes under `+ − ×`, and `÷` rises to `Rat` (DI-0074), so no division
   fails on `Dec`. What a fixed word adds is range, and range is decided before the program runs:
   a width per value (the digits of a coefficient add under `×`, the larger plus one under `+`)
   decides whether DEC64's 55-bit coefficient and exponents −127..127 hold. A program whose bounds
   do not fit is given another plug; one whose bounds fit never forms a `nan`, never rounds, and
   never meets `0 × nan`. Then what is left of DEC64 is its layout and its integer fast path.
   Prior, not measured: that the planner can track the bounds cheaply.

3. **What DEC64 gains over `Decimal`.** A fixed word with a fixed layout and no allocation;
   `Decimal` is a heap object with a context (precision, rounding, traps) that a compiled target
   would have to ship (libmpdec). DEC64 has no context and one rounding rule, so the same bits
   give the same answer on every machine; a Nat1 or Int that fits 55 bits converts by a shift. Speed
   of the fast path is Crockford's claim, a prior; the measured 62 ns per `Decimal` add is in DI-0074.

4. **What it costs.** Range: 55 bits of integer against 4096 decimal digits, a factor of about
   10^4080; an `Int` past 3.6e16 has no DEC64 form and 2^60 already rounds. Exactness: 16 to 17
   digits, so the product of two 9-digit money amounts already overflows the coefficient. A check
   (a wide multiply and a range test) is only avoided where the static bound has proved it.

5. **IEEE decimal64, read from the standard.** ISO/IEC 60559:2020, which is IEEE Std 754-2019
   (sold; resellers list the editions at roughly €89 to €268, not checked against the shops).
   Clause numbers are the standard's; nothing is quoted from it.
   - Table 3.6: decimal64 is 64 bits, 16 digits, `emax` 384 and `emin` 1 − `emax` (clause 3.3),
     so exponents reach about ±384 against DEC64's ±127; a 13-bit combination field and a 50-bit
     trailing significand. Binary or decimal encoding of the significand is the implementation's
     choice and the standard does not say how it is communicated.
   - 3.5.1: a value has a cohort of representations `(s, q, c)` and `(s, q + 1, c / 10)`, and zero
     has one per exponent: DEC64's "not normalised" and its 255 zeros, said with more care, and with
     a sign on zero.
   - Clause 7: five status flags (inexact, underflow, overflow, divideByZero, invalid) with non-stop
     results. A finite non-zero divided by zero is a signed `∞` (7.3); `0 ÷ 0` and `∞ ÷ ∞` are
     invalid and give a quiet NaN (7.2); overflow and inexact results are rounded under the
     rounding-direction attribute. DEC64 has one `nan` for all of it and no flags.
   - Same family: Cowlishaw, Schwarz, Smith and Webb, [A Decimal Floating-point
     Specification](https://www.speleotrove.com/mfc/files/cowlishaw2001-decimal-specification.pdf)
     (IBM, 2001, a proposal that is not the final format) and Cowlishaw's [Arith16
     slides](https://www.speleotrove.com/decimal/decArith16-charts.pdf) (2003): integers have
     exponent 0, equal exponents need no alignment, and without rounding the operations are integer
     operations.
   For FPL the flags are the trap he does not want, so decimal64 adds range and `∞` over DEC64 and
   nothing the kernel can use. Both are plugs with the same obligation: the program's values stay
   inside the plug's range and digits. Which one a target prefers is a question for that target.

6. **Von Neumann on scale factors, read.** Burks, Goldstine and von Neumann, *Preliminary
   discussion of the logical design of an electronic computing instrument* (IAS, 1946), in the HTML
   transcription from von Neumann's Collected Works (1963) at
   [MIT CSAIL](https://people.csail.mit.edu/ledlie/resources/papers/1963/neuman63.html); not
   checked against the 1946 or 1947 print.
   - Section 5.3 gives two reasons for a floating decimal point (keep the significant digits of a
     result; spare the operator the scale factors) and answers that the time spent on scale
     factors is "a very small percentage" of the time to prepare a problem, that the first reason
     is "somewhat illusory" because a floating word spends storage that could carry more digits, and
     that long precision, built from fixed multiples of the word, is harder with floating point.
   - Section 6.6.7 reframes the choice: not built in or unused, but built in or programmed from the
     operations the machine has. Floating point repeats a scale factor in every number where one
     often serves a whole set, and it can be programmed out of shifts when needed.
   Mapped here: DEC64 and decimal64 carry an exponent in every number, the redundancy he names;
   `scaled` below is his one scale factor per set; `exact` is his long precision built from integer
   primitives; a floating plug is something built from the others when a target asks, not a basis.
   Where this differs: he left the scale analysis to the programmer, and here the planner computes
   the bound (point 2).

7. **Plugs, and the hole that chooses.** His wish is that representations of `Dec` sit side by
   side as IEEE floating point does for a smooth sort: each states the conditions under which it
   implements the sort, and a target takes one whose conditions the program meets. That is
   02.04.13's rule applied to `Dec`. The plugs so far: the walker's bignum `Decimal`, DEC64, IEEE
   decimal64, and a scaled `int` (a decimal Q format, DI-0074).

   The planner chooses by the static bound. Where the bound does not decide, the choice is a hole in
   the sense of [02.04.07](../../02.04-explanation/02.04.07-principles-and-privileges.md): the
   compiler narrows it by stating which plugs still satisfy the bounds it could compute, and the
   author closes it by naming the kind of plug. The two ends of one mechanism are the planner
   picking (no hole when the bound decides) and the program pinning (the author closes the hole by
   hand).

   The hole takes the three fields of 02.04.07, section 1.1. *Depends on:* the static bound on
   coefficient digits and exponent, per value. *Default in force:* the smallest plug whose
   conditions the bound satisfies; where the bound is unknown, the exact plug, which is total, so
   an unknown bound costs speed and never correctness. *Closes by:* the author naming a kind, by the
   obligation that separates the plugs and not by their names:
   - `exact`: unbounded digits, no range obligation (the bignum);
   - `fixed`: a fixed word, its range an obligation discharged by the bound (DEC64, decimal64);
   - `scaled`: a fixed word with a static decimal scale, the cheapest and the narrowest.

   Naming one plug (`DEC64`) is a pin and a dispensatie: it closes the hole to a single plug, and if
   the bound does not fit that plug the build fails before it runs, never at run time. A closed
   hole records the kind or pin, the bounds the compiler computed and the plug chosen, in the log
   and in the interface hash (02.04.07, where profiles are part of it).

8. **Rounding is a word, not a kind.** A kind "may round, provided it is shown" would be a trap by
   another name, so there is none. Rounding is an operation the author writes, with a place, as
   `dec64_round(x, -2)` is "to the cent" in Crockford's library; its result is again a `Dec` and
   the operation is total. A program that wants fewer digits writes it, and what it wrote is on the
   page. Not designed here: the word's name and its rounding rule (DEC64 rounds ties away from
   zero, IEEE offers directions).

Outcome: the representation reading, the absence of a trap, the pluggable `Dec`, the hole as the
way to choose and `scaled` as a kind of its own are his. Open: the surface spelling of the three
kinds, whether the planner may split `fixed` between DEC64 and decimal64, the name and rule of the
rounding word, and the static bound of point 2 itself. No code was written; the model and the
converted assembly live outside the repository.

## Related

- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
- related:: [DI-0072](DI-0072-the-division-family.md)
- related:: [DI-0074](DI-0074-a-discrete-basis-dec-rat-and-the-slash-literal.md)
- related:: [02.04.13 numbers, ML and the library](../../02.04-explanation/02.04.13-numbers-ml-library.md)
- related:: [02.04.07 principles, holes and privileges](../../02.04-explanation/02.04.07-principles-and-privileges.md)

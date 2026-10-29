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
`nan` when none does; it models the page, not the assembly, whose last-place behaviour is a prior).
Against `Decimal` at precision 8192 with `Inexact` trapped:

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
relies on is a design to build, and DEC64 is a design question before it is a dependency.

## Options and outcome

1. **Representation or new sort.** [02.04.13](../../02.04-explanation/02.04.13-numbers-ml-library.md)
   answers Crockford's one-number-type with "one specification with representations chosen per
   obligation". DEC64 fits that rule as one representation of the `Dec` sort for a target that
   needs a fixed word. It is not a sort: it has a `nan` and rounds, both of which the kernel
   excludes. The kernel stays discrete and
   unbounded; DEC64 is below it. Prior: representation.
2. **The obligation a DEC64 target must discharge.** `Dec` closes under `+ − ×` and refuses `÷`
   that leaves ℤ[1/10]. DEC64 differs in four places, each one an obligation: (a) rounding must be
   refused, not applied (the target computes in a wider word and checks that the coefficient fits
   55 bits and the exponent −127..127, else it takes the error path, not `nan`); (b) one `nan` for
   overflow and division by zero must become two different failures; (c) `0 × nan` is `0`, so the
   target must never form a `nan` into a multiplication, or the refusal in (b) is lost; (d)
   magnitudes under 1e-127 must fail, not round to 0. With these, a program that runs on the walker
   and on the DEC64 target either gives the same value or fails on the target only through range,
   which is the bound that 02.04.13 already says a representation owes ("its error bound as an
   obligation"). Prior: this is the sound reading; DEC64's own rounding is then never used, and
   what is left of DEC64 is the layout and the integer fast path.
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
5. **IEEE 754-2008 decimal64**, the standard cousin (16 digits, a decimal exponent, several NaNs,
   inexact and other status flags, two encodings): not read from the standard in this note
   (paywalled), so a prior; it has the status flags DEC64 lacks, which suits obligation (a). Whether
   a target should prefer it over DEC64 is a later question, to be measured on a target.
6. **Decision for him.** Keep DEC64 as a named candidate target form of `Dec`, to be taken up when
   a compiled target needs a fixed-width decimal (no change to the kernel or the lattice now), or
   drop it. Not decided; the lean in DI-0074 (Dec above Int, below Rat) is untouched either way.

Outcome: open. No code was written; the model lives outside the repository.

## Related

- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
- related:: [DI-0072](DI-0072-the-division-family.md)
- related:: [DI-0074](DI-0074-a-discrete-basis-dec-rat-and-the-slash-literal.md)
- related:: [02.04.13 numbers, ML and the library](../../02.04-explanation/02.04.13-numbers-ml-library.md)

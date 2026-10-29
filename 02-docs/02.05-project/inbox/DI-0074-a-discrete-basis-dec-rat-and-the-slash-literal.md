---
type: Note
title: "DI-0074 A discrete basis: Dec, Rat written 1/3, and FPL_smooth derived"
description: "no floats in the kernel of FPL; Dec and Rat as the exact sorts under Number; whether 1/3 can be a literal while / is the path separator; FPL_smooth stays the derived variant for differentiation"
status: draft
date: 2026-10-29
related: []
---

# DI-0074 A discrete basis: Dec, Rat written 1/3, and FPL_smooth derived

## His words

> heeft python toegang tot fixed point arithmetic en kan dat makkleijk op deze machine (ik vraag dit voor fpl)

On the proposal to split `Number` into `Dec` (what `Decimal` is today) and a dyadic form, and to give `Rat` its literal with `/`:

> meet ja dec is handig en rat via `/` lijkt me ook handig (hoop dat het niet clasht met de scoping)

> Ik ben deze chat begonnen omdat floating point gezeik geeft... en zoals elders met andere agents besproken (niet alleen claude agents) willen we dat de basis van FPL discrete is zodat we er al onze bewijsvoerings zooi op kunnen doen en dat een `fpl_smooth` variant ons altijd dfifferentiatie kan geven (als we dat nodig gaan hebben) buiten algebraische differentiatie etc om

## Context

Said in a side chat on 2026-10-29, after [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
decided `nat` and the sorts commit (30b7a5e) split the literals into Nat1, Zero, Neg1 and
Number, with Rat reserved. Everything below is measured on this machine unless marked a prior.

**What Python gives, without installing anything** (Python 3.13.15 from nix, libmpdec 4.0.1):

| route | module | what it is | `0.1 + 0.2` | ns per add |
|---|---|---|---|---|
| decimal fixed point | `decimal.Decimal` | ℤ[1/10] with a context: precision, rounding, traps | `0.3` exact | 62 |
| binary fixed point | `int` scaled by 2^k | ℤ[1/2^k]; unbounded, so no overflow | `0.1` is not dyadic, rounds to 0.100006 in Q16.16 | 13 |
| rationals | `fractions.Fraction` | ℚ | `3/10` exact | 384 |

The bootstrap already uses the first: `desugar` reads `1.5` as `Decimal("1.5")` (exact as
written, up to `DIGITS = 4096` digits), FON has `Num`, "an exact decimal", and the codec tags a
`Decimal` with its text. `fxpmath` 1.4.1 (bounded Q formats on numpy) is in nixpkgs, not
installed; a bounded Q format is twenty lines on `int` if a target needs one. Any dependency
enters through `flake.nix`.

**Closure.** Dec closes under `+ − ×` when the precision is at least the digits of both operands
(a product of two 21-digit decimals trips `Inexact` at the default prec 28; prec 8192 covers
two literals); only `÷` leaves ℤ[1/10], and the `Inexact` trap turns that into a hard error
instead of a silent rounding. Rat closes under all four by a nonzero divisor. The dyadic form
has the shape of Dec with 2 for 10. All three are discrete: countable, exact, decidable
equality, so proofs run on them; a float is the only representation out.

**The contradiction with DI-0070.** DI-0070 says: no decimal point in the normal form of FPL or
FON, floats in a power-of-two base. FON today has `Num` with a point. Dec is ℤ[1/10], the
power-of-two base is ℤ[1/2^k], and `0.1` is in the first and not the second. So "dec is handig"
and DI-0070 force one of three readings; his line above is a lean, not a decision.

**The `/` clash is real and specific.** `/` is the path separator: `err/<tag>`
([02.03.01](../../02.03-reference/02.03.01-errors.md)), `../out/console` and positional paths
like `norm/3/ensure` ([02.04.05](../../02.04-explanation/02.04.05-syntax-rationale.md)), and a
bare `/` is escalation (02.04.05 row 15). The lexer's shape rule makes `1/2` the path
`('1', '2')` today, pinned by `tests/test_lex.py` and the lex page (`01.02.01-lex.md`, "a body
with a `/` is a path"). FON refuses `1/2` as a non-canonical number (`tests/test_fon.py`). So the
lexer and FON already disagree on what shape `1/2` has. On the walker, `1/3` is `unknown word:
1/3` and `1 / 3` is `unknown word: /`. No path in the corpus, the docs or the tests is two bare
digit segments without a sigil (a grep finds only prose fractions such as `29/29`).

**`FPL_smooth` is already recorded.** [02.04.13](../../02.04-explanation/02.04.13-numbers-ml-library.md)
(2026-09-28) has "`FPL_smooth` stays derived": a word is in it iff its primitives' derivative
obligations close at the type's denotational model; fixed point is a representation of ℝ, not a
subset of `FPL_smooth`; laws discharge exactly in ℤ[1/2^k]; complex over duals gives
complex-step differentiation. His words confirm that design, they do not add to it. The doc
spells it `FPL_smooth`, he writes `fpl_smooth`: one name, no second one.

## Options and outcome

1. **Dec against DI-0070**, one of: (a) Dec is a surface spelling that normalises to Rat
   (`0.1` is `1/10`; no Dec sort; FON's `Num` goes); (b) DI-0070's "no decimal point" is about
   floats only, Dec keeps its own normal form and sort; (c) DI-0070 is revised. Prior: (b) is the
   smallest change to the code that exists; (a) is the smallest lattice.
2. **The Rat literal.** The shape rule gains one line before the path rule: no sigil and
   `-?\d+/\d+` is a number. Any sigil keeps it a path (`./3/4`, `../a/b`), and positional paths
   carry a name segment, so nothing in the corpus moves. The division word cannot be `/`, that
   glyph is escalation; the word is [DI-0072](DI-0072-the-division-family.md)'s question.
3. **Canonical form**, by [DI-0013](DI-0013-strict-readers-one-value-one-spelling.md) and FON's
   canonical rule: `2/4`, `+1/2`, `1/-2` refused or normalised to `1/2`, `1/2`, `-1/2`; `1/0`
   refused at the lexer. The denominator is a Nat1, the sort 30b7a5e made so that "a Nat1 divisor
   is never zero".
4. **The lattice**, prior: Nat1, Zero, Neg1 under Nat0, Neg0, Int; Int rises to Dec and to the
   dyadic sort if it exists; both rise to Rat; Number is what is left (`∞`, `π`) or goes.
5. **Float.** Out of the kernel. Where a target needs IEEE, it is a representation under
   02.04.13's rule, with its error bound as an obligation.

Outcome: open. The three Python routes are all stdlib, so none of this waits on a dependency.

## Related

- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
- related:: [DI-0072](DI-0072-the-division-family.md)
- related:: [DI-0013](DI-0013-strict-readers-one-value-one-spelling.md)
- related:: [02.04.13 numbers, ML and the library](../../02.04-explanation/02.04.13-numbers-ml-library.md)
- related:: [02.04.05 syntax rationale](../../02.04-explanation/02.04.05-syntax-rationale.md)
- related:: [02.03.01 errors](../../02.03-reference/02.03.01-errors.md)

---
type: ADR
title: "ADR-0015 Modifiers take the word before them; quotations stay for what does not pervade"
description: "Draft of the maintainer's position of 2026-10-31: a word that runs over atoms pervades; a modifier applies to the word written before it (J, Uiua), so filtering and folding need no quotation; a quotation remains for a non-pervasive word per item or a multi-word body. Options recorded, decision pending."
tags:
  - adr
status: draft
rejected: false
date: 2026-10-31
deciders:
  - "psjg"
supersedes: []
superseded-by:
related:
  - ../notes/02.05.16-array-models.md
  - ../inbox/DI-0072-a-line-of-numbers-and-a-word.md
affects:
  - ../../02.04-explanation/02.04.05-syntax-rationale.md
  - ../../../03-fpl/words-on-strands.md
drivers:
  - "succinctness: a short expression that is the algorithm, the array family's reason to exist"
  - "the maintainer finds [ ] and [quote] ugly"
  - "fixed valence per glyph: arity must stay a running sum over tokens (02.04.05 point 71)"
  - "do not paint into a corner: the values must not change, only what words may take"
options:
  - name: "Quotations everywhere (Joy, Factor, the walker today; S32: modifiers are words on a quotation)"
    chosen: false
    pros: ["no grammar", "one mechanism for thunk and code"]
    cons: ["a pair of brackets per higher-order use", "the maintainer finds it ugly", "pervasion already makes [1 +] each redundant"]
  - name: "Pervasion plus modifiers on the preceding word (J adverbs, Uiua modifiers); quotations only where nothing pervades"
    chosen: false
    pros: ["filter, count, sum need no quotation and no dup", "the modifier's effect follows from the word's effect, as J's rank table gives +/ from +", "both a specific form (keep applies its predicate) and a general one (a by-like modifier before any word) exist in Uiua"]
    cons: ["a new part of speech in the grammar", "a word used as a modifier's operand must not run; the grammar, not the stack, decides that"]
  - name: "Ordinary words that sometimes take a word"
    chosen: false
    pros: ["no new part of speech"]
    cons: ["every name gets two readings; fixed valence per glyph no longer holds; this is the corner"]
---

# ADR-0015 Modifiers take the word before them; quotations stay for what does not pervade

- related:: [02.05.16 Array models](../notes/02.05.16-array-models.md)
- related:: [DI-0072 A line of numbers and a word](../inbox/DI-0072-a-line-of-numbers-and-a-word.md)
- affects:: [02.04.05 Syntax rationale](../../02.04-explanation/02.04.05-syntax-rationale.md)
- affects:: [Words on strands](../../../03-fpl/words-on-strands.md)

## Context

The array-model survey ([02.05.16](../notes/02.05.16-array-models.md)) put eleven languages to
the question how a word reaches into a value of higher rank. The dynamic array languages all
pervade scalar words; where a word does not pervade they differ: J makes rank a property of
every verb and resets it with the conjunction `"`; Dyalog and BQN add a rank operator over a
nested model; Uiua uses modifiers that take the following word, with static numeric
subscripts for rank; K and APL2 have each; Futhark, Dex and Julia write `map`, `for` or the
dot. The walker today takes Joy's route: `each`, `scan` and `fold` demand a quotation
("a quotation is expected"), and [02.04.05](../../02.04-explanation/02.04.05-syntax-rationale.md)
S32 records it: "modifiers are words on a quotation (`[+] fold`, `[f] each`, ...)".

The maintainer's words of 2026-10-31, in the design chat: the Uiua and J syntax is the
picture he aims at, "pervasiveness met die modifiers"; he finds `[ ]` and `[quote]` ugly; a
modifier should apply the predicate itself so filtering needs no `dup`, "tenzij ons dit een
hoek in schildert"; and both the specific and the general form are wanted: "eigenlijk geeft
me dat wel de wil het verlangen de zin om beide te suporten". He also asked that the
precedent be written down here.

The precedent, read from Uiua's own source (`parser/src/defs.rs`, 2026-10-29 copy): `keep`
(`▽`) is an ordinary word on a mask and an array, and the general modifier `by` (`⊸`) is
"Call a function but keep its last argument after its outputs"; its doc adds "[by] can be used
with [keep] to do simple filtering", example `F ← ▽⊸<`. J spells the same general form as a
hook, `(#~ even)`. The quotation stays in both languages for a multi-word body (Uiua's
`( )`), and FPL already has the off-side block as its main quotation form and the S34 lambda
with binders for a body with named inputs.

The syntax hand-off of 2026-09-27 ("Parsimony in programming languages", the design
conversation that preceded 02.04.05) already named this as an open step: "fix a stack-effect
discipline for head lines with children (an explicit ⊸-style 'under the quotation' modifier
would remove the →k workaround)", and listed "Ragged carrier vs the fast path" and "Shape
polymorphism. Arity inference is trivial; rank/shape in types is not" among what was still
open. The 2026-10-31 position answers the first and leaves the other two to [02.05.16](../notes/02.05.16-array-models.md).

What keeps the second option out of the corner: modifiers are their own part of speech
(J's adverbs and conjunctions, Uiua's modifier glyphs), so the grammar knows at `even? keep`
that `keep` takes the word, not its result, and the effect of the pair follows from the
effect of `even?` without running it. The third option gives one name two readings and is
refused by "fixed valence per glyph".

## Decision

None yet. The second option is the maintainer's stated preference; the specific and the
general modifier are both to be supported; the spelling of the modifier class and its
place in the grammar are open. The checks that the choice must satisfy are written as
`L |- R` lines in [Words on strands](../../../03-fpl/words-on-strands.md).

## Consequences

Once taken: S32 is revised (a modifier is a word on a word, a quotation is the operand only
where the body is more than one word); `each`, `scan` and `fold` accept a word as well as a
quotation; a mask word and a general argument-keeping modifier enter the prelude; the
grammar gains a part of speech whose arity is still a running sum. Refused: a word that is
sometimes a modifier.

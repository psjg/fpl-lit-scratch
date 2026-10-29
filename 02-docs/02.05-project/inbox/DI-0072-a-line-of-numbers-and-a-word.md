---
type: Note
title: "DI-0072 A line of numbers and a word: reduce, map, zip, and rank in the type"
description: "`1 2 3 4 +` reduces, `1 2 3 4 + 1` maps, `1 2 3 4 + 4 3 2 1` zips; what `|` is; is rank part of a list's type"
status: draft
date: 2026-10-29
related: []
---

# DI-0072 A line of numbers and a word: reduce, map, zip, and rank in the type

## His words

> probleem dat ik heb is dat ik zou willen dat: 1 2 3 4 +   |- 10 : Nat1 / 1 2 3 4 + 1 |- [2 3 4 5] : [Nat1 : [4]] ; idk hoe lijst type notatie zou moeten... is de dimensionaliteit van een lijst onderdeel van diens type? god... / 1 2 3 4 + 4 3 2 1 |- [5 5 5 5] : [Nat1 : [4]] / ik weet niet of dit ons zou lukken maar he... / dan hebben we dus een combinatie van lisp reductie / implicit map een array taal en een postfix taal dat was waar dat hele underflow concept voor bedoelt was... / idk of we dit kunnen pulen zonder de taal te verneuken... / `|` was bedoelt om dat te fixen maar dat doet het nu niet... / `1 1 + |- [1 1 +]` zegmaar `|` leest nu als een verkapte applicatie operator oid

> kijk ik wil gewoon wat APL ons geeft in veel van die gevallen dyadische operatoren kunnen impliciet mappen en anders ook reduceren (lisp) of juist een vector add zijn (wat het punt is van de array talen)

On the bar:

> wel iets interresnats wat `1 | 1 +` == `1 [ 1 + ]` maar ook `[ 1 ] 1 +` en == `[ 1 ] [ 1 + ]` `|` is eigenlijk een soort van macro voor `] [` idk of dat begrijpelijk is

On the end of a line:

> ok hier wordt het whack misschien is het einde van de regel wel een soort van impliciete operator die kijkt naar de regel en haar mogelijke frames met `[ ... ]`. en `|` zodat we dat zo makkelijker maken voor onszelf?

On `1 1 + |- [1 1 +]`:

> zou gelezen worden als een judgement test line weet je dus dat zou een error moeten geven als L != R voor `L |- R` idk of dat elegant en consistent is

> nee die laatste kolom moet dus iets worden als `|- ! err/<> ""`

## Context

Measured on the pad branch, the walker's REPL on stdin, with the values he wants beside
them (his column, 2026-10-29):

    line                        today                      desired
    1 2 3 4 +                   [ 1 2 3 4 + ]              10
    1 2 3 4 + 1                 [ 1 2 3 4 + 1 ]            2 3 4 5
    1 2 3 4 + 4 3 2 1           [ 1 2 3 4 + 4 3 2 1 ]      5 5 5 5
    1 1 +                       [ 1 1 + ]                  2
    1 | 1 +                     2                          2
    [ 1 2 3 4 ] +               [ [ 1 2 3 4 ] + ]          10
    1 2 | 3 4                   1 2 | 3 4                  1 2 | 3 4
    1 1 + |- [1 1 +]            [ 1 1 + ] [ - [ 1 1 + ] ]  |- ! err/<> ""
    1 | 1 2 3 +                 2 3 4                      2 3 4
    1 2 3 4 | +                 1 2 3 4 [ + ]              10
    1 2 3 4 | 1 +               2 3 4 5                    2 3 4 5
    1 2 3 4 | 4 3 2 1 +         5 5 5 5                    5 5 5 5
    4 3 2 1 | 1 2 3 4 +         5 5 5 5                    5 5 5 5
    1 2 3 4 [+] fold            10                         10
    1 2 3 4 | + fold            1 2 3 4 [ + fold ]         10
    1 2 3 4 [1 +] each          2 3 4 5                    2 3 4 5

The forms he equates with `1 | 1 +`, today:

    1 [ 1 + ]                   1 [ 1 + ]
    [ 1 ] 1 +                   ERROR: 1:9 arithmetic on a non-number
    [ 1 ] [ 1 + ]               [ 1 ] [ 1 + ]

Why the walker does this. A bare line is one frame (`grammar.lark`: `frames: frame (_BAR
frame)*`). Literals side by side in a frame strand into one value (`desugar.py`,
`frame()`). `+` then meets one value and underflows, and an unsaturated frame is pushed as a
quotation: the rule of [02.04.05](../../02.04-explanation/02.04.05-syntax-rationale.md)
("a word missing an argument suspends the frame into a section, never errors"). The bar is a
self-delimiting token that opens a frame with its own stack; underflow in that frame reaches
the values to its left (02.04.05, "the bar `x | frame` is Levy's push"). So the bar is not an
application operator: it is the boundary that lets a frame reach out. `|-` lexes as a bar and
the word `-` ([DI-0041](DI-0041-turnstile-literate-vs-decision-disagree.md) measured this).
Two of his three examples work today with the bar between strand and operand: the map
(`1 2 3 4 | 1 +`) and the zip (`1 2 3 4 | 4 3 2 1 +`). The reduce is
[DI-0018](DI-0018-binary-word-over-strand-acts-as-fold.md), open.

The tension with APL: APL is infix, so in `1 2 3 4 + 1` the `1` stands right of the word.
In postfix the `1` arrives after `+` has run. Either the line is read as a whole (his
end-of-line operator: on a bare line a word between two literal runs is dyadic over both
runs), or the second operand keeps needing the bar.

The fail judgment he remembers, `(form) |- ! err/suberr/subsuberr <form>`, is locked in
[02.03.01](../../02.03-reference/02.03.01-errors.md) as `|- ! err/<tag> : Error [@ n]`:
`!` the fail marker, `err/<tag>` a path (so sub-tags nest with `/`), `@ n` the deadline;
sketch in [02.04.03](../../02.04-explanation/inspiration/02.04.03-judgments.md). Not
printed yet; the TTY writes `ERROR: l:c message`. The locked shape has no left side; whether
the input form stands on the line is open.

## Options and outcome

Four clusters, each with its cost:

1. **Reduce.** A binary arithmetic word meeting one strand with nothing under it folds over
   the strand's items (DI-0018). Covers `1 1 +`, `1 2 3 4 +`, `[ 1 2 3 4 ] +`,
   `1 2 3 4 | +`. Evaluator only, no grammar. Open: fold direction, visible on `-` over
   `1 2 3`: left `((1-2)-3)` is -4, APL right `1-(2-3)` is 2.
2. **The line as operator.** The newline reads the whole bare line; its frames are what
   `[ ... ]` and `|` give; a word between two literal runs is dyadic over both (map when one
   side is a scalar, zip when both are strands). Covers `1 2 3 4 + 1` and
   `1 2 3 4 + 4 3 2 1`. Desugar at `Line` level, no grammar, evaluator unchanged if the line
   is rewritten into existing words. On a line with two words his answer (10-29) is
   `1 2 + 3 * |- 9 : Nat1`: the line reads left to right, each word dyadic over the run
   before it and the run after it, so `(1 2 +) 3 *`. Open: words of other arity. His bar-as-`] [` reading belongs here: every top-level quotation on a line
   runs. Alternative: the bar stays required for the second operand.
3. **`|-` on an input line as a check.** `L |- R` evaluates both sides; unequal gives the
   fail judgment `|- ! err/<tag> "..."`. Needs `|-` as a token (DI-0041's lexer route) and
   the fail printer (02.03.01). Ties to DI-0023.
4. **Rank in the type.** (a) element sort only, the shape is a value, what `types.py` does
   now; (b) rank in the sort, Remora-style, the result line gets a list notation; (c) the
   full shape, his `[Nat1 : [4]]`, "strands of unequal length" becomes a static error, lengths
   known at elaboration. Sort names are decided in DI-0070.

Outcome: open. Step 1 is the reduce, once he picks the direction.

## Related

- related:: [DI-0018](DI-0018-binary-word-over-strand-acts-as-fold.md)
- related:: [DI-0023](DI-0023-repl-results-as-judgement-claims.md)
- related:: [DI-0041](DI-0041-turnstile-literate-vs-decision-disagree.md)
- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
- related:: [02.04.05 syntax rationale](../../02.04-explanation/02.04.05-syntax-rationale.md)
- related:: [02.03.01 errors](../../02.03-reference/02.03.01-errors.md)

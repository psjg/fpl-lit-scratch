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

The September design chat ("2 CAESURA", 2026-09-26 to 29) decided the bar and
underflow model the walker implements, measured 10-29 on 88 rules read from it: the
frame on its own stack, literals strand and names never do, underflow is currying, a
section with nothing below stays a quotation, sections apply downward only (the
"force-apply on the next value" idea was dropped there), the bar reads as infix operand
order (`1 | 1 2 3 -` is `0 -1 -2`). All of these match the walker. Not implemented from
that chat: the commute `˜` (`1 | 1 2 3 -˜`), `curry` and `lcurry`, the REPL printing a
section with its effect (`[1 2 3 -] : n -- ns`), `;` as the fallback glyph, and the check
cells `⊨` and `⊢`. So his wishes above (a bare `1 2 3 4 +` reducing, map and zip without
the bar, the line as operator) are new against that chat, not a regression of it.

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
   `1 2 3`: left `((1-2)-3)` is -4, APL right `1-(2-3)` is 2. His words (10-29): "ja dat is
   een goede waar ik idd nog weinig over heb nagedacht.. wat is het meest elegant voor een
   wiskundige / geeft het minste hoofdpijn in een arrayytaal? hoe doen de andere array talen
   anast APL het? uh wat doen numpy blas etc?" and, on Julia keeping `reduce` free of a
   direction with `foldl` and `foldr` apart: "dit is precies wat ik net zat te typen! we
   moeten reduce waarschijnlijk uitsplitsen in een foldr en een foldl hoewel ik niet weet
   wat dat betekent in een postfix taal zoals FPL". Measured: in postfix the left fold is
   the word between the items (`1 | 2 - | 3 -` is -4) and the right fold the word after
   them, repeated (`1 | 2 | 3 - -` is 2); `[-] fold` today is the left fold (-4). So a
   word after a strand abbreviates `- -` after it, the right fold, and the lisp reading
   `(- 1 2 3)` abbreviates the word between. His addition (10-29): "en de ambitie voor FPL
   is dat we ook lazy zouden zijn dat compiceert de folds ook (dat doet het iig in
   haskell)".
2. **The line as operator.** The newline reads the whole bare line; its frames are what
   `[ ... ]` and `|` give; a word between two literal runs is dyadic over both (map when one
   side is a scalar, zip when both are strands). Covers `1 2 3 4 + 1` and
   `1 2 3 4 + 4 3 2 1`. Desugar at `Line` level, no grammar, evaluator unchanged if the line
   is rewritten into existing words. On a line with two words his answer (10-29) is
   `1 2 + 3 * |- 9 : Nat1`: the line reads left to right, each word dyadic over the run
   before it and the run after it, so `(1 2 +) 3 *`. His two readings of that line
   (10-29, verbatim): "kijk eignenlijk kan dit dus in FPL gelezen worden als `[[1 2 +] 3 *]`
   in die zin dus als een soort postfix lisp anderzijds zou het ook moeten lezen als
   `1 2 + | 3 *`". So a bare line nests like a postfix lisp, and the bar form says the
   same. Open: words of other arity. His bar-as-`] [` reading belongs here: every top-level quotation on a line
   runs. Alternative: the bar stays required for the second operand.
3. **`|-` on an input line as a check.** `L |- R` evaluates both sides; unequal gives the
   fail judgment `|- ! err/<tag> "..."`. Needs `|-` as a token (DI-0041's lexer route) and
   the fail printer (02.03.01). Ties to DI-0023.
4. **Rank in the type.** (a) element sort only, the shape is a value, what `types.py` does
   now; (b) rank in the sort, Remora-style, the result line gets a list notation; (c) the
   full shape, his `[Nat1 : [4]]`, "strands of unequal length" becomes a static error, lengths
   known at elaboration. Sort names are decided in DI-0070.

What the other languages do with `-` over `1 2 3`, read 10-29 from each one's own
reference (docs) or run (measured):

    APL (Dyalog)      2    right fold    docs      help.dyalog.com, Reduce: R ←→ ⊂(1⊃Y)f(2⊃Y)f...f(n⊃Y), right to left
    J                 2    right fold    docs      jsoftware.com dictionary d420, Insert
    BQN               2    right fold    docs      mlochbaum.github.io/BQN/doc/fold.html, "Fold performs a right fold"
    Uiua              2    left fold     docs      reduce goes left to right, but subtract is second minus first
    K / q             -4   left fold     docs      code.kx.com/q/ref/accumulators, Over feeds the result back as the left argument
    NumPy, Python     -4   left fold     measured  functools.reduce; ufunc.reduce is r = op(r, a[i])
    Common Lisp       -4   left fold     measured  CLHS reduce: left-associative unless :from-end
    Haskell           -4 / 2             measured  foldl1 (-) gives -4, foldr1 (-) gives 2
    Julia             undefined          docs      Base.reduce: "The associativity of the reduction is implementation dependent"; foldl, foldr apart
    BLAS              no general reduce            only associative sums (asum, dot, nrm2)

Haskell's laziness, read from the base library docs and measured with GHC 9.14 at -O0:
`foldr` ends on an unbounded list when the operator is lazy in its right argument
(`take 3 (foldr (:) [] [1..])` gave `[1,2,3]`); `foldl` builds "a thunk chain O(n)
elements long" (`foldl (-) 0 [1..1000000]` overflowed a 1 MB stack, `foldl'` gave the
sum); the docs say "you always want to use either foldl' or foldr instead".

The rule in the array family: the fold follows the reading direction of the language
(APL, J, BQN read right to left and fold from the right; K, Lisp, Python read left to
right and fold from the left). FPL reads left to right. In postfix both folds are plain
sequences: the word between the items is the left fold, the word after them, repeated,
the right fold.

Decided 10-29 on the direction, his words: "sws uitsplitsen rechts lijkt me beter voor nu
als default.. misschien moeten we echter data blijven vezamelen om te kijken wat beter is en
dit als een openvraag houden waarbij we ook de andere optie open houden". So: `foldl` and
`foldr` as two words beside `fold`; a bare word after a strand is the right fold for now;
the direction stays an open question with the other option kept, data to be gathered.

Outcome: cluster 1 in progress (the reduce, right fold); the rest open.

## Related

- related:: [DI-0018](DI-0018-binary-word-over-strand-acts-as-fold.md)
- related:: [DI-0023](DI-0023-repl-results-as-judgement-claims.md)
- related:: [DI-0041](DI-0041-turnstile-literate-vs-decision-disagree.md)
- related:: [DI-0070](DI-0070-nat-number-and-the-base-of-a-float.md)
- related:: [02.04.05 syntax rationale](../../02.04-explanation/02.04.05-syntax-rationale.md)
- related:: [02.03.01 errors](../../02.03-reference/02.03.01-errors.md)

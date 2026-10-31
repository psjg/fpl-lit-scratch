---
type: Note
title: "A line of numbers"
description: "An in-language test suite for reduce, map, zip, the bar and the line as operator, each line written L |- R."
---

# A line of numbers

This note is the test suite of [DI-0072](../02-docs/02.05-project/inbox/DI-0072-a-line-of-numbers-and-a-word.md), written in FPL. Here `|-` is the check of DI-0072: `L |- R` evaluates both sides, and unequal sides are an error. The walker reads `|-` as a check since 2026-10-29; `01-bootstrap/tests/test_line_of_numbers.py` still runs each row the long way: the output of `L` must be `R`. A row the walker cannot meet today is the target and is listed in that file as a strict expected failure, so a row that starts to pass turns the suite red until its entry goes.

## Reduce

A binary word over one strand with nothing under it folds over the strand. The bar and `fold` spellings must give the same sum. On `-` over `1 2 3` the direction shows: the bare word is the right fold `1-(2-3)`, which is 2, the default of DI-0072 with the direction left open.

```fpl
1 2 3 4 + |- 10
1 2 3 + |- 6
1 2 3 - |- 2
[ 1 2 3 4 ] + |- 10
1 2 3 4 | + |- 10
1 2 3 4 [+] fold |- 10
1 2 3 4 | + fold |- 10
```

## Folds

The words `fold`, `foldl` and `foldr` name the direction. `fold` stays the left fold, as it is today, and `foldr` is the right fold; `scan` keeps the running left fold. In the bar form the left fold is the word between the items and the right fold is the word after them, repeated.

```fpl
1 2 3 [-] fold |- -4
1 2 3 [-] foldl |- -4
1 2 3 [-] foldr |- 2
1 2 3 4 [+] foldr |- 10
1 2 3 [-] scan |- 1 -1 -4
1 | 2 - | 3 - |- -4
1 | 2 | 3 - - |- 2
```

## Map

A word with a strand on one side and a scalar on the other maps over the strand.

```fpl
1 2 3 4 + 1 |- 2 3 4 5
1 2 3 4 | 1 + |- 2 3 4 5
1 2 3 4 [1 +] each |- 2 3 4 5
```

## Zip

A word between two strands of equal length combines them item by item.

```fpl
1 2 3 4 + 4 3 2 1 |- 5 5 5 5
1 2 3 4 | 4 3 2 1 + |- 5 5 5 5
4 3 2 1 | 1 2 3 4 + |- 5 5 5 5
```

## The bar

The bar opens a frame that reaches the values to its left. These lines come from DI-0072 and from the September design chat; the chat had `1 2 3 - | 1` as `[ 1 2 3 - ] 1`, a section then a value, and the fold rule of DI-0072 makes the first frame `2`. The row therefore reads `2 | 1`: two values, since `2 1` would strand into one.

```fpl
1 | 1 + |- 2
1 2 | 3 4 |- 1 2 | 3 4
1 | 1 2 3 + |- 2 3 4
2 | 3 + |- 5
1 | 1 2 3 - |- 0 -1 -2
1 2 3 - | 1 |- 2 | 1
1 - |- [ 1 - ]
```

## The line as operator

A bare line is read left to right, each word dyadic over the run before it and the run after it, so this line is `(1 2 +) 3 *`. The walker spells multiplication `times` today; `*` is the spelling of DI-0072.

```fpl
1 2 + 3 * |- 9
1 | 2 + | 3 times |- 9
1 2 + | 3 times |- 9
```

The second and third lines are the bar form of the same line, which the walker meets today.

## Prefix

By [DI-0073](../02-docs/02.05-project/inbox/DI-0073-parens-are-the-prefix-notation-fpl-is-a-lisp.md) parentheses are the prefix notation, so `(+ 1 2)` is `1 2 +`. The last row is the postfix reading of the line `1 2 + 3 *` as nested quotations that run, and it is open.

```fpl
(+ 1 2) |- 3
(+ (times 2 3) 4) |- 10
( times 3 (+ 1 2) ) |- 9
[ [ 1 2 + ] 3 times ] ! |- 9
```

## The check line

The line `1 1 + |- [1 1 +]` compares the value 2 with a quotation. The sides differ, so the line must fail with the judgement `|- ! err/<> ""`. The row `1 1 + |- 2` is the same line with the right side that holds. The failing line `1 1 + |- 3` is not a row, because a row that must fail cannot sit in a suite of passing rows.

```fpl
1 1 + |- 2
1 1 + |- [1 1 +]  ; desired result: |- ! err/<> ""
```

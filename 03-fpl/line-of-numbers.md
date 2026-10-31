---
type: Note
title: "A line of numbers"
description: "An in-language test suite for reduce, map, zip, the bar and the line as operator, each line written L |- R."
---

# A line of numbers

This note is the test suite of [DI-0072](../02-docs/02.05-project/inbox/DI-0072-a-line-of-numbers-and-a-word.md), written in FPL. Here `|-` is the check of DI-0072: `L |- R` evaluates both sides, and unequal sides are an error. The walker does not read `|-` as a check yet, so this note is the target and is red today.

## Reduce

A binary word over one strand with nothing under it folds over the strand. The bar and `fold` spellings must give the same sum.

```fpl
1 2 3 4 + |- 10
1 1 + |- 2
[ 1 2 3 4 ] + |- 10
1 2 3 4 | + |- 10
1 2 3 4 [+] fold |- 10
1 2 3 4 | + fold |- 10
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

The bar opens a frame that reaches the values to its left. These lines come from DI-0072 and from the September design chat.

```fpl
1 | 1 + |- 2
1 2 | 3 4 |- 1 2 | 3 4
1 | 1 2 3 + |- 2 3 4
2 | 3 + |- 5
1 | 1 2 3 - |- 0 -1 -2
1 2 3 - | 1 |- [ 1 2 3 - ] 1
1 - |- [ 1 - ]
```

## The line as operator

A bare line is read left to right, each word dyadic over the run before it and the run after it, so this line is `(1 2 +) 3 *`. The walker spells multiplication `*` since 2026-10-31, as DI-0072 does (`times` before).

```fpl
1 2 + 3 * |- 9
```

## The check line

The line `1 1 + |- [1 1 +]` compares the value 2 with a quotation. The sides differ, so the line must fail with the judgement `|- ! err/<> ""`.

```fpl
1 1 + |- [1 1 +]  ; desired result: |- ! err/<> ""
```

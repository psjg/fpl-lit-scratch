---
type: Note
title: "Words on strands"
description: "An in-language test suite for the maintainer's picture of 2026-10-31: pervasion and modifiers over quotations, a bare word over a strand reduces, foldl and foldr beside it, * beside times, a mask word for filtering, ! as the fail marker. Each line is L |- R."
---

# Words on strands

This note is the target the maintainer drew on 2026-10-31 in the array-model discussion
([02.05.16](../02-docs/02.05-project/notes/02.05.16-array-models.md)), written as checks the
way [A line of numbers](line-of-numbers.md) writes DI-0072: `L |- R` evaluates both sides and
unequal sides are an error. The walker does not read `|-` as a check yet, so this note is red
today and names what is still missing. Word names that do not exist yet (`even?`, `keep`,
`foldl`, `foldr`, `apply`) are provisional spellings, not decisions; the behaviour is the
decision.

## Multiplication has the glyph spelling

`*` replaces `times` (walker and corpus, 2026-10-31; S32 had spelled APL verbs in English).

```fpl
2 3 * |- 6
1 2 3 4 | 1 2 3 4 * |- 1 4 9 16
```

## A bare word over one strand reduces

A strand of five is one value; `+` over it is the sum, not a section.

```fpl
1 2 3 4 1 + |- 11
1 2 3 4 + |- 10
```

## The two folds beside the bare one

The bare word is the right fold for now (DI-0072); `foldl` and `foldr` name the direction.

```fpl
1 2 3 [-] foldr |- 2
1 2 3 [-] foldl |- -4
```

## Pervasion reaches every atom

A unary word over a strand runs on each atom and gives a strand back; a mask is a strand of
booleans.

```fpl
1 2 3 4 even? |- 0 1 0 1
1 2 3 4 dup * |- 1 4 9 16
```

## A modifier takes the word, not its value

The maintainer's picture is Uiua's and J's: a modifier applies to the word written before it,
so filtering needs no quotation and no `dup`. Uiua spells the general form `▽⊸<`: `keep` is a
word on a mask and an array, and `by` (`⊸`) runs a function "but keep its last argument after
its outputs". Both the specific form (`keep` applies its predicate) and the general one (a
`by`-like modifier before any word) are wanted; the spelling below is the specific one.

```fpl
1 2 3 4 even? keep |- 2 4
```

## Masks compose with the reduce

Counting and summing need no higher-order word at all.

```fpl
1 2 3 4 even? + |- 2
1 2 3 4 dup * + |- 30
```

## The quotation stays for what does not pervade

A multi-word body or a non-pervasive word per item is still a quotation: the indented block,
inline `[ ]`, or a lambda with binders (S34).

```fpl
1 2 3 4 [ dup * 1 + ] each |- 2 5 10 17
1 2 3 [ →y →x  x y - ] foldl |- -4
```

## `!` is the fail marker; forcing has a name

```fpl
[ 1 2 + ] apply |- 3
1 1 + |- [1 1 +]  ; desired result: |- ! err/<> ""
```

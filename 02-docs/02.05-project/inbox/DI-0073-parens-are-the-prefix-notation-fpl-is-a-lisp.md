---
type: Note
title: "DI-0073 `( )` is the prefix notation, `[ ]` the postfix; FPL is at least a Lisp"
description: "everything written with `( )` should read as a Lisp; what is needed for that, measured against the walker"
status: draft
date: 2026-10-29
related: []
---

# DI-0073 `( )` is the prefix notation, `[ ]` the postfix; FPL is at least a Lisp

## His words

> oh ik weet niet of ik dit bij jou of iemand anders moet melden maar... hoe ik het voor me zie is dat `[ ]` de backfix (postfix, afix, reverse polish) notatie is van FPL en dat `( )` de prefix (poolse) notatie is van FPL: we zouden alles met `( )` kunnen schrijven en dan zou het for al intents and purposes moeten lezen als een lisp... want FPL zou op zijn minst een lisp moeten zijn.. ik weet niet wat de noodzakelijke en voldoende voorwaarden daarvoor zijn maar hey

> ja het hele punt is dat FPL ook homoiconisch moet kunnen zijn dat alle syntax als een datastructuur (unison achtige ABT) geadresserd moet kunenn code is data data is code etc etc

## Context

The condition he names: every piece of syntax addressable as a data structure, a
Unison-style abstract binding tree (hashed, names bound by structure;
[DI-0045](DI-0045-editor-and-repl-session-collapse.md) names Unison). Where the walker
stands, one line each: the surface tree (`fpl/ast_surface.py`: Program, Line, Frame, Cell,
items, spans left out of equality) and the core tree (`fpl/ast_core.py`: Define, Run,
nodes, values) are frozen Python dataclasses, not FPL values; a quotation `[ ]` is the one
piece of code that is an FPL value, run with `!` and built with `enclose` and `,`; the
log is content-addressed FON (`fpl/fon.py`, `fpl/multihash.py`, `&<multihash>` a reference
by content, `$name` by identity) but holds inputs and results as text, not the tree.
Missing for code as data at the REPL: a reader word (source text to a tree value), an
eval word on that value (`!` runs a quotation only), structural addressing (a hash per
node, names bound by position as in an ABT, so that `(+ 1 2)` and `[ 1 2 + ]` have one
address), and the tree itself as an FPL value (list, dict, symbol) rather than a Python
class. On that last point, his words (10-29): "voor nu dan? FPL moet ooit self hosting
wroden". So the bootstrap walker is the temporary form; the tree as an FPL value (reader,
eval, a hash per node) is the first step toward self-hosting.

The grammar already has the half of it: `prefix: "(" frames ")"` is "reader op: rotate
head to end, bar the arguments" (`01-bootstrap/fpl/grammar.lark`, line 30; the September
design chat decided `( )` bar-separates its arguments because `(+ 1 2)` rotated to `1 2 +`
would strand and become a section). Measured 2026-10-29 on the walker, with the reduce of
[DI-0072](DI-0072-a-line-of-numbers-and-a-word.md) in the tree:

    (+ 1 2)                 3
    (+ (times 2 3) 4)       10
    ( times 3 (+ 1 2) )     9
    (+ 1 2 3 4)             1 | 2 | 7      rotated to 1 | 2 | 3 | 4 +, so + takes the last two
    (+ 1 | 2)               ERROR: no evaluator yet
    [ 1 2 + ]               [ 1 2 + ]      a quotation is pushed, not run
    [ 1 2 + ] !             ERROR: stack underflow   (the reduce is decided by the static
                                            balance; inside a quotation the stack is
                                            unknown, so + keeps its two-value form)

So nested prefix already reads as a Lisp for fixed-arity words. Two gaps against "for all
intents and purposes a Lisp": a variadic head, `(+ 1 2 3 4)`, bars the arguments where a
Lisp would fold them (with DI-0072's reduce, stranding them instead, `1 2 3 4 +`, would give
10: a decision about what `( )` does with more arguments than the head takes); and
quotations do not run under the line rule yet (DI-0072 cluster 2), so `[ 1 2 + ] !`
underflows where the bare line `1 2 +` reduces.

What "at least a Lisp" needs, as a prior from McCarthy's 1960 paper (atoms and lists,
`quote`, `eval`, `cond`, `lambda`, the five list primitives) and the usual reading of
homoiconicity: code is a value of the language (a quotation `[ ]` is already that), a
prefix form can be quoted as data and run with `!`, and a definition form in prefix
(`(bind name …)`, which the September chat sketched). What FPL would add on top is that
`( )` and `[ ]` are the same term in two notations: `(f a b)` and `[ a b f ]` print each
other. Whether the stack (the "stack" of a postfix Lisp) is part of the language or an
implementation detail is the one open question that decides how far "a Lisp" goes.

## Options and outcome

Open. Options for the variadic head, one line each: (a) keep: `( )` bars the arguments,
the head takes its arity from the end; (b) strand the arguments past the head's arity, so
`(+ 1 2 3 4)` is `1 2 3 4 +` and folds; (c) the head is applied left to right as a Lisp
`(+ 1 2 3 4)` is `(+ (+ (+ 1 2) 3) 4)`, which is the left fold, against DI-0072's right
fold default.

## Related

- related:: [DI-0072](DI-0072-a-line-of-numbers-and-a-word.md)
- related:: [02.04.05 syntax rationale](../../02.04-explanation/02.04.05-syntax-rationale.md)

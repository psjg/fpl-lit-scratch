---
type: ADR
title: "ADR-0014 One composition operator at every level of a pass"
description: "The pipeline's composition operator also composes the stages inside a pass, but only a stage that meets the pass contract; accepted, to be checked against a measurement on the lex page."
tags:
  - adr
status: stable
rejected: false
date: 2026-10-28
deciders:
  - "psjg"
supersedes: []
superseded-by:
related:
  - ADR-0012-pipeline-is-a-computation-graph.md
  - ../inbox/DI-0061-composition-operator-fractally-inside-a-pass.md
  - ../notes/02.05.15-one-source-form.md
affects: []
drivers:
  - "one operator at every level is easier to teach and to inspect than two"
  - "the pass contract (total, origin map carried, refusals as FplError at a span) must hold for a composed stage"
  - "the stages of the pre-lexer are not a linear chain today"
options:
  - name: "Compose a stage with pass_compose only when it meets the pass contract"
    chosen: true
    pros:
      - "one operator where it is honest; the pipeline graph shows the stages as nodes"
      - "decided by a measurement on the lex page, not by a claim"
    cons:
      - "each stage needs checking against the contract"
      - "a mixed result leaves some stages as plain functions, with the reason on the page"
  - name: "Force all four stages into the pass contract for uniformity"
    chosen: false
    pros:
      - "one rule, no exceptions"
    cons:
      - "eager escapes decode every string whether read or not, a change of behaviour"
      - "the shape reader runs per token by design"
  - name: "Keep the stages as plain functions"
    chosen: false
    pros:
      - "no change"
    cons:
      - "the pipeline idea stops at the pass boundary without a stated reason"
---

# ADR-0014 One composition operator at every level of a pass

- supersedes:: none
- superseded-by:: none
- related:: [ADR-0012 The pipeline is a computation graph](ADR-0012-pipeline-is-a-computation-graph.md)
- related:: [DI-0061 The composition operator used fractally inside a pass](../inbox/DI-0061-composition-operator-fractally-inside-a-pass.md)
- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- affects:: none

Status: accepted on 2026-10-28. Proposed by the maintainer on 2026-10-27 while annotating the history web of the
lex page.

## Context

The pass pipeline composes passes with one operator (`pass_compose`, ADR-0012): every pass is a
function from one representation to the next, with the origin map carried along, so the
pipeline is a computation graph and a projection target. Inside a pass the same shape recurs.
The pre-lexer (01.02.01-lex) is told as four stages: the pair pass (strings and block comments
become placeholders, with a stash), the escapes of a string, the indentation pass, and the
shape of a word. The maintainer's question, on reading "The whole picture is a pipeline.
`pairs` walks the source once and writes the code": if that is so, the composition operator of
the pipeline can be used at this level too, fractally, so that one operator holds at every
level.

Two facts cut against treating it as obvious. The stages are not a linear chain today: the
escapes of a string are decoded on demand by the parser (`unescape` is a reader over a stretch
of source, not a stage the pre-lexer runs), and the shape of a word is read after lexing, per
token. And the stages do not all share the pass contract: `pairs` is source to code with an
origin map; `unescape` is a slice of source to a string; the indentation pass is code to code
with refusals; the shape reader is token to tuple.

## Decision

A stage inside a pass may be composed with the pipeline's operator when, and only
when, it meets the pass contract: a total function from one representation to the next that
carries the origin map and reports refusals through `FplError` at a source span. Stages that
meet it compose with `pass_compose`; stages that do not stay plain functions, and the page says
why. The lex page of the literate rewrite opens with this question for each of its four stages
and answers it with a measurement, not a claim: which stages meet the contract today, what it
costs to make the others meet it (the escapes as an eager stage would decode every string; the
shape reader as a stage would run per token), and whether the composed form reads better by the
page's own measures (dependency length, readable score, the maintainer's annotations).

Accepted by the maintainer on 2026-10-28; the lex page is rewritten to it.

This decision is about the Python bootstrap. In FPL's own source form (02.05.15) the question
dissolves into "a pass is a form like any other"; nothing here binds the language.

## Consequences

- The lex page gets a section "Is the pre-lexer a pipeline?" before its first chunk, with the
  four stages and their contracts in a table.
- The evaluation web of the history arm (E) is not rewritten: it is evaluation material with 21
  of the maintainer's annotations attached, and rewriting it would destroy a measurement point.
- If the measurement says yes for `pairs` and the indentation pass, the two compose with
  `pass_compose` and the pipeline graph (`fpl graph inspect`) shows them as nodes; the escapes
  and the shape reader stay readers unless the measurement says otherwise.
- The rewrite waits for the docstring port of `lex.py`, which touches the same chunks.

---
type: Note
title: "DI-0044 BQNPAD as the model for the IDE and REPL"
description: "instant eval while typing, Shift-Enter commits a line, results shown indented under the input, combined with the round-trip transcript and judgement lines"
status: draft
date: 2026-10-22
related: []
---

# DI-0044 BQNPAD as the model for the IDE and REPL

## His words

> ik vind deze workflow met instant eval (doet me denken aan de lighttable ideeen die ik heb besproken met de cursor agents over instant repl) en shift-enter workflow echt best wel sick... ook dat in en uitgesprongen resultaat weergave heeft iets wat heel nice is.... dat kunnen we mogelijk combineren met onze utop achtige REPL (met die roundtripple speciale comments) en judgement lines die eval resultaten terug de taal in stoppen met comments en deadlines enzo

## Context

The pad: https://bqnpad.mechanize.systems. It evaluates while you type, Shift-Enter commits a line, and the result sits indented under its input. This extends [DI-0040](DI-0040-bqnpad-instant-eval-model.md), which recorded the first reaction; here the pad is proposed as the model for the IDE/REPL as a whole.

It meets four things FPL already has or wants:

- the round-trip law read(print(session)) = session ([DI-0022](DI-0022-repl-transcripts-round-trip.md)): the displayed result is the comment line a transcript would hold;
- the `|=` judgement lines ([DI-0023](DI-0023-repl-results-as-judgement-claims.md)), which put an evaluation result back into the language;
- fuel and deadline annotations ([DI-0001](DI-0001-realtime-deadlines-beside-fuel.md)), which bound instant eval so typing never hangs the pad;
- ADR-0006: bare `fpl` is the REPL, so the pad is one more frontend of it.

## Options and outcome

Open. Options to weigh: instant eval only for bounded, effect-free lines versus everything under a deadline; Shift-Enter as commit (the line joins the transcript with its judgement) versus continuous re-evaluation of the whole buffer; where the indented result lives when the transcript is pasted back.

## Related

- related:: [ADR-0006](../adr/ADR-0006-one-fpl-executable.md)
- related:: [02.04.02 turnstiles](../../02.04-explanation/inspiration/02.04.02-turnstiles.md)
- related:: [02.04.03 judgments](../../02.04-explanation/inspiration/02.04.03-judgments.md)
- related:: [02.04.01 playgrounds](../../02.04-explanation/inspiration/02.04.01-playgrounds.md)
- related:: [02.05.13 playground tracing](../notes/02.05.13-playground-tracing.md)

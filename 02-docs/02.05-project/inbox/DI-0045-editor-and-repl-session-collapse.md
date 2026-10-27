---
type: Note
title: "DI-0045 The editor session and the REPL session collapse into one"
description: "composing an FPL program as playing a REPL like an instrument, as in a Jupyter notebook or a proof assistant"
status: draft
date: 2026-10-27
related: []
---

# DI-0045 The editor session and the REPL session collapse into one

## His words

> ik wil dat het verschil tussen een editor sessie en een REPL sessie eigenlijk weg valt dat het voelt alsof je een FPL programma componeert als het ware aan een REPL als een instrument in versmelting er mee... net zoals hoe dat zou kunnen op een jupyter werkbank of in een proof assistant zoals coq

## Context

The program is the session: one document that is both the source and the transcript. Precedents to study as options:

- Coq/Rocq interactive proof mode (Proof General, CoqIDE): the document is the script and the checked state follows the cursor.
- Jupyter and marimo cells: marimo's cells form a reactive DAG.
- Smalltalk workspaces and Lisp machine listeners: evaluate in place.
- BQNPAD and Light Table: instant eval ([DI-0044](DI-0044-bqnpad-as-model-for-ide-repl.md)).
- Unison: the codebase as structure, not text.

What it implies for FPL: a transcript that is a program (the round-trip law of [DI-0022](DI-0022-repl-transcripts-round-trip.md)); judgement lines as checked claims ([DI-0023](DI-0023-repl-results-as-judgement-claims.md)); the image as the live state the document walks through; the accessible web IDE and `fpl tui` as two frontends on one session kernel.

## Options and outcome

Open. Study the precedents above, then decide the session kernel's contract (what "the state at this line" means, and how an edit above it replays what follows) before either frontend is designed.

## Related

- related:: [DI-0044](DI-0044-bqnpad-as-model-for-ide-repl.md)
- related:: [ADR-0006](../adr/ADR-0006-one-fpl-executable.md)
- related:: [02.04.04 debugging](../../02.04-explanation/inspiration/02.04.04-debugging.md)
- related:: [02.05.06 pipeline open questions](../notes/02.05.06-pipeline-open-questions.md)
- related:: [DI-0022](DI-0022-repl-transcripts-round-trip.md)
- related:: [DI-0023](DI-0023-repl-results-as-judgement-claims.md)

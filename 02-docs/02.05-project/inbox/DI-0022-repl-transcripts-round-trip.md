---
type: Note
title: "DI-0022 REPL transcripts must round-trip"
description: "copy from the REPL, paste back, and it is a program"
status: draft
date: 2026-10-08
related: []
---

# DI-0022 REPL transcripts must round-trip

## His words

> het zou cool zijn als er geen `...` bij een definitie zouden komen te staan ... dan zou je namelijk gewoon kunnen copy pasten uit de REPL en dat dan weer terug kunnen copy pasten in een REPL dan kan je roundtrippen

## Context

Said on #143's continuation prompt. His two options: (1) print so that everything round-trips (a printer identity law); (2) make the REPL swallow the special markings. Agent recommendation: both, as one law, read(print(session)) = session: the reader swallows the exact prompt prefixes at column 0 (so the visual cue he likes can stay), and the loop writes every non-input line as a comment, the form the fixtures already use. Then any selection of a transcript is a program, and a pasted session is a fixture. The prompt itself is the remaining obstacle.

## Options and outcome

Open: the prompt prefix, and the exact law. Continues in DI-0023.

## Related

- related:: [02.05.05 REPL phrase costs](../notes/02.05.05-repl-phrase-costs.md)
- related:: [02.04.03 judgments](../../02.04-explanation/inspiration/02.04.03-judgments.md)


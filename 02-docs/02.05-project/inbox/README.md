---
type: Readme
title: Design inbox
description: Ideas for FPL itself, one file per idea, numbered DI-NNNN; how they are numbered and how to respond.
---

The inbox holds ideas about the language, raised in review, in chat or in passing, that belong in the next design note rather than in the bootstrap code. One idea is one file, `DI-NNNN-<slug>.md`, built from the maintainer's own words (Dutch kept verbatim), the context, and the options or the outcome.

Numbering: four digits, assigned once, never reused, not even after an item is closed or deleted. Take the next free number.

Status uses the OKF `status` field:

- `draft`: open, awaiting a decision or a design-note slot.
- `stable`: decided; the file says what was decided and where it is recorded.
- `deprecated`: done or superseded; the file names what replaced it.

How to respond: open [index.md](index.md) in Obsidian, tick the box when an item is answered, and write the answer under the item's "Options and outcome" heading. Set `status` to match. `stable` and `deprecated` items start ticked.

Items that bear on a decision link their ADRs, notes and tech-debt entries with `related::` lines.

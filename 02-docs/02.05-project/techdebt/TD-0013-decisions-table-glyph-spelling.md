---
type: Note
title: The decisions table still spells examples with the retired glyphs
description: The substrate decisions table and register use APL glyph examples while the grammar and section 8 use canonical name spellings, so examples do not match the canon.
tags: [docs, syntax, spelling]
status: draft
date: 2026-10-21
found-in: [02-docs/02.05-project/notes/02.05.11-substrate-liabilities.md, 02-docs/02.04-explanation/02.04.04-substrate.md, 02-docs/02.05-project/notes/02.05.08-archive-glyph-spelling.md]
related: []
closed-by:
---

## Symptom

Examples in the decisions table rows and in the register are written with glyphs (`⍴ ⊑ ⋈ ⊐ ¨ ⍣`), while the worked example (§8) and the grammar use the canonical name spelling chosen by S32. A reader copying an example from a row gets text the printer would not produce. The handoff brief to the implementation agent also called §8 glyph-spelled, which was stale (register row X10).

## Cause

The glyph spelling was the canon until 2026-09-27. The name spelling replaced it, and the rows written earlier were not rewritten. The printer translates both ways, so nothing is wrong semantically; the text is only out of step.

## Remedy

One mechanical pass: map each glyph to its name per the grammar's spelling table and rewrite the examples in the rows, keeping the glyph form only in the archive page. The pass is a candidate for a script keyed on that table, followed by a read-through of the changed rows. Update X10 in the register when done.

## How to reproduce

Search the substrate page and the register for glyphs such as `⍴`, `⊑` and `⋈` outside the archive page.

---
type: Note
title: "DI-0053 Relations between prose blocks and code chunks in the graph"
description: "store which prose block explains which code chunk as semantic relations in the graph (he suspects over-engineering)"
status: draft
date: 2026-10-27
related: []
---

# DI-0053 Relations between prose blocks and code chunks in the graph

## His words

> je kan misschien relaties tussen blokken text en codeblocks doen die je ook weer semantisch in een graaf kan opslaan oid? … het is waarschijnlijk grondige overengineering

## Context

Written while annotating literate pages. Caveat, his own: he flags it as probably thorough over-engineering. Recorded so the thought is not lost, not as a proposal to build.

## Options and outcome

Open.

**Follow-up, 2026-10-27.** In the morning he called this probable over-engineering, for the
Markdown tooling of the literate pages. The same afternoon, in a design conversation (not in the
repo), he made it the core of FPL itself: FPL is "symbolisch gestructureerde semantiek via o.a. doc
comments" and "een tangle en weave van markup die ook semantisch / symbolisch gekoppeld kan
worden". The two do not conflict once the place is named: not in the bootstrap tooling (`lit`
keeps its chunks and prose as they are), yes in the language, where a doc is a node with
references to symbols and a document is a view over the graph. See
[02.05.15 One source form](../notes/02.05.15-one-source-form.md),
[DI-0054](DI-0054-doc-fields-are-symbolic-edges.md) and
[DI-0055](DI-0055-documents-as-views-over-the-graph.md).

## Related

- related:: [DI-0049](DI-0049-clickable-references-foldable-elisions.md)
- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)

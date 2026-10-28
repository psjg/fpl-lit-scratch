---
type: Note
title: "DI-0060 A chunk declares its place and its dependencies"
description: "a chunk header carries its position in the tangle or, better, its computed dependency list, so the root chunk that fixes the order can go"
status: draft
date: 2026-10-28
related: []
---

# DI-0060 A chunk declares its place and its dependencies

## His words

> moeten die witregels hier staan?? WAT ALS WE IN DE CODE BLOCK EEN PARAMETER GEVEN DIE ZEGT ik ben dit nummer in de tangle of nog beter dit zijn mijn dependencies (kan je ook uitrekenen) je weet wel voor de marimo dependency achtige graaf

> dit kan weg als we order in de tangle blocks doen en ook die afhankelijkheden uitrekenen

## Context

Two notes in the annotation round of 2026-10-28, on the root chunk of the pre-lexer page. A
chunk header could carry its place in the tangle or, better, its dependencies, which `lit` can
compute from the names a chunk defines and uses (marimo orders its cells by such a graph). The
dependency-length measurement on the lex page already computes the same relation (page/best
1.69). The consequence he names in the second note: the root chunk that knows the order of the
module disappears once the tangler orders chunks by computed dependencies.

## Options and outcome

Open. Proposal; not implemented.

## Related

- related:: [DI-0055 Documents as views over the semantic graph](DI-0055-documents-as-views-over-the-graph.md)
- related:: [DI-0058 Stable identity between a literate fragment and its definition](DI-0058-stable-identity-fragment-to-definition.md)
- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)

---
type: Note
title: "DI-0054 Doc fields are symbolic edges"
description: "a doc comment is a typed node whose fields (raises, see, param) point at symbols, so a rename moves the documentation with it"
status: draft
date: 2026-10-27
related: []
---

# DI-0054 Doc fields are symbolic edges

## His words

> 1. symbolisch gestructureerde semantiek via o.a. doc comments.

## Context

From a design conversation of 2026-10-27 (not in the repo). The proposal he answered with the
quote above: a doc is not a blob of Markdown but a typed object (summary, parameters, returns,
raises, examples, references), and a field that names something holds an edge, not a string.
`raises UnboundName` is `Doc(resolve) --raises--> Symbol(UnboundName)`; `see Scope.lookup` is an
edge to that symbol; a `[Name]` in the summary is a `Ref` node. Renaming `UnboundName` then
renames it in every doc, and the projections (a hover, a page, a link in an export) are
renderings of one edge.

What the tree already has: the [mise en place](../notes/02.05.07-mise-en-place.md) feature table
puts per-argument docs as "a field in the doc, addressed by name", cross-references as paths,
and finds `@throws`/`Raises:` unnecessary because `+fail` is in the effect line; the doc itself
is `;;` on a definition
([spellings and comments §5](../../02.03-reference/02.03.06-spellings-and-comments.md#5-comments-s33-s48)).
The delta is that the references inside a doc, and the doc's fields, are resolved edges that
the checker sees and a rename follows, not text a tool scans later. Which fields remain once
effects and types are in the tree is open (a `raises` field may be redundant with the effect
line).

## Options and outcome

Open.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- related:: [Mise en place](../notes/02.05.07-mise-en-place.md)

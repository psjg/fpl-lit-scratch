---
type: Note
title: "DI-0055 Documents as views over the semantic graph"
description: "a document is a query over definitions, docs and examples, so the order of the explanation need not be the order of storage"
status: draft
date: 2026-10-27
related: []
---

# DI-0055 Documents as views over the semantic graph

## His words

> 2. een tangle en weave van markup die ook semantisch / symbolisch gekoppeld kan worden zodat we echt literate programming eindelijk ooit een keer goed doen.

## Context

From a design conversation of 2026-10-27 (not in the repo). The proposal: weaving need not mean
"print the source top to bottom". A document can be a view or query over the graph, for example
"explanation of `Resolver`, definition of `Scope`, implementation of `Resolver.resolve`, all
examples under `Resolver`", or an API reference as "public symbols grouped by module". Then
document order is a view, not storage order, and the classic conflict of literate programming
(the program wants one order, the explanation another) does not have to be settled by choosing
one. Different readers ask for different subsets of one symbol's neighbourhood: a hover wants
type, summary and failure; a review wants implementation, rationale and tests.

What the tree already has: FML's interface view (F20) is one such view (the tree with every body
removed), and island order is log order, so "defined later, used earlier" already holds
([FML §2](../../02.03-reference/02.03.04-fml.md#2-polarity-flipped-and-literate-programming-falls-out)).
The delta is the general case: a document whose content is a query, not a file.

## Options and outcome

Open.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- related:: [DI-0053](DI-0053-prose-code-relations-in-the-graph.md)

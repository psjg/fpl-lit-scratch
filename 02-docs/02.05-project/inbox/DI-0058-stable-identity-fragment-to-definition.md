---
type: Note
title: "DI-0058 Stable identity between a literate fragment and its definition"
description: "a fragment carries an id and names the definition it produces, so code edits map back to prose and prose to code without text heuristics"
status: draft
date: 2026-10-27
related: []
---

# DI-0058 Stable identity between a literate fragment and its definition

## His words

None on this point directly. Nearest, on keeping several editable forms in step:

> (ja synchronisatie is wel problematisch)

## Context

From a design conversation of 2026-10-27 (not in the repo), after nbdev 3's two-way sync, which
gives exported cells a permanent id so that an edit in the `.py` file finds its notebook cell.
The proposal, as a mechanism to study rather than adopt:

    literate fragment
    ---
    id: resolve.scope.lookup
    produces: fpl/resolve.py#resolve_name
    ---
              ⇅ stable identity
    Python definition

so that both directions (literate source to code, code edit to the fragment it came from) work
by identity, not by matching text.

What exists: `lit` records, for every tangled line, the page line it came from (`Tangled.origin`
in `.harness/tools/lit/lit/web.py`), and `lit run` rewrites tracebacks and linter output to page
lines. That map is one-way, per line, and keyed by chunk names that are strings. In the language,
FML gives a block identity with `$id` in its properties (F16) and span addressing from patches
over ABT edits. The delta is a two-way map at the granularity of a definition, for the bootstrap
while it still has two files per module; in the [one source form](../notes/02.05.15-one-source-form.md)
there is one tree and the question goes away.

## Options and outcome

Open.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- related:: [DI-0042](DI-0042-merge-literate-draft-back.md)

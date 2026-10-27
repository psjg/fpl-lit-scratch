---
type: Note
title: "DI-0057 One authority per kind of information"
description: "a table that names the one place each kind of information is edited; HTML, JupyterLite, API pages and Obsidian views are projections and never edited"
status: draft
date: 2026-10-27
related: []
---

# DI-0057 One authority per kind of information

## His words

> en als we sphinx wel erbij kunnen trekken dan moeten we dat doen (ja synchronisatie is wel problematisch)

## Context

From a design conversation of 2026-10-27 (not in the repo). The proposal: make authority explicit
everywhere, as the [Obsidian, OKF, COB bridge](../notes/02.05.04-obsidian-okf-cob-bridge.md)
already does for tasks ("COB is authoritative; note is projection"). One table, one home per kind
of information, and everything else generated:

| information | authority |
| --- | --- |
| language semantics | the feature spec and the reference spec |
| design rationale | explanation and design |
| implementation | the source |
| API signature and contract | the signature and its doc |
| worked computational narrative | the literate page |
| exploratory knowledge | the OKF vault |
| task state | the COB |
| rendered HTML, JupyterLite state, generated API pages, Obsidian views | never: projections |

A projection is never edited; an arrow runs from the authority to the projection and none runs
back. The point is to make sync a local problem (at most one sanctioned back-edge, as nbdev's
`.py` to notebook update) instead of a global one between every format.

Under the [one source form](../notes/02.05.15-one-source-form.md) most rows collapse into one:
the `.fpl`/`.fml` tree is the authority and the rest are exports. The table is still useful now,
for the bootstrap, where the tool chain has several formats that could each be edited.

## Options and outcome

Open. A table like the one above could sit in `AGENTS.md` or the project README for the bootstrap
period.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- related:: [02.05.04 Obsidian, OKF, COB bridge](../notes/02.05.04-obsidian-okf-cob-bridge.md)

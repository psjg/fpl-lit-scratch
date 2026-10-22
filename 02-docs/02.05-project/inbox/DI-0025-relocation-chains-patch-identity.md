---
type: Note
title: "DI-0025 Rebase noise and patch identity (the v0 idea)"
description: "git hashes the parent into identity; patch-based identity removes the rebase noise"
status: draft
date: 2026-10-17
related: []
---

# DI-0025 Rebase noise and patch identity (the v0 idea)

## His words

> pijul lost de rebase-ruis op

## Context

Said on the first hand relocation chain: rebases exist only because git hashes the parent into a commit's identity. Measured that night: nine sibling branches, three conflicts on the gates list, one on the trailer order, two on the workflow doc. Patch-style identity removes the rebase, not the list conflict; a structure store (a set of self-tests, not a line in a list) makes additions commute. For FPL's own store, identity on the patch is the git-side approximation of what he wants built in.

## Options and outcome

Open; a v0 design input for the store.

## Related

- related:: [ADR-0012](../adr/ADR-0012-pipeline-is-a-computation-graph.md)


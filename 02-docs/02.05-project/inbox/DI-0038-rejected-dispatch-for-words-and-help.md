---
type: Note
title: "DI-0038 PRs 141 and 148 rejected on mechanism"
description: "a `:`-prefixed command dispatch is a hard no for the redo"
status: stable
date: 2026-10-14
related: []
---

# DI-0038 PRs 141 and 148 rejected on mechanism

## His words

> ik heb PR 141 en 148 geweigerd vanwege hoe die dispatch zou worden toegevoegd

## Context

The `:words` (#141) and `:help` (#148, a dispatch table of `:` commands) PRs were closed on mechanism, not intent. The settled direction stands: introspection as words and paths; no `:`-prefixed commands; `:` is the judgement sign (DI-0039).

## Options and outcome

Hard constraint for the redo of both.

## Related

- none yet

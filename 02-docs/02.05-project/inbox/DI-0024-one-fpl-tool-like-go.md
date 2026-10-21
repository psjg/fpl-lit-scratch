---
type: Note
title: "DI-0024 One `fpl` tool, like `go`"
description: "convention over configuration; one tool with subcommands"
status: stable
date: 2026-10-08
related: []
---

# DI-0024 One `fpl` tool, like `go`

## His words

> ik wil een FPL tool net zoals de go tool: go run go whatever etc is gewoon heel fijn

## Context

Design goal: one formatter without options, tests found by naming convention, `fpl help <topic>` explains everything. His method: research go, cargo, zig, deno, bun, dune, mix, raco from primary sources, mock the CLI surface and help text, write tests against the mock (a CLI conformance suite), then implement. The same `fpl` name stays the entry when FPL self-hosts. Draft surface: `fpl run <file>`, `fpl run -e <expr>`, `fpl repl`, `fpl check`, `fpl test [path]` (files ending `_test.fpl`), `fpl spec [feature]`, `fpl fmt [path]`, `fpl doc <word>`, `fpl new <name>` (open: now or later), `fpl help [topic]`, `fpl version`. No `build` or `install` until there is something to build. Open: `check` versus `ready`.

## Options and outcome

Decided in direction; recorded as ADR-0006.

## Related

- related:: [ADR-0006](../adr/ADR-0006-one-fpl-executable.md)
- related:: [ADR-0001](../adr/ADR-0001-passes-are-pipeable-filters.md)


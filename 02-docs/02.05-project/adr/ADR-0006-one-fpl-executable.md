---
type: ADR
title: "ADR-0006 One fpl executable with a subcommand per stage"
description: "The shell route is `fpl source < f | fpl lex | fpl parse | ... | fpl render`, one executable whose subcommands are the stages; `fpl <file>` runs the whole chain in-process."
tags:
  - adr
status: stable
rejected: false
date: 2026-10-21
deciders:
  - "psjg"
supersedes: []
superseded-by:
related:
  - ADR-0001-passes-are-pipeable-filters.md
  - ADR-0007-cli-libraries-welcome.md
affects:
  - ../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md
  - ../../../01-bootstrap/01.01-boundary/01.01.01-source.md
  - ../../../01-bootstrap/01.01-boundary/01.01.04-render.md
  - ../../../01-bootstrap/01.04-compose/01.04.02-run.md
  - ../../../01-bootstrap/python/fpl/__main__.py
  - ../../../01-bootstrap/pyproject.toml
drivers:
  - "the shell workflow should read like `fpl lex | fpl parse | fpl eval`"
  - "no stage-specific CLI code: one adapter for every stage"
  - "the library API and the CLI stay separate"
options:
  - name: "One `fpl` executable, one subcommand per stage"
    chosen: true
    pros:
      - "one thing to install; `fpl <stage>` is one filter, `fpl <file>` a whole run"
      - "the dispatch can be derived from the stages"
    cons:
      - "needs a packaging entry point to exist as a command"
  - name: "One executable per stage (fpl-lex, fpl-parse, ...)"
    chosen: false
    pros:
      - "each program stands alone"
    cons:
      - "many executables to install and keep in step"
  - name: "Only `python -m fpl.<stage>`"
    chosen: false
    pros:
      - "no packaging"
    cons:
      - "long command lines; the shell route reads badly"
---

# ADR-0006 One fpl executable with a subcommand per stage

Supersedes: none. Superseded by: none.
Related: [ADR-0001 Pipeable filters](ADR-0001-passes-are-pipeable-filters.md),
[ADR-0007 CLI libraries welcome](ADR-0007-cli-libraries-welcome.md).
Affects: [01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md),
[01.01.01 Source](../../../01-bootstrap/01.01-boundary/01.01.01-source.md),
[01.01.04 Render](../../../01-bootstrap/01.01-boundary/01.01.04-render.md),
[01.04.02 Run](../../../01-bootstrap/01.04-compose/01.04.02-run.md),
[python/fpl/\_\_main\_\_.py](../../../01-bootstrap/python/fpl/__main__.py),
[pyproject.toml](../../../01-bootstrap/pyproject.toml).

## Context

The maintainer asked how to drop the passes onto the shell as something like
`fpl prelex | fpl lex | fpl parse | fpl eval`, and whether each stage's `__main__.py` could be
just a wrapper of a utility object around the stage its `__init__.py` exports.

The pipeline does not start in FON but in raw bytes, so the first command is an ingress
adapter, not a compiler pass. `prelex` fits if it does real work before lexing (byte
decoding, BOM, newline canonicalisation, a source path); `source` names the plain case. A
matching output adapter turns a FON value back into text.

## Decision

There is one `fpl` executable. `fpl <stage>` runs one stage as a filter; `fpl <file>` (and
`fpl run <file>`) runs the whole chain in-process. The ingress is `fpl source`, the egress
`fpl render`:

    fpl source < foo.fpl | fpl lex | fpl parse | fpl desugar | fpl elaborate | fpl eval | fpl render

## Consequences

- The tree has this shape. `01-bootstrap/python/fpl/__main__.py` is a Click group that
  registers `source`, `lex`, `parse`, `desugar`, `elaborate`, `eval`, `render` and `run`, and
  runs a bare file in-process. `fpl/__init__.py` is the library API.
- Each stage package's `__main__.py` is a few lines, `from . import <stage>; cli(<stage>)`,
  around the shared adapter in `python/fpl/pipe/__init__.py`, so `python -m fpl.lex` works as
  well. It never re-implements the stage or starts another FPL tool.
- `01-bootstrap/pyproject.toml` has no `[project.scripts]` entry, so packaging does not yet
  install an `fpl` command; the route today is `python -m fpl <stage>`.
- The command list is a hand-written tuple (`COMMANDS`), and the adapter dispatches on the
  stage name in `_run`. Deriving both from a registry of `Pass` objects with input and output
  types is a proposal, not part of this decision.
- The adapter has no `--trace` and no choice of FON encoding; an error is one stderr line and
  exit code 1.

---
type: ADR
title: "ADR-0006 One fpl executable with a subcommand per stage"
description: "The shell route is `fpl source < f | fpl lex | fpl parse | ... | fpl render`, one executable whose subcommands are the stages; `fpl run <file>` runs the whole chain in-process, and `fpl repl`, or bare `fpl`, opens the interactive interface."
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
  - ../../../01-bootstrap/01.01-boundary/01.01.06-cli.md
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
      - "one thing to install; `fpl` is the interactive interface, `fpl <stage>` one filter, `fpl run <file>` a whole run"
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

- supersedes:: none
- superseded-by:: none
- related:: [ADR-0001 Pipeable filters](ADR-0001-passes-are-pipeable-filters.md)
- related:: [ADR-0007 CLI libraries welcome](ADR-0007-cli-libraries-welcome.md)
- affects:: [01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md)
- affects:: [01.01.01 Source](../../../01-bootstrap/01.01-boundary/01.01.01-source.md)
- affects:: [01.01.04 Render](../../../01-bootstrap/01.01-boundary/01.01.04-render.md)
- affects:: [01.04.02 Run](../../../01-bootstrap/01.04-compose/01.04.02-run.md)
- affects:: [01.01.06 CLI](../../../01-bootstrap/01.01-boundary/01.01.06-cli.md)
- affects:: [python/fpl/\_\_main\_\_.py](../../../01-bootstrap/python/fpl/__main__.py)
- affects:: [pyproject.toml](../../../01-bootstrap/pyproject.toml)

## Context

The maintainer asked how to drop the passes onto the shell as something like
`fpl prelex | fpl lex | fpl parse | fpl eval`, and whether each stage's `__main__.py` could be
just a wrapper of a utility object around the stage its `__init__.py` exports.

The pipeline does not start in FON but in raw bytes, so the first command is an ingress
adapter, not a compiler pass. `prelex` fits if it does real work before lexing (byte
decoding, BOM, newline canonicalisation, a source path); `source` names the plain case. A
matching output adapter turns a FON value back into text.

## Decision

There is one `fpl` executable. `fpl repl` starts the interactive interface, and bare `fpl`,
with no arguments, is an alias of it: the existing REPL for now, with room for a
full-screen interface later.
`fpl <stage>` runs one stage as a filter; `fpl run <file>` runs the whole chain in-process.
The ingress is `fpl source`, the egress `fpl render`:

    fpl source < foo.fpl | fpl lex | fpl parse | fpl desugar | fpl elaborate | fpl eval | fpl render

## Consequences

- The tree has this shape. `01-bootstrap/python/fpl/__main__.py` calls `dispatch` of
  [01.01.06 CLI](../../../01-bootstrap/01.01-boundary/01.01.06-cli.md), a Click group with a
  filter per stage (`source`, `lex`, `parse`, `desugar`, `elaborate`, `eval`, `render`), `run`,
  `repl`, and `graph` and `shell`, which show a composition. `fpl/__init__.py` is the library API and
  does not import Click.
- The command names are read off the registries: `PASSES` and `ENDS` of the pipe,
  `COMPOSITIONS` of the run note. No list of stage names is written by hand.
- `fpl repl` and bare `fpl` run the seed walker's REPL (`01-bootstrap/fpl/repl.py`) as a child process with
  the seed ahead of its path, since the seed and the tangled tree are both named `fpl`. The
  wheel carries the seed as `fpl/_seed/fpl`, so an installed `fpl` has it too
  ([TD-0014](../techdebt/TD-0014-installed-fpl-no-repl.md)). The REPL is not yet a literate page.
- `fpl <file>` remains as short for `fpl run <file>`: it conflicts with no command, and a
  command name wins over a file of the same name.
- Each stage package's `__main__.py` is a few lines, `from . import <stage>`, then
  `raise SystemExit(cli(<stage>))`, around the shared adapter in
  `python/fpl/pipe/__init__.py`, so `python -m fpl.lex` works as well and exits with the
  filter's status. It never re-implements the stage or starts another FPL tool.
- `01-bootstrap/pyproject.toml` declares Click and the `fpl` script (`fpl.cli:entry`)
  ([TD-0010](../techdebt/TD-0010-click-undeclared.md)).
- The adapter has no `--trace` and no choice of FON encoding. A diagnostic crosses the pipe as
  an `Error` document, and `fpl render` prints it as `fpl run` does
  ([01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md)).

Revised 2026-10-22 by the maintainer: `fpl repl` starts the interactive interface, bare
`fpl` is an alias of it; the whole run is `fpl run <file>`. The consequences above describe the tree after that revision.

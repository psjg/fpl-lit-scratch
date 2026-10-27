---
type: ADR
title: "ADR-0007 The CLI may use third-party libraries"
description: "The standard library is not a requirement for the fpl CLI; a library that makes it better is welcome. The tree uses Click."
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
  - ADR-0006-one-fpl-executable.md
affects:
  - ../../../01-bootstrap/python/fpl/__main__.py
  - ../../../01-bootstrap/pyproject.toml
  - ../../../flake.nix
drivers:
  - "less boilerplate in the CLI layer"
  - "commands registered programmatically, so the CLI can follow the stages"
  - "help and shell completion for free"
options:
  - name: "Third-party CLI libraries where they help (Click, Typer)"
    chosen: true
    pros:
      - "Click's Group.add_command registers commands in a loop, so the CLI can follow a registry of passes"
      - "Typer builds commands from function signatures and type hints"
      - "help and completion come with the library"
    cons:
      - "a dependency to declare and pin"
  - name: "Standard library only: argparse with subparsers"
    chosen: false
    pros:
      - "no dependency"
      - "the dispatch is small"
    cons:
      - "more hand-written dispatch and help"
---

# ADR-0007 The CLI may use third-party libraries

- supersedes:: none
- superseded-by:: none
- related:: [ADR-0006 One fpl executable](ADR-0006-one-fpl-executable.md)
- affects:: [python/fpl/\_\_main\_\_.py](../../../01-bootstrap/python/fpl/__main__.py)
- affects:: [pyproject.toml](../../../01-bootstrap/pyproject.toml)
- affects:: [flake.nix](../../../flake.nix)

## Context

`argparse` subcommands under `fpl/__main__.py`, with a `[project.scripts]` entry, were
recommended as the zero-dependency route for [ADR-0006](ADR-0006-one-fpl-executable.md),
with Click and Typer named as the more ergonomic choice if the standard library is not a
hard requirement. The maintainer answered that it is not: if a library makes the CLI better,
that is welcome.

## Decision

The `fpl` CLI uses third-party libraries where they help. The standard library is not a
constraint on it.

## Consequences

- The tree uses Click: `01-bootstrap/python/fpl/cli.py` is a `click.group` and adds one
  command per stage with `add_command`; `__main__.py` only calls its `dispatch`. Typer was suggested as the first try; Click is the
  better fit once commands are generated from `Pass` metadata, which is not done yet.
- Click is declared: `01-bootstrap/pyproject.toml` lists `lark`, `icontract` and `click`, and
  `flake.nix` provides it, so an install from the package metadata has it
  ([TD-0010](../techdebt/TD-0010-click-undeclared.md), deprecated: resolved).

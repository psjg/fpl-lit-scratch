---
type: Note
title: "DI-0059 A docstring convention for the Python bootstrap"
description: "Google style with type hints, #: for public module data, doctests as executable witnesses, enforced by ruff's pydocstyle rules with convention = google"
status: draft
date: 2026-10-27
related: []
---

# DI-0059 A docstring convention for the Python bootstrap

## His words

> doe die hele mambo

> ok en hoe zou je deze full mambo combineren met de discipline van literate programming?

## Context

From a design conversation of 2026-10-27 (not in the repo), which started on Python docstring
conventions. A proposal for the bootstrap now, not for FPL:

| form | carries |
| --- | --- |
| type annotation | the shape of values; never repeated in the docstring |
| docstring (PEP 257, Google sections `Args:`, `Returns:`, `Raises:`, `Examples:`) | the public contract of a function or class |
| doctest in `Examples:` | a minimal executable witness of that contract |
| `#:` before a module constant or class attribute | the meaning of public data, which has no docstring position (Sphinx autodoc reads it) |
| `#` comment | the reason for a locally surprising implementation choice, never a paraphrase of the code |
| literate prose | derivation, motivation and argument |

The rule underneath: docstrings document interfaces; comments document surprising implementation
choices.

Enforceable as a gate: ruff's `D` rules (pydocstyle) with

    [lint.pydocstyle]
    convention = "google"

added to `select` in `.harness/quality/ruff.toml`, and `docstring-code-format = true` so ruff
formats the code in doctests. Today `D` is not selected. Changing that file is a harness commit
with `[policy]`, never one that changes code, so this is a proposal only.

Measured on 2026-10-27 (`ruff check --isolated --select D` with `convention = "google"` over
`01-bootstrap/fpl`): 1111 findings, 565 of them fixable by `--fix`. Nearly all are layout:
535 D212 (summary not on the first line), 337 D205 (no blank line after the summary), 196 D200
(a one-line docstring spread over three lines), 30 D403, 6 D415. Missing docstrings are rare:
6 D107 and 1 D105, no D100 to D103. So the gate is cheap on coverage and costs one mechanical
reformat, after which D212 against D213 is a choice to make, not a defect. `lit-example` already
runs `pycon` fences in walker pages as doctests.

## Options and outcome

Open. Proposal; not implemented.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- related:: [Mise en place](../notes/02.05.07-mise-en-place.md)

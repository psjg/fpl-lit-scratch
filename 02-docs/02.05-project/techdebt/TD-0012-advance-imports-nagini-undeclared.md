---
type: Note
title: The packaged fpl.advance imports nagini_contracts, which nothing declares or provides
description: "`01-bootstrap/python/fpl/advance.py` imports `nagini_contracts`; neither `01-bootstrap/pyproject.toml` nor `flake.nix` names it, so `import fpl.advance` fails in the installed package."
tags: [bootstrap, packaging]
status: draft
date: 2026-10-26
found-in: [01-bootstrap/01.06-nagini/01.06.01-advance.md, 01-bootstrap/python/fpl/advance.py, 01-bootstrap/pyproject.toml, flake.nix]
related:
  - TD-0011-installed-fpl-no-repl.md
closed-by:
---

Found when deptry was first run over the tangled tree, `python/`, for the nix-deps rule
(every dependency enters through the Nix flake, AGENTS.md), after
[TD-0011](TD-0011-installed-fpl-no-repl.md) put the package in the flake.

## Symptom

```text
$ cd 01-bootstrap && deptry python
python/fpl/advance.py:10:1: DEP001 'nagini_contracts' imported but missing from the dependency definitions
```

## Cause

The Nagini page tangles to `fpl/advance.py`, inside the wheel. Its contracts come from
`.vendor/` (`bin/fpl` puts it on the path), which is untracked; `nagini_contracts` is on
PyPI but not in nixpkgs.

## Remedy

Either keep `advance` out of the wheel (a module Nagini reads, not one `fpl` runs), or
package `nagini_contracts` in the flake and declare it. Until then `01-bootstrap/pyproject.toml`
tolerates the import under `DEP001`, naming this item.

## How to reproduce

`nix develop -c sh -c 'cd 01-bootstrap && ../.harness/.venv/bin/deptry python'`, run on
2026-10-26 at b9c1272.

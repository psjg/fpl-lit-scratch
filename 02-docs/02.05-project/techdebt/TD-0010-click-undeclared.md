---
type: Note
title: The fpl CLI imports Click, but the package does not declare it
description: "`01-bootstrap/python/fpl/__main__.py` imports click; `01-bootstrap/pyproject.toml` declares only lark and icontract, so `fpl.__main__` fails to import in the package's own environment."
tags: [bootstrap, packaging]
status: draft
date: 2026-10-21
found-in: [01-bootstrap/python/fpl/__main__.py, 01-bootstrap/pyproject.toml, flake.nix]
related:
  - ../adr/ADR-0006-one-fpl-executable.md
  - ../adr/ADR-0007-cli-libraries-welcome.md
closed-by:
---

The CLI of [ADR-0006](../adr/ADR-0006-one-fpl-executable.md) uses a library as
[ADR-0007](../adr/ADR-0007-cli-libraries-welcome.md) allows, but the package does not say so.

## Symptom

```text
$ nix develop -c uv run --project 01-bootstrap python -I <script that imports fpl.__main__>
ModuleNotFoundError: No module named 'click'
```

## Cause

`pyproject.toml` has `dependencies = ["lark", "icontract"]` and no `[project.scripts]`.
Click is provided only inside the `fpl-marimo` Python environment in `flake.nix`
(`ps.click`). The deptry gate excludes the tangled `python/` tree, so it does not see the
import.

## Remedy

Add `click` to the dependencies of `01-bootstrap/pyproject.toml`, and an
`fpl = "fpl.__main__:main"` entry under `[project.scripts]` so the `fpl` command of
ADR-0006 exists after an install. Both are policy changes: one commit with the `[policy]`
marker and no code (`.agents/QUALITY.md`).

## How to reproduce

From the repository root, run a script that puts `01-bootstrap/python` on `sys.path` and
imports `fpl.__main__`, under `nix develop -c uv run --project 01-bootstrap python -I`.
Run on 2026-10-21.

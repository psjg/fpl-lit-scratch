---
type: Note
title: The installed fpl cannot open the REPL
description: "`fpl repl` and bare `fpl` start the seed REPL from `01-bootstrap/fpl/` by its place in the checkout; the wheel holds only `python/fpl`, so an installed `fpl` reports that it has no REPL."
tags: [bootstrap, packaging]
status: draft
date: 2026-10-22
found-in: [01-bootstrap/01.01-boundary/01.01.06-cli.md, 01-bootstrap/python/fpl/cli.py, 01-bootstrap/pyproject.toml, flake.nix]
related:
  - ../adr/ADR-0006-one-fpl-executable.md
  - TD-0010-click-undeclared.md
  - TD-0009-seed-fon-braced-not-postfix.md
closed-by:
---

[ADR-0006](../adr/ADR-0006-one-fpl-executable.md) makes bare `fpl` the interactive
interface, but that holds only inside a clone. The script entry itself came with
[TD-0010](TD-0010-click-undeclared.md).

## Symptom

A wheel built from `01-bootstrap/`, installed into a fresh venv and run outside the
checkout:

```text
$ echo '1 2 +' | venv/bin/fpl repl
fpl: no REPL: .../venv/lib/python3.12/fpl is missing
$ echo $?
2
```

## Cause

`repl()` of [01.01.06 CLI](../../../01-bootstrap/01.01-boundary/01.01.06-cli.md) runs
`python -m fpl.repl` in a child whose `PYTHONPATH` is `SEED`, set to
`Path(__file__).resolve().parents[2]`. In the checkout that is `01-bootstrap/`, which holds
the seed package `fpl/`. Installed, it is a directory under the venv, and
`[tool.hatch.build.targets.wheel]` packages only `python/fpl`, so the seed is not there
at all. The child also gets the seed and nothing else on its path, so the REPL would miss
lark and icontract wherever they are not on the bare interpreter's own path, as in a Nix
store.

The REPL cannot simply move into the tangled tree: it needs the seed's `log`, `session`,
`driver` and `types`, and the session log is written in the seed's braced FON, which the
tangled `fpl.fon` (postfix) replaced ([TD-0009](TD-0009-seed-fon-braced-not-postfix.md)).
Both packages are named `fpl`, so one interpreter cannot hold the two.

## Remedy

Ship the seed inside the wheel and find it from the package, not from the checkout. A
literate REPL page on the tangled tree, run in-process, is the end state; it waits until
the session log speaks the postfix FON.

## Plan

1. A test that lays `python/fpl` out as the wheel does, with the seed beside it, and runs
   `python -m fpl repl` from outside the checkout on `1 2 +`. It fails today.
2. `[policy]`: `01-bootstrap/pyproject.toml` force-includes the seed as `fpl/_seed/fpl`
   in the wheel.
3. The CLI note looks for the seed in `fpl/_seed` first, then in the checkout, and gives
   the child the seed's root ahead of its own `sys.path`, so the dependencies stay
   visible; retangle `python/fpl`.
4. `flake.nix` builds the wheel in the Nix sandbox (`packages.fpl`, hatchling, click,
   lark and icontract from nixpkgs, no network), and `checks.<system>.fpl-repl` runs
   `echo '1 2 +' | fpl repl` and `fpl --help` against it, so `nix flake check` holds the
   installed command. `make nix-check` runs it outside the fast lane.

## How to reproduce

```sh
nix develop -c sh -c 'uv build --offline --wheel --out-dir "$T/dist" 01-bootstrap \
  && uv venv --offline -q "$T/venv" \
  && uv pip install --offline -q --python "$T/venv/bin/python" "$T"/dist/*.whl \
  && cd "$T" && echo "1 2 +" | "$T/venv/bin/fpl" repl'
```

with `T` a scratch directory outside the checkout. Run on 2026-10-22 at d450bf3.

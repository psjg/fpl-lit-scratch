---
type: Note
title: The shell filters after parse send rendered source text, not FON of the representation
description: "`fpl parse`, `fpl desugar` and `fpl elaborate` write the program rendered back to source as a FON string, and every later filter re-lexes and re-parses it, so no representation after Tokens crosses the pipe."
tags: [bootstrap, fon, pipe]
status: deprecated
date: 2026-10-21
found-in: [01-bootstrap/python/fpl/pipe/__init__.py, 01-bootstrap/01.01-boundary/01.01.03-pipe.md]
related:
  - ../adr/ADR-0002-fon-is-the-stage-protocol.md
  - ../adr/ADR-0004-native-abts-fon-at-boundaries.md
closed-by: df857db
---

Contradicts [ADR-0002](../adr/ADR-0002-fon-is-the-stage-protocol.md) (a filter writes
`FON<B>`) and [ADR-0004](../adr/ADR-0004-native-abts-fon-at-boundaries.md) (a representation
is materialised as FON at the process boundary).

## Symptom

For the source `1 2 +`, the bytes after each filter are:

```text
source:   「1 2 +\n」
lex:      { 「source」 … 「tokens」 ⟨ ( 「TOKEN」 「1」 0 1 ) … ⟩ … }
parse:    「1 2 +\n」
desugar:  「1 2 +\n」
eval:     「[ 1 2 + ]\n」
```

`parse` writes the same FON string as `source`. `desugar` writes the parsed program, not the
result of desugaring.

## Cause

`_run` in `01-bootstrap/python/fpl/pipe/__init__.py` (tangled from `01.01.03-pipe.md`) has a
real codec only for tokens (`fonify_tokens`, `defonify_tokens`). For `parse` it returns
`fonify_text(render(program))`. For `desugar`, `elaborate` and `eval` it reads that text and
runs `parse_pass(lex_pass(text))` again; `desugar` then drops the value of `desugar(program)`
and returns `fonify_text(render(program))`, and `elaborate` likewise. Only `eval` returns a
result of its own stage.

## Remedy

Write lossless FON codecs for Syntax and every later representation, so a filter decodes
`FON<A>`, runs the stage on the native value and encodes `FON<B>`; then remove the
render, re-lex and re-parse path. A generic, type-driven `defonify >> stage >> fonify` would
also replace the stage-name switch in `_run`. Equality of the piped and the in-process result
per boundary is the check ([TD-0007](TD-0007-pipeline-lab-missing-fon-cell.md)).

## How to reproduce

From the repository root, in `nix develop`, with `01-bootstrap/python` on `sys.path` under
`uv run --project 01-bootstrap python`: call `fpl.pipe._run` with `"source"` on `b"1 2 +\n"`,
then `"lex"`, `"parse"`, `"desugar"` and `"eval"` on each previous output, and print each.
Run on 2026-10-21; the output is the one shown above.

## Closed

Closed by df857db, which implements
[ADR-0002](../adr/ADR-0002-fon-is-the-stage-protocol.md). Every filter now reads and writes
FON of its own representation through the codecs in `01.01.05-codec.md`; `_run`, its
stage-name switch and the render/re-lex/re-parse round trip are gone, and errors cross the
pipe as Error documents. `prove.py` and `tests/test_lit_equivalence.py` hold the shell route
against the direct one, and fail if a filter lexes or parses again (d02b8af).

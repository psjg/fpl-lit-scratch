---
type: Note
title: The pipeline lab promises a FON cell it does not have, and nothing compares the two routes
description: "01.05.01-pipeline.md says one cell is the in-process chain and the other the same passes across FON, but only the in-process cell exists, and no test checks that the piped route equals the in-process one."
tags: [bootstrap, lab, test]
status: draft
date: 2026-10-21
found-in: [01-bootstrap/01.05-labs/01.05.01-pipeline.md, 01-bootstrap/tests/test_main.py]
related:
  - ../adr/ADR-0001-passes-are-pipeable-filters.md
  - ../adr/ADR-0004-native-abts-fon-at-boundaries.md
closed-by:
---

Contradicts the page's own first sentence, and leaves the equality that
[ADR-0004](../adr/ADR-0004-native-abts-fon-at-boundaries.md) requires of its two routes, and
that [ADR-0001](../adr/ADR-0001-passes-are-pipeable-filters.md) relies on, unchecked.

## Symptom

`01-bootstrap/01.05-labs/01.05.01-pipeline.md` reads "One cell is the in-process chain. The
other is the same passes across FON." It holds one code cell besides `setup`:
`run_now = fpl.lex >> fpl.parse >> fpl.desugar >> fpl.elaborate >> fpl.evaluate`.

## Cause

The second cell was never written. `01-bootstrap/tests/test_main.py` starts a subprocess only
for a fuel-limit test; no test runs a stage through the pipe and compares it with the
in-process pass.

## Remedy

Add the FON cell, and a test of the same claim: for each boundary,
`defonify(pipe(stage, fonify(x))) == stage(x)`, and for the whole linear chain,
direct equals shell. Until [TD-0006](TD-0006-pipe-reparses-rendered-text.md) is fixed the
check can only hold for `source` and `lex`, which is itself the useful signal.

## How to reproduce

Read `01-bootstrap/01.05-labs/01.05.01-pipeline.md`. Search `01-bootstrap/tests/` for a test
that compares piped and in-process output; none was found on 2026-10-21 (a grep, not an
exhaustive read).

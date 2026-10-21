---
type: Note
title: Pass composition erases its structure into a closure
description: "`Pass.__rshift__` returns a new Pass whose function is `lambda value: nxt(self(value))`, so a chain keeps only a name string and no executor, tracer or program can see its parts."
tags: [bootstrap, compose]
status: deprecated
date: 2026-10-21
found-in: [01-bootstrap/python/fpl/arrow.py, 01-bootstrap/stamp.py, 01-bootstrap/01.04-compose/01.04.01-pass.md]
related:
  - ../adr/ADR-0012-pipeline-is-a-computation-graph.md
  - ../adr/ADR-0010-first-class-staging.md
closed-by: a898ec1
---

Contradicts [ADR-0012](../adr/ADR-0012-pipeline-is-a-computation-graph.md) (draft: a
composition is data before it runs) and gets in the way of
[ADR-0010](../adr/ADR-0010-first-class-staging.md) (a program may inspect and extend a
pipeline).

## Symptom

```python
def __rshift__[C](self, nxt: Pass[B, C]) -> Pass[A, C]:
    return Pass(f"{self.name}>>{nxt.name}", lambda value: nxt(self(value)))
```

`(lex >> parse).name` is `"lex>>parse"`; the two passes inside are reachable only by calling
the closure.

## Cause

`Pass` in `01-bootstrap/python/fpl/arrow.py` is a frozen dataclass of `name` and `fn`. The
same code is written into the pages by `01-bootstrap/stamp.py` (around line 533), so a fix
starts there and regenerates the pages.

## Remedy

Make `a >> b` build a structural value (a `Pipeline` of passes, or nested `Then` normalised to
a flat sequence) that stays callable, and add a minimal direct interpreter for it; later
interpreters (pipe, trace, explain, a scheduler) read the same value. `run_now` and the
pipeline lab keep working because the value is still callable.

## How to reproduce

Read `01-bootstrap/python/fpl/arrow.py`.

## Closed

Closed by a898ec1, which implements
[ADR-0012](../adr/ADR-0012-pipeline-is-a-computation-graph.md). `>>` now builds
`pass_compose(a, b)`, a flat `PassCompose` value whose stages can be listed, printed and
run: `direct` runs it in process, `run_shell` as a Unix pipe (df857db), and `fpl.graph`
reads it as a graph (e3a56c9).

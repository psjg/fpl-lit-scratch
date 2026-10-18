---
title: REPL phrase costs
---

# 02.05.05 2026-10-18 — REPL phrase costs

Accepted and in the literate TTY REPL. This note keeps the shape that was locked before
the feat, and the non-goals that still hold.

## Context

The TTY REPL reads as a promptless transcript: no `fpl>`, results as `|- <value> : ...`,
and ASCII `;;!` phrase bars between turns. See
[Turnstile notation](../../02.04-explanation/inspiration/turnstiles.md).

```text
;;! -( 22:52:09 )-< command 1 >-----------------------------{ head: 0 }-
1 1 +
|- [ 1 1 + ] : ...
;;! -( 22:52:17 )-< command 2 >-------------{ head: 1; fuel: 12; ms: 0.4 }-
```

The bar carries clock time, phrase number, and session head. After an eval, the **next**
bar also names that phrase’s steps spent and wall ms. The bar field stays `fuel`; the
literature synonym is **gas** (PLFA). If spent fuel later moves onto the `|-` line, call
that component a **deadline** (prefer `@ <n>` chrome) — see
[Evaluation judgments](../../02.04-explanation/inspiration/judgments.md) (`02.04.03`).

## What the walker exposes

- [`Meter`](../../../01-bootstrap/fpl/eval.py) keeps the initial `budget` beside `left` and
  reports `spent` (`budget - left`). `evaluate` / `stacks` can append each run line’s spent
  into a sink, including when the line then fails.
- `enter` sums spent only for the **new input’s** run lines (history replay is omitted) and
  puts that on `Outcome.spent`. Session `event.fuel` stays the **budget**.
- The TTY loop times an entered source with `perf_counter` and prints prior `fuel` / `ms` on
  the next `;;!` `{ … }` block. First bar, pure `:command`s, and refusals that never enter
  omit both fields. A definition with no run lines omits `fuel` but may still show `ms`.

## Non-goals

- Changing the session log schema to persist spent fuel or wall time.
- Filling the result type slot (`: ...`) with real types — separate concern.
- Unicode box-drawing or other non-ASCII chrome on the bar.
- Changing non-TTY pipes or `-e` output; costs stay a TTY transcript feature.

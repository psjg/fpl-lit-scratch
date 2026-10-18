---
title: REPL phrase costs
---

# 02.05.05 2026-10-18 — REPL phrase costs

A proposal, not a decision. None of it is implemented. If it is accepted it becomes a
small feat on the literate TTY REPL; if it is not, this note records why.

## Context

The TTY REPL already reads as a promptless transcript: no `fpl>`, results as
`|- <value> : ...`, and ASCII `;;!` phrase bars between turns. See
[Turnstile notation](../../02.04-explanation/inspiration/turnstiles.md).

Example of what exists today:

```text
;;! -( 22:52:09 )-< command 1 >-----------------------------{ head: 0 }-
1 1 +
|- [ 1 1 + ] : ...
;;! -( 22:52:17 )-< command 2 >-----------------------------{ head: 1 }-
```

The bar carries clock time, phrase number, and session head. It does not say what the
last phrase cost.

## What exists today

Fuel metering is real work and already in force:

- [`Meter`](../../../01-bootstrap/fpl/eval.py) counts steps down (`left`); a run stops with
  `out of fuel` at the line.
- The REPL takes `--fuel N`; session events store that **budget** as `event.fuel`.
- `metered()` sets a meter, runs the line, then discards it in `finally`. Nothing returns
  how many steps were spent.
- There is no wall-clock timing around a REPL phrase.

So the harness knows the *ceiling*. It does not yet report the *cost*.

## Proposal

When someone implements this, keep the shape small and ASCII-only.

1. **Spent fuel.** After a run line finishes (ok or error), report steps spent from the
   meter — typically `budget - left` — up through `enter` / `_turn` so the loop can see it.
2. **Wall time.** Wrap the turn with `perf_counter` (or equivalent) and keep milliseconds
   as a plain number.
3. **Where it prints.** Put the previous phrase’s costs on the **next** `;;!` bar’s
   `{ … }` block, so the bar stays status *between* phrases:

```text
;;! -( 22:52:17 )-< command 2 >-------------{ head: 1; fuel: 12; ms: 0.4 }-
```

   `fuel` here means steps spent on the previous phrase, not the session budget. `ms` is
   wall time for that phrase. Omit either field when there is no previous phrase (first
   bar) or when the previous turn was not an eval (for example a pure `:command` with no
   meter).

## Non-goals

- Changing the session log schema to persist spent fuel or wall time.
- Filling the result type slot (`: ...`) with real types — separate concern.
- Unicode box-drawing or other non-ASCII chrome on the bar.
- Changing non-TTY pipes or `-e` output; costs stay a TTY transcript feature.

## Why this is worth a note

The utop-shaped transcript is already easy to copy. Costs next to `head` would make the
same buffer a light performance log without a second tool. The missing piece is a few
lines of reporting, not a new subsystem — but until Meter exposes spent steps, the UI
has nothing honest to print.

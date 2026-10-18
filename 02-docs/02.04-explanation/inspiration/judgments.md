---
title: Evaluation judgments
---

# 02.04.04 2026-10-18 — Evaluation judgments

A map of cousins for treating the REPL transcript as **equateable oordelen**, not
pretty-print. This note does **not** invent FPL language semantics; it names a pattern
and what we have not built. Implementation of first-class errors and deadlines on the
`|-` line waits on a later plan.

## The pattern

**Multi-component evaluation judgments:** each successful (or failed) phrase leaves a
line you could copy into a fixture — value, and eventually type, cost, error — in one
shape. Status *between* phrases (clock, head, wall ms) stays on the phrase bar; what you
would *equate* belongs on the judgment line.

Today the shell already uses [turnstile](turnstiles.md) form and bar costs:

```text
;;! -( 22:52:09 )-< command 1 >-----------------------------{ head: 0 }-
1 | 1 +
|- 2 : ...
;;! -( 22:52:17 )-< command 2 >-------------{ head: 1; fuel: 3; ms: 0.4 }-
```

See [REPL phrase costs](../../02.05-project/notes/repl-phrase-costs.md) for what `fuel`
and `ms` on the bar mean now (`fuel` = steps spent; `event.fuel` remains the budget).

## Axes

Three questions for every cousin below:

1. **Judgment line vs between-phrase status.** What is equateable (`|- …`) vs chrome
   (`;;! { … }`)?
2. **Spent fuel vs wall time.** Steps are deterministic enough to name; wall ms is a
   thermometer, not a law.
3. **Failure as value vs failure as channel.** Does the error sit in the value domain
   (Result / error-union), or only on stderr / exception unwind?

**Vocabulary.** When spent fuel later appears on the judgment line, call that component a
**deadline** (steps taken under the meter). Keep wall `ms` on the bar.

## Lineage

### Result and error-unions

Rust `Result`, Zig error sets, Elm / Roc `Result`: failure is a value you can match and
return.

- Steal: errors in the value domain, so a transcript can show the same shape for ok and
  fail once FPL has native error syntax.
- Not yet: no FPL error term; TTY failures are still `ERROR: …` lines, not `|- …`.

### Effect handlers

Eff, Koka, Unison abilities: failure (and other effects) as something a handler can turn
back into a value.

- Steal: failure as an effect you can handle, not only an exit.
- Not yet: no effect system; Eff is a cousin, not a delivery promise.

### Restarts and supervision

Erlang supervision, Eiffel rescue/retry, the Common Lisp condition system: recover or
restart without pretending the failure never happened.

- Steal: a north-star for “gore restart” — recoverable failure in a live system.
- Not yet: no design; not a numbered playground part. Open as ambition only.

### Fuel and deadlines

Idris / Agda fuel arguments for totality; graded / resource-aware types: cost as part of
meaning.

- Steal: spent steps as something you can name next to the result; **deadline** = that
  spent count on a future judgment slot.
- Not yet: fuel and ms sit on the next `;;!` bar only; nothing on `|-` yet.

## Deferred (separate plan)

Do **not** invent syntax in this note. When someone writes the next plan, it covers:

1. Native error syntax so failures can live in the value domain.
2. Deadline (spent fuel) on the `|-` judgment line (bar may keep `head` and wall `ms`).

Until then, the ledger in [README.md](README.md) keeps those promises as `deferred`.

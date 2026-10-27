---
type: Note
title: "DI-0056 Spec examples as conformance assertions"
description: "an example in a spec carries an id and its expected output, a negative example its expected diagnostic category, and every example has one of five kinds"
status: draft
date: 2026-10-27
related: []
---

# DI-0056 Spec examples as conformance assertions

## His words

> ik denk echter dat jouw toevoegingen ***ZEER*** waardevol kunnen zijn

(on the remark that FPL should keep concepts in literate chapters, public semantics near the
code, executable examples as claims and tests as the evidence layer, "almost an executable
language specification"; the proposal below came in answer to it).

## Context

From a design conversation of 2026-10-27 (not in the repo), taken from nbdev's example, evidence,
test idea. The proposal: an example inside a spec's prose is a conformance assertion with an id
and an expected observation, conceptually ```` ```fpl {.spec #nat-add-basic expect="3"} ````;
a negative example names the diagnostic category it must produce, not the exact message
(```` {.spec-error #add-type-error} ````, category, location); and every example has one of five
kinds:

| kind | meaning |
| --- | --- |
| example | teaching, not normative |
| spec-example | a normative positive case |
| counterexample | a program that must be refused |
| law | a property over many inputs |
| regression | one former bug |

What already exists, so the delta is small:

- The archived oracle, `03-fpl/OLD/03.01-features/<name>/`, is the executable spec: `spec.md`
  plus `examples/*.fpl` and `*.expected`, run by `01-bootstrap/tests/test_conformance.py`
  ([conventions](../../../.agents/CONVENTIONS.md)). The examples are separate files beside the
  prose, identified by file name; an error case is the exact line `ERROR: <line>:<col> <message>`.
- The [errors reference](../../02.03-reference/02.03.01-errors.md) already makes the path tag
  `err/<tag>` "the stable id for fixtures", which is the diagnostic category this item wants.
- `lit` runs every `pycon` fence of a walker page as a doctest (`lit-example`), so examples in
  prose are executable today, for Python, without ids or kinds.
- [DI-0016](DI-0016-conformance-suite-inside-fpl-image.md) keeps the fixtures as data run by
  both the bootstrap and FPL; [DI-0023](DI-0023-repl-results-as-judgement-claims.md) and
  [DI-0050](DI-0050-inplace-doctest-for-prose-claims.md) want results and prose claims checked
  in place.

The delta: the assertion lives in the prose with an id; a refusal is matched by `err/<tag>`
and location, not by message text; and the five kinds are named, so a reader and the runner
both know which examples are normative. Where the next oracle lives is undecided (conventions:
"the next oracle home is undecided").

## Options and outcome

Open.

## Related

- related:: [02.05.15 One source form](../notes/02.05.15-one-source-form.md)
- related:: [DI-0016](DI-0016-conformance-suite-inside-fpl-image.md)
- related:: [DI-0050](DI-0050-inplace-doctest-for-prose-claims.md)
- related:: [Errors and diagnostics](../../02.03-reference/02.03.01-errors.md)

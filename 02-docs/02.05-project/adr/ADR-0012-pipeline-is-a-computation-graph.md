---
type: ADR
title: "ADR-0012 The pipeline is an inspectable computation graph that several executors run"
description: "A composition of passes is data before it runs; in-process execution, the shell pipe and a dependency scheduler are interpreters of the same graph, and work runs out of order only as far as dependencies allow."
tags:
  - adr
status: draft
rejected: false
date: 2026-10-21
deciders:
  - "psjg"
supersedes: []
superseded-by:
related:
  - ADR-0001-passes-are-pipeable-filters.md
  - ADR-0004-native-abts-fon-at-boundaries.md
  - ADR-0010-first-class-staging.md
  - ADR-0013-events-observe-not-drive.md
affects:
  - ../../../01-bootstrap/python/fpl/arrow.py
  - ../../../01-bootstrap/01.04-compose/01.04.01-pass.md
  - ../../../01-bootstrap/01.04-compose/01.04.02-run.md
  - ../../../01-bootstrap/01.04-compose/01.04.03-inspect.md
  - ../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md
drivers:
  - "run the same pipeline with different interpreters"
  - "out-of-order and parallel work, but only as far as dependencies allow"
  - "the semantics must not change with the executor"
  - "a pipeline a program can inspect, explain and extend (ADR-0010)"
options:
  - name: "A reified, typed computation graph; executors interpret it"
    chosen: true
    pros:
      - "direct, shell, process, job-scheduler and later remote execution share one meaning"
      - "the graph can be shown, traced, cached and explained before or while it runs"
      - "a dynamic graph (a computation may demand more computations) covers what a static DAG cannot"
    cons:
      - "a graph value and an interpreter to build before any speed-up appears"
      - "dynamic demands during elaboration need suspend and resume"
  - name: "A dependency-driven job system as the architecture (Jai-like)"
    chosen: false
    pros:
      - "parallel, out-of-order compilation with work stealing and priorities"
    cons:
      - "an execution machine, not a program: the pipeline exists only as it runs"
  - name: "An event-driven compiler"
    chosen: false
    pros:
      - "very dynamic; natural for watchers, editors and REPLs"
    cons:
      - "dependencies hide in callbacks; see ADR-0013"
  - name: "A fixed linear list of passes (the tree today)"
    chosen: false
    pros:
      - "simplest; already runs"
    cons:
      - "one execution strategy; no branching, caching or scheduling"
---

# ADR-0012 The pipeline is an inspectable computation graph that several executors run

- supersedes:: none
- superseded-by:: none
- related:: [ADR-0001 Pipeable filters](ADR-0001-passes-are-pipeable-filters.md)
- related:: [ADR-0004 Native ABTs, FON at boundaries](ADR-0004-native-abts-fon-at-boundaries.md)
- related:: [ADR-0010 First-class staging](ADR-0010-first-class-staging.md)
- related:: [ADR-0013 Events observe, they do not drive](ADR-0013-events-observe-not-drive.md)
- affects:: [python/fpl/arrow.py](../../../01-bootstrap/python/fpl/arrow.py)
- affects:: [01.04.01 Pass](../../../01-bootstrap/01.04-compose/01.04.01-pass.md)
- affects:: [01.04.02 Run](../../../01-bootstrap/01.04-compose/01.04.02-run.md)
- affects:: [01.04.03 Inspect](../../../01-bootstrap/01.04-compose/01.04.03-inspect.md)
- affects:: [01.01.03 Pipe](../../../01-bootstrap/01.01-boundary/01.01.03-pipe.md)

## Context

The maintainer asked whether the pass design stays fast and can be parallelised, and whether
it is compatible with a job-system compiler of the kind Jai has. Three architectures were set
apart. A dependency-driven job system is an execution machine: jobs, a dependency relation,
and a scheduler that picks among the ready ones. A computation graph is a program
representation: typed nodes and edges that exist as data before anyone decides how to run
them. An event-driven system is a transition system of handlers. A finite static DAG is not a
superset of a dynamic job system (it cannot discover new work while running); a dynamic graph,
in which a computation may demand further computations, is.

The maintainer's answers: running the same pipeline with different interpreters is a good
idea; out of order, but only as far as dependencies allow; and a compiler pipeline that is an
inspectable computation graph, with the scheduler, the shell pipeline, an incremental
evaluator and a distributed executor as its interpreters, is appealing to him, provided it
turns out to be possible. That condition is why this ADR is a draft.

## Decision

A composition of passes is data before it is run: a typed computation graph that may grow
while it runs. The in-process run, the shell pipeline and any later scheduler, process, cache
or remote executor are interpreters of that graph. The graph fixes which orders are legal;
an executor only picks one. The meaning of a program does not depend on the executor.

## Consequences

- The shell pipeline of [ADR-0001](ADR-0001-passes-are-pipeable-filters.md) stays, as the
  linear projection of the graph; graphs that branch are the job of an executor with a
  coordinator, not of `tee` and FIFOs.
- The tree follows this for composition: `>>` in `01-bootstrap/python/fpl/arrow.py` builds a
  `PassCompose`, a flat tuple of stages that refuses a chain whose representations do not
  meet, so the structure of a chain is data, not a name string over an opaque lambda; calling
  it runs the stages directly, and `01-bootstrap/stamp.py` emits the same code into the pages
  ([TD-0008](../techdebt/TD-0008-pass-composition-opaque-closure.md), deprecated: resolved).
  The graph that may grow while it runs is still not built.
- Only one interpreter exists: a direct in-process call (`01.04.02-run.md`); the shell
  filters dispatch on stage names, not on a graph.
- Executors can be tested against each other: a pass run natively must equal the same pass
  run across FON, and a linear pipeline run directly must equal it run through the shell.
- How far this goes (executor taxonomy, task and artifact identity, scheduling order of the
  work) is proposed but not ratified; the proposals and their order are in
  [02.05.06 Pipeline open questions](../notes/02.05.06-pipeline-open-questions.md).

---
type: ADR
title: "ADR-0013 Events observe the compiler; they do not carry its dependencies"
description: "An event stream reports what the compiler does and may trigger new demands from outside, but no event callback runs a compiler action the dependency graph does not name."
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
  - ADR-0012-pipeline-is-a-computation-graph.md
affects:
  - ../../../01-bootstrap/fpl/session.py
  - ../../../01-bootstrap/fpl/log.py
drivers:
  - "answer 'why did elaborate(foo) run again' from the graph, not from callbacks"
  - "file watchers, editors, the REPL and a debugger still need events"
  - "one log that an IDE, a notebook, a visualiser and agents can all read"
options:
  - name: "Events are an observation of the graph and a source of outside demands"
    chosen: true
    pros:
      - "dependencies stay explicit and inspectable"
      - "the same stream serves tooling, notebooks and agents"
    cons:
      - "an event vocabulary to define and keep in step with the graph"
  - name: "Event callbacks trigger compiler actions"
    chosen: false
    pros:
      - "very flexible; easy to add a reaction"
    cons:
      - "dependencies hide in handlers; becomes event spaghetti"
  - name: "No events at all"
    chosen: false
    pros:
      - "nothing extra to build"
    cons:
      - "watchers, editors and a REPL have no way in"
---

# ADR-0013 Events observe the compiler; they do not carry its dependencies

- supersedes:: none
- superseded-by:: none
- related:: [ADR-0012 The pipeline is a computation graph](ADR-0012-pipeline-is-a-computation-graph.md)
- affects:: [fpl/session.py](../../../01-bootstrap/fpl/session.py)
- affects:: [fpl/log.py](../../../01-bootstrap/fpl/log.py)

## Context

With the compiler as a graph of computations ([ADR-0012](ADR-0012-pipeline-is-a-computation-graph.md)),
the question is where events fit. The proposal was to make them secondary: the graph and its
scheduler are the truth, and an event stream (demanded, started, cache hit, produced,
invalidated, diagnostic, completed) is an observation of what they do. The alternative, an
event callback that causes an arbitrary compiler action, soon becomes an event-spaghetti
system. The maintainer agreed with that point.

Events are not bad in themselves: a file watcher, an editor, the REPL, a debugger, hot reload
and user interaction are naturally events. They are bad as the only carrier of dependencies.

## Decision

Events report what the compiler does, and an outside event may submit a new demand or
invalidate an input. No event handler performs a compiler action the dependency graph does not
name; ordering comes from the graph and from explicit effects.

## Consequences

- There is no compiler event stream and no scheduler in the tree. The REPL session
  (`01-bootstrap/fpl/session.py`) derives its state from an append-only log of hashed events
  (`01-bootstrap/fpl/log.py`), but those events are an input or a rewind, not compiler work.
- The event vocabulary above is a proposal; it is not ratified
  ([02.05.06 Pipeline open questions](../notes/02.05.06-pipeline-open-questions.md)).
- Draft because it rests on [ADR-0012](ADR-0012-pipeline-is-a-computation-graph.md), which is
  a draft.

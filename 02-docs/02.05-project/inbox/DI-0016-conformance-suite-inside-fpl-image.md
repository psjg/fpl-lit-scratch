---
type: Note
title: "DI-0016 The conformance suite inside the FPL image"
description: "features/ as the oracle any implementation passes; where does it live in FPL's own namespace"
status: draft
date: 2026-10-05
related: []
---

# DI-0016 The conformance suite inside the FPL image

## His words

> we must find a path for it within the FPL image then

## Context

Said on the move of fpl/. Later, reviewing #133: "moet features niet onder fpl hangen? ... dan kan FPL zichzelf in de toekomst testen?". Answer: yes, possible. features/ is language-neutral data (spec.md, .fpl examples, .expected). The risk: the judge is the defendant, so one bug could hide in both. Remedy: fixtures stay pure data; bootstrap (Python) and FPL run the same fixtures as a differential check, which keeps the walker useful after self-hosting. Not in #133 (a pure move under review; the spec guard keys on today's paths).

## Options and outcome

A later PR once fpl/ becomes FPL's tree; the exact path (e.g. fpl/spec/, fpl/test/) is for the design agents.

## Related

- related:: [spec](../../02.03-reference/spec.md)


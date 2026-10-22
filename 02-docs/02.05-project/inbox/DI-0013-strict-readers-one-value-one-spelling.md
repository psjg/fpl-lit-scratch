---
type: Note
title: "DI-0013 Strict readers: one value, one spelling"
description: "the writer emits one canonical form; the reader refuses every other spelling"
status: stable
date: 2026-10-05
related: []
---

# DI-0013 Strict readers: one value, one spelling

## His words

> afweging tussen bandbreedte vs correctness (met Postels les in het achterhoofd) ... normaliseren en misschien zelfs een error gooien

## Context

Said on #122's FON hex floats. The source he recalled is RFC 9413 "Maintaining Robust Protocols" (2023): tolerating faulty input makes it the de facto standard. Belongs with correctness by construction, as a principle for FON and for FPL's readers.

## Options and outcome

Decided as a principle. Consequence used in DI-0023.

## Related

- related:: [ADR-0003](../adr/ADR-0003-fon-is-an-fpl-subset.md)


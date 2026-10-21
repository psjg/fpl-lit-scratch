---
type: Note
title: "DI-0026 Native ABTs in an address space, FON at a serialisation boundary"
description: "compose in-process without text; materialise to FON over a pipe"
status: stable
date: 2026-10-17
related: []
---

# DI-0026 Native ABTs in an address space, FON at a serialisation boundary

## His words

> als het binnen een adres space gecomponeerd wordt dat die gewoon ABT's door yeet maar dat als het als een unix pipeline draait dat het dan materialiseert naar FON over de pipe heen

## Context

Also: "idealiter zouden het losse programma's kunnen zijn die gepiped kunnen worden (compositie)"; FON is a subset of FPL easier to push over the wire, a pseudo-binary ASCII postfix format; FPL natively has an ABT and only needs a textual materialisation. A pass knows nothing of FON: the shell wrapper decodes and encodes. FON sits under the pipeline (transport, not a stage); a FON decoder that needs the full evaluator would be a design error.

## Options and outcome

Decided; recorded in ADR-0003, ADR-0004, ADR-0005.

## Related

- related:: [ADR-0003](../adr/ADR-0003-fon-is-an-fpl-subset.md)
- related:: [ADR-0004](../adr/ADR-0004-native-abts-fon-at-boundaries.md)
- related:: [ADR-0005](../adr/ADR-0005-fonify-defonify.md)


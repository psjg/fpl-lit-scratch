---
type: Note
title: "DI-0031 Shell UX: `fpl lex | fpl parse | fpl eval`"
description: "one executable, subcommands generated from the pass registry"
status: stable
date: 2026-10-19
related: []
---

# DI-0031 Shell UX: `fpl lex | fpl parse | fpl eval`

## His words

> fpl prelex | fpl lex | fpl parse | fpl eval

## Context

Ingress `source` and egress `render` were added; the pipe is `fon.decode >> stage >> fon.encode`, and a `>>` chain orders passes without being the semantics (resolve, expand and elaborate may interleave later). A `__main__.py` is a 2-4 line generic stdio adapter. Third-party CLI libraries are welcome ("zeker niet! als ik het beter kan maken met extra libraries dan is dat een geweldig idee").

## Options and outcome

Decided; ADR-0006 and ADR-0007.

## Related

- related:: [ADR-0006](../adr/ADR-0006-one-fpl-executable.md)
- related:: [ADR-0002](../adr/ADR-0002-fon-is-the-stage-protocol.md)


---
type: Note
title: "DI-0028 Hold as much state as long as possible; strip in a release build"
description: "information-monotone passes with stable identities; stripping only at release"
status: stable
date: 2026-10-17
related: []
---

# DI-0028 Hold as much state as long as possible; strip in a release build

## His words

> ik wil graag zoveel mogelijk toestand zo lang mogelijk vasthouden; een optimizing release build kan het allemaal shaken aan het einde (-O1..4)

## Context

Passes keep stable node identities and provenance; only a release build strips.

## Options and outcome

Decided; recorded as ADR-0009.

## Related

- related:: [ADR-0009](../adr/ADR-0009-keep-information-strip-at-release.md)


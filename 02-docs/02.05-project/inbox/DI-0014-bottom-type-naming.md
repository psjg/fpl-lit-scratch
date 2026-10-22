---
type: Note
title: "DI-0014 Bottom type naming: abort, never, bottom glyph"
description: "a name for the bottom type; `!` is taken (force)"
status: draft
date: 2026-10-05
related: []
---

# DI-0014 Bottom type naming: abort, never, bottom glyph

## His words

> `-- abort` is cleaner dan een switch plus unicode

## Context

Totality early means a bottom type; `!` is taken by force (`! q -- x`). Measured on 10-05 (marginal tokens in `loop : x -- ...`): `never` is 1 token everywhere; the bottom glyph is 3 tokens in cl100k and 2 in o200k, 1 alone in Qwen and DeepSeek but 2 or more mid-line; `NEVER` is 1 mid-line in open BPEs but 4-5 in Claude; `abort` is 1 in open BPEs and 2-3 in Claude; `_|_` is 2-3. Agent prior: `abort` names the act whose effect ends in the bottom type, as Rust `panic!()` has type `!`; it fits the Unix genealogy (abort(3)); `panic` may exist beside it. His reactions: the glyph "leest wiskundiger en is vet"; `_|_` is ugly and may clash with `|`; `never` is fine; NEVER in caps jumps out. Mercury's `erroneous` determinism is the same idea. Connect to panic/restart (condition systems) and Eiffel contracts.

## Options and outcome

Open: pick by first-contact eval and a token count of the glyph, `never` and `NEVER`.

## Related

- related:: [spec](../../02.03-reference/spec.md)


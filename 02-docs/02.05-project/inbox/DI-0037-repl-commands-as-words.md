---
type: Note
title: "DI-0037 REPL introspection as words, not `:` commands"
description: "everything about the program is a word or path with data on the stack"
status: stable
date: 2026-10-12
related: []
---

# DI-0037 REPL introspection as words, not `:` commands

## His words

> zijn meestal niet handig en werken vaak beter als ze een echt onderdeel van de taal zelf zijn ... ze faciliteren reflectie

## Context

After a side-session on `:`. Everything about the program is a word/path (`words/*/effect`, documentation, history); only what acts on the log or terminal (rewind, quit, canonical) stays a command, as sugar over a function the CLI also exposes, and a `:`-led token in code is a lexer error so the namespaces are disjoint. Lessons checked against primary sources: CL `apropos` prints versus `apropos-list` returns; Python `dir`/`vars` return versus `help` prints; Forth `WORDS`; APL `)FNS` to `NL` migration; psql `\d` with ECHO_HIDDEN; Unison keeps the codebase outside the language.

## Options and outcome

Decided direction. Reshape the words session function into the evaluator of `words/*/effect` rather than merging a `:words` command.

## Related

- related:: [02.05.05 REPL phrase costs](../notes/02.05.05-repl-phrase-costs.md)


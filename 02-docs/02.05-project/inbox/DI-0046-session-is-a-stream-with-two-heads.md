---
type: Note
title: "DI-0046 The session is a stream with two heads"
description: "REPL session as a stream over the append-only hashed .fon log: --at is the read head, --head the write head; the log is a queryable directory; REPL commands become words"
status: draft
date: 2026-10-17
related: []
---

# DI-0046 The session is a stream with two heads

"De sessie is een stream met twee koppen." From the 2026-10-17 REPL-design session.

## His words

> dit soort uitzonderingen zijn meestal niet handig en werken vaak beter als ze een echt onderdeel van de taal zelf zijn ze zijn dan principieel meestal ook beter omdat ze compositie doorgeven aan andere delen van de taal... ze faciliteren reflectie

## Context

The session is a stream over the append-only, hashed `.fon` log.

- `--at EVENT` is the read head: a free seek that leaves no trace.
- `--head EVENT` is the write head: append only against the checked head, under the session lock.
- Frontends (line stream, PTY, TUI) are cursors on one log: several readers, one writer.

The log is a queryable directory for the language itself:

- `log/*`, `log/N/input`, `log/N/program`, `log/N/fuel`.
- `log/N/output` is derived, not stored; a `|=` claim pins an output as an event.
- `rewind` is an event `log/rewind` with `+log`; a seek is a query.

The prompt shows position (`3> `, `1@3> `), and the reader swallows the exact prompt prefix, so a pasted transcript still reads.

REPL commands become words and paths (`words/*/doc`, `help` as a view), with no `:`-commands.

Precedents, verified in that session from primary sources: VMS DCL HELP/SET COMMAND, C64 BASIC immediate mode, Plan 9 rc, PowerShell Get-Command/Get-Help, nushell help-as-table, Genera "no command levels", TempleOS DolDoc executable links, Oberon M.P, Acme, IPython `In [N]:`, Pharo streams/Transcript, Scheme ports.

Not decided: "een Jupyter-kernel bouwen". Jupyter and nREPL were named as protocol models only.

## Options and outcome

Open. Draft only; nothing here is decided beyond what the session recorded.

## Related

- related:: [DI-0044](DI-0044-bqnpad-as-model-for-ide-repl.md)
- related:: [DI-0045](DI-0045-editor-and-repl-session-collapse.md)
- related:: [ADR-0006](../adr/ADR-0006-one-fpl-executable.md)
- related:: [02.04.02 turnstiles](../../02.04-explanation/inspiration/02.04.02-turnstiles.md)
- related:: [02.04.03 judgments](../../02.04-explanation/inspiration/02.04.03-judgments.md)
- related:: [DI-0037](DI-0037-repl-commands-as-words.md)
- related:: [DI-0039](DI-0039-colon-is-the-judgement-sign.md)
- related:: [DI-0022](DI-0022-repl-transcripts-round-trip.md)

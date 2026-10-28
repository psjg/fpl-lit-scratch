---
type: Note
title: "DI-0069 The space before a comment as part of its token"
description: "when every pad line ends in ` ;`, is the space before the comment sign part of the NOTE token?"
status: draft
date: 2026-10-28
related: []
---

# DI-0069 The space before a comment as part of its token

## His words

> en voeg een `;` aan het einde van elke regel toe

> Elke regel

> oh misschien moet de ene whitespace voor de comment token onderdeel worden van de token... hmmm....

## Context

Said while the pad (the one-buffer front end on the REPL session) was being shaped. The pad is to end every non-blank line of its buffer in ` ;`: bars, inputs and result lines alike. In the grammar a NOTE is `(;(?!;)|⍝)[^\n]*` and `;` is not a TOKEN character, so `1 | 1 + ;` and `1 | 1 +;` both read as the code and an empty note; the program is the same with or without the terminator, which is what lets a pad buffer round-trip.

The thought: the one space before `;` could belong to the NOTE token itself.

## Options and outcome

Open. Options:

- The space stays whitespace: `;` opens a note wherever it stands, `a;b` is `a` and a note `;b`. The pad writes ` ;` and strips exactly that on reading. Nothing in the grammar changes.
- The space is part of the NOTE token (` ;…`, or the start of a line): a note is always set off from the code by a space, and `;` glued to a word is then either a lexing error or a word character. This changes what `a;b` means and needs a `[spec]` change, DI-0013 (one spelling per value) weighs on it.
- A line terminator of its own, apart from the note: `;` at the end of a line as a sign that the line is a statement, read and written by the pad only.

## Related

- related:: [DI-0022](DI-0022-repl-transcripts-round-trip.md)
- related:: [DI-0045](DI-0045-editor-and-repl-session-collapse.md)
- related:: [DI-0039](DI-0039-colon-is-the-judgement-sign.md)

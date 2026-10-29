---
type: Note
title: "DI-0071 Line numbers as part of the grammar"
description: "every line carries its number, as BASIC and COBOL did: 10: 20: 30:"
status: draft
date: 2026-10-29
related: []
---

# DI-0071 Line numbers as part of the grammar

## His words

> of... we doen iets anders whacky's en dat had ik eigenlijk ook altijd wel willen zien... we maken regelnummers onderdeel van de grammatica...
> dus
> 10:
> 20:
> 30:
> 40:
> 50:
> 60:
> je weet well overal een regelnummer voor vgm deden cobol en basic dat ook zo ooit?

## Context

Said in the pad, looking at the margin beside the buffer. BASIC numbered every line and used the numbers for `GOTO` and for inserting lines between them (hence the steps of ten); COBOL's columns 1 to 6 held a sequence number for the card deck. In the pad a number per line would be an address for a cell or a result, and the `:` after it meets DI-0039 (colon is the judgement sign).

## Options and outcome

Open: a thought, not a decision. Options: numbers the pad writes and strips, as it writes ` ; `; numbers the grammar reads as labels (then `10:` must not collide with a definition head `name :`); none.

## Related

- related:: [DI-0039](DI-0039-colon-is-the-judgement-sign.md)
- related:: [DI-0046](DI-0046-session-is-a-stream-with-two-heads.md)

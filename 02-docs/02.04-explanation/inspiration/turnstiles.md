---
title: Turnstile notation
---

ASCII inventory of the four turnstile orientations. This note does **not** invent FPL language semantics; it records common logic notation and what the scratch shell uses today.

## The 2×2

Not “two bars,” but **horizontal stroke** (single `-` vs double `=`) × **stem side** (left vs right).

| | Stem left (standard) | Stem right (reversed) |
| --- | --- | --- |
| Single (`-`) | `|-` → ⊢ (`\vdash`) — syntactic / provable | `-|` → ⊣ (`\dashv`) |
| Double (`=`) | `|=` → ⊨ (`\vDash` / `\models`) — semantic / models | `=|` → ⫤ (`\Dashv`) |

FOL teaching mostly uses `|-` (proof) and `|=` (models). The reversed forms exist in Unicode/LaTeX but are rarer.

## What FPL uses now (shell / UI)

Only **`|-`** is a result marker in the scratch experience:

- Playground ghost: grayed `|- <value>` at end of line (decoration).
- Tab / Accept commits a trailing note `; |- <value>` (valid FPL `NOTE` today; `|-` inside the note is convention until a later `[spec]`).
- TTY interactive REPL prefixes successful eval stdout lines with `|- ` (prompts stay `fpl>`). Non-TTY and `-e` stay raw.

`|=`, `-|`, and `=|` are **not** wired. Giving them meaning in the grammar is a future, maintainer-owned decision.

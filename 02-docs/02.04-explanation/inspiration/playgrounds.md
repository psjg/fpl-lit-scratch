---
title: Playgrounds and live programming
---

# 02.04.01 2026-10-18 — Playgrounds and live programming

A map of systems that shape how we think about `/try`, katas, and literate walkthroughs. Axes first, brands second. This note does not invent FPL language semantics; it only situates the shell.

## Taxonomy

Three questions for every entry:

1. **Where does the result live?** In-buffer ghost text (Quokka), a side column (Swift Playground), a separate Term, or the world/image itself (Smalltalk, many Bret Victor demos).
2. **What runs?** Whole buffer, per expression, or a continuous live world.
3. **What is the document?** Scratch pad, graded kata, literate essay, or a living image.

## Core lineage

### Bret Victor

Talks and essays (*Inventing on Principle*, *Learnable Programming*): make the runtime visible; scrub inputs; kill the “edit → compile → pray” loop as a design ethic, not as a single app.

- Steal: results tied to the thing you are looking at; time/input as something you can drag.
- Not yet: scrubbing, timeline, or a real data→picture probe in FPL.

### Smalltalk

The environment *is* the program: image, inspectors, live objects you can poke.

- Steal: inspect state instead of guessing; the tool and the language grow together.
- Steal (browser): **path-browser** — Finder-like columns over `/`-scoped modules
  (Unix / Plan 9 path scopes), body of the selected scope below — System Browser shape
  without classes.
- Not yet: an image, object inspectors, a hot world between edits, or a path-browser UI.

### Glamorous Toolkit

Moldable development: custom inspectors and views for the object in front of you
(Pharo lineage).

- Steal: the tool reshapes itself around the value.
- Not yet: moldable inspectors over walker IR / stack.

### Light Table

Chris Granger’s IDE research vehicle after the Kickstarter: instant eval, “no hidden state,” related code and values in context.

- Steal: evaluate in place; surface what the program is doing now.
- Not yet: a real inspector over walker IR/stack; Light Table itself is not our editor.

### Eve

Follow-on from the Light Table team (`witheve.com`): literate document with code embedded in prose; relational / reactive under the hood. Project inactive; the essays still matter.

- Steal: document = program (closest cousin to Quarto walkthrough + live FPL blocks).
- Not yet: Eve’s language or its grid/block IDE; we are not reimplementing Eve.

### Quokka.js

Live JS/TS scratchpad in the editor: **grayed-out values on the same line** as decorations, plus probe comments (`//?`, etc.). Values are not a separate source column and are not editable as code.

- Steal: type → see; probes when you want a specific value.
- Now: Monaco after-text ghosts with `|-`; Tab commits into `; |- …` notes (`repl-buffer-part4`). Still no `//?`-style probes.

### Swift Playgrounds / Xcode playground

Results in a **column beside the code**, often with richer value previews than a raw stdout string.

- Steal: side-by-side “this line → that value.”
- Not yet: Swift’s value widgets, timeline, or live views. Our gutter is a thin cousin (stdout lines paired 1:1 with source lines).

## Cousins we already brushed in the scratch UI

- **Tour of Go** — lesson left, editor + run right; walkthrough shape.
- **TryAPL / J wasm playground** — full-bleed Edit | Term (or Term | Edit).
- **Codecademy** — Learn | Edit | Term, edge to edge.
- **CodePen** — editors + preview, full width.
- **LeetCode / Exercism** — graded: prompt vs editor; Exercism puts commentary on the right.
- **Observable** — reactive notebooks; code and view woven.
- **JupyterLite / Marimo** — labs we already ship under `werkbank/` and `marimo/`; not the learn/try shell.

## Editor substrate

- **VS Code in the browser** (`vscode.dev`, code-server): full workbench. Possible to embed; heavy for `/try`.
- **Monaco**: the editor core of VS Code (the CodePen / LeetCode path) — highlighting, decorations, no workbench.

When the `<textarea>` is too thin, prefer **Monaco**, not a full VS Code embed. Quokka-style ghost text is much easier with Monaco decorations than with a textarea plus a side gutter.

Current state: playground uses **Monaco** with Quokka-style `|-` ghosts; Tab / Accept commits `; |- …` notes (`repl-buffer-part4`). Katas still use a `<textarea>`. The Swift-cousin side gutter from part 2 is retired on `/try/`.

Turnstile ASCII inventory (notation only): [turnstiles.md](turnstiles.md).

## Splash / MOTD (TTY chrome)

Minecraft-style one-liner at REPL startup — not language keywords. Pool includes FPL /
Favourite / Final Programming Language, don’t get eaten by a grue, west of a white house,
Dunnet, meatdog, Chuck Norris, Gas Town’s Mayor / Overseer, Clipper quips. Full Clipper
ASCII speaking diagnostics lives in [judgments](judgments.md); error tags in
[02.03.01](../../02.03-reference/errors.md). Site: [fpl-lit-scratch](https://psjg.github.io/fpl-lit-scratch/).

## Where FPL `/try` sits today

| Milestone | Tag | What it is |
| --- | --- | --- |
| Pure buffer | `repl-buffer-part1` | Edit holds FPL only; the site wraps `fpl.run.default.src` |
| Live side results | `repl-buffer-part2` | Debounced run + side gutter (Swift-cousin); superseded on playground |
| Instant inline | `repl-buffer-part3` | Monaco + grayed end-of-line decorations (Quokka-cousin) |
| Roundtrip transcript | `repl-buffer-part4` | Ghost `|-`; Tab commits `; |- …`; TTY utop transcript (`|- value : ...`, `;;!` bars) |

Also true right now:

- **Term** is still the full dump and the error surface (raw walker stdout, no `|-` prefix).
- Pairing is **1:1** of non-empty stdout lines with non-blank, non-`;;;` source lines. Matching committed `; |-` notes suppress the ghost; mismatch shows a ghost to refresh. If counts differ, decorations clear and Term carries the truth.
- There is **no walker inspector API** feeding the UI.
- Homepage `{.python .live}` fences stay **Python drivers** for the literate walker story; only playground, katas, and `data-kata` fences are pure FPL.

## Long arc

Order of ambition after the pure buffer. Not a delivery promise — implementation stays in separate plans; this note only names cousins and sequence.

| Part | Name | Cousin | Intent |
| --- | --- | --- | --- |
| 1 | Pure FPL buffer | — | Done (`repl-buffer-part1`) |
| 2 | Live side results | Swift-cousin gutter | Done (`repl-buffer-part2`); playground moved on |
| 3 | Instant inline / probes | Quokka | Done on playground (`repl-buffer-part3`): Monaco after-text; no `//?` probes yet |
| 4 | Roundtrip transcript | Quokka commit + utop | Done (`repl-buffer-part4`): Tab → `; |- …`; TTY promptless `|- value : ...` + ASCII `;;!` phrase bars |
| 5 | No hidden state | Light Table | Inspector over stack / walker IR |
| 6 | Document = program | Eve | Walkthrough/essay as the primary live buffer |
| 7 | Scrub / time | Bret Victor | Parameter scrub; needs cheap deterministic re-run |

**Smalltalk** (path-browser) and **Glamorous Toolkit** sit beside this table as north-stars,
not as numbered parts. Parts 5–7 remain the home for Light Table / Eve / Bret Victor.


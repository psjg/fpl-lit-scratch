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
  without classes. Longer argument (explorer vs tabs vs Miller):
  [Navigation](#navigation-miller-vs-explorer-vs-tabs) below.
- Now (MVP on `/try`, `repl-buffer-part5`): Miller columns above Edit | Term over
  buffer `name/` scopes. Click navigates in the full buffer; Focus (or double-click)
  shows only that scope’s body (edits splice back; `#c=` stays the full source).
  Outline is a client-side indent heuristic, not a second desugar. **Examples** mode
  tab is stubbed (kata library next). Still not: an image, object inspectors, or a
  hot world between edits.

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

Current state: playground uses **Monaco** with Quokka-style `|-` ghosts; Tab / Accept commits `; |- …` notes (`repl-buffer-part4`); Miller **path-browser** columns over buffer paths (`repl-buffer-part5`); **dockable** Paths / Edit / Term (`repl-buffer-part6`). Katas still use a `<textarea>`. The Swift-cousin side gutter from part 2 is retired on `/try/`.

### Docking

RemedyBG / VS-ish panels on `/try` only — **client-only** progressive enhancement on the
static Pages host. `curl …/try/` still returns real Paths / Edit / Term markup
(`data-dock` sections); docking moves those nodes into [dockview](https://dockview.dev)
panels when the bundle loads. No app-shell SPA, no client router: Playground / Katas /
docs stay separate documents.

Default layout: Paths on top (collapsible / closable), Edit | Term below. Drag title bars
to split, reorder, and tab-stack. Layout persists in `localStorage` (`fpl-try-dock-v1`);
**Reset layout** restores the default. Closing Paths replaces the old Hide columns escape;
header **Paths** reopens the panel.

Out of scope for this host (future dock *components* once the shell exists): floating OS
windows, kata-page docking, Light Table / inspector panes, project-file Miller, yazi
previews.

### Scroll host / locked ZUI

Docking is the **guest** inside one workspace. Above it sits a longer-arc **host**: a
scrollable space of workspaces/tiles. Two cousins name the shape without being
requirements:

- **1D strip** — [niri](https://github.com/YaLTeR/niri) / PaperWM scrollable-tiling: columns
  on an infinite horizontal strip; new tiles extend the strip instead of squeezing the
  viewport. Glamorous Toolkit’s **Pager** / TreePager is the in-image cousin: inspect →
  pane to the right → scroll the trail (tool trail, not a window manager).
- **Locked gridded ZUI** — later: a 2D sheet of tiles at fixed scale (or discrete zoom
  steps), not free Pad++ pan/zoom theater. “ZUI feel” by moving the viewport over a
  grid, not by continuous camera freedom.

Layering: curlable HTML shell → (enhance) scroll host → dock guest in the focused tile;
fail closed to today’s static dock / CSS grid. Playground / Katas / docs stay **separate
documents** — no client router, no empty `#root` SPA. Host and dock are progressive
layout behavior; the first bytes must still read as hypertext (HTMX hypermedia doctrine).

Part6 is the dock guest in a single tile (live). A **2D pseudo-ZUI scroller**
(integer camera, edge-peek, trackpad tile-move — browser pan stand-in, not real
`scaleE` ZUI) was tried on `try-tiles` and parked — tag
`repl-buffer-2d-pseudo-zui-failed`. That parks the scroller, not tiles-as-such: a
focused tile hosting the dock (and a **1D niri-style strip**) stay open.

Turnstile ASCII inventory (notation only): [turnstiles.md](turnstiles.md).

## Navigation: Miller vs explorer vs tabs

The playaround question is the same as every large IDE: **where am I in a large
space?** Two common scales both fail.

| Pattern | Strength | Breaks when |
| --- | --- | --- |
| Project **explorer** / folder tree (Cursor left bar) | Whole checkout visible | Depth × width × noise; scroll-hell |
| **Horizontal tabs** | “What do I have open?” | Tab spam; no hierarchy |
| Vertical / tree-tabs | Open set + a bit of structure | Often a second tree beside the explorer |
| **dired** | List + actions in the buffer | One directory at a time; no path columns |
| **Miller columns** (Finder / NeXT; Mark Miller) | Path = columns; focus on *here* | Weak for fifty unrelated open files with no path |

Miller is a candidate to replace **both** explorer and tabs for a path-shaped world:
navigate `demo/ → math/ → inc`, not the whole disk tree; the “open set” is the selected
path plus the body below (Focus = one scope), not twenty tab strips. That is closer to
a Smalltalk System Browser / path-browser than to “IDE with files + tabs.”

**Lived cousins** (not requirements for `/try`): terminal file managers — **yazi**
(column + preview), **vifm** / **mc** (dual-pane), **broot** (tree + fuzzy). Dired was
strong for *action in a directory*; Miller is stronger for *depth without tree spam*.

**FPL fit:** `/`-scoped modules, body under the columns, no class browser. The shell
wants path structure the language already speaks.

| Layer | Status |
| --- | --- |
| Buffer-path Miller on `/try` (indent heuristic, navigate + Focus) | **now** (`repl-buffer-part5`) |
| Dockable Paths / Edit / Term on `/try` (dockview; curlable shell; Reset layout) | **now** (`repl-buffer-part6`) |
| Paths beside Edit = **content-width Miller strip** (editable Edit, not yazi preview) | **now** |
| No empty child column after a leaf / empty dir (no “No children” gutter) | **now** |
| Close / reopen Paths (replaces Hide columns when dock enhances) | **now**; static fallback still has Hide columns |
| Miller arrow-key nav; reopen Edit / Term without full Reset | **open** (dock UX; not the scroll host) |
| Examples mode = kata / library columns | **open** (stub today) |
| Miller as primary playaround nav (mental model vs explorer + tabs) | **vision** |
| Scroll host (1D strip of workspaces; niri / GT Pager cousins) | **vision** |
| Locked gridded ZUI (2D sheet of tiles) | **allude** — longer arc under the scroll host |
| Workspace / project-file Miller (real paths, not only buffer `name/`) | **vision** — separate feat plan |
| Inspector / Light Table panels as further dock components | **open** (dock guest exists; panes not yet) |
| yazi-parity (previews, richer chrome) | **allude** only — not a promise to clone yazi |

**Escape hatch:** close or minimize Paths (or Hide columns when JS/dock fails) →
Edit \| Term fills the height (Tour of Go / early `/try`) when the browser is in the way.

## Splash / MOTD (local TTY chrome)

**Offline for now** — local `make repl` only; not part of the published site face.

At startup a session picks one ASCII **assistant** (Clipper, rare smoke/jonko variants,
meatdog, or none) and prints face + hello line; the same face says **bye** on `:quit` /
clean EOF. Minecraft-style one-liners (grue, white house, Dunnet, Chuck, Mayor, …) sit
in each assistant’s hello/bye pools. Not language keywords; not a MUD.

Diagnostic Clipper sketches: [judgments](judgments.md). Error tags:
[02.03.01](../../02.03-reference/errors.md).

## Where FPL `/try` sits today

| Milestone | Tag | What it is |
| --- | --- | --- |
| Pure buffer | `repl-buffer-part1` | Edit holds FPL only; the site wraps `fpl.run.default.src` |
| Live side results | `repl-buffer-part2` | Debounced run + side gutter (Swift-cousin); superseded on playground |
| Instant inline | `repl-buffer-part3` | Monaco + grayed end-of-line decorations (Quokka-cousin) |
| Roundtrip transcript | `repl-buffer-part4` | Ghost `|-`; Tab commits `; |- …`; TTY utop transcript (`|- value : ...`, `;;!` bars) |
| Path-browser columns | `repl-buffer-part5` | Miller strip above Edit; buffer `name/` outline; navigate + Focus; Examples tab stub |
| Dockable panels | `repl-buffer-part6` | Paths / Edit / Term via dockview; curlable `data-dock` shell; persist + Reset layout |

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
| 4b | Path-browser | Smalltalk / Finder | Done MVP (`repl-buffer-part5`): Miller columns; navigate + Focus; Examples stub |
| 4c | Dockable panels | RemedyBG / VS | Done MVP (`repl-buffer-part6`): Paths / Edit / Term dock; curlable shell |
| 5 | No hidden state | Light Table | Inspector over stack / walker IR (future dock components) |
| 6 | Document = program | Eve | Walkthrough/essay as the primary live buffer |
| 7 | Scrub / time | Bret Victor | Parameter scrub; needs cheap deterministic re-run |

**Glamorous Toolkit** (incl. Pager trail), **scroll host / locked ZUI**, and
**Miller-as-shell-nav** (explorer + tab spam replaced by path columns + body) stay
north-stars beside this table — not numbered delivery parts. Parts 5–7 remain Light
Table / Eve / Bret Victor. Path-browser Examples mode (kata library columns) is still
open; see [Navigation](#navigation-miller-vs-explorer-vs-tabs) and
[Scroll host / locked ZUI](#scroll-host--locked-zui).


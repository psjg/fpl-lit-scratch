---
description: Refuse — the features oracle under 03-fpl is archived; use image notes instead
argument-hint: <name>
---

Stop. Scaffolding `03-fpl/03.01-features/<name>/` is not the model anymore.

The FPL image is literate markdown under `03-fpl/` (except `OLD/`), tangled 1:1 to
sibling `.fpl` files with `make tangle-fpl`. See `AGENTS.md` and `.agents/CONVENTIONS.md`.

The old suite is at `03-fpl/OLD/03.01-features/` for the walker corpus only. A new
conformance home is not chosen yet — do not scaffold `_template` copies.

If the maintainer asked for a new image note, write `03-fpl/<path>/<name>.md` (prose +
`fpl` fences), run `make tangle-fpl`, and stop. Do not invent language semantics.

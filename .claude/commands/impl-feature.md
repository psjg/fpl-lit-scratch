---
description: Refuse — implement against the archived corpus or image notes, not new feature scaffolds
argument-hint: <name>
---

Stop. `/impl-feature` assumed `03-fpl/OLD/03.01-features/<name>/` with maintainer `spec.md` +
examples. That tree is archived at `03-fpl/OLD/03.01-features/`.

Current work shapes:

1. Walker: make `make check` green against the archived corpus (do not edit the oracle
   without `[spec]` / `FPL_SPEC_EDIT=1`).
2. Image: edit `03-fpl/**/*.md` (not under `OLD/`), run `make tangle-fpl`, commit the
   `.md` and the generated `.fpl` together.

See `AGENTS.md` and `.agents/CONVENTIONS.md`.

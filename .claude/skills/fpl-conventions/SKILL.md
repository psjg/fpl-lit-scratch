---
type: AgentDoc
name: fpl-conventions
description: The FPL repo's layout, commit convention, and stacked-commit workflow. Use before implementing an FPL feature, scaffolding a worktree, or making a commit in this repo.
---

The canonical rules live in the repo root and `.agents/`. This skill just loads them so a
Claude session follows the same conventions any agent would. Read, in order:

1. **`AGENTS.md`** — what the repo is, the worktree model, the settled stack, the `make check`
   gate, the FPL image and the oracle rule.
2. **`.agents/CONVENTIONS.md`** — the `01-bootstrap/fpl/` module tree (surface AST → desugar →
   core AST → semantics), the `03-fpl/` image (`*.md` → `make tangle-fpl` → `*.fpl`), the
   archived corpus under `03-fpl/OLD/03.01-features/` and how its examples check
   themselves, `make check`.
3. **`.agents/COMMITS.md`** — Conventional-Commits header + the git-trailer provenance block,
   the machine-account authorship model, `[gate]` vs `[advisory]` rules. Commit with
   `.harness/scripts/acommit.sh`.
4. **`.agents/WORKFLOW.md`** — stacked commits: base → stack → restack → land; `.harness/scripts/restack.sh`.
5. **`.agents/STACK.md`** — why the stack is what it is; do not reopen it.

Key don'ts: never edit a `03-fpl/OLD/03.01-features/*/spec.md`,
`02-docs/02.04-explanation/design.md`, or `02-docs/02.03-reference/spec.md` (hooks enforce
this); never invent language semantics; never hand-edit tangled `03-fpl/**/*.fpl`; never
report work done on a red or unrun `make check`. Harness how-tos belong in skills, not
markdown slop in `.agents/`.

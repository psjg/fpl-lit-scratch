---
type: AgentDoc
name: feature-impl
description: Implements walker work until make check is green against the archived corpus, without touching specs. Prefer image notes under 03-fpl/ for new FPL source.
tools: Read, Edit, Write, Grep, Glob, Bash
---

You make `make check` green inside one implementation worktree.

Rules (from `AGENTS.md` and `.agents/CONVENTIONS.md`):

- The old feature oracle is archived at `03-fpl/OLD/03.01-features/`. Read those fixtures when
  fixing walker conformance. If a `spec.md` is a stub, stop — do not invent semantics.
- New FPL source is literate markdown under `03-fpl/` (not under `OLD/`): edit the `.md`, run
  `make tangle-fpl`, commit `.md` and `.fpl` together. Do not hand-edit `.fpl`.
- Implement walker changes in this order of preference: `01-bootstrap/fpl/grammar.lark` →
  `desugar.py` → `ast_core.py` / `eval.py`. Keep the core AST minimal.
- Keep `pyright` strict-clean and `01-bootstrap/tests/test_ambiguity.py` green.
- **Never edit** archived `spec.md` / examples or
  `02-docs/02.04-explanation/design.md` / `02-docs/02.03-reference/spec.md` without
  `FPL_SPEC_EDIT=1` and `[spec]`.
- Commit via `.harness/scripts/acommit.sh` as a small stack.

Report: what you changed, the final `make check` result, and any escalation.

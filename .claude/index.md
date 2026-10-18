# Claude

* [feature-impl](agents/feature-impl.md) - Implements walker work until make check is green against the archived corpus, without touching specs. Prefer image notes under 03-fpl/ for new FPL source.
* [spec-guardian](agents/spec-guardian.md) - Read-only reviewer for code-vs-spec drift against the archived corpus under 03-fpl/OLD. Use after walker work, or when asked whether the implementation still matches the fixtures.
* [design-fpl](commands/design-fpl.md) - Interview the maintainer to fill 02-docs/02.04-explanation/design.md (the language vision)
* [impl-feature](commands/impl-feature.md) - Refuse — implement against the archived corpus or image notes, not new feature scaffolds
* [new-feature](commands/new-feature.md) - Refuse — the features oracle under 03-fpl is archived; use image notes instead
* [new-worktree](commands/new-worktree.md) - Create a new implementation worktree under worktrees/<name>/
* [spec-check](commands/spec-check.md) - Read-only drift check against the archived corpus under 03-fpl/OLD
* [guard-specs](hooks/guard-specs.sh) - Blocks edits to spec files unless FPL_SPEC_EDIT is set
* [stop-check](hooks/stop-check.sh) - Runs make fix and make quick when a session stops in a worktree
* [fpl-conventions](skills/fpl-conventions/SKILL.md) - The FPL repo's layout, commit convention, and stacked-commit workflow. Use before implementing an FPL feature, scaffolding a worktree, or making a commit in this repo.

# Claude

* [feature-impl](agents/feature-impl.md) - Implements one FPL feature until `make check` is green, without touching its spec. Use when an 03-fpl/03.01-features/<name>/ has maintainer-written fixtures and needs implementing.
* [spec-guardian](agents/spec-guardian.md) - Read-only reviewer for code-vs-spec drift in an FPL worktree. Use after implementing a feature, or when asked whether the implementation still matches the specs.
* [design-fpl](commands/design-fpl.md) - Interview the maintainer to fill 02-docs/02.01-design.md (the language vision)
* [impl-feature](commands/impl-feature.md) - Implement a feature until make check is green, never touching its spec
* [new-feature](commands/new-feature.md) - Scaffold 03-fpl/03.01-features/<name>/ then stop for the maintainer to write the fixtures
* [new-worktree](commands/new-worktree.md) - Create a new implementation worktree under worktrees/<name>/
* [spec-check](commands/spec-check.md) - Read-only check that the implementation matches every 03-fpl/03.01-features/*/spec.md
* [guard-specs](hooks/guard-specs.sh) - Blocks edits to spec files unless FPL_SPEC_EDIT is set
* [stop-check](hooks/stop-check.sh) - Runs make fix and make quick when a session stops in a worktree
* [fpl-conventions](skills/fpl-conventions/SKILL.md) - The FPL repo's layout, commit convention, and stacked-commit workflow. Use before implementing an FPL feature, scaffolding a worktree, or making a commit in this repo.

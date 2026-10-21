# Tech debt items

- [TD-0000-template.md](TD-0000-template.md): template for a new item.
- [TD-0001-atomic-check-amend-fixup.md](TD-0001-atomic-check-amend-fixup.md): atomic-check misjudges `--amend` and fixup commits because it sees only the delta.
- [TD-0002-new-worktree-attempt-only.md](TD-0002-new-worktree-attempt-only.md): `.harness/scripts/new-worktree.sh` only creates `attempt/` branches.
- [TD-0003-stamp-does-not-reproduce-tree.md](TD-0003-stamp-does-not-reproduce-tree.md): `01-bootstrap/stamp.py` does not reproduce the committed tree.
- [TD-0004-worktree-du-overcounts.md](TD-0004-worktree-du-overcounts.md): `du` over-counts the space freed by removing worktrees.
- [TD-0005-pre-push-lower-subseries-stack-missing.md](TD-0005-pre-push-lower-subseries-stack-missing.md): pre-push refuses a lower sub-series with `stack-missing` when the upper branch is pushed first.
- [TD-0006-pipe-reparses-rendered-text.md](TD-0006-pipe-reparses-rendered-text.md): the shell filters after `parse` send rendered source text and re-parse it instead of FON of the representation.
- [TD-0007-pipeline-lab-missing-fon-cell.md](TD-0007-pipeline-lab-missing-fon-cell.md): the pipeline lab promises a FON cell it does not have; nothing compares piped and in-process results.
- [TD-0008-pass-composition-opaque-closure.md](TD-0008-pass-composition-opaque-closure.md): `Pass.__rshift__` erases a chain's structure into a closure.
- [TD-0009-seed-fon-braced-not-postfix.md](TD-0009-seed-fon-braced-not-postfix.md): the seed FON is braced, not the postfix stream FON is decided to be.
- [TD-0010-click-undeclared.md](TD-0010-click-undeclared.md): the `fpl` CLI imports Click, but `01-bootstrap/pyproject.toml` does not declare it.

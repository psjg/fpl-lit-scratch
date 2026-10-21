# Tech debt items

- [TD-0000-template.md](TD-0000-template.md): template for a new item.
- [TD-0001-atomic-check-amend-fixup.md](TD-0001-atomic-check-amend-fixup.md): atomic-check misjudges `--amend` and fixup commits because it sees only the delta.
- [TD-0002-new-worktree-attempt-only.md](TD-0002-new-worktree-attempt-only.md): `.harness/scripts/new-worktree.sh` only creates `attempt/` branches.
- [TD-0003-stamp-does-not-reproduce-tree.md](TD-0003-stamp-does-not-reproduce-tree.md): `01-bootstrap/stamp.py` does not reproduce the committed tree.
- [TD-0004-worktree-du-overcounts.md](TD-0004-worktree-du-overcounts.md): `du` over-counts the space freed by removing worktrees.
- [TD-0005-pre-push-lower-subseries-stack-missing.md](TD-0005-pre-push-lower-subseries-stack-missing.md): pre-push refuses a lower sub-series with `stack-missing` when the upper branch is pushed first.

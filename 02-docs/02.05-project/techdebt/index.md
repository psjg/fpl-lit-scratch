# Tech debt items

- [TD-0000-template.md](TD-0000-template.md): template for a new item.
- [TD-0001-atomic-check-amend-fixup.md](TD-0001-atomic-check-amend-fixup.md): atomic-check misjudges `--amend` and fixup commits because it sees only the delta.
- [TD-0002-new-worktree-attempt-only.md](TD-0002-new-worktree-attempt-only.md): `.harness/scripts/new-worktree.sh` only creates `attempt/` branches.
- [TD-0003-stamp-does-not-reproduce-tree.md](TD-0003-stamp-does-not-reproduce-tree.md): `01-bootstrap/stamp.py` does not reproduce the committed tree.
- [TD-0004-worktree-du-overcounts.md](TD-0004-worktree-du-overcounts.md): `du` over-counts the space freed by removing worktrees.
- [TD-0005-pre-push-lower-subseries-stack-missing.md](TD-0005-pre-push-lower-subseries-stack-missing.md): pre-push refuses a lower sub-series with `stack-missing` when the upper branch is pushed first.
- [TD-0006-substrate-citations-unaudited.md](TD-0006-substrate-citations-unaudited.md): Roughly sixty references behind the substrate design were verified by source for five of them; the rest carry a measured base rate of one wrong year or venue in ten.
- [TD-0007-atlas-pinned-agda-untested.md](TD-0007-atlas-pinned-agda-untested.md): The cubical Agda atlas typechecked only under Agda 2.6.3 and cubical 0.5; the flake pins Agda 2.8 and cubical 0.9, and the check verb under Nix never ran.
- [TD-0008-decisions-table-glyph-spelling.md](TD-0008-decisions-table-glyph-spelling.md): The substrate decisions table and register use APL glyph examples while the grammar and section 8 use canonical name spellings, so examples do not match the canon.

---
type: Readme
title: Tech debt and friction items
description: One file per friction or tech-debt item found while working on FPL; how to file, number and close them.
---

One file per friction or tech-debt item, named `TD-NNNN-<slug>.md`. Copy [TD-0000-template.md](TD-0000-template.md) and take the next free number. Numbers are identities: they are never reused, not even after an item is closed or deleted.

Status uses the OKF `status` field:

- `draft`: open, not yet accepted.
- `stable`: accepted and being worked.
- `deprecated`: closed. Set `closed-by:` to the commit, PR or ADR id that closed it.

An item states what an agent or human could not close in the session that found it. Claims that were not reproduced are marked as such in the body.

The list of items is [index.md](index.md).

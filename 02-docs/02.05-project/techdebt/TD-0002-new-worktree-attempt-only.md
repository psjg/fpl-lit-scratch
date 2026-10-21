---
type: Note
title: new-worktree.sh only creates attempt/ branches
description: The script creates only attempt/<name> branches, while the branch grammar admits agent/claude/... for Claude sessions.
tags: [harness, branches]
status: draft
date: 2026-10-21
found-in: [.harness/scripts/new-worktree.sh, .agents/BRANCHES.md]
related: []
closed-by:
---

## Symptom

`.harness/scripts/new-worktree.sh` creates only `attempt/<name>` branches. The branch grammar (`.agents/BRANCHES.md`) admits `agent/claude/...` for Claude sessions, and the hooks reject agent commits elsewhere, so an agent that needs an `agent/claude/` branch must create it by hand.

## Cause

The prefix is fixed in the script.

## Remedy

Take a branch-prefix argument (default `attempt/`) validated by `.harness/scripts/branch-lint.sh`.

## How to reproduce

Run the script with a new name and read the branch it made. Not run in this pass.

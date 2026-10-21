---
type: Note
title: pre-push refuses a lower sub-series pushed after the upper branch
description: The pre-push gate lints every commit not yet on the remote against the tip branch, so a stacked lower sub-series fails with stack-missing when the upper branch goes first.
tags: [harness, push]
status: draft
date: 2026-10-21
found-in: [.githooks/pre-push, .harness/scripts/commit-lint.sh]
related: []
closed-by:
---

## Symptom

Pushing the upper branch of a stack first is refused with `stack-missing`: the message needs `Stack: <upper>` and the commit has `Stack: miller-commit.fix`. The commits are the lower sub-series, correct under their own branch.

## Cause

Gate 4 of `.githooks/pre-push` judges every commit the remote does not yet hold, with `.harness/scripts/commit-lint.sh -b <branch>`, under the name of the branch being pushed. While the lower branch is not on the remote, its commits are in that range and are judged against the upper branch's `Stack:`. Not measured beyond the one refusal seen.

## Remedy

Workaround: push the lower branch first. Its commits are then on the remote, outside the range, and the upper push judges only its own.

A fix would exclude the commits of an ancestor branch that carries a stack sub-series name of its own from the range, as gate 4 already does for a parent on the remote.

## How to reproduce

Make a branch with a commit whose `Stack:` is `<name>.part`, branch the upper `<name>` from it with a commit of its own, and push the upper first. Not repeated in this pass.

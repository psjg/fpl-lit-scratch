---
type: Note
title: atomic-check misjudges --amend and fixup commits
description: atomic-check judges only the delta of an amend or fixup commit, so it raises false positives.
tags: [hooks, commits]
status: draft
date: 2026-10-21
found-in: [.githooks/atomic-check]
related: []
closed-by:
---

## Symptom

atomic-check reports false positives on `git commit --amend` and on fixup commits. `FPL_ATOMIC_GATE=warn` is used as the override.

## Cause

It judges only the delta of the new commit, not the commit as it will read after the amend or autosquash.

## Remedy

Judge the resulting commit (the amended tree against its parent), or skip fixup commits that autosquash will fold. The override stays a designed exit.

## How to reproduce

Not reproduced in this pass; recorded from the 2026-10-21 session.

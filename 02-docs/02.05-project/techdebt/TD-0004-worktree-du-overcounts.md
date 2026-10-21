---
type: Note
title: du over-counts the space freed by removing worktrees
description: A du inventory estimated 9.0 GB for 38 removed worktrees, but df showed about 2 GB freed.
tags: [harness, worktrees]
status: draft
date: 2026-10-21
found-in: []
related: []
closed-by:
---

## Symptom

A worktree inventory made with `du` estimated 9.0 GB for 38 removed worktrees. `df` showed about 2 GB freed.

## Cause

Likely shared caches and APFS block sharing, which `du` counts per worktree. This is a prior, not measured.

## Remedy

Measure freed space with `df` before and after the removal, not with a `du` sum.

## How to reproduce

Run `df` on the volume, remove worktrees, run `df` again, and compare with the `du` estimate. Not repeated in this pass.

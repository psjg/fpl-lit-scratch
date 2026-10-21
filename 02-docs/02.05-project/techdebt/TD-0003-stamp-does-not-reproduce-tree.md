---
type: Note
title: stamp.py does not reproduce the committed tree
description: Running 01-bootstrap/stamp.py drops the space between joined string literals in about 30 files, so regeneration cannot serve as a check.
tags: [bootstrap, tooling]
status: draft
date: 2026-10-21
found-in: [01-bootstrap/stamp.py]
related: []
closed-by:
---

## Symptom

`01-bootstrap/stamp.py` does not reproduce the committed tree: it drops the space between adjacent joined string literals in about 30 files. Regeneration therefore cannot be used as a check that the tree is current.

## Cause

Whitespace between joined string literals is not preserved when the literals are joined.

## Remedy

Preserve the literal whitespace when joining, or fail the stamp check loudly. Add a test that stamp output equals the tree.

## How to reproduce

Run `stamp.py` in a scratch clone, then `git diff --stat`, list the files and read one example hunk. The count of about 30 files is from the 2026-10-21 session; the run was not repeated in this pass.

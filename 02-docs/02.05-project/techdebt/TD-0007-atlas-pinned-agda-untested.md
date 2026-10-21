---
type: Note
title: The atlas was only run under Agda 2.6.3, not the pinned Agda
description: The cubical Agda atlas typechecked only under Agda 2.6.3 and cubical 0.5; the flake pins Agda 2.8 and cubical 0.9, and the check verb under Nix never ran.
tags: [substrate, atlas, nix]
status: draft
date: 2026-10-21
found-in: [02-docs/02.05-project/notes/02.05.11-substrate-liabilities.md, flake.nix]
related: []
closed-by:
---

## Symptom

The atlas is a literate cubical Agda file (rungs of evidence for lambda, CBPV, MLL, coalgebra, games, interaction nets, time and univalence). It was run only with Agda 2.6.3 and cubical 0.5. The flake that is meant to run it under nixpkgs pins Agda 2.8 and cubical 0.9 (register row U13), and the check verb under Nix was written but not run: the seam ran, the check did not (S2).

## Cause

The atlas was developed and checked outside the pinned environment; the flake was written afterwards and never exercised.

## Remedy

Run the atlas check from the flake on the pinned versions. If it typechecks, record that against U13 and S2. If it does not, fix the breakage (Agda 2.6 to 2.8 and cubical 0.5 to 0.9 renamed and moved some library modules) or pin the working versions in the flake, and record which. The result belongs in the register rows, with the command used.

## How to reproduce

Enter the flake shell and run the atlas check verb on the atlas file. Not repeated in this pass; the claim comes from rows U13 and S2.

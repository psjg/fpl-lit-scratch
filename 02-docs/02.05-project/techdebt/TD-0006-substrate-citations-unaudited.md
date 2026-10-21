---
type: Note
title: Substrate references were stated from recall and never audited
description: Roughly sixty references behind the substrate design were verified by source for five of them; the rest carry a measured base rate of one wrong year or venue in ten.
tags: [docs, substrate, citations]
status: draft
date: 2026-10-21
found-in: [02-docs/02.05-project/notes/02.05.11-substrate-liabilities.md, 02-docs/02.04-explanation/02.04.04-substrate.md]
related: []
closed-by:
---

## Symptom

The substrate design cites about sixty works. The session that wrote it verified by source only slotted e-graphs (Schneider et al., PLDI 2025), the Gonçalves–Kokke / Zucker thinnings line, the 1lab page names, the HVM/Bend install docs and the cubical library names. Rows U1 to U12 and U15 to U17 of the [register](../notes/02.05.11-substrate-liabilities.md) list the rest, with attribution, year or venue as the risk. Reviewer corrections (U12) were adopted on the reviewers' word, and the reviewers were wrong elsewhere.

## Cause

The references were written from recall during a survey. The working preference to verify a recalled claim before stating it was not followed for most of that session (P4). The measured base rate so far is one wrong year or venue in ten (co-de-Bruijn, TIMI and contextual ES were wrong).

## Remedy

Run the citation audit the register calls review role E (P3): for each row, open the primary source, check authors, year, venue and the claim as stated, and record the result in the row's status with the source named. Rows that pass are discharged; wrong ones are corrected on the substrate page. Rows U12 (partly done for RaML), U15 (the token counts are already reproduced) and U16 to U17 (partly verified) need only their open parts. An agent can do this; it should read the sources raw, not summaries of them.

## How to reproduce

Not applicable: it is an audit. The unverified list is in rows U1 to U17 of the register.

---
type: Readme
title: fabula
description: A run read as text - speedscope turned 90 degrees with the source line of each step beside the time axis (fabula against syuzhet). Experiment, scratch remote only.
---

# fabula

An experiment from the literate sandbox (11-07..11-10). Literary theory keeps two orders:
the **syuzhet** is the order in which the text tells, the **fabula** the order in which it
happens. For code the syuzhet is the source, line by line, and the fabula is the run.
Here the time axis of a flame graph is counted in source lines (1 step = 1 line, 1 u = 1
bytecode instruction) and each step shows the line that ran, so a run can be read as text
without learning the chart. Nothing here is wired into `make`; it is not on a PR.

## Layout

    web/                 the served root: everything the pages load, flat
      rot-a.html           variant A, turned 90 degrees (the one to open)
      zui-a.html           variant A: semantic zoom in the blocks (lines, then ops)
      rot.html             patched speedscope turned 90 degrees (index.html in an iframe)
      *.fabula.json        the data: trace-lex, stash-only (steps with line, frame, ops)
      trace-lex.speedscope.json  the same run as a speedscope profile
      index.html, *.js ... the speedscope v1.25.0 build with speedscope-as-maat.patch
    speedscope/speedscope-as-maat.patch   the patch (measure switch on the axis), against v1.25.0
    tofabula.py          trace -> fabula.json (python3 -I tofabula.py TRACE.json OUT.fabula.json)
    tospeedscope.py      trace -> speedscope profiles (steps, u, m, t)
    test_tofabula.py     checks a fabula against the speedscope file of the same trace
    zui-a.cjs gap-check.cjs pan-check.cjs rot-a-shot.cjs   headless checks (playwright)
    shots/               screenshots of the last good state (10-10)

The raw traces (`stepper-lex.json`, `stepper-stash.json`) are not committed; they live
with the side-session notes. The two `.fabula.json` files are generated from them.

## View

    cd .harness/tools/fabula/web && python3 -m http.server 8792

Then open <http://127.0.0.1:8792/rot-a.html>. `?cw` turns it clockwise, `?run=stash-only`
picks the other run, arrow keys go to the turned view. `rot.html` shows the patched
speedscope itself, `zui-a.html` the unturned page. The checks take the same base:

    CHROME=... node zui-a.cjs PLAYWRIGHT_DIR http://127.0.0.1:8792 shots
    CHROME=... node gap-check.cjs PLAYWRIGHT_DIR zui-a.html trace-lex shots

`web/` is the speedscope build minus its `.map` files (3 MB less); rebuild from
speedscope v1.25.0 plus the patch if you need them.

## PSJ's answers, 2026-11-12

- A click sets the selection in speedscope: **yes**.
- Variant C (zoom = fold: file, function, line, bytecode) is **dropped**. Variant B (source
  as canvas) was not asked about and is not built.
- Open, unanswered: should the fabula strip sit **beside** the flame graph or **replace**
  it? The current A replaces the block drawing with cells at zoom; the plan
  (`plan-fabula-syuzhet-2026-11-07.md`) put a separate strip beside the axis.

## State

Gaps in the turned A are filled (caller's column continues dimmed, `↳ name` at the start of
the gap, pinned caller line): 149 of 149 gaps in trace-lex and 26 of 26 in stash-only carry
the right text (gap-check, 11-10). Not measured: the pinned line at half zoom may paint over
a strip; hover on a waiting column does not yet say what it waits on.

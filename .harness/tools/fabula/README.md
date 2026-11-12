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
      rot-beside.html      turned speedscope, fabula strip beside the flame graph
      rot-replace.html     turned speedscope, fabula strip over the flame graph
      fabula-strip.js/.css the strip and the syuzhet, shared by those two pages
      rot-a.html           variant A, turned 90 degrees
      zui-a.html           variant A: semantic zoom in the blocks (lines, then ops)
      *.fabula.json        the data: trace-lex, stash-only (steps with line, frame, ops)
      *.speedscope.json    the same runs as speedscope profiles
      index.html, *.js ... the speedscope v1.25.0 build with speedscope-as-maat.patch
    speedscope/speedscope-as-maat.patch   the patch (measure switch on the axis), against v1.25.0
    tofabula.py          trace -> fabula.json (python3 -I tofabula.py TRACE.json OUT.fabula.json)
    tospeedscope.py      trace -> speedscope profiles (steps, u, m, t)
    test_tofabula.py     checks a fabula against the speedscope file of the same trace
    zui-a.cjs gap-check.cjs pan-check.cjs rot-a-shot.cjs strip-check.cjs
                         headless checks (playwright)
    shots/               screenshots of the last good state (10-10)

The raw trace (the stepdemo v8 `trace-lex.json`) is not committed; it lives with the
side-session notes. The data files are generated from it, machine paths cut to
`stepdemo-v8/...`: `tofabula.py` gives the `.fabula.json`, `tospeedscope.py` the
`.speedscope.json` (regenerated 11-12: equal to the committed trace-lex file). stash-only is
the one run `prelex("“a” 「b」").stash` of the same trace. (`stepper-*.json` in the notes
are Chrome trace events, not this format.)

## View

    cd .harness/tools/fabula/web && python3 -m http.server 8792

Then open <http://127.0.0.1:8792/rot-beside.html> or `rot-replace.html`; `?run=stash-only`
picks the other run, `?ccw` turns it the other way (time then runs upward). In both, a
click on a strip row sets the selection in speedscope, the wheel over the strip scrolls
time, ctrl+wheel (pinch) zooms about the cursor, dragging pans. `rot-replace` lays the
strip over the flame graph's body, between the ruler and the detail panel a selection
opens, and draws the call stack as narrow named columns at the root side; the ruler
(click: next measure), the minimap and the detail tables stay visible, and in
the sandwich view or the μ/t measures the strip steps aside. `rot-a.html` is variant A
turned, `zui-a.html` unturned.

The strip needs speedscope's atoms on `window`. The source patch that did this is lost, so
the bundle carries it as one inserted statement:

    perl -0pi -e 's/Ne\.subscribe\(\(\)=>\{Y\.clearHoverNode\(\)\}\);/$&window.profileGroupAtom=Y;window.viewModeAtom=Ne;/' web/speedscope-H26NIAF6.js

The checks take the same base. For the strip pages use Chrome for Testing
(`ms-playwright/chromium-*`), not the headless shell: the shell drops the iframe's WebGL
layer once the strip covers part of it (the minimap goes blank; measured 11-12, 304 vs
6795 lit pixels).

    CHROME=... node zui-a.cjs PLAYWRIGHT_DIR http://127.0.0.1:8792 shots
    CHROME=... node gap-check.cjs PLAYWRIGHT_DIR zui-a.html trace-lex shots
    CHROME=... node pan-check.cjs PLAYWRIGHT_DIR rot-replace.html shots
    CHROME=... node strip-check.cjs PLAYWRIGHT_DIR rot-replace.html trace-lex shots

`web/` is the speedscope build minus its `.map` files (3 MB less); rebuild from
speedscope v1.25.0 plus the patch if you need them.

## PSJ's answers, 2026-11-12

- A click sets the selection in speedscope: **yes**.
- Variant C (zoom = fold: file, function, line, bytecode) is **dropped**. Variant B (source
  as canvas) was not asked about and is not built.
- Beside or replace: PSJ leans to the strip **in place of** the flame graph but wants to
  see both; `rot-beside.html` and `rot-replace.html` are the two (11-12), on the same code.

## State

Gaps in the turned A are filled (caller's column continues dimmed, `↳ name` at the start of
the gap, pinned caller line): 149 of 149 gaps in trace-lex and 26 of 26 in stash-only carry
the right text (gap-check, 11-10). Not measured: the pinned line at half zoom may paint over
a strip; hover on a waiting column does not yet say what it waits on.

The strip pages (strip-check, 11-12): for every step of all 15 trace-lex runs (1052 steps)
and of stash-only (176) the frame chain from speedscope equals the `frame.parent` chain in
the fabula, a sweep at 18 px per step draws every step with its line as text, and in
replace the stack columns equal the calls in view (depth, start, end), 261 and 47 column
blocks; a click on a row sets speedscope's selection and a selection made in speedscope
marks its rows; after the click the detail panel opens and no table lies under the strip
(in replace the strip ends at the panel). gap-check has no referent in the strip (no held gaps); strip-check's
column invariant is its counterpart. Not checked: the υ measure (strip-check sweeps
"· stappen" only) and `?ccw`.

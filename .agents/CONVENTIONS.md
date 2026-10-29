---
type: AgentDoc
title: "How the walker is laid out"
description: "The walker's source tree, the FPL image, the archived conformance suite and the make check gate."
---

# CONVENTIONS.md — how the walker, the implementation, is laid out

Canonical for every agent. The Claude `fpl-conventions` skill and the `.claude/commands/*`
wrappers just point here. The walker, the Python implementation, is a project of its own in
`01-bootstrap/`: its package is `fpl`, so `import fpl` and the module names below are what they
were; only the directory moved, and with it the paths of its files.

The FPL image is `03-fpl/`: literate `*.md` tangled 1:1 to sibling `*.fpl` (`make tangle-fpl`).
The archived conformance suite at `03-fpl/OLD/03.01-features/` is what the walker corpus still
reads; a new oracle home is open.

## Source tree (`01-bootstrap/fpl/`)

```
01-bootstrap/fpl/
  grammar.lark      syntax spec; the file the maintainer edits. Declarative only.
  parse.py          grammar → Lark tree → surface AST. Dumb. No semantics here.
  ast_surface.py    frozen @dataclass nodes; every node carries a Span.
  desugar.py        surface AST → core AST. All sugar is erased here.
  ast_core.py       the tiny stable core: Lit, Var, Lam, App, Let, If, BinOp, …
  eval.py           match-based tree-walking interpreter over core AST only.
  types.py          type-check pass over core AST (starts as a stub).
  errors.py         FplError(span, message) → caret-underlined source rendering.
  driver.py         parse → desugar → (typecheck) → eval. Shared by CLI and tests.
  repl.py           interactive loop.
  __main__.py       `python -m fpl file.fpl` runs a file; `python -m fpl` starts the REPL.
                    From the root: `make run FILE=file.fpl`, `make repl` (the package is
                    01-bootstrap/fpl, so `python -m fpl` runs only inside 01-bootstrap/).
```

Hard rules:

- **`parse.py` holds zero semantics.** Meaning lives in `desugar.py` and `eval.py`.
- **`ast_core.py` stays small.** Adding syntax = grammar + desugar + tests. If a change needs
  a new core node, that's a design decision — flag it.
- **Spans from parse time** on every surface node, threaded through desugar so errors point at
  real source.
- **Frozen dataclasses**, so `pyright` strict + `reportMatchNotExhaustive` actually bites.

## The FPL image (`03-fpl/`)

```
03-fpl/
  hello.md                 literate source (canon)
  hello.fpl                tangled; do not hand-edit
  OLD/03.01-features/      archived oracle the corpus still reads
01-bootstrap/
  tangle_fpl.py            md → fpl (prose → `;` comments; fpl fences → source)
```

`make tangle-fpl` from the root. A `.fpl` without a matching `.md` (outside `OLD/`) is an
error. README and index.md under `03-fpl/` are not tangled.

## Archived conformance (corpus only)

```
03-fpl/OLD/03.01-features/
  <name>/
    spec.md
    examples/*.fpl
01-bootstrap/tests/
  corpus.py              finds 03-fpl/OLD/03.01-features/
  test_conformance.py    runs the driver on each example; it passes when none raises
  test_ambiguity.py      asserts the grammar parses the corpus with zero Earley ambiguity
```

Each example checks itself (DI-0072); there are no `.expected` files:

- A run line that prints carries its value: `1 | 2 + |- 3`, before any `;` note. Both sides
  run; the line prints its left side, and unequal stacks fail with `err/check/unequal`.
- A program that fails closes on one line, after every trailing comment:
  `|- ! err/<tag> “<message>”` (the message optional, exact when given). It must fail with that
  tag; `python -m fpl <file>` (`make run FILE=<file>` from the root) then prints the output so
  far and the error line `ERROR: <line>:<col> <message>` and exits 0.
- A program that prints nothing carries no check.

No Python traceback ever reaches the user: an error is the one line `ERROR: <line>:<col>
<message>` on stdout.

**The oracle rule:** the maintainer writes the fixtures that remain. The agent makes
`make check` green against them. `spec.md`, the examples, `02-docs/02.04-explanation/design.md`
and `02-docs/02.03-reference/spec.md` are edit-protected (`[spec]` marker required). Do not
scaffold new feature dirs under the archived tree; the next oracle home is undecided.

## The gate (`make check` at the root)

`01-bootstrap/Makefile` is `include ../.harness/quality/noslop.mk`, and the root's `Makefile` runs each
lane in `01-bootstrap/`, so `make check` from the root is the walker's gate. It runs ruff, strict pyright
(`reportMatchNotExhaustive=error`) and strict mypy, the tests (unit, `test_ambiguity`, conformance) under
100% branch coverage, and the structural checks of `.agents/QUALITY.md`: CRAP, a property test
per module, the layering of the source tree above, declared dependencies, dead and duplicate
code, and named waivers.

Green ⇔ done. Work with a red or unrun `make check` is not done.

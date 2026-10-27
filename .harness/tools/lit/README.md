---
type: Readme
title: lit
description: The walker's literate pages, tangled, checked against their files, linted, woven to HTML and read by a model without their code.
---

# lit

A literate page of the walker (01-bootstrap/) is the source of a module. The module file is
generated from the page, committed, and held to it by a gate. lit is our own small tool: it
reads noweb chunks written in plain Markdown. It replaces the Entangled prototype. The OKF
index is [index.md](index.md).

    lit tangle   [PAGE ...]      write each file a page names, read-only
    lit check    [PAGE ...]      the web's rules, and drift (make check)
    lit lint     [PAGE ...]      prose and code agree; examples pass (make check)
    lit weave OUT [PAGE ...]     each page as one HTML page (make lit-weave)
    lit readable PAGE            a model answers the tests from the prose (make lit-readable)
    lit run -- CMD ...           run CMD; its output names page lines, not file lines

Every command takes `--root DIR`. File chunks are written relative to it, and without PAGE
every page under it is read. The walker's root is `01-bootstrap/`, so run lit from there:

    cd 01-bootstrap && PYTHONPATH=../.harness/tools/lit ../.harness/.venv/bin/python -m lit check

## The page

A page is Markdown. A fence opened by exactly ```` ```python ```` is a code chunk. Its first
line names it, and every chunk is named for its purpose:

    ```python
    <<Count one pair>>=
    def counted(text: str, at: int, close: str, end: int) -> int | None:
        ...
    ```

- `<<Name>>=` defines a chunk and `<<Name>>+=` adds to one defined earlier on the page.
- A line holding only `<<Name>>` is a use. The chunk's lines go there, each indented by the
  use's indentation, so a chunk can be the body of an `if` inside a function.
- A chunk named like a path, such as `<<fpl/lex.py>>=`, is a file. It is written relative to
  the root, byte for byte, with no header line, and set read-only (0444). git does not keep
  the mode, so the drift gate is what holds the file to the page.
- Every other fence (`pycon`, `text`, `fpl`) is prose. A `pycon` fence is an example, and the
  lint runs it.
- Prose comes before each chunk. A section is the prose up to and including one chunk.

The reader is strict and guesses nothing. These are findings, each at its page line: a
python fence without a header, a `+=` before its `=`, a second `=`, a use of a chunk never
defined, a chunk no file reaches, a cycle, a fence that never closes, and two pages writing
one file.

## The gates

`lit check` (in `make check`). A file that differs from its page fails at the page line the
first differing line came from: `page.md:L: lit-drift: fpl/lex.py:K differs from the page`.
The remedy is to edit the page and run `lit tangle`, never to edit the file.

`lit lint` (in `make check`). Prose names code in the Emacs docstring form: a backtick, the
name, an apostrophe, as in `` `prelex' `` or `` `Lines.span' ``. A plain code span, `` `x` ``,
is any code and is not checked. Three rules:

- **lit-unknown**: a reference must name something the tangled code binds: a definition, a
  field, a parameter, an assignment or an import.
- **lit-unmentioned**: every constant (an upper-case module name, `_LEXER` included) and
  every public name (a function, class, method or field without a leading underscore) must
  be referenced in the prose of the section whose chunk defines it. The front matter can
  exempt names: `lit-allow: [NAME, ...]`.
- **lit-example**: every `pycon` fence is a doctest, run against the namespace of the page's
  first Python file, executed from the fresh tangle (not from the file on disk). A failure is
  reported at the example's line. An expected exception is written as doctest writes one:
  `Traceback (most recent call last):`, then the exception line.

The examples are the one form of executable prose. A `|=` judgement form was the other
candidate; it waits for FPL pages. A `` `name' `` reference in Markdown has an odd number of
backticks, so GitHub pairs it with the next backtick on the line. The Quarto alias of a page
(`tangle.py`) turns each reference into a code span. The weave links each one to its
definition.

## The reader check

`lit readable PAGE` asks whether the prose alone teaches what the tests assert.

1. The page is stripped of its code. Each chunk leaves only `⟨Name⟩`. The `pycon` examples
   stay, since they are prose; `--no-examples` strips them too.
2. The facts come from the page's tests, by default `tests/test_<stem>.py` for each Python
   file. They are read mechanically. Every `assert L == R` and `assert L is None` in a test
   function becomes "What is `L`?", with `R` as the answer, once for each row of a
   `pytest.mark.parametrize` table. A fact stays only when a reader could answer it: every
   name in it is bound by the page's code, is a builtin, or is a test helper with a
   docstring, which the question quotes. Facts over a test's locals are dropped.
3. A model gets the chapter and the questions in one prompt. The default is Haiku through
   the claude CLI: `claude -p --model haiku --tools "" --safe-mode`. It runs in an empty
   directory, with extended thinking off, three times. An answer counts as right when it
   evaluates to the expected value. Only literals, containers and calls of the page's own
   classes are evaluated, with no builtins.
4. The score is the mean fraction right. Below `--threshold` (default 0.7) the exit status
   is 1.

It needs a model, costs a few cents and varies from run to run, so it is not in `make
check`; `make lit-readable` runs it over every page. The claude CLI is not in the flake: it
comes from the user's own profile. Without it, `--command CMD` names any program that reads
the prompt on stdin and prints the answers, and `--show` prints the prompt for a person to
answer.

Measured on 01.02.01-lex.md, 2026-10-27: the knuth-max prose scored 0.32. Rewriting the prose
where the misses showed real gaps (the refusal messages and their places, what a comment
leaves behind, the sigils and number forms of a token) brought it to 0.74 over three runs.

## Layout

- [lit/web.py](lit/web.py): reading a page, and the tangle. Standard library only, so the
  walker's `tangle.py` imports it.
- [lit/lint.py](lit/lint.py): the three lint rules.
- [lit/readable.py](lit/readable.py): facts, prompt and scoring.
- [lit/run.py](lit/run.py): tool output rewritten to page lines.
- [lit/weave.py](lit/weave.py): the HTML. It is the only module that needs markdown-it-py.
- [lit/__main__.py](lit/__main__.py): the command line.

`make tools` judges the tool like the language: ruff, pyright and mypy strict, the escapes
check, and 100% line and branch coverage.

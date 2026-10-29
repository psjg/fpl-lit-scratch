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
    lit check    [PAGE ...]      the web's rules, drift, and the hand rows (make check)
    lit lint     [PAGE ...]      prose and code agree; examples pass (make check)
    lit weave OUT [PAGE ...]     each page as one HTML page, its facts marked (make lit-weave)
    lit readable PAGE            a model answers the tests from the prose (make lit-readable)
    lit run -- CMD ...           run CMD; its output names page lines, not file lines
    lit facts --out DIR [PAGE ...]  each page's spans and hand rows as DIR/<stem>.json
    lit facts --import DIR_OR_FILE --item LABEL=PAGE@COMMIT [PAGE]
                                    the annotation program's rows for LABEL into PAGE's
                                    sidecar, merged by id, then checked
    lit facts --export PAGE [--item LABEL=PAGE@COMMIT] [--out FILE]
                                    the sidecar's span rows in the program's row shape
    lit anchor --verify [PAGE ...]  each hand row's text is at its place in its commit (git)

Every command takes `--root DIR`. Files are written relative to it, and without PAGE
every page under it is read. The walker's root is `01-bootstrap/`, so run lit from there:

    cd 01-bootstrap && PYTHONPATH=../.harness/tools/lit ../.harness/.venv/bin/python -m lit check

## The page

A page is Markdown. A fence opened by exactly ```` ```python ```` is a code chunk. Its
header gives the chunk's place, its name, and the files it stands in, one path a line:

    ```python
    <<3.8 Count one pair
    fpl/lex.py
    python/fpl/lex/__init__.py>>=
    def counted(text: str, at: int, close: str, end: int) -> int | None:
        ...
    ```

- The place is a dotted number, first on the name line. Places sort by their numbers:
  3 < 3.1 < 3.2 < 3.10. A path line may open with a place of its own for that file
  (`2 fpl/lex.py`); otherwise the name line's place holds there too.
- `<<Name>>+=` adds to the chunk, with no place and no path. Other chunks name it without
  its place.
- A line holding only `<<Name>>` is a use. The chunk's lines go there, each indented by the
  use's indentation, so a chunk can be the body of an `if` inside a function. A used chunk
  stands under its user's place (`3.9.1` under `3.9`) and in its user's files.
- A file is the chunks that name it and that no chunk uses, in the order of their places.
  Between two of them stand two blank lines when either is a def or a class (PEP 8), none
  when their places share a parent (3.1 and 3.2), and one otherwise. The file is written
  relative to the root, byte for byte, and set read-only (0444). A `.` or `..` segment is
  refused, so a file cannot land outside the root. git does not keep the mode, so the
  drift gate is what holds the file to the page.
- Every other fence (`pycon`, `text`, `fpl`) is prose. A `pycon` fence is an example, and the
  lint runs it.
- Prose comes before each chunk. A section is the prose up to and including one chunk.

The reader is strict and guesses nothing. These are findings, each at its page line: a
python fence without a header, a header without a place or without a path, a path line
that does not parse, a `+=` with a path, a `+=` before its `=`, a second `=`, a use of a
chunk never defined, a chunk named like a path (the old file root), a chunk that only uses
others (give its parts places instead), a used chunk outside a user's place or files, two
chunks at one place of a file, a chunk no file reaches, a cycle, a `tangle:` key in the
front matter (gone), a fence that never closes, and two pages writing one file.

## The gates

`lit check` (in `make check`). A file that differs from its page fails at the page line the
first differing line came from: `page.md:L: lit-drift: fpl/lex.py:K differs from the page`.
The remedy is to edit the page and run `lit tangle`, never to edit the file.

`lit lint` (in `make check`). Prose names code in the Emacs docstring form: a backtick, the
name, an apostrophe, as in `` `prelex' `` or `` `Lines.span' ``. A plain code span, `` `x` ``,
is any code and is not checked. Three rules:

- **lit-unknown**: a reference must name something the tangled code binds: a definition, a
  field, a parameter, an assignment or an import. `Cls.member' must be a member the class
  defines. A reference into an import, `re.compile', is checked only as far as the import.
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
   the claude CLI: `claude -p --model haiku --tools "" --safe-mode`, with a system prompt
   that asks for the answer lines alone. It runs in an empty directory, with extended
   thinking off, three times. An answer counts as right when it evaluates to the expected
   value. Only literals, containers and calls of data classes without a `__post_init__`
   are evaluated, with no builtins, since an answer is a model's text. A fact whose
   expected value is anything else is dropped.
4. The score is the mean fraction right. Below `--threshold` (default 0.7) the exit status
   is 1.

It needs a model, costs a few cents and varies from run to run, so it is not in `make
check`; `make lit-readable` runs it over every page. The claude CLI is not in the flake: it
comes from the user's own profile. Without it, `--command CMD` names any program that reads
the prompt on stdin and prints the answers, and `--show` prints the prompt for a person to
answer.

Measured on 01.02.01-lex.md, 2026-10-27, 28 facts from tests/test_lex.py: the knuth-max
prose scored 0.32 in one run. Rewriting the prose where the misses showed real gaps (the
refusal messages and their places, what a comment leaves behind, the sigils and number
forms of a token) brought it to 0.71 and 0.73 in two measurements of three runs each,
and 0.60 and 0.61 with the examples stripped.

## Annotating the published page

Every page of the site loads `assets/fpl-annot.js`. It draws the page's sidecar (shipped
beside the page) as underlined spans, each with a card in the right margin at the height of
its span and a line between the two: the span's labels and note, then the facts about it
(a relation as `contradicts L-G2`, a fact about a fact nested under it). A row whose text is
not on the page any more, or is there more than once, gets a card at the top of the margin
with its old text struck through. The right margin is free because `assets/fpl-nav.js` moves
the page's own sections under its entry in the left sidebar, and `essay.lua` nests the
headings' anchors (`#strings-and-comments/counted`), so a URL reads `page#scope/subscope`.

The control floating at the top right has three stands, also cycled with the key `a`:
*Lezen* shows nothing; *Spans* underlines the spans whose labels pass the filter (a row of
label chips under the control while it is hovered; a struck chip hides its spans) and a click
on a span opens its card alone; *Kantlijn* shows every card, the lines and the editor. The
stand and the filter are remembered in that browser for the whole site; a page opens in Lezen.

Outside Lezen every block carries its address: below the page's own number (01.02.01 Lex is
1.2.1) the headings count (`1.2.1.3`), and under a heading the blocks, paragraphs and code
alike, in page order: `§4` is the fourth block, `§5:C` the fifth when it is code, `§4.2` the
second sentence of block 4, `§4.2.3` that sentence's third clause (cut at , ; : or a dash,
shown while the sentence is hovered), `§5:12` the twelfth line of code block 5. Each has an
id in the page, `strings-and-comments/b4`, `…/b4s2`, `…/b4s2c3`, `…/b5l12`, so a URL can
name one, and a fact can cite one: a row without text whose first target is such an id gets
a card at that element, with a line to it.

A reader selects text, writes a note and picks labels (chips; type `label/sub` for one
more) in a card at that height, and saves it (⌘↩) as a quote row: `{id, item, commit,
text, prefix, suffix, labels, note, targets, createdAt, updatedAt}`, the text as shown and
32 characters of shown text either side. The rows stay in that browser (localStorage) until
Export in the margin's head downloads them as `<stem>.annot.json`; the head then prints the
`lit facts` line that takes them into the sidecar. Run it from `01-bootstrap/`, with the
path of the downloaded file:

    lit facts --import FILE \
      --item 01-bootstrap/01.02-pass/01.02.01-lex.md=01-bootstrap/01.02-pass/01.02.01-lex.md@COMMIT

The commit is the one the page was rendered from (`<meta name="fpl-commit">`). The quote is
then found on the raw page by the table of `plain`: measured 2026-10-29, a sentence selected
on the lex page exported, imported with 0 findings in 0.12 s, and was drawn as a sidecar
span on the next load. Where the window has no margin column (a phone) each card folds
under the block its span is in, and the editor is a popover.

## Layout

- [lit/web.py](lit/web.py): reading a page, and the tangle. Standard library only, so the
  walker's `tangle.py` imports it.
- [lit/lint.py](lit/lint.py): the three lint rules.
- [lit/readable.py](lit/readable.py): facts, prompt and scoring.
- [lit/run.py](lit/run.py): tool output rewritten to page lines.
- [lit/facts.py](lit/facts.py): a page as spans; its hand rows (`<stem>.facts.json`)
  validated and located, its ledger (`<stem>.decisions.tsv`) read.
- [lit/weave.py](lit/weave.py): the HTML. It is the only module that needs markdown-it-py.
  A page with hand rows shows each span found on it as a `<mark>` (green where it was
  written, amber where it moved) and ends with their footnotes: a legend, the rows counted
  by state, and one entry per row with its targets and the rows that cite it.
- [lit/__main__.py](lit/__main__.py): the command line.

`make tools` judges the tool like the language: ruff, pyright and mypy strict, the escapes
check, and 100% line and branch coverage.

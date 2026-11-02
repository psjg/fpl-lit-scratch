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
    lit check    [PAGE ...]      the web's rules, drift, ruff, the hand rows (make check)
    lit lint     [PAGE ...]      prose and code agree; examples pass (make check)
    lit weave OUT [PAGE ...]     each page as one HTML page, its facts marked (make lit-weave)
    lit readable PAGE            a model answers the tests from the prose (make lit-readable)
    lit run -- CMD ...           run CMD; its output names page lines, not file lines
    lit facts --out DIR [PAGE ...]  each page's spans and hand rows as DIR/<stem>.json
    lit facts --import DIR_OR_FILE --item LABEL=PAGE@COMMIT [PAGE]
                                    the annotation program's rows for LABEL into PAGE's
                                    sidecar, merged by id, then checked
    lit facts --export PAGE [--item LABEL=PAGE@COMMIT] [--out FILE]
                                    the sidecar's hand rows in the program's row shape
    lit anchor --verify [PAGE ...]  each hand row's text is at its place in its commit (git)

Every command takes `--root DIR`. Files are written relative to it, and without PAGE
every page under it is read. The walker's root is `01-bootstrap/`, so run lit from there:

    cd 01-bootstrap && PYTHONPATH=../.harness/tools/lit ../.harness/.venv/bin/python -m lit check

## The page

A page is Markdown. A fence opened by exactly ```` ```python ```` is a code chunk. Its
header is two lines: the chunk's place and name, then the files it stands in, separated by
spaces:

    ```python
    <<3.8 Count one pair
    fpl/lex.py python/fpl/lex/__init__.py>>=
    def counted(text: str, at: int, close: str, end: int) -> int | None:
        ...
    ```

- The place is a dotted number, first on the name line. Places sort by their numbers:
  3 < 3.1 < 3.2 < 3.10. A path may carry a place of its own for that file, before a colon
  (`2:fpl/lex.py`); otherwise the name line's place holds there too.
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
python fence without a header, a header without a place or without a path, a path that
does not parse, paths on more than one line, a `+=` with a path, a `+=` before its `=`, a
second `=`, a use of a chunk never defined, a chunk named like a path (the old file root),
a chunk that only uses others (give its parts places instead), a used chunk outside a
user's place or files, two chunks at one place of a file, a chunk no file reaches, a
cycle, a `tangle:` key in the front matter (gone), a fence that never closes, and two
pages writing one file.

## The gates

`lit check` (in `make check`). A file that differs from its page fails at the page line the
first differing line came from: `page.md:L: lit-drift: fpl/lex.py:K differs from the page`.
The remedy is to edit the page and run `lit tangle`, never to edit the file.

`lit check` also hands each tangled Python file, as the page tangles it, to ruff on stdin
with the lanes' `.harness/quality/ruff.toml`: `ruff format` must leave it as it is, and the
blank-line rules E301, E302, E303, E305 and E306 (preview in ruff) must pass, so the tangle's
rule for blank lines between chunks is checked against PEP 8, not assumed. A file ruff would
format otherwise is one `lit-tangle-ruff` finding at its first line that would change, each
blank-line fault one at its line, both at the page line the file line came from. ruff is
looked for beside the interpreter (the lanes' `.harness/.venv`), then on PATH; when there is
none, that is a finding too. `lit tangle` runs no ruff. Measured 2026-10-29: both files of the
lex page pass with no change, the check adds 24 ms, and a blank line taken out before a `def`
gives both findings at the page line of that `def`.

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
its span's last line and a line between the two. A card is headed by the first words of its
quote (never an id) and its kind as a chip; under it the note and one line: who wrote it, when
the row says so, its relations by their other end's text (`spreekt tegen → grammar-theory ·
Lexing splits…`: a target `L-<id>` in `<stem>.decisions.tsv` is a decision chip, topic and
first words, and a click opens the ledger row, its reason, date and who, in the card), and `n
reacties`. Open (a click, its menu `⋯`, `n reacties` on a card of one's own) it shows its thread:
each message with its labels, author and time when known, replies one step in and no further,
a reply arrow on hover that answers that message, and one field `Antwoord…` that saves a reply
(Enter); a thread of more than four folds to `n reacties`. The menu `⋯` holds Verbind met… (`l`:
steunt, valt aan, zelfde als, then a click on the other end), Graph van deze kaart, Toon beide,
and Verwijder (a sidecar row says why it cannot). The cards
stand in the order of their lines and are only pushed down, so the lines, which stay in the
gutter between the text and the cards, never cross; a span over three lines or more gets a
thin bar in the gutter instead of an underline. A card's quote is one line and its note two
until the card is under the mouse or holds the focus; nothing moves on hover, and a card
is never narrower than 220 px (narrower, the cards fold in). A row whose text is not on the page
any more, or is there more than once, is one amber line at the top of the margin that says so. The right margin is free because `assets/fpl-nav.js` moves
the page's own sections under its entry in the left sidebar, and `essay.lua` nests the
headings' anchors (`#strings-and-comments/counted`), so a URL reads `page#scope/subscope`.

One bar, fixed above the margin, holds three stands as tabs, also cycled with the key `a`:
*Lezen* shows nothing; *Spans* underlines the spans whose labels pass the filter and a click
on a span opens its card alone; *Kantlijn* shows every card, the lines and the editor. Beside
the tabs stand `Graph` and a menu `⋯`; under them the search field (key `z`) and a quiet line
of counts. The label filter (a struck chip hides its spans) and the layers are a panel that
opens on a click into the empty search field or on `z` with no query, never on hover; an
active filter reads `filter aan` in the count line. Where Quarto shows its top
bar (a narrow window) the bar folds into it as a stand picker and three icons. The stand and
the filter are remembered in that browser for the whole site; a page opens in Lezen. In
Kantlijn an empty margin says in three lines how to annotate, connect and fold. From about
1380 px wide, `fpl-annot.css` lets the right side of Quarto's grid take room from the left, so
the margin holds the full bar and a 316 px card behind a 40 px gutter (at 1440 the text column
starts at x 320, as on the design boards); narrower, the bar is folded at the top right.

Outside Lezen every block carries its address: below the page's own number (01.02.01 Lex is
1.2.1) the headings count (`1.2.1.3`), and under a heading the blocks, paragraphs and code
alike, in page order: `§4` is the fourth block, `§5:C` the fifth when it is code, `§4.2` the
second sentence of block 4, `§4.2.3` that sentence's third clause (cut at , ; : or a dash,
shown while the sentence is hovered), `§5:12` the twelfth line of code block 5. Each has an
id in the page, `strings-and-comments/b4`, `…/b4s2`, `…/b4s2c3`, `…/b5l12`, so a URL can
name one, and a fact can cite one: a row without text whose first target is such an id gets
a card at that element, with a line to it.

A reader selects text, writes a note and picks labels (the six most used as chips; a field that
completes from every label, or takes a new `label/sub`) in a card at that height, a card in
the stack that pushes the cards below it down, and saves it (⌘↩) as a quote row: `{id, item, commit, by, text, prefix,
suffix, labels, note, targets, createdAt, updatedAt}`, the text as shown and 32 characters of
shown text either side; `by` is who wrote it, the name given under Naam in the menu or an agent's
model id. A reply, or a fact about a fact or an address, is the same row without `text`,
`prefix` and `suffix`: a fact about its first target. The rows stay in that browser
(localStorage) until Exporteer rijen in the menu downloads them as `<stem>.annot.json`; the
menu then prints the `lit facts` line that takes them into the sidecar (Importeer rijen merges
a file back, Wis mijn rijen empties the page after asking). Run it from
`01-bootstrap/`, with the path of the downloaded file:

    lit facts --import FILE \
      --item 01-bootstrap/01.02-pass/01.02.01-lex.md=01-bootstrap/01.02-pass/01.02.01-lex.md@COMMIT

The commit is the one the page was rendered from (`<meta name="fpl-commit">`). The quote is
then found on the raw page by the table of `plain`: measured 2026-10-29, a sentence selected on
the lex page exported, imported with 0 findings in 0.12 s, and was drawn as a sidecar span on
the next load. A row without text needs a target and lands as `{id, labels, note, targets,
commit, by, createdAt, updatedAt}`, with no `item`: in a sidecar a row that names an item is a
span. A row with neither text nor targets is refused. `lit facts --export` gives every hand row
back, a row without text under the page's label. Where the window has no margin column (a
phone) each card folds under the block its span is in, and the editor is a popover.

Arguments follow the Argument Interchange Format (Chesñevar et al. 2006,
https://doi.org/10.1017/S0269888906001044): a claim never points at a claim. A `supports` or
`attacks` row stands between them, its targets read source -> ends, and since it has an id of
its own an `attacks` row may aim at it, an undercut that attacks the inference rather than its
premise. `lit facts` refuses an arguing row with fewer than two targets, one that names itself,
or one that runs from a row to that row (`lit-facts-argument`). The rows stay a graph, so one
premise may serve two claims; a card shows the tree read from its row as `Argument · 2 voor ·
1 tegen`, grounds under the claim (+ supports, − attacks), undercuts under the inference they
attack, a cycle marked where it closes. Verbind met… in a card's menu arms a pick of a kind
(`Steunt…`, `Valt aan…`, `Zelfde als…`, keys 1-3): the next click on a span, card, fact or branch is the end of a new row, and Esc cancels it.

An arguing row may carry a `weight`, an integer 1 to 5 (Kialo's impact): how much the reader
thinks the inference bears. `lit facts` refuses a weight outside 1 to 5 or on a row that does
not argue (`lit-facts-argument`). The tree shows it as five dots after the branch, the count
adds `gewicht 4 : 2` (the weights for and against, summed one level down), and the graph draws
the edge that wide. On a row of the browser a dot sets the weight and the lit last dot clears
it; a sidecar row's weight changes only through `lit facts`. `lit facts --argdown ID PAGE`
prints the tree on `ID` as Argdown (https://argdown.org/syntax/): the claim as `[ID]`, each
arguing row as an argument `<row>` described by its source and carrying `{weight: n}`, `<+`
for a support, `<-` for an attack, and `<_` for an attack on an inference, since Argdown's
undercut holds between arguments only. A row met again is named without its description.

### Layers

The rows stack in layers after the Prague Dependency Treebank (Pajas & Štěpánek 2008, PML,
https://aclanthology.org/C08-1085/). One rule holds them apart: **only a span anchors in the
text; every other row names an id**, a row's, a generated span's, a ledger row's or a page
address (`[<heading>/…/]b<n>[s<n>[c<n>]]`, the heading a path, each number from 1, which lit
takes by its shape and the page resolves). A row without `item` that carries `text`, `prefix`
or `suffix` is refused already (`lit-facts-span`). Müller (2005,
https://aclanthology.org/P05-3028/) keeps the other side: each level a self-contained module,
markables that do not point at markables of another level, their order and containment read
from the base data, and links kept apart as set and pointer relations, so that a query need
not speak in representation details. The answer here is a query over the layers later
(PML-TQ's shape, Pajas & Štěpánek 2009), not a second anchoring.

A row's layer is read from what it is and never written down (`facts.layer`, and `layerOf`
in the overlay): `span` (it names an item, or it is a `parts` set), `argument` (`supports`,
`attacks`), `tfa` (`tfa/t`, `tfa/c`, `tfa/f`, `resumes`), `coref`, `relation` (any other
relation), `thread` (a fact whose first target is a row that is no span), else `fact`. A row of
chips under the label filter hides a layer.

- **Sets** group instead of pointing. `coref` is Müller's set relation, undirected and
  transitive: its targets name one referent, and hovering one (a span, a card, a clause)
  lights the whole chain. `parts` holds what Müller keeps as a markable of several token
  ranges: its targets, spans (a sidecar span, a generated span or a ledger row), are the pieces
  of one discontinuous span. A piece may be a `parts` row itself, a piece in pieces; the
  bundles form a tree, so each piece has one whole and no bundle holds itself. Both need two
  members at least, each once (`lit-facts-set`).
- **Topic-focus** after the t-layer manual (Mikulová et al. 2006, ch. 10): one value per
  clause, `tfa/t` bound, `tfa/c` bound and contrastive, `tfa/f` not bound; topic and focus as
  wholes are not marked, they follow (`lit-facts-tfa`: the value is the row's first label, one
  value, one target, no unit marked twice). Alt-click a clause (a sentence of one clause has
  none of its own, so the sentence) cycles its value; the lens washes it. A value the sidecar
  holds is changed there: the browser can override it, not clear it.
- **Thematic progression** after Daneš (1974): a `resumes` row runs from one clause to one
  other (`lit-facts-argument`: exactly two targets), by convention from a clause to the earlier
  one whose matter it takes up; nothing checks the order. Alt-Shift-click a clause, then click
  the earlier one; the left gutter draws each link as an arc, and a click on an arc of this
  browser removes it. An arc whose two ends fold into one band is not drawn.

### Labels

Labels are free. A label is a name scoped by names to any depth, `fn/claim`,
`slop/beeld/dood` (`lit-facts-field` refuses an empty segment or a space). Only the reserved
kinds are vocabulary: a relation or set as the first label (`supports`, `coref`, …) and the
`tfa/` scope, which their own gates read. This follows
Marshall: no fixed palette of marks (1997, https://doi.org/10.1145/263690.263806), and types
that arise from examples, with structure available on demand (Marshall, Shipman & Coombs, VIKI, 1994,
https://doi.org/10.1145/192757.192759). The editor ranks its chips by use, the rows of the page
plus the times this browser saved each label anywhere on the site; the seeds, among them the
rhetorical functions under `fn/` (`fn/definition`, `fn/example`, `fn/transition`, `fn/claim`,
`fn/evidence`, `fn/aside`, `fn/hedge`), only start the list: unused, they sink, they never go.
The filter lists every scope above a label, and striking a scope strikes all below it.

When three rows of a page carry a label written in the editor, the margin offers it as a quick
chip, and the offer stays until it is answered; a yes puts it at the top of the editor of an
address (a sentence number, a clause), saved with one click, and a no is kept too, so each
label is asked about until it has an answer. Rows made by an Alt-click or a pick count
neither toward the ranking nor toward an offer. The tool proposes, the reader decides.

Several rows on one address share one card, one under the other, each whole (its replies,
its argument, its other ends for Toon beide). With different first labels they are readings, as
Empson reads one passage several ways at once (*Seven Types of Ambiguity*, 1930; read in the
1947 edition), and so are several facts with different labels on one span. A row that passes
the filter shows its whole group.

### The graph

`Graph` in the bar draws every row of the page and every id a row names, in the
layers shown, on a canvas laid out by force (Fruchterman & Reingold 1991,
https://doi.org/10.1002/spe.4380211102), the same layout each time for the same rows. A
relation row is a node of its own, a small diamond between its ends, so an undercut has a node
to aim at; a fact hangs from what it is about (`over`). `Graph` on a card draws that row and
what lies within two steps. A click on a node closes the graph and goes to the node's place on
the page; Esc closes it. Plain JavaScript, no outside assets.

### Not yet built (decided 2026-11-01, keep)

These are in the model now and gated, but the overlay does not draw them yet, or not fully.
They are the next work on this layer, not ideas:

1. **Discontinuous spans: built 2026-11-01.** A `parts` row has one card; its pieces are
   underlined as spans, light together, and have no cards of their own; a fact about the whole
   names the `parts` row. Alt-select text adds a piece (a span row of this browser), again for
   the next, and Enter bundles them and opens the editor for a fact on the whole; Esc stops and
   leaves the pieces as loose spans. The card lists the pieces as chips in order. On a `parts`
   row of this browser `Deel erbij…` arms the next Alt-selects to append to that row's targets,
   one piece each, until Esc, Enter or leaving Kantlijn (a bundle in the making is dropped first,
   its pieces left loose; text a piece of a shown bundle already covers is refused); a chip's × takes its piece out of the targets and leaves the span row as a loose
   span. Down to one piece, it asks and then deletes the `parts` row, since a one-member set is
   refused (`lit-facts-set`); a fact on that row is kept, the ask says how many, and it shows
   as a lost line at the top of the margin ("kwijt · “its note” wijst nergens heen"),
   counted under `kwijt` in the head, as any fact whose row is gone: open it to delete or
   rewrite it, since lit refuses it (`lit-facts-target`) until it names something. A sidecar
   `parts` row lists its chips read-only. A piece of a piece, built 2026-11-02: an Alt-select
   in text of another whole (while bundling, or armed on a row) takes that whole in as one
   piece, the outermost one if it is itself inside a bundle, and writes no span; text of the
   bundle being made is refused. A bundle inside has no card: it stands on its whole's card as
   one chip, its pieces in brackets, a click on it writes a fact about it, and its facts hang
   on that card under "over deel <id>". Its × makes it a whole again, with its card.
2. **Coreference as a layer of its own: built 2026-11-01.** `coref` rows that share a member
   are one chain (union-find), as PDT links an anaphor to its antecedent and a chain follows
   (Mikulová et al. 2006 ch. 9); chains are numbered by where their first member stands, and
   each member on the page carries its number. `Zelfde als…` (Verbind met… on a card) arms a pick whose end
   joins the chain. Still open: the PDT's link types (textual, grammatical) as sub-labels
   (`coref/text`), and a gutter column of the chains.
3. **Querying across layers: built 2026-11-01** (Müller's objection, PML-TQ's answer).
   Terms `[!]key:value`, all to hold, a negation a condition met zero times: `label:` (at or
   under a scope), `layer:`, `by:`, `text:`, `has:R` (an R row ends at it), `gives:R` (one
   starts from it); a fact on a page address speaks for the address. A term that is just
   `|` splits the query into groups, and a row is found when every term of one group holds
   (PML-TQ's or, in disjunctive normal form); a `|` at either end or beside another is an
   error. `has:R+N` and `gives:R+N` ask for a chain of at least N R edges ending or
   starting there (PML-TQ's `{N,}`): an edge runs from a relation's first target to each of
   the others, and both ways between the members of a set; a chain visits no node twice,
   so a cycle does not lengthen it, and only its end is widened to the address a fact
   speaks for. Bare `has:R` is `has:R+1`, one edge ending there; bare `gives:R` is
   `gives:R+1` for a relation and never holds for a set's member. A node never joins itself,
   so a row with one target, or one naming its first target again, bears no edge and is
   found by neither form. A chain longer than the nodes its end reaches is no at once;
   past 100 000 steps a walk stops with `chain too long to search at COL` (a simple path is
   a search that grows as the factorial of a set's members), and `N` past nine digits reads
   as 10⁹. `lit facts --query Q PAGE` prints what
   it finds; the bar's search field fades the rest. One language, two
   readers, held together by `tests/query_cases.json`, which both `facts.query` and the
   overlay's block (run in node, `tests/test_query_js.py`) must answer alike. Examples:
   `label:claim !has:attacks` (a claim no one attacks), `label:tfa/f !has:resumes` (a
   focus no clause takes up), `label:claim | label:question` (either), `has:supports+3`
   (the end of three supports in a row).
4. **The graph, step two: built 2026-11-01.** `lit graph [PAGE ...]` writes
   `<page stem>.graph.json` beside each page: its chunks (ids as in the fact layer), the files
   they tangle to, `uses` edges from a chunk to every chunk its body names, and `tangles` edges
   with the number of lines given, read from the tangle rows (lit tangles a page's first Python
   file only, so one file per page today). Generated at publish (`publish.sh html`), shipped by
   `_quarto-site.yml`, ignored by git. The overlay adds them to its graph: a chunk as a square,
   a tangle edge as wide as log2 of its lines, a click on a chunk goes to its code block; a row
   that names a chunk joins the two.

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

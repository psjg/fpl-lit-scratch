# The root's Makefile: the walker is a project of its own under 01-bootstrap/, so every lane of
# the noslop gate (.harness/quality/noslop.mk) is run there, and CI's `make check` / `make ready` reach it
# from the root unchanged (.github/workflows/noslop.yml, map.yml). This file names the lanes
# and adds none: what each runs, and how hard, is .harness/quality/noslop.mk's.
#
# It also holds the walker's entry from the root, where a README points: the package is
# 01-bootstrap/fpl, so a bare `python -m fpl` run here does not find it. `run` and `repl` put
# 01-bootstrap/ on the path of the one .venv's python, and the check lane runs `run` on an example
# from here (.harness/quality/noslop.mk), so the entry cannot break unnoticed.
#
#   make              the one gate, as `make check`
#   make <lane>       fix quick check harden ready gates tools map venv pristine clean-noslop
#   make run FILE=f   run the file f, a path from the root:    make run FILE=path/to/p.fpl
#   make repl ARGS=a  the REPL, with its arguments a:          make repl ARGS='-e "1 + 2"'
#   make graph        the repository as one OKF bundle, as Turtle: build/okf.ttl
#   make okf-check    the OKF gates over that graph (.harness/tools/okfgraph/README.md)
#   make okf-check-tg the same OKF rules, judged by Typed Graph's checker, pinned
#   make nix-check    the fpl package built in the Nix sandbox, and its REPL run there (nix flake check)
#   make lit-readable a model reads each literate page without its code and answers its tests'
#                     facts; report-only, since it needs the claude CLI (.harness/tools/lit/README.md)
#   make lit-weave    each literate page as HTML, into build/lit/
.DEFAULT_GOAL := check
LANES := fix quick check harden ready gates tools map venv pristine clean-noslop
.PHONY: $(LANES) run repl tangle-fpl graph okf-check okf-check-tg nix-check lit-readable lit-weave

$(LANES):
	@$(MAKE) --no-print-directory -C 01-bootstrap $@

# 03-fpl/**/*.md (except OLD/) → sibling *.fpl. Markdown is the source.
tangle-fpl:
	@$(CURDIR)/.harness/.venv/bin/python $(CURDIR)/01-bootstrap/tangle_fpl.py


# The walker as the root runs it: the lanes' interpreter (.venv, the root's, synced by `venv`)
# with the package, 01-bootstrap/fpl, put on its path. A relative path means what it means from
# the root, so FILE and a REPL's --session are written from there.
FPLPY := PYTHONPATH=$(CURDIR)/01-bootstrap $(CURDIR)/.harness/.venv/bin/python

# The venv is prepared inside 01-bootstrap/ with its chatter sent to stderr, so stdout is the
# program's output and nothing else: `make run` prints what `python -m fpl` prints.
VENV = @$(MAKE) --no-print-directory -C 01-bootstrap venv >&2

run:
	$(VENV)
	@test -n "$(FILE)" || { echo "make run: name the file: make run FILE=path/to/p.fpl" >&2; exit 2; }
	@$(FPLPY) -m fpl "$(FILE)"

repl:
	$(VENV)
	@$(FPLPY) -m fpl.repl $(ARGS)


# okfgraph reads the bundle from the git index and runs in its own locked environment, the one
# `make tools` judges it in, so its dependencies never enter the walker's .venv. A baseline,
# while one exists, lists findings a new rule tolerates until the notes meet it.
OKFG := $(CURDIR)/.harness/tools/okfgraph
OKFGRAPH = UV_PROJECT_ENVIRONMENT=$(OKFG)/.venv uv run --quiet --frozen --project $(OKFG) okfgraph
OKF_BASELINE := $(wildcard $(OKFG)/baseline)

# The generated fact layer (.harness/tools/lit/README.md): the spans of every literate page,
# written to build/facts/ for okfgraph to load beside the hand-written sidecars. Nothing in it
# is committed; it is a function of the pages, their tests and their decisions tables.
facts:
	$(VENV)
	@cd 01-bootstrap && PYTHONPATH=$(LITG) $(CURDIR)/.harness/.venv/bin/python -m lit facts \
	  --out $(CURDIR)/build/facts

graph: facts
	@$(OKFGRAPH) graph --root $(CURDIR) --out $(CURDIR)/build/okf.ttl

# The gate judges the bundle before the walker: a note without a type, or an edge into
# nothing, fails `make check` as a type error does.
check: okf-check

okf-check: facts
	@$(OKFGRAPH) check --root $(CURDIR) $(if $(OKF_BASELINE),--baseline $(OKF_BASELINE))

# A second, independent judge of OKF §11. It reads the working tree, not the index, and skips
# dot-folders, so run it on a clean checkout.
okf-check-tg:
	@npm_config_yes=true npx @typedgraph/cli@0.6.0 okf check $(CURDIR)

# The installed command, hermetic: flake.nix builds the wheel from nixpkgs alone and runs
# `fpl repl` and `fpl --help` against it, with no network. Slower than a lane, so check does not
# wait on it; CI and the full lane run it by name.
nix-check:
	nix flake check


# The literate pages' reader check and weave (.harness/tools/lit/README.md). The reader check
# runs lit with the lanes' interpreter, which can load the page's module to judge an answer,
# and asks Haiku through the claude CLI; it costs a few cents and varies from run to run, so
# no gate waits on it. The weave needs markdown-it-py, so it runs in lit's own environment.
LITG := $(CURDIR)/.harness/tools/lit
LIT_PAGES = $(shell cd 01-bootstrap && PYTHONPATH=$(LITG) python3 -c \
  'from pathlib import Path; from lit.web import discover; print(*discover(Path(".")))')

lit-readable:
	$(VENV)
	@cd 01-bootstrap && for p in $(LIT_PAGES); do \
	  PYTHONPATH=$(LITG) $(CURDIR)/.harness/.venv/bin/python -m lit readable $$p || status=1; \
	done; exit $${status:-0}

lit-weave:
	@cd 01-bootstrap && UV_PROJECT_ENVIRONMENT=$(LITG)/.venv uv run --quiet --frozen \
	  --project $(LITG) python -m lit weave $(CURDIR)/build/lit

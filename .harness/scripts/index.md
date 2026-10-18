# Scripts

* [acommit](acommit.sh) - make a commit that follows .agents/COMMITS.md.
* [agent-identity](agent-identity.sh) - read / write the agent author email for this worktree.
* [boundary-self-test](boundary-self-test.sh) - proof that .harness/scripts/boundary.sh judges one commit by its own paths,
* [boundary](boundary.sh) - one commit holds harness paths or implementation paths, never both.
* [branch-lint](branch-lint.sh) - the branch-name grammar, as an executable.
* [commit-lint](commit-lint.sh) - run the commit-msg gates over commits that already exist.
* [essay](essay.lua) - essay
* [gen-config-self-test](gen-config-self-test.sh) - proof that the generated-config gate still bites.
* [homepage](homepage.py) - homepage
* [import-pr](import-pr.sh) - take a pull request from a forge into pijul as one change.
* [land](land.sh) - the maintainer's half of landing a pull request: wait, look, decide.
* [layer](layer.sh) - turn the opt-in layers of the dev shell on and off for this checkout.
* [leak-check-self-test](leak-check-self-test.sh) - proof that .harness/scripts/leak-check.sh refuses what it must, lets
* [leak-check](leak-check.sh) - keep private terms, and secrets, out of a public repository.
* [mirror-self-test](mirror-self-test.sh) - .harness/scripts/mirror.sh and .harness/scripts/import-pr.sh against a real pijul and
* [mirror](mirror.sh) - project a pijul channel onto a git branch, for a public forge.
* [new-worktree](new-worktree.sh) - create an implementation worktree under worktrees/<name>/.
* [pr](pr.sh) - open the pull request for an agent branch, as the machine account.
* [pre-push-self-test](pre-push-self-test.sh) - proof that .githooks/pre-push holds every commit a push adds
* [publish](publish.sh) - Publish the literate site and the LuaLaTeX book to psjg/fpl-lit-scratch.
* [restack](restack.sh) - rebase the current stack onto the latest base, moving every
* [review](review.sh) - render the diff of a branch as a page, with the whole file around it.
* [setup](setup.sh) - make a clone or worktree ready for the FPL commit workflow.
* [spec-guard-self-test](spec-guard-self-test.sh) - proof that both halves of the oracle rule still bite where the

# Workflows

* [branch-lint](branch-lint.yml) - side half of the branch-name gate (docs/BRANCHES.md).
* [claude-code-review](claude-code-review.yml) - A review costs a model call; the two lint workflows cost seconds. So this one runs
* [claude](claude.yml) - claude
* [codex-review](codex-review.yml) - A second reviewer from outside Anthropic. It proposes; a Claude model signs off on anything
* [commit-lint](commit-lint.yml) - side half of the commit-message gates (docs/COMMITS.md).
* [gitlab-mirror](gitlab-mirror.yml) - Mirror every branch and tag of fpl-org/fpl to gitlab.com/PSJx/fpl (#108).
* [map](map.yml) - The map of the code, for whoever reviews a pull request (docs/QUALITY.md, `make map`).
* [noslop](noslop.yml) - The noslop gate, where it cannot be skipped: on the pull request (docs/QUALITY.md).
* [tools](tools.yml) - The tools lane: the tooling beside the language, judged as strictly as the code

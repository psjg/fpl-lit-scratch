# Okfgraph queries

* [a-untyped](a-untyped.rq) - gate: every note has a type
* [a2-index-frontmatter](a2-index-frontmatter.rq) - gate: no frontmatter on index.md below the root
* [a3-frontmatter-error](a3-frontmatter-error.rq) - gate: a typed note's frontmatter projects
* [b-into](b-into.rq) - report: every edge into one note
* [c-adr](c-adr.rq) - report: ADR states and edges
* [d-supersede-pair](d-supersede-pair.rq) - gate: supersedes and superseded-by agree
* [e-edge-without-link](e-edge-without-link.rq) - gate: every typed edge is also a body link
* [fact-load](fact-load.rq) - gate: every rows file of the fact layer loads whole
* [fact-stats](fact-stats.rq) - report: fact rows by kind and state
* [f-dangling](f-dangling.rq) - gate: no edge into nothing
* [g-wikilink](g-wikilink.rq) - gate: no wikilinks
* [h-status-enum](h-status-enum.rq) - gate: status is draft, stable or deprecated
* [i-type-unknown](i-type-unknown.rq) - gate: the type is in the vocabulary
* [j-edge-disagree](j-edge-disagree.rq) - gate: a typed body link agrees with the frontmatter
* [k-body-dangling](k-body-dangling.rq) - gate: no typed body link into nothing
* [l-body-undeclared](l-body-undeclared.rq) - report: body relations the context does not declare
* [z-stats](z-stats.rq) - report: counts

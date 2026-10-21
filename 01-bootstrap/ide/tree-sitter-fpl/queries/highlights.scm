; Shapes are lex.py's SHAPE and NUMBER, as predicates over the one word node.
(note) @comment
(doc) @comment.documentation
(block_comment) @comment
(string) @string
(raw_string) @string.special
(bar) @punctuation.delimiter
["[" "]" "(" ")" "⟨" "⟩" "{" "}"] @punctuation.bracket
((word) @number (#match? @number "^-?(\\d+(\\.\\d+)?|∞|π)$"))
((word) @operator (#match? @operator "^[´`¨˜⁼˙]+$"))
((word) @keyword (#match? @keyword "^(->|→|\\$|#|&|\\.\\./|\\.\\.)"))
((word) @module (#match? @module "/"))
(word) @variable

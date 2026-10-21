/**
 * Tree-sitter grammar for FPL, hand-ported from
 * 01-bootstrap/fpl/grammar.lark (there is no Lark -> tree-sitter converter).
 *
 * Same layers as the Lark grammar: words are one generic token, enclosures
 * [] () <> {} are counted pairs, a line may head an indented block. What the
 * Lark grammar does with a pre-lexer (strings, block comments) and an
 * Indenter (INDENT/DEDENT) lives in src/scanner.c. Frames and cells are not
 * nodes here: `|` and tab are tokens in the line, because tree-sitter rules
 * may not match the empty string and an empty frame is legal FPL.
 */
module.exports = grammar({
  name: "fpl",

  externals: ($) => [
    $._nl, // end of a line outside any enclosure; carries the next line's tabs
    $._inner_nl, // a newline inside an enclosure: not block structure
    $._indent,
    $._dedent,
    $.string, // “ ” counted, nesting
    $.raw_string, // 「 」 counted
    $.block_comment, // ⟦ ⟧ counted
    $.note, // ; or ⍝ to end of line, plus the ; lines right under it
  ],

  extras: ($) => [/[ \f\r]/, $.block_comment],

  rules: {
    source_file: ($) => repeat($.line),

    line: ($) =>
      seq(
        repeat($._unit),
        optional(choice($.note, $.doc)),
        $._nl,
        optional($.block),
      ),

    block: ($) => seq($._indent, repeat1($.line), $._dedent),

    _unit: ($) => choice($._item, $.bar, $.tab),
    _inner: ($) => choice($._item, $.bar, $.tab, $._inner_nl),

    _item: ($) =>
      choice(
        $.word,
        $.string,
        $.raw_string,
        $.quotation,
        $.prefix,
        $.group,
        $.dict,
      ),

    quotation: ($) => seq("[", repeat($._inner), "]"),
    prefix: ($) => seq("(", repeat($._inner), ")"),
    group: ($) => seq("⟨", repeat($._inner), "⟩"),
    dict: ($) => seq("{", repeat($._inner), "}"),

    bar: () => "|",
    tab: () => /\t+/,
    doc: () => /;;[^\n]*/,

    // grammar.lark TOKEN: any run of characters that are not whitespace or
    // self-delimiting. Its shape (sigil, number, path, modifiers) is the
    // affix pass, so highlights.scm classifies it with #match? predicates.
    word: () => /[^\s\[\]()“”「」⟦⟧⟨⟩{}|⍝;]+/,
  },
});

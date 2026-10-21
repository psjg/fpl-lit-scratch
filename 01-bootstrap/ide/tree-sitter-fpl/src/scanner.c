/*
 * External scanner for FPL: what grammar.lark leaves to its pre-lexer (counted
 * strings, block comments) and to Lark's Indenter (INDENT/DEDENT: one tab per
 * level, a counter, no width comparison). A newline outside an enclosure is
 * _nl, followed by pending _indent/_dedent; inside one it is _inner_nl and
 * changes no level.
 */
#include "tree_sitter/parser.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum { NL, INNER_NL, INDENT, DEDENT, STRING, RAW_STRING, BLOCK_COMMENT, NOTE };
#define MAX_DEPTH 64

typedef struct {
  uint8_t depth;          /* levels open */
  uint8_t pending_dedent; /* dedents still to emit */
  uint8_t pending_indent; /* 0 or 1 */
  uint8_t eof_done;       /* the line break at EOF was emitted */
} Scanner;

void *tree_sitter_fpl_external_scanner_create(void) {
  return calloc(1, sizeof(Scanner));
}
void tree_sitter_fpl_external_scanner_destroy(void *p) { free(p); }
unsigned tree_sitter_fpl_external_scanner_serialize(void *p, char *buf) {
  memcpy(buf, p, sizeof(Scanner));
  return sizeof(Scanner);
}
void tree_sitter_fpl_external_scanner_deserialize(void *p, const char *buf,
                                                  unsigned n) {
  if (n == sizeof(Scanner)) memcpy(p, buf, n);
  else memset(p, 0, sizeof(Scanner));
}

static void next(TSLexer *l) { l->advance(l, false); }

/* A counted pair: open already seen at lookahead; consume through its close. */
static bool pair(TSLexer *l, int32_t open, int32_t close) {
  int depth = 0;
  do {
    if (l->eof(l)) return false;
    if (l->lookahead == open) depth++;
    else if (l->lookahead == close) depth--;
    next(l);
  } while (depth > 0);
  return true;
}

/* ; (not ;;) or ⍝ at lookahead? Consumes the mark only. */
static bool note_mark(TSLexer *l) {
  if (l->lookahead == 0x235D) { next(l); return true; }
  if (l->lookahead == ';') {
    next(l);
    return l->lookahead != ';';
  }
  return false;
}

static void to_eol(TSLexer *l) {
  while (!l->eof(l) && l->lookahead != '\n') next(l);
}

bool tree_sitter_fpl_external_scanner_scan(void *p, TSLexer *l,
                                           const bool *valid) {
  Scanner *s = p;
  if (s->pending_dedent && valid[DEDENT]) {
    s->pending_dedent--;
    s->depth--;
    l->result_symbol = DEDENT;
    return true;
  }
  if (s->pending_indent && valid[INDENT]) {
    s->pending_indent = 0;
    s->depth++;
    l->result_symbol = INDENT;
    return true;
  }
  while (l->lookahead == ' ' || l->lookahead == '\f' || l->lookahead == '\r')
    l->advance(l, true);

  if (valid[BLOCK_COMMENT] && l->lookahead == 0x27E6) {
    if (!pair(l, 0x27E6, 0x27E7)) return false;
    l->result_symbol = BLOCK_COMMENT;
    return true;
  }
  if (valid[STRING] && l->lookahead == 0x201C) {
    if (!pair(l, 0x201C, 0x201D)) return false;
    l->result_symbol = STRING;
    return true;
  }
  if (valid[RAW_STRING] && l->lookahead == 0x300C) {
    if (!pair(l, 0x300C, 0x300D)) return false;
    l->result_symbol = RAW_STRING;
    return true;
  }
  if (valid[NOTE] && (l->lookahead == ';' || l->lookahead == 0x235D)) {
    if (!note_mark(l)) return false;
    to_eol(l);
    l->mark_end(l);
    /* continuation: the next lines, after their tabs, begin with a note mark */
    for (;;) {
      if (l->lookahead != '\n') break;
      next(l);
      while (l->lookahead == '\t') next(l);
      if (!note_mark(l)) break;
      to_eol(l);
      l->mark_end(l);
    }
    l->result_symbol = NOTE;
    return true;
  }

  if (l->lookahead == '\n' || l->eof(l)) {
    bool inner = valid[INNER_NL] && !valid[NL];
    if (!valid[NL] && !valid[INNER_NL]) return false;
    if (l->eof(l)) {
      if (inner || s->eof_done) return false;
      s->eof_done = 1;
    } else {
      unsigned tabs = 0;
      bool counting = true;
      next(l);
      for (;;) {
        if (l->lookahead == '\n') { tabs = 0; counting = true; }
        else if (l->lookahead == '\t' && counting) tabs++;
        else if (l->lookahead == ' ' || l->lookahead == '\f' ||
                 l->lookahead == '\r' || l->lookahead == '\t') counting = false;
        else break;
        next(l);
      }
      if (l->eof(l)) { s->eof_done = 1; tabs = 0; }
      if (!inner) {
        if (tabs > s->depth) s->pending_indent = 1;
        else s->pending_dedent = s->depth - tabs;
      }
    }
    if (l->eof(l) && !inner && s->pending_dedent == 0 && s->depth) {
      s->pending_dedent = s->depth;
    }
    l->mark_end(l);
    l->result_symbol = inner ? INNER_NL : NL;
    return true;
  }
  return false;
}

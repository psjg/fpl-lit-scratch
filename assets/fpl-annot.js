/*
 * fpl-annot.js: the facts of a published literate page, in its margin.
 *
 * The page's fact sidecar (<stem>.facts.json, shipped beside it) is drawn
 * as underlined spans, each with a card in the right margin at the height
 * of its span and a line between the two; a reader selects text, writes a
 * note and picks labels in a card at that height, and the row is kept in
 * this browser until it is exported and imported into the sidecar by lit.
 * Nothing is sent anywhere.
 *
 * Where a page is. The script's own URL ends in assets/fpl-annot.js, and
 * the directory above assets/ is the site root, so the page's repo path
 * (its item) is its URL below that root with .html read as .md. This
 * works on the published site (<meta name="fpl-site">) and on a local
 * serve of .site alike. The commit is <meta name="fpl-commit">, the HEAD
 * the page was rendered from (essay.lua).
 *
 * A row, as lit facts --import reads it:
 *
 *   { id: "a-" + base36 time + random, item, commit, by,
 *     text,            the selection as shown, whitespace made one space
 *     prefix, suffix,  32 characters of shown text either side of it
 *     labels: [], note, targets: [], createdAt, updatedAt }  (times in ms)
 *
 * by is who wrote the row: the name this browser was given under Naam
 * in the bar's menu (localStorage["fpl-annot:by"]), or, for a row an agent
 * imported with lit, that agent's model id; a row without one shows no
 * author, never a "?". A reply is a row without text whose first target
 * is the fact it answers: a message in its card's thread, one step in.
 *
 * A quote row has no offsets: lit finds it in the raw page by text, and
 * prefix and suffix choose among several hits. Rows of the sidecar keep
 * their own shape and are drawn by their text the same way. A row without
 * text is a fact about its first target: it is shown on the card of the
 * span it hangs from, nested under the fact it is about. When that target
 * is not a row but an address on the page (a block, sentence, clause or
 * code line: essay.lua and fpl-nav.js give them ids such as
 * strings-and-comments/b5l12), the row gets a card of its own at that
 * element, with a line to it. A click on a block's or sentence's number
 * puts that address in the URL and on the clipboard and, in the
 * kantlijn stand, opens the editor for a fact on it: the way a lawyer
 * cites a clause.
 *
 * Storage. localStorage["fpl-annot:" + item] holds a JSON array of this
 * browser's rows for that page; the sidecar is never written here. The
 * menu's Exporteer rijen downloads that array as <stem>.annot.json
 * (JSON.stringify(rows, null, 1)) and shows the lit command that takes
 * it in; Importeer rijen merges a file of rows into it by id; Wis mijn
 * rijen empties it, after asking. Exporteer logboek downloads the log
 * (below) as <stem>.log.json.
 *
 * Finding a quote. The page's text nodes, but not the overlay's or a
 * card's folded in under its block, are read into one string, the
 * shown text: a backtick dropped, a curly quote read as a straight one,
 * every run of space or "|" one space, each character remembering the
 * node and offset it came from. A row's text is read the way lit reads
 * markdown (`name' as name, [text](url) as text, heading marks dropped)
 * and searched for in it; found once it is drawn, more than once it is
 * dubbel, nowhere stale. Both get one amber line at the top of the
 * margin that says so, not a span.
 *
 * A saved copy. A page saved with its overlay (the snapshot artifact PSJ
 * annotates) has no site URL and no sidecar beside it; it sets
 * window.FPL_SNAPSHOT = { item, commit, rows } before this script, and
 * the overlay runs on that instead.
 *
 * The margin. Quarto's right column (#quarto-margin-sidebar) is empty
 * once fpl-nav.js has moved the page's sections to the left, and holds
 * the cards; the margin starts RAIL (12px) past the text column, under
 * the bar's left edge, and ends RIGHT (24px) from the window's, at most
 * a CARD and the gutter's 28px wide. From 1380px wide fpl-annot.css
 * lets the right side of Quarto's grid take room from the left, so that
 * at 1440 the column stands at x320 and the bar (344px) and a card
 * (316px) fit, as on the boards. Where the column is hidden or a card
 * there would be narrower than NARROW (220px), each card folds under the block
 * its span is in, and the editor is a popover; the span keeps its knob,
 * with no line to the card under it.
 * A card stands at the height of its span's last line, in the order of
 * those lines, and is only pushed down, by the card above it; the
 * editor is a card in that stack and pushes the rest down, never over
 * them. Its line stays in the gutter: a stub at the text's edge, then
 * one curve to the card's dot, so no two lines cross and none crosses
 * the text. A span over three lines or more gets a thin bar in the
 * gutter instead of an underline on every line. A quote in a card is
 * one line and a note two, until the card is hot (its span, knob,
 * line or card under the mouse, all lit together) or holds the focus;
 * a hot card opens over the one below it, so nothing moves. A card's
 * colour is its dot's. A clause's number shows only on the sentence
 * under the mouse, above the clause.
 *
 * A card (board F) is headed by the first words of its quote, never an
 * id, and its kind as a chip; its Graph and ⋯ keep their room while
 * hidden and show on hover. Under the note one meta line: who, when
 * known, the relations by their other end's text, a decision of the
 * page's ledger (<stem>.decisions.tsv, ids L-<id>) as a chip whose click
 * opens the row in the card, and "n reacties". A card opened (a click,
 * its ⋯, its "n reacties") is laid out open and pushes the rest down: its
 * thread, replies one step in, a reply arrow per message, and one field
 * Antwoord… whose Enter saves a reply row; past four messages the thread
 * folds to "n reacties". The ⋯ menu stands left of its card: Verbind
 * met… (key l), Graph van deze kaart, Toon beide, Verwijder (a sidecar
 * row says why not).
 *
 * The knob (board C) at the end of a span is a handle: a plain dot that
 * grows under the mouse, on focus and while carried, never a ring. Drag
 * it onto a span, card, fact or address (on touch after a long press):
 * the end under the pointer lights, and a dashed line from the span's
 * stub follows, in the gutter while the pointer is over the text and to
 * the pointer over the margin, a dot under the pointer. On the drop a
 * chooser asks the kind: verbindt (relates, also Enter), steunt, valt
 * aan, zelfde als, citeert (keys 1-5); Esc or a click elsewhere lets go.
 * A drop on nothing or on its own span lets go and says so. A click on
 * the knob, its card's Verbind met… or the key l (on the knob or card
 * with the focus, else the card under the mouse) arms a pick instead: a
 * click on the other end, or Tab and the arrows to it and Enter, asks the
 * same. The row is saved as every pick's is, targets [start, end].
 *
 * The same knob stretches (board D): carried along the text of its own
 * block rather than onto another end, it moves the end of a span of this
 * browser a whole word at a time, the words gained washed and dashed,
 * the words lost washed grey, and a tip "+ n woorden · loslaten bewaart
 * · Esc zet terug"; the drop saves text, prefix and suffix read anew,
 * Esc puts it back. Where it is let go decides: over another span, card,
 * fact or knob, or another block's text, it connects. A bundle's knob
 * stretches the piece it ends; a sidecar span only connects, and says
 * why. Shift with the arrows on a focused knob stretches by a word, Enter
 * saves.
 *
 * The bar. One bar, fixed above the margin column, holds the three
 * stands as tabs (Lezen, Spans, Kantlijn, also the key "a"), the search
 * field (the key "/" in Kantlijn, where it is taken from Quarto's site
 * search, and "z" in every stand), Graph and a menu ⋯: Naam, Importeer rijen,
 * Exporteer rijen, Exporteer logboek, Vouw tot de spans, Context 0-3,
 * Sneltoetsen (also "?") and Wis mijn rijen. A quiet line under it
 * counts the spans, the relations, the lost rows and this browser's,
 * and says "filter aan" while a filter holds. The label and layer
 * filters are a panel that a click into the empty search field (or z
 * with no query) opens, hover never does, and nothing in the bar changes size
 * or place on hover or on a change of stand. Where Quarto shows its top
 * bar (a narrow window) the bar folds into it, a stand picker and three
 * icons, the search and the counts in the filter panel, and that top bar
 * then stays on a scroll down rather than sliding away; where neither
 * fits, the folded bar stands at the top right of the window. In
 * Kantlijn an empty margin says in three lines how to annotate,
 * connect and fold.
 *
 * Three stands: lezen shows nothing; spans underlines the spans whose
 * labels pass the filter, and a click on a span opens
 * its card alone; kantlijn shows every card, the lines and the editor.
 * localStorage["fpl-annot:mode"] keeps the stand
 * and "fpl-annot:hide" the labels switched off, for the whole site.
 *
 * Bands (after LiquidText's collapse, Tashman & Edwards, CHI 2011;
 * boards G and H). A band folds the blocks from one block address to
 * another, both ends included, into a seam of 28px: two hairlines
 * across the column and at their left its range, "1.2.1.3 §9 - 1.2.1.4
 * §7 · 25 blokken", so the reader sees where the text is folded and how
 * much, and the page stays one scroll. Headings, lists and tables
 * between the two blocks fold with them. A click on the seam (or Enter)
 * opens it, Escape the newest; under the mouse it darkens and a tip
 * under it says how to fold further. The bands are in the URL as
 * ?scrunch=a..b,c..d (block ids such as the-plan/b3) and in
 * localStorage["fpl-annot:scrunch:" + item]; at load the URL wins. A
 * span inside a band draws its line, and places its card, at the seam.
 *
 * Folding is a gesture, as in LiquidText. Shift+wheel over the text
 * folds around the pointer, the block under it first and then outward,
 * as far as the wheel turns, the seam staying under the pointer;
 * turned back it opens the band under the pointer (or the nearest in
 * the window). On a touch screen two fingers drawn together fold the
 * blocks between them, from the middle out, as many as the fingers
 * closed by; drawn apart over a band they open it. With a filter or a
 * query on, the same Shift+wheel folds to the spans they let through:
 * every block further than the context (0-3 blocks, the menu's
 * Context, kept in localStorage["fpl-annot:context"]) from such a span,
 * and back opens them; the count line then reads "5 van 9 spans ·
 * ingevouwen tot de spans, context 1". Vouw tot de spans, in the menu,
 * does the same without the gesture; chosen again it opens them, and a
 * new context refolds. A card whose row points at another place on the
 * page has "Toon beide", which folds what lies between the two so both
 * are in view (its menu, or a click on the other end in its meta line).
 * A query asked lights the search field, whose key gives way to an x
 * that clears it.
 *
 * Close reading. Outside Lezen each block carries a bar in its left
 * gutter, shaded by how many rows hang from it (after Zyto 2012, where
 * the most annotated regions of a text showed where readers stumbled).
 * And j and k move a reading cursor sentence by sentence (after Miall
 * 1994): the sentence is washed, its address is the URL's hash, so a
 * reload returns to it, and Enter opens the editor for a fact on it.
 *
 * Arguments, after the Argument Interchange Format (Chesnevar et al.
 * 2006): a claim never points at a claim. A supports or attacks row
 * stands between them, read targets[0] -> targets[1:], and has an id of
 * its own, so an attacks row may aim at it: an undercut, which attacks
 * the inference rather than its premise. The data stays a graph (a
 * premise may serve two claims); a card shows the tree read from its
 * row, grounds under the claim, undercuts under the inference they
 * attack. Steunt and valt aan are kinds of the knob's chooser, and a
 * branch of a tree is an end like a span, a card or a fact.
 *
 * Layers, after the Prague Dependency Treebank's stacked annotation:
 * only a span anchors in the text, every other row names an id. A row's
 * layer is read from what it is, as lit's facts.layer reads it (span,
 * fact, thread, argument, tfa, coref, relation), and a row of chips
 * under the labels in the filter panel hides a layer. A coref row groups ids that name
 * one referent: hovering one lights the others. The tfa lens marks a
 * clause t (bound), c (bound, contrastive) or f (not bound), after the
 * t-layer manual (Mikulova et al. 2006): Alt-click a clause cycles its
 * value. A resumes row says a clause takes up an earlier one (Danes
 * 1974); Alt-Shift-click a clause arms the pick, and the left gutter
 * draws each such link as an arc, so the thematic progression shows.
 *
 * Labels are free paths, a name scoped by names to any depth (fn/claim,
 * slop/beeld/dood), after Marshall (1997: no fixed palette of marks)
 * and VIKI (Marshall et al. 1994: types arise from examples, structure
 * comes on demand). The
 * editor ranks the labels by use, on this page and in this browser across
 * the site, and shows the first six as chips; its field completes from
 * all of them. The seeds under fn/ only start the list and sink, never go.
 * Striking a scope in the filter strikes everything under it. When three
 * rows on a page share a label, the margin offers it once as a quick
 * chip, one click in the editor of an address; nothing is imposed. Rows
 * on one address share one card, side by side; with different labels
 * they are readings, as Empson reads one passage several ways at once,
 * and so are facts on one span with different labels. A row that passes
 * the filter shows its group.
 *
 * The graph: every row of the page and everything a row names, in the
 * layers shown, laid out by a force model (Fruchterman and Reingold 1991)
 * on a canvas. A relation row is a node of its own, a small diamond, so
 * an undercut has something to aim at (AIF); a fact hangs from what it is
 * about. "Graph" in the bar shows the page; "Graph" on a card (board J)
 * a popover left of the card, as large as what it holds: that row and
 * what lies within two steps, read as the card's meta line reads it (a
 * relation between two ends an edge with its verb, an undercut's target
 * a diamond, the thread left in the card), each node named by its first
 * words, never an id, and a button Hele pagina; a click on a node goes
 * there.
 * Beside the rows stand the page's chunks and the files they tangle to,
 * from <stem>.graph.json (lit graph, written at publish): a chunk uses
 * chunks, tangles to a file, and a row may name a chunk.
 *
 * Discontinuous spans: a parts row bundles span rows as the pieces of
 * one span (Mueller 2005 keeps such a span as several token ranges). Its
 * pieces are underlined as before but light together and share one card,
 * the parts row's, where a fact about the whole hangs. Alt-select text to
 * add a piece, again for the next, and Enter bundles them; Esc stops.
 * The card lists the pieces as chips in order. On a parts row of ours
 * "Deel erbij…" arms the next Alt-selects to join that row, until Esc,
 * Enter or leaving Kantlijn, and text a shown bundle's piece covers is
 * refused; a chip's × lets its piece go as a loose span; with one piece
 * left the bundle goes (lit refuses a one-member set), and a fact on it,
 * kept, gets a lost card like any fact whose row is gone (the ask counts
 * them; lit refuses them until they name something).
 * A sidecar row's chips only read. A piece may be a bundle: Alt-select
 * text of another whole and that whole (the outermost) joins as one
 * piece. It has no card then; its whole's card shows it as one chip of
 * bracketed pieces, a click writes a fact about it, and its facts hang
 * there under "over deel <id>". lit keeps the bundles a tree.
 *
 * The coref lens: coref rows that share a member are one chain (a
 * union-find over the sets), numbered in page order, and each member on
 * the page carries its chain's number, as the PDT links an anaphor to its
 * antecedent (Mikulova et al. 2006, ch. 9) and a chain follows from the
 * links. Zelfde als in the knob's chooser joins its end to the chain.
 *
 * Querying across the layers (after PML-TQ, Pajas and Stepanek 2009):
 * the bar's search field takes terms [!]key:value, all to hold, in
 * groups apart by "|" of which one must hold, and has:R+N or gives:R+N
 * for a chain of at least N R edges; the same language as lit facts
 * --query (facts.parse_query, facts.query) and tested against the same
 * cases (tests/query_cases.json): what it finds stays, the rest fades.
 * The count line says how many it found, or why the query does not
 * parse; a query asked in Lezen turns to Spans, where there is
 * something to find.
 *
 * The log (feedback 7): window.fplAnnotLog keeps the last 200 acts,
 * {t, action, target, ok, reason}, what the reader did and every
 * refusal with the reason its toast gave; a selection outside Kantlijn
 * and a quote not found are logged without a toast. Nothing is sent.
 */
(() => {
  "use strict";
  const LABELS = ["reason", "claim", "question", "history", "slop", "good",
    "because", "supports", "attacks", "contradicts", "cites", "relates", "checkedBy",
    "resumes", "coref", "parts", "tfa/t", "tfa/c", "tfa/f",
    "fn/definition", "fn/example", "fn/transition", "fn/claim", "fn/evidence", "fn/aside", "fn/hedge"];
  const LABEL = /^[^/ \t\n\r\f\v]+(?:\/[^/ \t\n\r\f\v]+)*$/;   // lit's facts.LABEL, whitespace spelt out alike
  /** A label and every scope above it: fn/claim/strong gives fn, fn/claim, fn/claim/strong. */
  const scopes = (l) => l.split("/").map((_, i, a) => a.slice(0, i + 1).join("/"));
  /** Whether a label lies at or under a scope. */
  const under = (l, p) => l === p || l.startsWith(p + "/");
  const store = (k, d) => (set) => {
    try {
      if (set !== undefined) localStorage.setItem(k, JSON.stringify(set));
      return JSON.parse(localStorage.getItem(k) || "null") ?? d;
    } catch { return set ?? d; }
  };
  const tally = store("fpl-annot:used", {});        // label -> times saved in this browser, site-wide
  const quick = store("fpl-annot:quick", []);       // labels confirmed as quick chips
  const declined = store("fpl-annot:declined", []); // labels whose offer was turned down
  const LAYERS = ["span", "fact", "thread", "argument", "tfa", "coref", "relation"];
  const RELATIONS = new Set(["because", "supports", "attacks", "contradicts", "supersedes", "checkedBy", "cites", "relates", "resumes"]);
  const AROUND = 32;
  // not the page's text: a card folded in under its block (a narrow
  // screen) shows its quote again, and would make every span dubbel
  const SKIP = "script, style, button, .fpl-annot-ui, .fpl-card";
  const QUOTE = { "‘": "'", "’": "'", "“": '"', "”": '"' };
  const GAP = 12;
  const HEAD = 19;   // a card's top to the middle of its first row: its border, padding and half the row
  const LONG = 56;   // px: an address taller than this (a block, one rect) is long, as a span over three lines is
  const CARD = 360;  // px: the widest a card in the margin gets
  const NARROW = 220;   // px: the narrowest; below it the cards fold in under their blocks (a card of one word a line, feedback 17)
  const RAIL = 12;   // px: from the text column's edge to the margin (the bar's left edge); a card stands 28px further in
  const RIGHT = 24;  // px: from the margin's right edge to the window's

  const snap = window.FPL_SNAPSHOT;
  const root = snap ? "" : new URL("../", document.currentScript.src).href;
  const here = location.href.split(/[?#]/)[0];
  const meta = (name) =>
    document.querySelector(`meta[name="${name}"]`)?.content ?? "";
  const commit = snap?.commit ?? meta("fpl-commit");
  if (!snap && (!here.startsWith(root) || !here.endsWith(".html") || !commit)) return;
  const page = snap ? snap.item.replace(/\.md$/, ".html") : decodeURIComponent(here.slice(root.length));
  const item = page.replace(/\.html$/, ".md");
  const stem = page.slice(page.lastIndexOf("/") + 1, -".html".length);
  const key = "fpl-annot:" + item;
  const body = document.querySelector("main") || document.body;
  const column = document.getElementById("quarto-margin-sidebar");

  let sidecar = [];

  /*
   * The log (feedback 7): what the reader did and what the margin
   * refused, with the reason it gave, as window.fplAnnotLog, an array of
   * the last LOGMAX entries, oldest first:
   *
   *   { t,        the time in ms
   *     action,   a Dutch verb: verbind, rek, bewaar, vouw, zoek, stand…
   *     target,   the row, address, label or stand it was about, or null
   *     ok,       false for a refusal
   *     reason }  why it was refused, as its toast said it; else null
   *
   * Every refusal goes through refuse(), which logs it and shows its
   * toast; an act done goes through did() or log(). A wheel turned is
   * one act: an entry of vouw replaces the one before it when both say
   * the same ok within a second and a half. The
   * log lives in this page only: nothing is stored or sent, and
   * Exporteer logboek in the menu downloads it as <stem>.log.json.
   */
  const LOGMAX = 200;
  const LIVE = new Set(["vouw"]);
  const journal = [];
  window.fplAnnotLog = journal;
  const unanchored = new Set();   // rows whose quote was not found, logged once
  function log(action, target = null, ok = true, reason = null) {
    const t = Date.now(), last = journal.at(-1);
    if (LIVE.has(action) && last?.action === action && last.ok === ok
      && t - last.t < 1500) journal.pop();
    journal.push({ t, action, target, ok, reason });
    if (journal.length > LOGMAX) journal.splice(0, journal.length - LOGMAX);
  }
  /** A refusal: logged with its reason, which a toast shows. */
  function refuse(action, target, reason) {
    log(action, target, false, reason);
    toast(reason);
  }
  /** An act done: logged, and a toast says so when there is text. */
  function did(action, target, text) {
    log(action, target);
    if (text) toast(text);
  }
  const LINKS = "Verbinden doe je in de stand Kantlijn (a)";
  const PARTS = "Delen schrijf je in de stand Kantlijn (a)";
  const NEXT = "Alt-selecteer het volgende · Esc stopt";

  const MODES = ["lezen", "spans", "kantlijn"];
  const NONE = "zonder label";
  const mode = (set) => {
    try {
      if (set) localStorage.setItem("fpl-annot:mode", set);
      const m = localStorage.getItem("fpl-annot:mode");
      return MODES.includes(m) ? m : "lezen";
    } catch { return set ?? "lezen"; }
  };
  const hidden = (set) => {
    try {
      if (set) localStorage.setItem("fpl-annot:hide", JSON.stringify([...set]));
      return new Set(JSON.parse(localStorage.getItem("fpl-annot:hide") || "[]"));
    } catch { return set ?? new Set(); }
  };

  const offLayers = (set) => {
    try {
      if (set) localStorage.setItem("fpl-annot:layers", JSON.stringify([...set]));
      return new Set(JSON.parse(localStorage.getItem("fpl-annot:layers") || "[]"));
    } catch { return set ?? new Set(); }
  };

  /** This browser's rows for the page; [] when none or unreadable. */
  const local = () => {
    try { return JSON.parse(localStorage.getItem(key) || "[]"); }
    catch { return []; }
  };
  const keep = (rows) => localStorage.setItem(key, JSON.stringify(rows));
  const by = (set) => {
    try { if (set != null) localStorage.setItem("fpl-annot:by", set); return localStorage.getItem("fpl-annot:by") || ""; }
    catch { return set ?? ""; }
  };

  /** A markdown text as lit's plain() shows it (facts.py MARKUP). */
  const plain = (s) => s
    .replace(/`([A-Za-z_][\w.]*)'/g, "$1").replace(/`/g, "")
    .replace(/’/g, "'").replace(/\[([^\]\n]*)\]\([^)\s]*\)/g, "$1")
    .replace(/^#+[ \t]+/gm, "").replace(/[\s|]+/g, " ");

  /**
   * The shown text of the page body: flat, and for each of its characters
   * the [node, offset] it came from.
   */
  function shown() {
    const walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => n.parentElement.closest(SKIP)
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    let flat = "", space = true;
    const from = [];
    for (let n; (n = walk.nextNode());) {
      for (let i = 0; i < n.data.length; i++) {
        let c = n.data[i];
        if (c === "`") continue;
        if (/[\s|]/.test(c)) {
          if (space) continue;
          c = " ";
        }
        space = c === " ";
        flat += QUOTE[c] ?? c;
        from.push([n, i]);
      }
    }
    return { flat, from };
  }

  /** Where a row's text is shown: [start, end), or "dubbel" or "stale". */
  function find(ix, row) {
    const want = plain(row.text);
    let hits = [];
    for (let i = ix.flat.indexOf(want); i >= 0; i = ix.flat.indexOf(want, i + 1))
      hits.push(i);
    if (hits.length > 1) {
      const pre = plain(row.prefix ?? ""), suf = plain(row.suffix ?? "");
      hits = hits.filter((i) => ix.flat.endsWith(pre, i)
        && ix.flat.startsWith(suf, i + want.length));
    }
    if (hits.length === 1) return [hits[0], hits[0] + want.length];
    return hits.length ? "dubbel" : "stale";
  }

  /** Wrap shown characters [s, e) in marks, one per text node they cross. */
  function wrap(ix, s, e, row) {
    const cuts = [];
    for (let i = s; i < e; i++) {
      const [n, o] = ix.from[i], last = cuts[cuts.length - 1];
      if (last && last[0] === n) last[2] = o + 1;
      else cuts.push([n, o, o + 1]);
    }
    for (const [n, a, b] of cuts) {
      const r = document.createRange(), m = document.createElement("mark");
      r.setStart(n, a);
      r.setEnd(n, b);
      m.className = `fact fact-${row.mine ? "mine" : "vers"}`;
      m.dataset.id = row.id;
      r.surroundContents(m);
    }
  }

  const el = (tag, props = {}, ...kids) => {
    const e = Object.assign(document.createElement(tag), props);
    e.append(...kids.filter((k) => k != null && k !== false));
    return e;
  };
  const button = (text, onclick, className = "") =>
    el("button", { type: "button", onclick, className }, text);
  const marksOf = (id) => body.querySelectorAll(`mark.fact[data-id="${CSS.escape(id)}"]`);
  /** What a row is drawn at: its marks, or the addressed element it is about. */
  /** The shown parts row a span row is a piece of, or undefined. */
  const partsOf = (id) => all.find((r) => r.labels?.[0] === "parts" && shows(r) && r.targets?.includes(id));
  const bundleOf = (id) => all.find((r) => r.id === id && r.labels?.[0] === "parts");
  /** The outermost shown whole a row is a piece of, through bundles in bundles, or undefined. */
  const wholeOf = (id) => {
    let w;
    const seen = new Set([id]);
    for (let p = partsOf(id); p && !seen.has(p.id); p = partsOf(p.id)) { w = p; seen.add(p.id); }
    return w;
  };
  /** A parts row and every id inside it, bundles in it and their pieces, in order (lit refuses a ring; this stops at one). */
  const treeOf = (pr, seen = new Set([pr.id])) => [pr.id, ...(pr.targets ?? []).flatMap((t) => {
    const q = bundleOf(t);
    return !q ? [t] : seen.has(t) ? [] : (seen.add(t), treeOf(q, seen));
  })];
  /** The span rows a parts row is made of, through the bundles in it. */
  const leavesOf = (pr) => treeOf(pr).filter((t) => !bundleOf(t));
  /** A whole and everything in it, from any of its ids; else just the id. */
  const groupOf = (id) => {
    const p = bundleOf(id), w = wholeOf(id) ?? p;
    return w ? treeOf(w) : [id];
  };
  function anchorsOf(id) {
    const pr = bundleOf(id);
    if (pr) return leavesOf(pr).flatMap((t) => [...marksOf(t)]);   // a discontinuous span: its pieces' marks
    const ms = marksOf(id);
    if (ms.length) return [...ms];
    const row = all.find((r) => r.id === id);
    const at = row && typeof row.text !== "string" && row.targets?.[0];
    const e = at && !all.some((r) => r.id === at) && document.getElementById(at);
    return e && body.contains(e) ? [e] : [];
  }
  // a tfa row is drawn by the lens on its clause, not as a card
  const addressed = (r) => typeof r.text !== "string" && layerOf(r) !== "tfa" && anchorsOf(r.id).length > 0;
  /**
   * A fact whose row is gone (an unbundled parts row, a deleted span):
   * no text, its first target shaped as a row id (lit's generated ids
   * carry a colon, a ledger is L-..., a file has a slash, an address is
   * b1s2c3) that names no row and no place on the page. It gets a lost
   * card, as a span not found does, so it can be moved or deleted
   * rather than sit unseen until lit refuses it. Worked out once per
   * set of rows.
   */
  const ROWLIKE = /^(?!L-[A-Z0-9]+$)(?![^/\s]*b[1-9]\d*(?:s[1-9]\d*(?:c[1-9]\d*)?)?$)[^:/\s]+$/;
  let orphans = { of: null, ids: new Set() };
  const orphan = (r) => {
    if (orphans.of !== all) {
      const ids = new Set(all.map((x) => x.id));
      orphans = { of: all, ids: new Set(all.filter((x) => typeof x.text !== "string" && !RELATIONS.has(x.labels?.[0] ?? "")
        && !SETKINDS.has(x.labels?.[0] ?? "") && layerOf(x) !== "tfa" && typeof x.targets?.[0] === "string"
        && ROWLIKE.test(x.targets[0]) && !ids.has(x.targets[0]) && !place(x.targets[0])).map((x) => x.id)) };
    }
    return orphans.ids.has(r.id);
  };

  /** Every row, the sidecar's first, each marked mine when it is local. */
  const rows = () => [...sidecar, ...local().map((r) => ({ ...r, mine: true }))];
  let all = [], state = {};

  /** A row's layer, read as lit's facts.layer reads it: never written down. */
  function layerOf(r) {
    const k = r.labels?.[0] ?? "";
    if (typeof r.text === "string" || k === "parts") return "span";
    if (k === "supports" || k === "attacks") return "argument";
    if (k === "resumes" || k.startsWith("tfa/")) return "tfa";
    if (k === "coref") return "coref";
    if (RELATIONS.has(k)) return "relation";
    const up = all.find((x) => x.id === r.targets?.[0]);
    return up && typeof up.text !== "string" && up.labels?.[0] !== "parts" ? "thread" : "fact";
  }
  const shows = (r) => !offLayers().has(layerOf(r));

  /** The labels a span is filtered by: its own and those of the facts about it, in the layers shown. */
  function labelsOf(row) {
    const got = new Set(row.labels ?? []);
    const walk = (id) => { for (const r of all.filter((x) => typeof x.text !== "string" && x.labels?.[0] !== "parts" && x.targets?.[0] === id && shows(x))) {
      for (const l of r.labels ?? []) got.add(l); walk(r.id); } };
    for (const id of bundleOf(row.id) ? treeOf(bundleOf(row.id)).filter(bundleOf) : [row.id]) walk(id);   // a bundle in it is the whole's too
    return got.size ? got : new Set([NONE]);
  }
  const passes = (row) => { const off = [...hidden()]; return [...labelsOf(row)].some((l) => !off.some((h) => under(l, h))); };

  /** Remove the marks, draw every row the stand and the filter allow, and lay the margin out. */
  function draw() {
    for (const m of body.querySelectorAll("mark.fact")) m.replaceWith(...m.childNodes);
    body.normalize();
    all = rows();
    if (asked) try { found = new Set(QUERY.query(all, asked)); } catch { found = null; }   // an edit changes what the query finds
    state = {};
    for (const row of all) {
      if (typeof row.text !== "string" || !row.text.trim()) continue;
      const ix = shown(), at = find(ix, row);
      state[row.id] = typeof at === "string" ? at : "vers";
      if (typeof at === "string" && !unanchored.has(row.id)) {
        unanchored.add(row.id);
        log("anker", row.id, false, at === "dubbel"
          ? "staat meer dan eens in de tekst" : "staat niet meer in de tekst");
      }
      const p = wholeOf(row.id);   // a piece shows when its whole does
      if (typeof at !== "string" && mode() !== "lezen" && (p ? passes(p) : passes(row))) wrap(ix, at[0], at[1], row);
    }
    for (const row of all) if (addressed(row)) state[row.id] = "vers";
    for (const p of all.filter((r) => r.labels?.[0] === "parts"))   // a whole is found only when every piece is
      state[p.id] = leavesOf(p).every((t) => state[t] === "vers") ? "vers" : "stale";
    layout();
  }

  /* ---- the bar: the stands, the search, Graph and a menu, in one place ---- */

  /** The bar's icons, one stroke on a 16-unit grid (the canvas boards' set). */
  const ICONS = {
    graph: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="3.5" r="1.8"/><circle cx="3.5" cy="12.5" r="1.8"/><circle cx="12.5" cy="12.5" r="1.8"/><path d="M7.2 5.1 4.4 10.9M8.8 5.1l2.8 5.8M5.3 12.5h5.4"/></g>',
    more: '<g fill="currentColor"><circle cx="3.5" cy="8" r="1.3"/><circle cx="8" cy="8" r="1.3"/><circle cx="12.5" cy="8" r="1.3"/></g>',
    search: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14"/></g>',
    filter: '<path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" d="M2.5 3h11L9.5 8v4.5l-3 1.5V8z"/>',
    chevron: '<path fill="none" stroke="currentColor" stroke-width="1.6" d="m4 6 4 4 4-4"/>',
    name: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5a5 5 0 0 1 10 0"/></g>',
    import: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M8 2v8M5 7l3 3 3-3M3 11v2.5h10V11"/>',
    export: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M8 10V2M5 5l3-3 3 3M3 11v2.5h10V11"/>',
    log: '<g fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3.5" y="2" width="9" height="12" rx="1"/><path d="M6 5.5h4M6 8h4M6 10.5h2.5"/></g>',
    fold: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M2 8h12M8 1.5v4M6 3.5l2 2 2-2M8 14.5v-4M6 12.5l2-2 2 2"/>',
    context: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M3 4h10M3 8h10M3 12h6"/>',
    keys: '<g fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="4" width="13" height="8" rx="1.5"/><path d="M4 7h1M7 7h1M10 7h1M5 9.5h6"/></g>',
    wipe: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 9h5.6l.7-9"/>',
    select: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M6 2.5h4M6 13.5h4M8 2.5v11"/>',
    knob: '<circle cx="8" cy="8" r="3.5" style="fill: var(--fpl-mine)"/>',
    clear: '<path fill="none" stroke="currentColor" stroke-width="1.8"'
      + ' d="m4 4 8 8M12 4l-8 8"/>',
    shift: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="m5 6 3-3 3 3M5 10l3 3 3-3"/>',
    reply: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M6.5 4 2.5 8l4 4M2.5 8H10a3.5 3.5 0 0 1 3.5 3.5V13"/>',
    link: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M6.5 9.5l3-3M7 4.5l1-1a2.8 2.8 0 0 1 4 4l-1 1M9 11.5l-1 1a2.8 2.8 0 0 1-4-4l1-1"/>',
    supports: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5.5"/><path d="M8 5.5v5M5.5 8h5"/></g>',
    attacks: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5.5"/><path d="M5.5 8h5"/></g>',
    same: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6" cy="8" r="4"/><circle cx="10" cy="8" r="4"/></g>',
    cites: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M3 12V9a3.5 3.5 0 0 1 3.5-3.5M9 12V9a3.5 3.5 0 0 1 3.5-3.5"/>',
  };
  const ico = (name) => {
    const s = el("span", { className: "fpl-ico" });
    s.ariaHidden = "true";
    s.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16">${ICONS[name]}</svg>`;
    return s;
  };
  /** A button of the bar: an icon, and a name that a narrow bar keeps for the screen reader only. */
  const tool = (name, text, onclick) => {
    const b = button("", onclick, "fpl-tool");
    b.append(ico(name), el("span", { className: "fpl-name" }, text));
    return b;
  };

  const STANDS = { lezen: "Lezen", spans: "Spans", kantlijn: "Kantlijn" };
  const stand = (m) => {
    if (m !== "kantlijn") disarm();
    mode(m); draw(); log("stand", m);
  };
  const tabs = el("div", { className: "fpl-tabs", role: "tablist", ariaLabel: "Stand" },
    ...MODES.map((m) => Object.assign(button(STANDS[m], () => stand(m), "fpl-tab"), { role: "tab" })));
  const picker = el("select", { className: "fpl-stand", ariaLabel: "Stand", onchange: () => stand(picker.value) },
    ...MODES.map((m) => el("option", { value: m }, STANDS[m])));
  const graphBtn = tool("graph", "Graph", () => { shut(); graph(null); });
  const moreBtn = tool("more", "Meer", () => flip(menu, moreBtn, fillMenu));
  const filterBtn = tool("filter", "Filter: labels en lagen", () => flip(panel, filterBtn, fillChips));
  moreBtn.classList.add("fpl-icon", "fpl-more"); filterBtn.classList.add("fpl-icon", "fpl-filter-btn");
  for (const b of [moreBtn, filterBtn]) { b.ariaHasPopup = "true"; b.ariaExpanded = "false"; }
  const field = el("input", { className: "fpl-query", placeholder: "Zoek of filter, bv. label:claim", ariaLabel: "Zoek of filter",
    autocomplete: "off", spellcheck: false });
  // a query asked (board H): the field is lit, its key gives way to an x
  const clear = el("button", { type: "button", className: "fpl-x",
    ariaLabel: "Wis het filter", title: "Wis het filter",
    onclick: () => { field.value = ""; ask(); field.focus(); } }, ico("clear"));
  const search = el("div", { className: "fpl-search" },
    ico("search"), field, el("kbd", { className: "fpl-key" }, "/"), clear);
  const count = el("p", { className: "fpl-count" });
  const row = el("div", { className: "fpl-row" }, tabs, el("span", { className: "fpl-picker" }, picker, ico("chevron")), graphBtn, moreBtn);
  const bar = el("div", { className: "fpl-annot-ui fpl-topbar", role: "region", ariaLabel: "Kantlijn" }, row, search, count);
  const menu = el("div", { className: "fpl-annot-ui fpl-menu", hidden: true });
  const chips = el("div", { className: "fpl-filters" });
  const panel = el("div", { className: "fpl-annot-ui fpl-menu fpl-panel", hidden: true, role: "group", ariaLabel: "Filter" }, chips);
  const file = el("input", { type: "file", accept: ".json", hidden: true });
  file.onchange = () => { file.files[0]?.text().then(merge); file.value = ""; };
  bar.append(file);
  let bad = "";   // why the query in the field does not parse

  /** Run the query in the field; a query in Lezen shows the spans, since Lezen draws none. */
  const ask = () => {
    const was = bands.length > 0 && folded(runsNear(context));   // to the spans
    asked = field.value.replace(/^ +| +$/g, "");   // only U+0020 apart, as the parser
    try { found = asked ? new Set(QUERY.query(all, asked)) : null; bad = ""; }
    catch (e) { found = null; bad = e.message; }
    if (bad) refuse("zoek", asked, `Deze zoekvraag lees ik niet: ${bad}`);
    else log("zoek", asked || null);
    field.classList.toggle("is-bad", !!bad);
    search.classList.toggle("is-on", !!asked);
    field.title = bad;
    if (asked && mode() === "lezen") stand("spans"); else layout();
    // folded to the spans: refold to the new ones, as a new Context does
    if (was) setBands(runsNear(context) ?? []);
  };
  /** The full bar has no filter button: a click into the empty field opens the panel, typing a query closes it. */
  const filters = () => { if (bar.classList.contains("is-full") && !field.value && panel.hidden) flip(panel, filterBtn, fillChips, false); };
  field.onclick = filters;
  field.oninput = () => { if (field.value && bar.classList.contains("is-full") && !panel.hidden) shut(); };
  field.onkeydown = (e) => {
    e.stopPropagation();   // j, k, a, z and Esc belong to the page, not while typing a query
    if (e.key === "Enter") ask();
    if (e.key === "Escape") { if (field.value) { field.value = ""; ask(); } else { shut(); field.blur(); } }
  };

  /**
   * Where the bar goes, measured each layout. Where Quarto shows its top
   * bar (a narrow window) the bar docks in it, left of the site's search,
   * folded to a stand picker and three icons, and the search field and
   * the counts move into the filter panel. Where the margin has 320px
   * (from about 1380px wide), the bar is fixed above it, as wide as the
   * margin. Between the two it is the folded bar, fixed at the top right.
   */
  const nav = document.querySelector(".quarto-secondary-nav .container-fluid");
  function dock() {
    const top = !!nav && nav.offsetHeight > 0, room = wide() ? reserve() : 0;
    const full = !top && room >= 320;
    bar.classList.toggle("is-full", full);
    bar.classList.toggle("is-docked", top);
    bar.style.left = full ? `${rail()}px` : "";
    bar.style.width = full ? `${room}px` : "";
    if (top) { if (bar.parentElement !== nav) nav.insertBefore(bar, nav.querySelector(".quarto-search-button")); }
    else if (bar.parentElement !== document.body) document.body.append(bar);
    if (bar.dataset.form !== String(full)) {   // the folded bar keeps the search in its panel
      bar.dataset.form = full;
      if (full) { filterBtn.remove(); bar.insertBefore(search, file); bar.insertBefore(count, file); }
      else { row.insertBefore(filterBtn, graphBtn); panel.prepend(search, count); }
    }
    if (!menu.hidden) hang(menu, moreBtn);
    if (!panel.hidden) hang(panel, full ? search : filterBtn);
  }

  /** A count with its noun: "1 span", "3 spans". */
  const some = (n, one, more) => `${n} ${n === 1 ? one : more}`;
  /** The bar's state: which stand, the counts, the filter's mark; the open panel's chips. */
  function drawBar() {
    const cur = mode();
    for (const [i, t] of [...tabs.children].entries()) { t.ariaSelected = String(MODES[i] === cur); t.classList.toggle("is-on", MODES[i] === cur); }
    picker.value = cur;
    // "/" is Quarto's site search outside Kantlijn (feedback 22)
    search.querySelector(".fpl-key").textContent =
      cur === "kantlijn" ? "/" : "z";
    const spans = all.filter((r) => typeof r.text === "string" || addressed(r));
    const lost = spans.filter((r) => state[r.id] !== "vers").length + all.filter(orphan).length, mine = local().length;
    // a reply or a fact on a span is no relation: only rows with two ends
    const rels = all.filter((r) => typeof r.text !== "string" && relates(r));
    const head = all.length
      ? `${some(spans.length, "span", "spans")} · `
        + some(rels.length, "relatie", "relaties")
      : "Nog geen spans op deze pagina";
    const line = el("p", {}, head,
      lost ? el("span", { className: "fpl-lost" }, ` · ${lost} kwijt`) : null,
      mine ? el("span", { className: "fpl-mine" }, ` · ${mine} van jou`) : null,
      bad ? el("span", { className: "fpl-bad" }, ` · ${bad}`) : found ? ` · ${found.size} gevonden` : null,
      hidden().size + offLayers().size
        ? el("span", { className: "fpl-mine" }, " · filter aan") : null);
    count.title = line.textContent;
    // folded to the spans (board H): how many spans the fold keeps, of all
    if (bands.length && folded(runsNear(context))) {
      const kept = new Set([...body.querySelectorAll("mark.fact")]
        .filter((m) => !m.matches(".fpl-faded")).map((m) => m.dataset.id));
      const k = spans.filter((r) => kept.has(r.id)).length;
      count.replaceChildren(
        `${k} van ${some(spans.length, "span", "spans")} · `,
        el("b", {}, "ingevouwen tot de spans"), `, context ${context}`);
    } else count.replaceChildren(...line.childNodes);
    filterBtn.classList.toggle("is-on", hidden().size + offLayers().size > 0);
    if (!panel.hidden) fillChips();
    dock();
  }

  /** Open one popover under its button, or close it if it was open; one at a time. focus false leaves the focus where it is. */
  function flip(pop, btn, fill, focus = true) {
    const was = !pop.hidden;
    shut();
    if (was) return;
    fill();
    pop.hidden = false;
    btn.ariaExpanded = "true";
    btn.classList.add("is-open");
    hang(pop, pop === panel && bar.classList.contains("is-full") ? search : btn);
    if (focus) pop.querySelector("button:not(:disabled), [tabindex='0']")?.focus({ preventScroll: true });
  }
  /** A popover hangs under what opened it, right edges flush, inside the window. */
  function hang(pop, at) {
    const r = at.getBoundingClientRect();
    pop.style.top = `${Math.max(8, r.bottom + 6)}px`;   // a docked bar may have scrolled away with Quarto's header
    pop.style.right = `${Math.max(8, innerWidth - r.right)}px`;
    pop.style.width = at === search ? `${r.width}px` : "";
  }
  /** Close the menu, the filter panel and a card's menu. */
  function shut() {
    if (link?.open) {   // the chooser closed unanswered
      const from = link.from;
      link = null; drawAim(); hot(null);
      did("breek af", from, "Niet verbonden");
    }
    for (const [pop, btn] of [[menu, moreBtn], [panel, filterBtn]]) { pop.hidden = true; btn.ariaExpanded = "false"; btn.classList.remove("is-open"); }
    cardMenu.hidden = true;
    if (menuOf) for (const b of margin.querySelectorAll(".fpl-card-more")) b.ariaExpanded = "false";
    menuOf = null;
  }
  document.addEventListener("pointerdown", (ev) => {
    const t = ev.target;
    if (link?.open && t.closest?.(".fpl-knob")) { link = null; drawAim(); }   // a new drag replaces the question, quietly
    if (!t.closest?.(".fpl-menu, .fpl-card-more") && !moreBtn.contains(t) && !filterBtn.contains(t) && t !== field) shut();
  }, true);
  /** A click outside every card, menu and panel lets the open card close; not while a new fact is written. */
  document.addEventListener("click", (ev) => {
    if (!openId || ev.target.closest?.(".fpl-card, .fpl-menu, .fpl-pop, .fpl-graph, .fpl-toast, .fpl-topbar")) return;
    openId = null;
    if (!editing) layout();
  });

  /** The filter panel: the labels to show, as a tree of chips, and the layers. */
  function fillChips() {
    const was = panel.contains(document.activeElement) ? document.activeElement.dataset.chip : null;
    const off = hidden();
    const bySegment = (a, b) => {   // children right after their scope: slop, slop/beeld, slop-ish
      const x = a.split("/"), y = b.split("/");
      for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i].localeCompare(y[i]);
      return x.length - y.length;
    };
    const labels = [...new Set(all.filter((r) => typeof r.text === "string" || addressed(r))   // spans and rows on addresses
      .flatMap((r) => [...labelsOf(r)].flatMap(scopes)))]
      .sort((a, b) => a === NONE ? 1 : b === NONE ? -1 : bySegment(a, b));
    const toggle = (c, act) => {
      c.tabIndex = 0;
      c.onclick = act;
      c.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); act(); } };
      return c;
    };
    const offL = offLayers(), present = new Set(all.map(layerOf));
    chips.replaceChildren(
      el("p", { className: "fpl-panel-head" }, "Labels", off.size ? button("alles aan", () => { hidden(new Set()); draw(); }, "fpl-link") : null),
      labels.length ? el("div", { className: "fpl-chips fpl-filter" }, ...labels.map((l) => {
        const struck = [...off].some((h) => under(l, h)), c = chip(l, struck ? "is-off" : "is-on");
        c.dataset.chip = "l:" + l;
        c.style.marginLeft = `${(l.split("/").length - 1) * 0.6}rem`;
        return toggle(c, () => {
          const o = hidden(), above = [...o].find((h) => h !== l && under(l, h));
          // struck by its scope: the scope decides
          if (above) { refuse("filter", l, `Zet eerst ${above} aan`); return; }
          o.has(l) ? o.delete(l) : o.add(l); hidden(o); draw();
          log("filter", l);
        });
      })) : el("p", { className: "fpl-panel-none" }, "Nog geen labels op deze pagina"),
      el("p", { className: "fpl-panel-head" }, "Lagen"),
      el("div", { className: "fpl-chips fpl-filter fpl-layers" }, ...LAYERS.filter((l) => present.has(l) && l !== "span").map((l) => {
        const c = chip(l, offL.has(l) ? "is-off" : "is-on");
        c.dataset.chip = "y:" + l;
        return toggle(c, () => { const o = offLayers(); o.has(l) ? o.delete(l) : o.add(l); offLayers(o); draw(); });
      })));
    if (was) chips.querySelector(`[data-chip="${CSS.escape(was)}"]`)?.focus();
  }

  /** The menu under ⋯; ask is "export" after an export (the lit command shows), "wipe" while wiping asks. */
  function fillMenu(ask) {
    const mine = local().length, rows = mine === 1 ? "1 rij" : `${mine} rijen`;
    const entry = (name, text, onclick, after, cls = "") => {
      const b = button("", onclick, "fpl-item " + cls);
      b.append(ico(name), text, ...after ? [after] : []);
      return b;
    };
    const why = (text) => el("small", {}, text);
    const none = (b) => { b.disabled = true; return b; };
    const name = el("input", { value: by(), placeholder: "jij", onchange: (ev) => by(ev.target.value.trim()) });
    const ctx = el("span", { className: "fpl-ctx", role: "group", ariaLabel: "Context rond elke span, in blokken" },
      ...[0, 1, 2, 3].map((n) => Object.assign(button(String(n), () => { setContext(n); fillMenu(); }), { ariaPressed: String(n === context) })));
    const exp = entry("export", "Exporteer rijen", () => { exportRows(); fillMenu("export"); }, why(mine ? `${mine} van jou` : "geen van jou"));
    const wipe = entry("wipe", "Wis mijn rijen op deze pagina…", () => fillMenu("wipe"), mine ? null : why("geen"), "fpl-danger");
    const acts = journal.length === 1 ? "1 actie" : `${journal.length} acties`;
    const record = entry("log", "Exporteer logboek",
      () => { exportLog(); fillMenu(); }, why(acts));
    menu.classList.remove("fpl-keysheet");
    menu.replaceChildren(...[
      el("label", { className: "fpl-item" }, ico("name"), "Naam", name),
      el("hr"),
      entry("import", "Importeer rijen…", () => { shut(); file.click(); }),
      mine ? exp : none(exp),
      ask === "export" ? el("p", { className: "fpl-cmd" }, "Dan, vanuit 01-bootstrap/: ",
        el("code", {}, `lit facts --import ${stem}.annot.json --item ${item}=${item}@${commit}`)) : null,
      journal.length ? record : none(record),
      el("hr"),
      entry("fold", "Vouw tot de spans", () => { shut(); squeeze(); }),
      el("div", { className: "fpl-item" }, ico("context"), "Context", ctx),
      el("hr"),
      entry("keys", "Sneltoetsen", () => keysheet(), el("kbd", {}, "?")),
      ask === "wipe"
        ? el("div", { className: "fpl-item fpl-confirm" }, `${rows} van jou wissen?`,
          button("Wis", () => {
            localStorage.removeItem(key); shut(); draw();
            did("wis", item, `${rows} gewist`);
          }, "fpl-go fpl-danger"),
          button("Nee", () => fillMenu()))
        : mine ? wipe : none(wipe)].filter(Boolean));
  }

  /** The keys, in the menu's place: "?" or the menu's Sneltoetsen. */
  function keysheet() {
    if (menu.hidden) flip(menu, moreBtn, () => {});
    menu.classList.add("fpl-keysheet");
    const keys = [["a", "Volgende stand"],
      ["/  z", "Zoek of filter; / alleen in Kantlijn"],
      ["j  k", "Volgende, vorige zin"],
      ["Enter", "Een feit op de zin onder de cursor"], ["⌘↩", "Bewaar in de editor"],
      ["Shift + scroll",
        "Vouwt rond de muis in, terug opent; met een filter tot de spans"],
      ["Esc", "Sluit of breekt af; anders opent de laatste band"], ["Alt + selectie", "Een deel van een span; Enter bundelt"],
      ["Alt-klik", "De tfa-waarde van een bijzin"], ["Alt-Shift-klik", "Deze bijzin neemt een eerdere op"],
      ["l", "Verbind de kaart onder de muis of de focus; Tab kiest het andere eind, Enter het soort"],
      ["Shift + ← →", "Rek je span een woord, met de focus op zijn bolletje; Enter bewaart"], ["?", "Deze lijst"]];
    menu.replaceChildren(el("p", { className: "fpl-panel-head" }, "Sneltoetsen"),
      el("dl", {}, ...keys.flatMap(([k, what]) => [el("dt", {}, ...k.split(/ {2}/).map((x) => el("kbd", {}, x))), el("dd", {}, what)])));
    menu.tabIndex = -1;
    menu.focus({ preventScroll: true });
  }

  /**
   * / or z: the search field, in the panel when the bar is folded; with
   * no query yet, the filter panel opens under it.
   */
  function seek() {
    if (!bar.classList.contains("is-full") && panel.hidden) flip(panel, filterBtn, fillChips);
    field.focus();
    field.select();
    filters();
  }

  /** The margin when Kantlijn has no card yet: how to annotate, connect and fold, in three lines. */
  const hint = () => el("ul", { className: "fpl-hint" },
    ...[["select", "Selecteer tekst", " en schrijf een notitie."],
      ["knob", "Sleep het bolletje", " achter een span naar een andere span om ze te verbinden."],
      ["shift", "", ["Houd ", el("kbd", {}, "Shift"), " en scroll boven de tekst om hem in te vouwen. Terug scrollen opent."]]]
      .map(([i, b, rest]) => el("li", {}, ico(i), el("span", {}, b ? el("b", {}, b) : null, ...[rest].flat()))));

  /* ---- what a card shows: a head, its relations, a thread (board F) ---- */

  const chip = (label, cls) => {
    const [head, sub] = label.split(/\/(.*)/);
    return el("span", { className: "fpl-chip " + cls }, head, sub ? el("small", {}, "/" + sub) : null);
  };
  // a parts row names its pieces, it says nothing about the first one
  const facts = (id) => all.filter((r) => typeof r.text !== "string" && r.labels?.[0] !== "parts" && r.targets?.[0] === id && shows(r));
  /** A row that ties its first target to others (supports, cites, coref): a line on the card, not a message. */
  const relates = (r) => (r.targets ?? []).length > 1;
  /** The first words of a text, cut at a word, with an ellipsis when cut. */
  const clip = (s, n = 40) => {
    const t = String(s ?? "").replace(/\s+/g, " ").trim();
    return t.length <= n ? t : `${t.slice(0, n).replace(/\s+\S*$/, "")}…`;
  };
  const VERB = { supports: "steunt", attacks: "valt aan", contradicts: "spreekt tegen", because: "omdat", cites: "citeert",
    checkedBy: "getoetst door", resumes: "neemt op", supersedes: "vervangt", coref: "zelfde als", relates: "verbindt" };
  /** A relation's verb: Dutch for the labels lit knows, else the label as written. */
  const verb = (r) => VERB[r.labels?.[0]] ?? ((r.labels ?? []).join(" ") || "verbindt");
  /** Who wrote a row, when the row says so; a row without a name has no author line, never a "?". */
  const author = (r) => (typeof r.by === "string" && r.by.trim()) || null;
  /** A row's time, from createdAt: the clock today, else the day; nothing for a row without a real time. */
  const stamp = (t) => {
    if (!Number.isFinite(t) || t < 1e11) return "";
    const d = new Date(t);
    return d.toDateString() === new Date().toDateString()
      ? d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleDateString("nl-NL", { day: "numeric", month: "short" });
  };

  /**
   * The page's decision ledger, <stem>.decisions.tsv beside the page
   * (columns id, topic, date, who, decision, reason), read once at load.
   * lit makes each of its rows a span L-<id> (facts.generate), so a
   * relation that ends at L-I4 ends at a decision: the card draws it as a
   * chip, its topic and the first words of the decision, and a click opens
   * the row, its reason, date and who, in the card.
   */
  let ledger = new Map();
  const readLedger = (tsv) => {
    const [head, ...rest] = String(tsv ?? "").split("\n").filter((l) => l.trim());
    const ks = head?.split("\t") ?? [];
    return new Map(rest.map((l) => { const v = l.split("\t"); return Object.fromEntries(ks.map((k, i) => [k, v[i] ?? ""])); })
      .filter((r) => r.id).map((r) => [r.id, r]));
  };
  const decision = (t) => { const m = /^L-(.+)$/.exec(t); return m ? { id: m[1], ...ledger.get(m[1]) } : null; };
  const told = new Set();   // "<card id> <decision id>": ledger rows opened in a card, kept across draws
  function decisionChip(d, owner) {
    const k = `${owner} ${d.id}`;
    const b = el("button", { type: "button", className: "fpl-decision", title: d.decision ? `Besluit ${d.id} uit de ledger` : `${d.id} staat niet in de ledger` },
      el("b", {}, d.topic || `besluit ${d.id}`), d.decision ? ` · ${clip(d.decision, 34)}` : " · niet in de ledger");
    b.ariaExpanded = String(told.has(k));
    b.onclick = (ev) => {
      ev.stopPropagation();
      if (!d.decision) {
        refuse("besluit", `L-${d.id}`,
          `Besluit ${d.id} staat niet in ${stem}.decisions.tsv`);
        return;
      }
      told.has(k) ? told.delete(k) : told.add(k);
      openId = owner;
      layout();
    };
    return b;
  }
  /** A ledger row opened in a card: the decision whole, why, and when and by whom. */
  const ledgerRow = (d) => el("div", { className: "fpl-ledger" },
    el("p", {}, d.decision), d.reason ? el("p", { className: "fpl-why" }, d.reason) : null,
    el("p", { className: "fpl-when" }, [`besluit ${d.id}`, d.date, d.who && d.who !== "unclear" ? d.who : null].filter(Boolean).join(" · ")));

  /** What a target that is not a row is called: a chunk by its name, a test, a refusal; a row id that names nothing, "". */
  const named = (t) => {
    let v = t;
    try { v = decodeURIComponent(t); } catch { /* a stray % */ }
    const m = /^(chunk|test|refusal):(.*)$/.exec(v);
    if (m) return { chunk: `«${m[2].replace(/:\d+$/, "")}»`, test: `test ${m[2].replace(/:\d+$/, "")}`, refusal: `weigering “${m[2]}”` }[m[1]];
    return ROWLIKE.test(t) ? "" : v;
  };
  /**
   * The other end of a relation, by its text: a decision as its chip, a
   * row or a place on the page by its first words (a click folds what lies
   * between, Toon beide), anything else by its name; never a bare id.
   */
  function endOf(t, owner) {
    const d = decision(t);
    if (d) return decisionChip(d, owner);
    const r = all.find((x) => x.id === t), e = place(t);
    const said = r ? (typeof r.text === "string" ? plain(r.text) : r.note || (r.labels ?? []).join(" ")) : e?.textContent;
    const name = said ? `“${clip(said, 32)}”` : named(t);
    if (!name) return el("span", { className: "fpl-lost", title: t }, "iets dat weg is");
    if (!e) return el("span", { className: "fpl-end", title: t }, name);
    return el("button", { type: "button", className: "fpl-end", title: "Toon beide", onclick: (ev) => { ev.stopPropagation(); both(owner, t); } }, name);
  }
  /**
   * A relation as a line: its verb, its other ends and, unless its note
   * is already on screen (noted, the row whose note its card or message
   * shows), that note after a colon. data-fact lets a pick end at the
   * relation itself (an undercut).
   */
  function relLine(r, owner, noted = null) {
    const ends = r.targets.slice(1)
      .flatMap((t, i) => [i ? ", " : "", endOf(t, owner)]);
    const note = r.note && r.id !== noted
      ? el("span", { className: "fpl-relnote" }, `: ${r.note}`) : null;
    const line = el("span", { className: "fpl-rel" },
      el("b", {}, verb(r)), " → ", ...ends, note);
    line.dataset.fact = r.id;
    return line;
  }
  /** The ledger rows opened under some relations, in a card. */
  const ledgerRows = (rels, owner) => rels.flatMap((r) => r.targets.slice(1).map(decision))
    .filter((d) => d?.decision && told.has(`${owner} ${d.id}`)).map(ledgerRow);

  /**
   * What hangs from an id: the relations it starts, and the messages
   * about it or about those relations (a note on "contradicts L-G2" is a
   * message of the span's thread, as on board F), oldest first: a reply
   * stands under what it answers, wherever that hangs.
   */
  function about(id) {
    const rels = [], msgs = [], seenIds = new Set([id]);
    for (const r of facts(id)) (relates(r) ? rels : msgs).push(r);
    for (const r of rels) for (const f of facts(r.id)) if (!seenIds.has(f.id)) { seenIds.add(f.id); (relates(f) ? rels : msgs).push(f); }
    msgs.sort((a, b) => (a.createdAt ?? 0) - (b.createdAt ?? 0));
    return { rels, msgs };
  }
  /** The messages in a thread, all the way down. */
  function replies(id, been = new Set([id])) {
    let n = 0;
    for (const m of about(id).msgs) if (!been.has(m.id)) { been.add(m.id); n += 1 + replies(m.id, been); }
    return n;
  }
  const unfolded = new Set();   // the ids whose long thread is shown whole, kept across draws
  const LONG_THREAD = 4;        // more messages than this fold to "n reacties"

  /**
   * One message of a thread: its labels, who and when when known, its
   * text, the relations it starts, an arrow (on hover or focus) that
   * answers this message in the card's one field, and, one step in, the
   * messages about it. Deeper replies stay at that step, so a long
   * exchange does not walk off the card. A message of ours opens in the
   * editor on a click.
   */
  function msgView(r, owner, been) {
    const li = el("li", { className: `fpl-msg fpl-fact${r.mine ? " mine" : ""}` });
    li.dataset.fact = r.id;
    const who = author(r), when = stamp(r.createdAt), own = relates(r) ? [] : r.labels ?? [];
    if (who || when || own.length)
      li.append(el("div", { className: "fpl-mhead" }, ...own.map((l) => chip(l, r.mine ? "is-mine" : "is-vers")),
        who ? el("b", {}, who) : null, when ? el("span", {}, when) : null));
    const { rels, msgs } = about(r.id);
    if (relates(r)) rels.unshift(r);
    if (r.note) li.append(el("p", { className: "fpl-text" }, r.note));
    if (rels.length) li.append(el("p", { className: "fpl-meta" },
      ...rels.flatMap((x, i) => [i ? " · " : "", relLine(x, owner, r.id)])),
    ...ledgerRows(rels, owner));
    const box = argBox(r.id);
    if (box) li.append(box);
    const to = el("button", { type: "button", className: "fpl-ib fpl-rep", ariaLabel: "Antwoord op dit bericht", title: "Antwoord op dit bericht" }, ico("reply"));
    to.onclick = (ev) => { ev.stopPropagation(); aim(li.closest(".fpl-card"), r); };
    li.append(to);
    const sub = msgs.filter((m) => !been.has(m.id));
    if (sub.length) {
      for (const m of sub) been.add(m.id);
      li.append(el("ol", { className: "fpl-msgs sub" }, ...sub.map((m) => msgView(m, owner, been))));
    }
    // a message of ours opens in the editor; a click in a reply under it
    // is that reply's (which opens its own, or nothing)
    if (r.mine) li.onclick = (ev) => {
      if (picking || ev.target.closest("button, a, details, input, label")
        || ev.target.closest(".fpl-msg") !== li) return;
      ev.stopPropagation();
      edit(r, null, li.getBoundingClientRect());
    };
    return li;
  }
  /** Point the card's one answer field at a message: its placeholder says whom it answers; Esc points it back at the card. */
  function aim(card, r) {
    const field = card?.querySelector(".fpl-answer input");
    if (!field) return;
    for (const m of card.querySelectorAll(".fpl-msg.is-aimed")) m.classList.remove("is-aimed");
    if (r) {
      field.dataset.to = r.id;
      field.placeholder = author(r) ? `Antwoord aan ${author(r)}…` : `Antwoord op “${clip(r.note || verb(r), 22)}”…`;
      card.querySelector(`.fpl-msg[data-fact="${CSS.escape(r.id)}"]`)?.classList.add("is-aimed");
    } else {
      field.dataset.to = card.dataset.id;
      field.placeholder = "Antwoord…";
    }
    field.focus({ preventScroll: true });
  }
  /** The card's one answer field: Enter saves a reply row to what it points at, the card stays open. */
  function answerField(id) {
    const field = el("input", { type: "text", placeholder: "Antwoord…", autocomplete: "off" });
    field.dataset.to = id;
    field.onkeydown = (e) => {
      e.stopPropagation();   // j, k, a, z, l and Esc belong to the page, not while typing
      if (e.key === "Escape") { if (field.dataset.to !== id) aim(field.closest(".fpl-card"), null); else field.blur(); return; }
      if (e.key !== "Enter" || e.isComposing) return;
      e.preventDefault();
      const note = field.value.trim();
      if (!note) {
        refuse("antwoord", field.dataset.to, "Leeg antwoord: typ eerst iets");
        return;
      }
      const to = field.dataset.to;
      log("antwoord", save({ targets: [to] }, { note, labels: [] }));
      openId = id;
      draw();
      margin.querySelector(`.fpl-card[data-id="${CSS.escape(id)}"] .fpl-answer input`)?.focus({ preventScroll: true });
    };
    return el("label", { className: "fpl-answer" }, el("span", { className: "fpl-vh" }, "Antwoord op deze kaart"), field);
  }

  /** The text a card is headed by: a span's quote, an address's text, a bundle's pieces, a lost fact's note; never its id. */
  function headOf(row) {
    if (row.labels?.[0] === "parts") return leavesOf(row).map((t) => { const r = all.find((x) => x.id === t); return typeof r?.text === "string" ? plain(r.text).trim() : ""; })
      .filter(Boolean).join(" … ");
    if (typeof row.text === "string") return plain(row.text).trim();
    const at = anchorsOf(row.id)[0];
    return at ? at.textContent.replace(/\s+/g, " ").trim() : row.note || "een feit";
  }
  /** A card's kind, its chip: its own first label, else that of the first fact or relation hanging from it. */
  const kindOfCard = (row) => (row.labels?.[0] !== "parts" && row.labels?.[0]) || facts(row.id).find((r) => r.labels?.length)?.labels[0] || null;

  /**
   * The card of a span (board F). At rest two rows: a head (the dot in the
   * row's colour, the first words of the quote, the kind as a chip, and
   * the card's Graph and ⋯, whose place is kept while they are hidden so
   * nothing moves when they show) and a meta line (who, the relations by
   * their other end, "n reacties"), and the argument's tree, folded, in
   * reach of a pick. Open (a click, its menu, a ledger row, "n reacties")
   * or holding the focus, the thread shows under it, then one field,
   * Antwoord…; hover alone shows the icons and opens the clamped note over
   * the card below, as board E. An open card is laid out open and pushes
   * the rest down. A row lost from the text is one amber line that says so.
   */
  function cardOf(row) {
    const gone = orphan(row), st = gone ? "weg" : state[row.id], cls = row.mine ? "is-mine" : "is-vers";
    const card = el("div", { className: `fpl-card ${row.mine ? "mine" : ""} ${st !== "vers" ? "lost" : ""}` });
    card.dataset.id = row.id;
    if (row.id === openId) card.classList.add("is-open");
    const head = headOf(row);
    const readings = typeof row.text === "string" || st !== "vers" ? []
      : all.filter((r) => r !== row && addressed(r) && shows(r) && r.targets[0] === row.targets[0]);
    const { rels, msgs } = readings.length ? { rels: [], msgs: [] } : about(row.id);
    if (relates(row) && typeof row.text !== "string" && !readings.length) rels.unshift(row);   // a fact on an address may itself relate
    const n = readings.length ? 0 : replies(row.id);
    const graphBtn = el("button", { type: "button", className: "fpl-ib", ariaLabel: "Graph van deze kaart", title: "Graph van deze kaart" }, ico("graph"));
    graphBtn.onclick = (ev) => { ev.stopPropagation(); graph(row.id); };
    const more = el("button", { type: "button", className: "fpl-ib fpl-card-more", ariaLabel: "Meer acties voor deze kaart", title: "Meer acties" }, ico("more"));
    more.ariaHasPopup = "menu";
    more.ariaExpanded = String(menuOf === row.id && !cardMenu.hidden);
    more.onclick = (ev) => { ev.stopPropagation(); openMenu(row.id); };
    if (st !== "vers") {   // board B: one amber line, the same card underneath
      const what = gone ? "wijst nergens heen" : st === "dubbel" ? "staat meer dan eens in de tekst" : "staat niet meer in de tekst";
      card.append(el("div", { className: "fpl-cardhead" },   // no Graph: a lost row has no place to draw from
        el("p", { className: "fpl-lostline" }, el("b", {}, st === "dubbel" ? "dubbel" : "kwijt"), " · ",
          el("span", { className: "fpl-excerpt" }, `“${clip(head, 44)}”`), ` ${what}`), more));
    } else {
      const dot = el("span", { className: "fpl-dot" });
      const kind = readings.length ? null : kindOfCard(row);
      card.append(el("div", { className: "fpl-cardhead" }, dot, el("span", { className: "fpl-title", title: clip(head, 300) }, head),
        kind ? chip(kind, cls) : null, graphBtn, more));
    }
    if (row.labels?.[0] === "parts") card.append(piecesOf(row, card));
    if (readings.length) {
      const differ = new Set([row, ...readings].map((r) => r.labels?.[0] ?? "")).size > 1;
      const been = new Set([row, ...readings].map((r) => r.id));
      card.append(el("p", { className: "fpl-meta" }, el("b", {}, `${readings.length + 1} ${differ ? "lezingen" : "rijen"}`)),
        // each reading is a whole fact: its replies, its argument, data-fact for a pick
        el("ol", { className: "fpl-msgs fpl-readings" }, ...[row, ...readings].map((r) => {
          const v = msgView(r, row.id, been);
          v.classList.add("fpl-reading");
          return v;
        })));
    } else if (row.note && st === "vers") card.append(el("p", { className: "fpl-note" }, row.note));
    // the meta line: what always shows, then "n reacties" at rest or the block's address open, never both
    const base = [author(row) ? el("b", {}, author(row)) : null,
      ...rels.map((r) => relLine(r, row.id, row.id)),
      // a bundle of ours takes more pieces: the next Alt-selects join it
      row.labels?.[0] === "parts" && row.mine ? button("Deel erbij…", (ev) => { ev.stopPropagation(); arm(row.id); }, "fpl-end fpl-arm") : null].filter(Boolean);
    const u = st === "vers" ? place(row.id)?.closest(".fpl-p") : null, sep = base.length ? " · " : "";
    const opener = n ? button(`${n} ${n === 1 ? "reactie" : "reacties"}`, (ev) => { ev.stopPropagation(); openId = row.id; layout(); hot(row.id); }, "fpl-end") : null;
    if (opener) opener.title = "Open de thread";   // a card of ours opens its editor on a click; this opens its thread
    const tail = [n ? el("span", { className: "fpl-count-r" }, sep, opener) : null,
      u?.dataset.n ? el("span", { className: "fpl-where" }, sep, addr(u)) : null].filter(Boolean);
    if ((base.length || tail.length) && !readings.length)
      card.append(el("p", { className: "fpl-meta" }, ...base.flatMap((x, i) => [i ? " · " : "", x]), ...tail));
    card.append(...ledgerRows(rels, row.id));
    // the argument stays in reach at rest (feedback 19): its tree's branches are ends a pick may click
    const box = readings.length ? null : argBox(row.id);   // a reading's message drew it
    if (box) card.append(box);
    const over = new Map();   // a bundle inside has no card: its facts hang here, under its name
    if (row.labels?.[0] === "parts") for (const d of treeOf(row).slice(1).filter(bundleOf)) for (const r of facts(d)) { msgs.push(r); over.set(r.id, d); }
    const been = new Set([row.id, ...msgs.map((m) => m.id)]);
    const thread = el("div", { className: "fpl-thread" });
    if (msgs.length > 0 && n > LONG_THREAD && !unfolded.has(row.id))
      thread.append(button(`${n} reacties`, (ev) => { ev.stopPropagation(); unfolded.add(row.id); openId = row.id; layout(); }, "fpl-link fpl-thread-fold"));
    else if (msgs.length) thread.append(el("ol", { className: "fpl-msgs" }, ...msgs.map((m) => {
      const v = msgView(m, row.id, been);
      if (over.has(m.id)) v.prepend(el("div", { className: "fpl-mhead" }, "over deel ", el("code", {}, over.get(m.id))));
      return v;
    })));
    thread.append(answerField(row.id));
    card.append(thread);
    card.onmouseenter = () => hot(row.id);
    card.onmouseleave = () => hot(null);
    card.onclick = (ev) => {
      // a message is not the card: one of ours edits itself, another's
      // is read, not a way into the card's own editor
      if (picking || ev.target.closest(
        "button, a, input, label, details, .fpl-editor, .fpl-ask, .fpl-msg"))
        return;
      const m = anchorsOf(row.id)[0];
      m && seen(m).scrollIntoView({ block: "center", behavior: "smooth" });
      if (row.mine && (m || gone)) { edit(row, card); return; }   // a lost fact of ours: open it to delete or rewrite
      if (openId !== row.id) { openId = row.id; layout(); hot(row.id); }
    };
    return card;
  }

  /* ---- a card's menu ⋯ (board F): Verbind met…, Graph, Toon beide, Verwijder ---- */

  let openId = null;   // the card laid out open: its thread shows and the cards below make room
  let menuOf = null;   // the id of the card whose menu is open
  const cardMenu = el("div", { className: "fpl-annot-ui fpl-menu fpl-cardmenu", hidden: true, role: "menu", ariaLabel: "Acties voor deze kaart" });
  const cardEl = (id) => margin.querySelector(`.fpl-card[data-id="${CSS.escape(id)}"]`);
  /**
   * Open the menu of a card, left of it as on board F (under its ⋯ where
   * there is no room), with the card laid out open. Its Verbind met… arms
   * a pick, as the key l and a press on the card's knob do.
   */
  function openMenu(id) {
    const was = menuOf === id && !cardMenu.hidden;
    shut();
    if (was) return;
    if (openId !== id) { openId = id; layout(); }
    const card = cardEl(id), row = all.find((r) => r.id === id);
    if (!card || !row) return;
    hot(id);
    menuOf = id;
    fillCardMenu(row);
    cardMenu.hidden = false;
    const btn = card.querySelector(".fpl-card-more");
    btn.ariaExpanded = "true";
    const r = card.getBoundingClientRect(), b = btn.getBoundingClientRect(), w = 240, left = r.left - 8 - w >= 8;
    cardMenu.style.width = `${w}px`;
    cardMenu.style.left = `${scrollX + (left ? r.left - 8 - w : Math.max(8, b.right - w))}px`;
    cardMenu.style.top = `${scrollY + (left ? r.top - 2 : b.bottom + 6)}px`;
    cardMenu.querySelector("button:not([aria-disabled='true'])")?.focus({ preventScroll: true });
  }
  /** An item of a menu: an icon, its name, and a key or a reason after it. */
  const entry = (name, text, onclick, after) => {
    const b = button("", onclick, "fpl-item");
    b.role = "menuitem";
    b.append(ico(name), text, ...after ? [after] : []);
    return b;
  };
  function fillCardMenu(row) {
    const ends = [...new Set([row, ...facts(row.id)].flatMap((r) => (r.targets ?? []).slice(typeof r.text === "string" ? 0 : 1)))]
      .filter((t) => place(t) && t !== row.id).slice(0, 3);
    const mine = !!row.mine, n = replies(row.id);
    const del = entry("wipe", "Verwijder", () => {
      if (!mine) {
        refuse("verwijder", row.id,
          "Een rij uit de sidecar verwijder je met lit facts, niet hier");
        return;
      }
      del.replaceWith(el("div", { className: "fpl-item fpl-confirm" }, n ? `Verwijderen? ${n} ${n === 1 ? "reactie wijst" : "reacties wijzen"} dan nergens heen.` : "Verwijderen?",
        button("Verwijder", () => {
          shut(); save(row, "delete"); openId = null; draw();
          did("verwijder", row.id, "Verwijderd");
        }, "fpl-danger"),
        button("Nee", () => fillCardMenu(row))));
      cardMenu.querySelector(".fpl-confirm button")?.focus();
    }, mine ? null : el("small", {}, "uit de sidecar"));
    del.classList.add("fpl-danger");
    if (!mine) del.ariaDisabled = "true";
    cardMenu.ariaLabel = "Acties voor deze kaart";
    cardMenu.replaceChildren(...[
      entry("link", "Verbind met…", () => { shut(); pick(row.id); }, el("kbd", {}, "l")),
      entry("graph", "Graph van deze kaart", () => { shut(); graph(row.id); }),
      ...ends.map((t) => entry("fold", `Toon beide · ${clip(said(t), 22)}`, () => { shut(); both(row.id, t); })),
      el("hr"),
      del,
      el("footer", {}, "Steunt, valt aan, zelfde als: sleep het bolletje naar een andere span.")]);
  }
  cardMenu.onkeydown = (e) => {
    const items = [...cardMenu.querySelectorAll("button")];
    const i = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length]?.focus();
    } else if (/^[1-5]$/.test(e.key) && cardMenu.querySelector("kbd")?.textContent === "1") {   // the chooser's kinds
      e.preventDefault();
      [...cardMenu.querySelectorAll(".fpl-item")].find((x) => x.querySelector("kbd")?.textContent === e.key)?.click();
    } else if (e.key === "l" && menuOf) {
      e.preventDefault();
      const id = menuOf;
      shut();
      pick(id);
    }
  };

  /**
   * The pieces of a parts row as chips, in its order. On a row of ours a
   * chip's × lets the piece go, a loose span again; the last but one
   * asks first, since a bundle of one is none and goes whole.
   */
  function piecesOf(row, card) {
    const text = (t) => { const r = all.find((x) => x.id === t);
      return typeof r?.text === "string" ? plain(r.text).trim().slice(0, 40) : t; };
    // a bundle in the bundle: its pieces in brackets, and a click writes a fact about it
    const gist = (t) => !bundleOf(t) ? el("span", { className: "fpl-gist" }, text(t))
      : el("button", { type: "button", className: "fpl-gist fpl-inner", title: `Feit over ${t}`, onclick: (ev) => {
        ev.stopPropagation(); edit({ targets: [t] }, null, ev.currentTarget.getBoundingClientRect()); } },
        "⟨", ...leavesOf(bundleOf(t)).flatMap((u, j) => [j ? " · " : "", text(u).slice(0, 16)]), "⟩");
    return el("div", { className: "fpl-pieces" }, ...(row.targets ?? []).map((t, i) => el("span",
      { className: `fpl-chip fpl-piece ${state[t] === "vers" ? "" : "is-lost"}`, title: t }, gist(t),
      row.mine ? button("×", (ev) => {
        ev.stopPropagation();
        const rest = row.targets.filter((_, j) => j !== i);
        if (rest.length > 1) {
          save(row, { targets: rest }); draw();
          log("deel los", row.targets[i]);
          return;
        }
        if (card.querySelector(".fpl-ask")) return;
        const n = all.filter((r) => typeof r.text !== "string" && r.targets?.[0] === row.id).length;   // kept, they name nothing then
        const left = n ? ` ${n} ${n > 1 ? "feiten" : "feit"} over de bundel ${n > 1 ? "blijven" : "blijft"} bewaard maar ${n > 1 ? "wijzen" : "wijst"} dan nergens heen.` : "";
        const ask = el("div", { className: "fpl-bar fpl-ask" }, `Dan blijft één deel over: de bundel opheffen?${left}`,
          button("Ja, hef op", () => {
            save(row, "delete"); if (adding === row.id) adding = null; draw();
            const lost = n > 1 ? "feiten wijzen" : "feit wijst";
            did("bundel op", row.id, "Bundel opgeheven: de delen zijn "
              + `losse spans${n ? ` · ${n} ${lost} nergens heen` : ""}`);
          }, "fpl-go"),
          button("Nee", () => { ask.remove(); layout(); }));
        card.append(ask);
        if (wide()) makeRoom(card);
      }, "fpl-unpiece") : null)));
  }

  /* ---- arguments: supports and attacks rows between rows ---- */

  const ARGUING = ["supports", "attacks"];
  const kindOf = (r) => ARGUING.includes(r.labels?.[0]) ? r.labels[0] : null;
  /** The supports and attacks rows ending at an id: a claim's grounds and attackers, an inference's undercuts. */
  const grounds = (id) => all.filter((r) => kindOf(r) && shows(r) && (r.targets ?? []).slice(1).includes(id));
  /** One line of what an id says: its row's note or text, else the text where it shows, else the id. */
  function gist(id) {
    const r = all.find((x) => x.id === id);
    const s = r?.note || (typeof r?.text === "string" ? plain(r.text) : "") || place(id)?.textContent || "";
    return s.replace(/\s+/g, " ").trim().slice(0, 120) || id;
  }
  /** What a row is called in a sentence: a span by its quote, anything else by its gist. */
  const said = (id) => { const r = all.find((x) => x.id === id); return typeof r?.text === "string" ? plain(r.text).trim() : gist(id); };
  /**
   * The tree read from an id: each ground a branch, + when it supports
   * and − when it attacks; under a branch first the attacks and supports
   * of its inference, then the grounds of its premise. An id met again
   * on its own path is a cycle (the graph allows one) and stops there;
   * one drawn before elsewhere in the tree (a premise two claims share)
   * shows once more, unexpanded, so the tree grows with the rows and not
   * with the paths through them.
   */
  function argTree(id, path, drawn) {
    const ul = el("ul", { className: "fpl-arg" });
    for (const rel of grounds(id)) {
      const src = rel.targets[0], k = kindOf(rel);
      const li = el("li", { className: `fpl-arg-${k}` });
      li.dataset.id = rel.id;
      const go = el("button", { type: "button", className: "fpl-arg-node", title: `${rel.id}: ${src}` },
        el("b", {}, k === "supports" ? "+" : "−"), " ", gist(src));
      go.onclick = (ev) => {
        if (picking) return;
        ev.stopPropagation();
        const e = place(src);
        if (!e) {
          refuse("ga naar", src, `${src} staat niet op deze pagina`);
          return;
        }
        seen(e).scrollIntoView({ block: "center", behavior: "smooth" });
      };
      li.append(go, weigh(rel));
      if (rel.note) li.append(el("p", { className: "fpl-note" }, rel.note));
      if (path.has(src) || path.has(rel.id)) li.append(el("span", { className: "fpl-lost" }, "kring"));
      else if (drawn.has(rel.id) || drawn.has(src)) li.append(el("span", { className: "fpl-lost" }, "zie boven"));
      else {
        drawn.add(rel.id).add(src);
        const deeper = new Set([...path, rel.id, src]);
        if (grounds(rel.id).length) li.append(el("div", { className: "fpl-arg-under" }, "op de gevolgtrekking", argTree(rel.id, deeper, drawn)));
        if (grounds(src).length) li.append(argTree(src, deeper, drawn));
      }
      ul.append(li);
    }
    return ul;
  }
  /**
   * A branch's weight, 1 to 5 (Kialo's impact), as five dots. On a row
   * of ours a dot sets it and the lit last dot clears it; a sidecar row
   * shows its weight and only `lit facts' changes it.
   */
  function weigh(rel) {
    const w = rel.weight ?? 0;
    const box = el("span", { className: "fpl-weight", title: w ? `gewicht ${w}` : "geen gewicht" });
    for (let n = 1; n <= 5; n++) {
      const dot = el(rel.mine ? "button" : "span", { className: n <= w ? "on" : "" }, "●");
      if (rel.mine) {
        dot.type = "button";
        dot.title = n === w ? "gewicht weg" : `gewicht ${n}`;
        dot.onclick = (ev) => {
          if (picking) return;
          ev.stopPropagation();
          save(rel, { weight: n === w ? undefined : n });   // undefined: JSON drops the key
          log("gewicht", rel.id);
          draw();
        };
      }
      box.append(dot);
    }
    return box;
  }
  const opened = new Set();   // the ids whose tree is open, kept across draws
  /** A claim's count, "2 voor · 1 tegen", over its tree; null when nothing argues about it. */
  function argBox(id) {
    const g = grounds(id);
    if (!g.length) return null;
    const pro = g.filter((r) => kindOf(r) === "supports");
    const sum = (rs) => rs.reduce((n, r) => n + (r.weight ?? 0), 0);
    const con = g.filter((r) => kindOf(r) === "attacks");
    const weighed = g.some((r) => r.weight) ? ` · gewicht ${sum(pro)} : ${sum(con)}` : "";
    const d = el("details", { className: "fpl-args" },
      el("summary", {}, `Argument · ${pro.length} voor · ${con.length} tegen${weighed}`), argTree(id, new Set([id]), new Set([id])));
    d.open = opened.has(id);
    // a new box set open fires toggle too: only a change by hand lays out again
    d.ontoggle = () => { if (d.open === opened.has(id)) return; d.open ? opened.add(id) : opened.delete(id); layout(); };
    d.onclick = (ev) => { if (!picking) ev.stopPropagation(); };
    return d;
  }

  /**
   * Connecting (board C). A pick waits for the other end: Verbind met…,
   * the key l, or a press on a knob arms one, and a click on an end, or
   * Tab to it and Enter, asks the kind. The knob may instead be dragged
   * onto the end (on touch after a long press). Either way the chooser
   * then offers verbindt (relates, Enter), steunt, valt aan, zelfde als
   * and citeert (1-5); Esc or a click elsewhere lets go. Alt-Shift-click
   * arms a pick whose kind is known, resumes, which saves at once.
   */
  let picking = null;   // {from, kind}: the next click on an end ends a pick from `from`; kind null asks it there
  let picked = 0;       // when the last pick landed: the gesture's late touchend (pointerDone) is swallowed
  /**
   * The connect in flight, kept as data so that a layout in between
   * draws it again (drawAim): from, the row it starts at; to, the end
   * under the pointer or reached with Tab; x and y, the pointer in page
   * px while the knob is carried; open, once the chooser asks the kind.
   */
  let link = null;
  let drag = null;   // the pointer on a knob: {from, id, x, y, live, touch, moved, timer}
  const HOLD = 350;  // ms: a touch held this long on a knob carries it; a shorter one is a tap, which arms a pick
  /** What a connect may end at: a branch, a fact, a card, a span or an address. */
  const AIMS = "li[data-id], [data-fact], .fpl-card[data-id]:not([data-id='draft']), mark.fact:not([data-id='draft']), .fpl-c[id], .fpl-s[id], .fpl-p[id]";
  const aimOf = (e) => e.dataset.fact ?? (e.matches(".fpl-p, .fpl-s, .fpl-c") ? e.id : e.dataset.id);
  /** The end under a point of the window, or null. */
  const aimAt = (x, y) => {
    const hit = document.elementFromPoint(x, y), k = hit?.closest?.(".fpl-knob");
    if (k) return k.dataset.id;   // another span's knob is that span: dot onto dot connects
    const e = hit?.closest?.(AIMS);
    return e && !e.closest(".fpl-menu") ? aimOf(e) : null;
  };
  /** The text column's right edge, where every line leaves for the margin, in page px. */
  const gutter = () => body.getBoundingClientRect().right + scrollX + 2;

  /** Arm a pick from a row: the next click on an end, or Tab to one and Enter, asks the kind. */
  const pick = (from) => {
    adding = null;   // one armed gesture at a time
    picking = { from, kind: null };
    link = { from, to: null };
    document.body.classList.add("fpl-picking");
    hot(from);
    drawAim();
    did("kies eind", from, `Verbind “${clip(said(from), 28)}”: klik het `
      + "andere eind, of Tab en Enter. Esc breekt af.");
  };
  const unpick = () => {
    picking = null;
    document.body.classList.remove("fpl-picking");
    if (link && !link.open) { link = null; drawAim(); hot(null); }
  };
  /** The pick's click: the row under it, from the innermost of a branch, a fact, a card, a span or a block. */
  document.addEventListener("click", (ev) => {
    if (!picking || ev.target.closest?.(".fpl-arm")) return;   // "Deel erbij…" ends the pick itself (arm)
    const at = ev.target.closest?.(picking.kind === "resumes" ? ".fpl-c[id], .fpl-s[id]:not(:has(.fpl-c))" : AIMS);
    if (!at) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();   // the Alt listener below must not see a pick's click
    const to = aimOf(at), { from, kind } = picking;
    picked = performance.now();
    if (!kind) {
      if (to === from) {
        refuse("verbind", from, "Dat is hetzelfde eind: kies een ander");
        return;
      }
      chooser(from, to, { x: ev.pageX, y: ev.pageY }, false);
      return;
    }
    unpick();
    connect(from, to, kind);
  }, true);

  /** Save a row of a kind from -> to, unless it is there already; its toast names both ends by their text. */
  function connect(from, to, kind) {
    picked = performance.now();
    if (to === from) {
      refuse("verbind", from, "Een rij argumenteert niet over zichzelf");
      return;
    }
    const twin = (r) => r.labels?.[0] === kind && r.targets?.[0] === from
      && r.targets?.[1] === to;
    if (all.some(twin)) { refuse("verbind", from, "Die rij is er al"); return; }
    const id = save({ targets: [from, to] }, { note: "", labels: [kind] });
    opened.add(to);
    draw();
    did("verbind", id, `“${clip(said(from), 24)}” ${VERB[kind] ?? kind} `
      + `“${clip(said(to), 24)}”`);
  }

  /** The chooser's kinds in their keys' order, each with its icon: verbindt is lit's relates. */
  const KINDS = [["relates", "link"], ["supports", "supports"], ["attacks", "attacks"], ["coref", "same"], ["cites", "cites"]];
  /**
   * Ask what kind of row joins from to to: the chooser (board C) in the
   * card menu's place, 23px right of and 16px under the point at, the
   * first kind focused, so Enter saves verbindt. carried: the knob was
   * dragged there, and its line stays at the drop until the answer.
   */
  function chooser(from, to, at, carried) {
    unpick();
    link = { from, to, x: carried ? at.x : null, y: carried ? at.y : null };
    shut();
    link.open = true;
    hot(from);
    drawAim();
    menuOf = null;
    cardMenu.ariaLabel = "Soort verbinding";
    cardMenu.replaceChildren(
      el("header", {}, "Verbind met ", el("b", {}, `“${clip(said(to), 24)}”`), " als"),
      ...KINDS.map(([k, i], n) => entry(i, VERB[k], () => choose(k), el("kbd", {}, String(n + 1)))),
      el("footer", {}, el("kbd", {}, "Enter"), " kiest verbindt · ", el("kbd", {}, "Esc"), " laat los"));
    const w = 248;
    cardMenu.style.width = `${w}px`;
    cardMenu.hidden = false;
    const h = cardMenu.offsetHeight, right = scrollX + document.documentElement.clientWidth - w - 8;
    cardMenu.style.left = `${Math.max(scrollX + 8, Math.min(at.x + 23, right))}px`;
    cardMenu.style.top = `${at.y + 16 + h > scrollY + innerHeight - 8 ? Math.max(scrollY + 8, at.y - h - 8) : at.y + 16}px`;
    cardMenu.querySelector(".fpl-item")?.focus({ preventScroll: true });
  }
  function choose(kind) {
    const { from, to } = link;
    link = null;
    shut();
    drawAim();
    hot(null);
    connect(from, to, kind);
  }

  /**
   * While a pick waits: Tab and the arrows walk the cards in page order
   * (a span and its card are one end) and, after a card, the facts its
   * open thread shows, the end lit and scrolled into view; Enter asks
   * the kind. A clause or block with no card is an end for the pointer
   * only: a walk through every clause of a page would not be one.
   * Whether the key was the walk's.
   */
  function walk(ev) {
    const back = ev.key === "ArrowUp" || ev.key === "ArrowLeft" || (ev.key === "Tab" && ev.shiftKey);
    if (!back && !["Tab", "ArrowDown", "ArrowRight", "Enter"].includes(ev.key)) return false;
    ev.preventDefault();
    ev.stopPropagation();
    const { from } = picking;
    if (ev.key === "Enter") {
      if (!link?.to) {
        refuse("verbind", from, "Kies eerst het andere eind: Tab of een klik");
        return true;
      }
      const m = anchorsOf(link.to).at(-1), e = m ? seen(m) : cardEl(link.to)
        ?? document.getElementById(link.to) ?? factEl(link.to);
      const r = e.getBoundingClientRect();
      chooser(from, link.to, m ? { x: r.right + scrollX, y: r.top + scrollY + r.height / 2 } : { x: r.left + scrollX, y: r.top + scrollY + HEAD }, false);
      return true;
    }
    const ends = document.querySelectorAll(
      ".fpl-card[data-id], .fpl-card .fpl-msg[data-fact]");
    const ids = [...new Set([...ends]
      .map((c) => c.dataset.id ?? c.dataset.fact))]
      .filter((id) => id !== "draft" && id !== from);
    if (!ids.length) {
      refuse("verbind", from, "Geen ander eind op deze pagina");
      return true;
    }
    const i = ids.indexOf(link.to), n = ids.length;
    link.to = ids[i < 0 ? (back ? n - 1 : 0) : (i + (back ? n - 1 : 1)) % n];
    drawAim();
    const m = anchorsOf(link.to)[0];
    (m ? seen(m) : cardEl(link.to) ?? factEl(link.to))
      ?.scrollIntoView({ block: "nearest" });
    return true;
  }
  /** A fact shown in a thread, by its id. */
  const factEl = (id) => document.querySelector(
    `.fpl-card .fpl-msg[data-fact="${CSS.escape(id)}"]`);

  /** Where a connect ends when no pointer holds it: a card's dot, else the gutter at its end's line. */
  function aimPoint(to) {
    const c = cardEl(to);
    if (c) { const r = c.getBoundingClientRect(); return { x: r.left + scrollX - 1, y: r.top + scrollY + HEAD }; }
    const at = reach(to), e = !at && document.getElementById(to);
    if (e) { const r = seen(e).getBoundingClientRect(); return { x: gutter(), y: r.top + scrollY + Math.min(r.height, 24) / 2 }; }
    return at && { x: gutter(), y: at.y };
  }
  /**
   * The connect in flight: its end lit, its knob big, and a dashed line
   * from its span's stub at the text's edge: over the margin it runs to
   * the pointer; while the pointer is over the text it stays in the
   * gutter, at the pointer's height, and only a dot follows the pointer,
   * so no line crosses the text.
   */
  function drawAim() {
    for (const n of document.querySelectorAll(".fpl-target")) n.classList.remove("fpl-target");
    for (const n of lines.querySelectorAll(".fpl-aim")) n.remove();
    for (const n of lines.querySelectorAll(".fpl-knob.is-drag")) n.classList.remove("is-drag");
    document.body.classList.toggle("fpl-linking", !!link);
    if (!link) return;
    const to = link.to, q = to && CSS.escape(to);
    if (to) for (const e of [...anchorsOf(to).map(seen), ...document.querySelectorAll(`.fpl-card[data-id="${q}"], li[data-id="${q}"], [data-fact="${q}"]`),
      ...all.some((r) => r.id === to) ? [] : [document.getElementById(to)]])
      if (e && !e.closest(".fpl-menu")) e.classList.add("fpl-target");
    lines.querySelector(`.fpl-knob[data-id="${CSS.escape(link.from)}"]`)?.classList.add("is-drag");
    const from = reach(link.from), end = link.x != null ? { x: link.x, y: link.y } : to && aimPoint(to);
    if (!from || !end || !lines.isConnected) return;
    const gx = gutter(), { x, y } = end, k = (x - gx - 6) / 2;
    svg("path", { class: "fpl-aim fpl-aim-line", d: x > gx + 6 ? `M${gx},${from.y} h6 C${gx + 6 + k},${from.y} ${x - k},${y} ${x},${y}`
      : `M${gx},${from.y} C${gx + 28},${from.y} ${gx + 28},${y} ${gx},${y}` }, link.from);
    if (link.x != null) svg("circle", { class: "fpl-aim fpl-aim-dot", cx: x, cy: y, r: 6 }, link.from);
  }

  /** The knob leaves its place: the line and its dot follow the pointer from here. */
  function carry() {
    drag.live = true;
    link = { from: drag.from, to: null, x: drag.x + scrollX, y: drag.y + scrollY };
    dropStretch();   // a stretch by keys waiting on another knob
    stretching = stretchOf(drag.from);   // null when its row is no span in the text: then the knob only connects
    document.body.classList.add("fpl-dragging");
    hot(drag.from);
    drawAim();
  }
  function dragMove(ev) {
    if (ev.pointerId !== drag?.id || drag.cancelled) return;
    if (!drag.live) {
      const far = Math.hypot(ev.clientX - drag.x, ev.clientY - drag.y);
      if (drag.touch) { if (far > 8) drag.moved = true; return; }   // a touch that wanders before HOLD carries nothing
      if (far < 4) return;
      carry();
    }
    const st = stretching;
    if (st && onGround(st, ev.clientX, ev.clientY)) {   // along its own text: a stretch, no line to follow the pointer
      if (st.row.mine) {
        link.to = link.x = link.y = null;
        st.end = endAt(st, ev.clientX, ev.clientY);
        paintStretch();
        drawAim();
        return;
      }
      if (!drag.told) {
        drag.told = true;
        refuse("rek", st.id, `${SIDECAR}; slepen verbindt`);
      }
    } else if (st && st.end !== st.e) { st.end = st.e; paintStretch(); }   // off its text: the span as it was
    const to = aimAt(ev.clientX, ev.clientY);
    link.x = ev.pageX;
    link.y = ev.pageY;
    link.to = to === drag.from ? null : to;
    drawAim();
  }
  /** The drop: on an end the chooser asks the kind; on itself or on nothing it lets go, and says so. */
  function dragEnd(ev) {
    if (ev.pointerId !== drag?.id) return;
    for (const [t, f] of DRAG) removeEventListener(t, f);
    clearTimeout(drag.timer);
    const d = drag;
    drag = null;
    document.body.classList.remove("fpl-dragging");
    if (!d.live) { if (ev.type === "pointerup" && !d.moved) pick(d.from); return; }
    picked = performance.now();
    const eat = (e) => { e.stopImmediatePropagation(); e.preventDefault(); };   // the click a drag ends in is the drop's
    addEventListener("click", eat, { capture: true, once: true });
    setTimeout(() => removeEventListener("click", eat, { capture: true }), 0);
    if (d.cancelled) return;   // Esc let it go already
    const st = stretching, up = ev.type === "pointerup";
    if (st?.row.mine && up && onGround(st, ev.clientX, ev.clientY)) { link = null; keepStretch(); drawAim(); hot(null); return; }
    dropStretch();
    const to = up ? aimAt(ev.clientX, ev.clientY) : null;
    if (to && to !== d.from) { chooser(d.from, to, { x: ev.pageX, y: ev.pageY }, true); return; }
    link = null;
    drawAim();
    hot(null);
    refuse("verbind", d.from, !up ? "Slepen afgebroken"
      : !to ? "Losgelaten naast een span, kaart of feit: niets verbonden"
        : st && !st.row.mine ? `${SIDECAR}; niets verbonden`
          : "Losgelaten op de eigen span: niets verbonden");
  }
  /** Esc while a knob is carried: the stretch put back and the connect let go; the drop that follows does nothing. */
  function cancelDrag() {
    const moved = stretching && stretching.end !== stretching.e;
    drag.cancelled = true;
    dropStretch();
    link = null;
    drawAim();
    hot(null);
    document.body.classList.remove("fpl-dragging");
    did("breek af", drag.from, moved ? "Teruggezet" : "Slepen afgebroken");
  }
  const DRAG = [["pointermove", dragMove], ["pointerup", dragEnd], ["pointercancel", dragEnd]];

  /**
   * Stretching (board D). The same knob, carried along the text of its
   * own block (its .fpl-p) instead of onto another end, moves the end of
   * its span there, a whole word at a time; only the end moves, never
   * past the block, and a span keeps one word. While carried the part
   * gained is washed and underlined dashed (lost words are washed grey),
   * drawn in the lines' svg so the text itself is not touched until the
   * drop; the knob and its line stand at the new end, the card's quote
   * follows, and a tip says "+ n woorden · loslaten bewaart · Esc zet
   * terug". Letting go there saves the row with its text, prefix and
   * suffix read anew from the shown text, as a selection makes them, so
   * the quote finder finds it once; Esc puts it back. Where the pointer
   * is let go decides (PSJ's choice 1): over another span, a card, a
   * fact or a knob, or text of another block, the knob connects as
   * before. A bundle's knob stretches the piece it ends, as a single
   * span. A span of the sidecar is lit's to change: its knob only
   * connects, and says why once it passes over its own text. Shift with
   * the arrows on a focused knob stretches by a word, shown the same
   * way; Enter saves, Esc puts back.
   */
  let stretching = null;   // {id, row, ix, s, e, end, block, hi, keys}: id the knob's card, row the span it moves, [s, e) its text in ix, end the end shown, hi its block's end
  const SIDECAR = "Een span uit de sidecar rek je niet: die verandert alleen met lit";
  const tip = el("div", { className: "fpl-annot-ui fpl-tip", role: "status" });
  const words = (t) => t.split(" ").filter(Boolean).length;
  /** The box of shown character i in the window, or null. */
  const charBox = (ix, i) => {
    const [n, o] = ix.from[i] ?? [];
    if (!n) return null;
    const r = document.createRange();
    r.setStart(n, o);
    r.setEnd(n, o + 1);
    return r.getBoundingClientRect();
  };

  /** What a knob would stretch, or null when its row is no span drawn in a block (a fact on an address only connects). */
  function stretchOf(id) {
    const at = reach(id), row = all.find((r) => r.id === at?.tail?.dataset?.id);
    const block = at?.tail?.closest?.(".fpl-p"), ix = typeof row?.text === "string" && block && shown();
    const got = ix && find(ix, row);
    if (!Array.isArray(got)) return null;
    const r = document.createRange();
    r.selectNodeContents(block);
    return { id, row, ix, s: got[0], e: got[1], end: got[1], block, hi: bounds(ix, r)[1] };
  }
  /** Whether a point of the window is a stretch's own ground: text of its block, outside every span but its own. */
  function onGround(st, x, y) {
    const hit = document.elementFromPoint(x, y), m = hit?.closest?.("mark.fact");
    return !!hit && st.block.contains(hit) && (!m || groupOf(st.id).includes(m.dataset.id));
  }
  /**
   * The shown index past the word under a point: the span's own end
   * while the point is in its last word, at least past its first word,
   * at most its block's end.
   */
  function endAt(st, x, y) {
    const { ix, s, e, hi } = st, flat = ix.flat;
    const pos = document.caretPositionFromPoint?.(x, y), cr = !pos && document.caretRangeFromPoint?.(x, y);
    if (!pos && !cr) return st.end;
    const r = document.createRange();
    r.setStart(pos ? pos.offsetNode : cr.startContainer, pos ? pos.offset : cr.startOffset);
    let k = bounds(ix, r)[0];   // the character right of the caret, or the one left of it when the pointer is there
    const b = charBox(ix, k);
    if (!b || x < b.left || x > b.right) k--;
    while (k > s && flat[k] === " ") k--;
    const past = (i) => { while (i < hi && flat[i] !== " ") i++; return i; };
    const end = past(Math.max(k, s));
    return end === past(e - 1) ? e : Math.min(hi, Math.max(end, Math.min(e, past(s))));
  }
  /** The stretch drawn: the part gained or lost per line, the knob and line at the new end, the card's quote and the tip. */
  function paintStretch() {
    for (const n of lines.querySelectorAll(".fpl-grow")) n.remove();
    tip.remove();
    const st = stretching;
    if (!st) return;
    const { flat, from } = st.ix, cut = st.end < st.e, last = charBox(st.ix, st.end - 1);
    let a = Math.min(st.e, st.end);
    const z = Math.max(st.e, st.end);
    while (a < z && flat[a] === " ") a++;
    if (a < z) {
      const r = document.createRange(), rows = [];
      r.setStart(...from[a]);
      r.setEnd(from[z - 1][0], from[z - 1][1] + 1);
      for (const q of r.getClientRects()) {   // one box per line: the inline boxes of a line overlap by more than half
        if (!q.width || !q.height) continue;
        const o = rows.find((w) => Math.min(w.b, q.bottom) - Math.max(w.t, q.top) > Math.min(w.b - w.t, q.height) / 2);
        if (o) Object.assign(o, { l: Math.min(o.l, q.left), r: Math.max(o.r, q.right), t: Math.min(o.t, q.top), b: Math.max(o.b, q.bottom) });
        else rows.push({ l: q.left, r: q.right, t: q.top, b: q.bottom });
      }
      const cls = cut ? " is-cut" : "";
      for (const w of rows) {
        svg("rect", { x: w.l + scrollX, y: w.t + scrollY, width: w.r - w.l, height: w.b - w.t, class: `fpl-grow fpl-grow-wash${cls}` }, st.id);
        svg("path", { d: `M${w.l + scrollX},${w.b + 0.5 + scrollY} H${w.r + scrollX}`, class: `fpl-grow fpl-grow-line${cls}` }, st.id);
      }
    }
    const card = cardEl(st.id), q = CSS.escape(st.id);
    const knob = lines.querySelector(`.fpl-knob[data-id="${q}"]`), line = lines.querySelector(`.fpl-line[data-id="${q}"]`);
    if (last && knob) { knob.setAttribute("cx", last.right + scrollX + 3); knob.setAttribute("cy", last.bottom - 2 + scrollY); }
    if (last && card && line) line.setAttribute("d", curve(last.bottom - Math.min(last.height, 24) / 2 + scrollY, card));
    const title = card?.querySelector(".fpl-title");
    if (title) {   // the quote as it would be saved, through headOf, so a bundle's card shows its pieces
      const was = all;
      all = all.map((r) => (r.id === st.row.id ? { ...r, text: flat.slice(st.s, st.end) } : r));
      title.textContent = headOf(all.find((r) => r.id === st.id));
      all = was;
    }
    if (st.end === st.e || !last) return;
    const n = words(flat.slice(st.s, st.end)) - words(flat.slice(st.s, st.e)), m = Math.abs(n);
    tip.replaceChildren(`${n < 0 ? "−" : "+"} ${m} ${m === 1 ? "woord" : "woorden"} · `,
      ...(st.keys ? [el("kbd", {}, "Enter"), " bewaart"] : ["loslaten bewaart"]), " · ", el("kbd", {}, "Esc"), " zet terug");
    document.body.append(tip);
    const col = body.getBoundingClientRect(), w = tip.offsetWidth;
    tip.style.top = `${last.bottom + scrollY + 8}px`;
    tip.style.left = `${Math.max(col.left, Math.min(last.right - w / 2, col.right - w)) + scrollX}px`;
  }
  /** Put the span back as it was (Esc, a drop elsewhere, a new stretch); the stretch, or null. */
  function dropStretch() {
    const st = stretching;
    if (st) { st.end = st.e; paintStretch(); }
    stretching = null;
    tip.remove();
    return st;
  }
  /** Save the stretch: its text, prefix and suffix read from the shown text, as a selection makes them. */
  function keepStretch() {
    const st = stretching;
    if (!st) return;
    if (st.end === st.e) {
      dropStretch();
      refuse("rek", st.id, "Losgelaten op de eigen span: niets veranderd");
      return;
    }
    const { flat } = st.ix, n = words(flat.slice(st.s, st.end)) - words(flat.slice(st.s, st.e));
    const got = { text: flat.slice(st.s, st.end), prefix: flat.slice(Math.max(0, st.s - AROUND), st.s), suffix: flat.slice(st.end, st.end + AROUND) };
    if (!Array.isArray(find(st.ix, { ...st.row, ...got }))) {
      dropStretch();
      refuse("rek", st.id, "Zo staat de tekst vaker op de pagina: niet gerekt");
      return;
    }
    stretching = null;
    tip.remove();
    save(st.row, got);
    draw();
    const w = (k) => `${k} ${k === 1 ? "woord" : "woorden"}`;
    did("rek", st.row.id, n > 0 ? `${w(n)} erbij`
      : n < 0 ? `${w(-n)} eraf` : "Gerekt");
  }
  /** Shift and an arrow on a focused knob: its span's end a word on (d 1) or back (d -1), shown as a drag shows it. */
  function nudge(id, d) {
    if (stretching?.id !== id) {
      dropStretch();
      const st = stretchOf(id);
      if (!st) {
        refuse("rek", id,
          "Hier valt niets te rekken: dit eind is geen span in de tekst");
        return;
      }
      if (!st.row.mine) { refuse("rek", id, SIDECAR); return; }
      stretching = { ...st, keys: true };
      hot(id);
    }
    const st = stretching, { flat } = st.ix;
    let i = st.end;
    if (d > 0) { while (i < st.hi && flat[i] === " ") i++; while (i < st.hi && flat[i] !== " ") i++; }
    else { while (i > st.s && flat[i - 1] !== " ") i--; while (i > st.s && flat[i - 1] === " ") i--; }
    if (i === st.end || i <= st.s) {
      refuse("rek", id, d > 0
        ? "Het blok houdt hier op: verder rekt de span niet"
        : "Een span houdt minstens één woord");
      return;
    }
    st.end = i;
    paintStretch();
  }

  /* ---- the graph: rows and what they name, laid out by force ---- */

  /* query: begin. Self-contained: tests/test_query_js.py runs this block in node against tests/query_cases.json. */
  const QUERY = (() => {
    const RELS = new Set(["because", "supports", "attacks", "contradicts", "supersedes", "checkedBy", "cites", "relates", "resumes"]);
    const SETS = new Set(["coref", "parts"]);
    const KEYS = ["label", "layer", "by", "text", "has", "gives"];
    const LAYERS = ["span", "fact", "thread", "argument", "tfa", "coref", "relation"];
    const CHAIN_BUDGET = 100000;   // steps one chain walk may take, rather than freeze the tab (lit's facts.CHAIN_BUDGET)
    const strs = (v) => Array.isArray(v) && v.every((x) => typeof x === "string");
    const first = (r) => (strs(r.labels) && r.labels.length ? r.labels[0] : "");
    function layer(r, by) {   // lit's facts.layer
      const k = first(r);
      if ("item" in r) return "span";
      if (k === "parts") return "span";
      if (k === "coref") return "coref";
      if (k === "resumes" || k.startsWith("tfa/")) return "tfa";
      if (k === "supports" || k === "attacks") return "argument";
      if (RELS.has(k)) return "relation";
      const up = strs(r.targets) && r.targets.length ? by.get(r.targets[0]) : undefined;
      return up !== undefined && !("item" in up) && first(up) !== "parts" ? "thread" : "fact";
    }
    function parse(q) {   // groups of [neg, key, value, chain length, column]; a row is found when one group holds
      const groups = [[]];
      let bar = 0;   // the column of the last "|", 0 before any
      for (const m of q.matchAll(/[^ ]+/g)) {   // terms apart by U+0020 only, as lit
        const term = m[0], col = [...q.slice(0, m.index)].length + 1, neg = term.startsWith("!");   // columns in code points
        if (term === "|") {   // "|" closes a group (PML-TQ's or)
          if (!groups[groups.length - 1].length) throw new Error(`empty group at ${col}`);
          groups.push([]);
          bar = col;
          continue;
        }
        const rest = term.slice(neg ? 1 : 0), i = rest.indexOf(":");
        const key = i < 0 ? "" : rest.slice(0, i);
        let value = i < 0 ? "" : rest.slice(i + 1), n = 0;
        if (i < 0 || !/^[a-z]+$/.test(key)) throw new Error(`no key:value at ${col}`);
        if (!KEYS.includes(key)) throw new Error(`unknown key '${key}' at ${col}`);
        if (!value) throw new Error(`empty value at ${col}`);
        if (key === "has" || key === "gives") {   // R or R+N, N from 1 without leading zeros, past nine digits 1e9
          const p = value.indexOf("+"), length = p < 0 ? "" : value.slice(p + 1);
          if (p >= 0) value = value.slice(0, p);
          if (!RELS.has(value) && !SETS.has(value)) throw new Error(`'${value}' is no relation or set at ${col}`);
          if (p >= 0 && !/^[1-9][0-9]*$/.test(length)) throw new Error(`bad chain length at ${col}`);
          n = p < 0 ? 0 : length.length > 9 ? 1e9 : Number(length);
        }
        if (key === "layer" && !LAYERS.includes(value)) throw new Error(`'${value}' is no layer at ${col}`);
        groups[groups.length - 1].push([neg, key, value, n, col]);
      }
      if (bar && !groups[groups.length - 1].length) throw new Error(`empty group at ${bar}`);
      return groups;
    }
    function query(rows, q) {
      const groups = parse(q), by = new Map(rows.filter((r) => typeof r.id === "string").map((r) => [r.id, r]));
      const add = (m, k, x) => m.set(k, (m.get(k) ?? new Set()).add(x));
      const back = new Map(), ahead = new Map();   // kind -> node -> the nodes an edge joins it to, into it / out of it
      const link = (m, k, a, b) => { if (!m.has(k)) m.set(k, new Map()); add(m.get(k), a, b); };
      for (const r of rows) {   // lit's facts.relation_edges: no node joins itself
        const k = first(r), t = r.targets;
        if (!strs(t) || !t.length) continue;
        const edges = SETS.has(k) ? t.flatMap((a) => t.filter((b) => a !== b).map((b) => [a, b])) : t.slice(1).filter((b) => b !== t[0]).map((b) => [t[0], b]);
        for (const [a, b] of edges) { link(ahead, k, a, b); link(back, k, b, a); }
      }
      const reaches = (step, x, n) => {   // lit's facts.reaches: x reaches n other nodes, a count that stops there
        const reach = new Set([x]), todo = [x];
        while (todo.length && reach.size <= n) {   // pop outside step?.get(), which would skip it when step is undefined
          const at = todo.pop();
          for (const y of step?.get(at) ?? []) if (!reach.has(y)) { reach.add(y); todo.push(y); }
        }
        return reach.size > n;
      };
      const chain = (step, x, n, col) => {   // lit's facts.chained: a simple path of at least n edges from x along step
        if (!reaches(step, x, n)) return false;   // too few nodes for n edges: no at once
        const path = [x], seen = new Set([x]), nexts = [(step.get(x) ?? new Set()).values()];   // a walk on a stack of its own
        let budget = CHAIN_BUDGET;
        while (nexts.length) {
          const it = nexts[nexts.length - 1];
          let s = it.next();
          while (!s.done && seen.has(s.value)) s = it.next();
          if (s.done) { nexts.pop(); seen.delete(path.pop()); continue; }
          if (path.length === n) return true;
          if (--budget < 0) throw new Error(`chain too long to search at ${col}`);
          path.push(s.value); seen.add(s.value); nexts.push((step.get(s.value) ?? new Set()).values());
        }
        return false;
      };
      const about = (r) => {   // a fact on an address speaks for the address; one on a row, or a relation, only for itself
        const t0 = strs(r.targets) && r.targets.length ? r.targets[0] : null;
        const own = "item" in r || RELS.has(first(r)) || SETS.has(first(r));
        return own || !t0 || by.has(t0) ? [r.id] : [r.id, t0];
      };
      const holds = (r, key, v, n, col) => {   // bare has:R is has:R+1; bare gives:R is gives:R+1 for a relation, never for a set
        const labels = strs(r.labels) ? r.labels : [];
        switch (key) {
          case "label": return labels.some((x) => x === v || x.startsWith(v + "/"));
          case "layer": return layer(r, by) === v;
          case "by": return r.by === v;
          case "text": return [r.text, r.note].filter((x) => typeof x === "string").join(" ").toLowerCase().includes(v.toLowerCase());
          case "has": return about(r).some((x) => chain(back.get(v), x, n || 1, col));
          default: return Boolean(n || RELS.has(v)) && about(r).some((x) => chain(ahead.get(v), x, n || 1, col));
        }
      };
      return rows.filter((r) => typeof r.id === "string" && groups.some((g) => g.every(([neg, k, v, n, col]) => holds(r, k, v, n, col) !== neg))).map((r) => r.id);
    }
    return { parse, query };
  })();
  /* query: end */
  let asked = "", found = null;   // the query in the field, and the ids it finds (null: no query)
  /** Fade what the query does not find: a card stays when its row or a row in it is found, a span when its card stays. */
  function fade() {
    for (const n of document.querySelectorAll(".fpl-faded")) n.classList.remove("fpl-faded");
    if (!found) return;
    const stays = new Set();   // a row found, and the rows its thread hangs from, up to a span or an address
    for (const id of found) for (let r = all.find((x) => x.id === id), been = new Set(); r && !been.has(r.id); been.add(r.id), r = all.find((x) => x.id === r.targets?.[0])) {
      stays.add(r.id);
      for (const g of groupOf(r.id)) stays.add(g);
    }
    for (const c of document.querySelectorAll(".fpl-card")) {   // inline cards too, on a narrow screen
      const ids = [c.dataset.id, ...[...c.querySelectorAll("[data-fact]")].map((x) => x.dataset.fact)];
      if (!ids.some((i) => stays.has(i))) c.classList.add("fpl-faded");
    }
    for (const m of body.querySelectorAll("mark.fact")) if (!stays.has(m.dataset.id)) m.classList.add("fpl-faded");
    for (const e of body.querySelectorAll("[data-tfa-row]")) if (!found.has(e.dataset.tfaRow)) e.classList.add("fpl-faded");
  }

  const SETKINDS = new Set(["coref", "parts"]);
  /**
   * The page's graph in the layers shown: a node per row and per id a row
   * names; a relation row (or set) is a node between its ends, a fact an
   * edge to what it is about. Edges carry the relation's label.
   */
  let code = null;   // the page's code graph (lit graph), when the site shipped one
  const coded = (snap ? Promise.resolve(snap.graph ?? null) : fetch(`${stem}.graph.json`).then((r) => (r.ok ? r.json() : null)))
    .catch(() => null).then((g) => { code = g && Array.isArray(g.nodes) && Array.isArray(g.edges) ? g : null; });
  function graphOf() {
    const nodes = new Map(), edges = [];
    const kinds = new Map((code?.nodes ?? []).map((n) => [n.id, n.kind]));
    const kindOf = (id) => {
      const r = all.find((x) => x.id === id);
      return r ? layerOf(r) : kinds.get(id) ?? (document.getElementById(id) ? "address" : "elders");
    };
    const node = (id) => nodes.get(id) ?? nodes.set(id, { id, kind: kindOf(id), x: 0, y: 0, dx: 0, dy: 0 }).get(id);
    for (const r of all.filter(shows)) {
      node(r.id);
      const k = r.labels?.[0] ?? "", ts = (r.targets ?? []).filter(Boolean);
      if (typeof r.text === "string") continue;
      if (RELATIONS.has(k)) {
        if (ts[0]) edges.push({ a: node(ts[0]), b: node(r.id), label: "" });
        for (const t of ts.slice(1)) edges.push({ a: node(r.id), b: node(t), label: k, w: r.weight ?? 0 });
      } else if (SETKINDS.has(k)) for (const t of ts) edges.push({ a: node(r.id), b: node(t), label: k });
      else if (ts[0]) edges.push({ a: node(r.id), b: node(ts[0]), label: "over" });
    }
    for (const n of code?.nodes ?? []) node(n.id).label = n.label;
    // a tangle edge carries no word, its width says how many lines it gives (many labels at one file hide each other)
    for (const e of code?.edges ?? []) edges.push({ a: node(e.a), b: node(e.b), label: e.label === "tangles" ? "" : e.label, lines: e.n ?? 0 });
    return { nodes: [...nodes.values()], edges };
  }
  /**
   * The code block a chunk stands in: the k-th block whose header names
   * it (k from the chunk id). The header is the block's first line,
   * <<[number ]name, read as lit's web.HEAD reads it and normalised as
   * web.norm does; a use (<<name>>) inside another block is no header.
   */
  function chunkBlock(id) {
    const n = code?.nodes.find((x) => x.id === id);
    if (!n || n.kind !== "chunk") return null;
    const norm = (x) => x.split(/\s+/).filter(Boolean).join(" ");
    const head = (b) => {
      const m = /^<<([^<>\n]+)/.exec(b.textContent.replace(/^\s+/, ""));
      return m ? norm(m[1].replace(/^[\d.]+\s+/, "").replace(/>>\+?=?\s*$/, "")) : null;
    };
    const k = Number(id.split(":").at(-1)) || 1;
    return [...body.querySelectorAll('.fpl-p[data-kind="C"]')].filter((b) => head(b) === norm(n.label))[k - 1] ?? null;
  }
  /** The part of a graph within two steps of an id. */
  function near({ nodes, edges }, id, steps = 2) {
    const keep = new Set([id]);
    for (let i = 0; i < steps; i++) {   // breadth first: a round reaches one step past the last, no further
      const was = new Set(keep);
      for (const e of edges) if (was.has(e.a.id) || was.has(e.b.id)) { keep.add(e.a.id); keep.add(e.b.id); }
    }
    return { nodes: nodes.filter((n) => keep.has(n.id)), edges: edges.filter((e) => keep.has(e.a.id) && keep.has(e.b.id)) };
  }
  /**
   * Fruchterman-Reingold, a fixed number of rounds from a circle (the same
   * layout every time for the same rows): neighbours pull, all push, a
   * weak gravity holds the loose parts of the graph near the middle
   * (without it they drift to the walls), and the step cools to nothing.
   * The right edge keeps room for the labels drawn right of each node.
   * k and GRAV measured 2026-11-01 on the lex page (28 nodes, 22 edges):
   * at 0.6 and 2 no node rests on a wall and no two lie within 12 px;
   * gravity 0.5 left 16 nodes on the walls, 1.2 with k 0.8 left 19.
   */
  function settleGraph({ nodes, edges }, w, h, rounds = 300) {
    const k = Math.sqrt((w * h) / Math.max(nodes.length, 1)) * 0.6, GRAV = 2;
    nodes.forEach((n, i) => { const a = (2 * Math.PI * i) / nodes.length; n.x = w / 2 + (w / 3) * Math.cos(a); n.y = h / 2 + (h / 3) * Math.sin(a); });
    for (let t = 0; t < rounds; t++) {
      for (const n of nodes) { n.dx = 0; n.dy = 0; }
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const p = nodes[i], q = nodes[j], dx = p.x - q.x, dy = p.y - q.y, d = Math.hypot(dx, dy) || 0.01, f = (k * k) / d;
        p.dx += (dx / d) * f; p.dy += (dy / d) * f; q.dx -= (dx / d) * f; q.dy -= (dy / d) * f;
      }
      for (const { a, b } of edges) {
        const dx = a.x - b.x, dy = a.y - b.y, d = Math.hypot(dx, dy) || 0.01, f = (d * d) / k;
        a.dx -= (dx / d) * f; a.dy -= (dy / d) * f; b.dx += (dx / d) * f; b.dy += (dy / d) * f;
      }
      for (const n of nodes) { n.dx += (w / 2 - n.x) * GRAV; n.dy += (h / 2 - n.y) * GRAV; }
      const temp = (w / 10) * (1 - t / rounds);
      for (const n of nodes) {
        const d = Math.hypot(n.dx, n.dy) || 0.01;
        n.x = Math.min(w - 150, Math.max(20, n.x + (n.dx / d) * Math.min(d, temp)));
        n.y = Math.min(h - 20, Math.max(20, n.y + (n.dy / d) * Math.min(d, temp)));
      }
    }
  }
  /**
   * Where a node goes: its own place, else that of what it is about,
   * followed up its first targets.
   */
  function goal(nid, been = new Set()) {
    const e = place(nid) ?? chunkBlock(nid);
    if (e || been.has(nid)) return e;
    been.add(nid);
    const r = all.find((x) => x.id === nid);
    return r?.targets?.[0] ? goal(r.targets[0], been) : null;
  }
  /** Close a graph and go to a node, lit; or say why not. */
  function goTo(nid, close) {
    const e = goal(nid);
    if (!e) {
      refuse("ga naar", nid, `${nid} staat niet op deze pagina`);
      return;
    }
    close();
    seen(e).scrollIntoView({ block: "center", behavior: "smooth" });
    hot(nid);
    log("ga naar", nid);
  }

  /**
   * The graph of one card (board J, feedback 9), read so that it and the
   * card's meta line agree: the card's row and what lies within two
   * steps of it, where a relation that joins its ends is an edge with its
   * verb, unless a relation aims at it (an undercut keeps its diamond,
   * as in the page's graph), and the messages of the card's thread, which
   * the card shows, are left out.
   */
  function aroundOf(id) {
    const g = graphOf(), at = new Map(g.nodes.map((n) => [n.id, n]));
    if (!at.has(id)) at.set(id, { id });
    const rels = facts(id).filter(relates).map((r) => r.id);
    const thread = new Set();   // messages on it or its relations, replies
    for (const todo = [id, ...rels]; todo.length;) {
      for (const r of facts(todo.pop())) {
        if (relates(r) || thread.has(r.id)) continue;
        thread.add(r.id);
        todo.push(r.id);
      }
    }
    const kept = (e) => !thread.has(e.a.id) && !thread.has(e.b.id);
    const two = near({ nodes: [...at.values()], edges: g.edges.filter(kept) },
      id);
    const in2 = new Map(two.nodes.map((n) => [n.id, n]));
    let { edges } = two;
    for (const r of all.filter((x) => in2.has(x.id) && relates(x)
      && typeof x.text !== "string" && RELATIONS.has(x.labels?.[0]))) {
      const n = in2.get(r.id), [from, ...to] = r.targets;
      if (![from, ...to].every((t) => in2.has(t))) continue;   // an end too far
      const into = edges.filter((e) => e.b === n && e.a.id !== from);
      if (into.some((e) => RELATIONS.has(e.label))) continue;   // undercut
      edges = edges.filter((e) => e.a !== n && e.b !== n).concat(to.map((t) =>
        ({ a: in2.get(from), b: in2.get(t), label: verb(r) })));
      in2.delete(r.id);
    }
    return { nodes: [...in2.values()], edges };
  }
  /**
   * What a node of a graph (a card's or the page's) is called: its first
   * words, never an id.
   */
  function nodeName(nid, own) {
    const r = all.find((x) => x.id === nid), d = decision(nid);
    const span = typeof r?.text === "string";
    if (nid === own) return span ? "deze span" : "deze kaart";
    if (d) return d.decision || d.topic || `besluit ${d.id}`;
    const c = code?.nodes.find((x) => x.id === nid);
    if (c) return c.label ?? named(nid);
    if (r && !span && RELATIONS.has(r.labels?.[0])) return verb(r);
    if (r && !span && !r.note && SETKINDS.has(r.labels?.[0]))
      return r.labels[0] === "coref" ? "zelfde als" : "delen";
    // a row that says nothing (no note, no text) by its labels
    if (r) return gist(nid) !== nid ? said(nid)
      : (r.labels ?? []).join(" ") || "een feit";
    return place(nid) ? said(nid) : named(nid) || "iets dat weg is";
  }
  /**
   * Open the graph of a card as a popover beside it (board J), sized to
   * what it holds: one column per step from the card, its own node
   * first, each node named under it and each edge by its verb above it.
   * One edge or none says how to connect more. "Hele pagina" opens the
   * page's graph; a node goes there; Esc, × or a click elsewhere closes
   * it, and the card's Graph again too. While it is up around.id names
   * the card, which hot() keeps lit, as board J draws it.
   */
  async function around(id) {
    await coded;
    const was = document.querySelector(".fpl-graph");
    if (was) was.close();
    if (was?.dataset.id === id) return;
    const g = aroundOf(id);
    const card = document.querySelector(
      `.fpl-card[data-id="${CSS.escape(id)}"]`);
    const btn = card?.querySelector('[aria-label="Graph van deze kaart"]');
    const col = new Map([[id, 0]]);
    for (let d = 0; d < 2; d++) for (const e of g.edges)
      for (const [p, q] of [[e.a, e.b], [e.b, e.a]])
        if (col.get(p.id) === d && !col.has(q.id)) col.set(q.id, d + 1);
    g.nodes = g.nodes.filter((n) => col.has(n.id));   // a fold may strand one
    g.edges = g.edges.filter((e) => col.has(e.a.id) && col.has(e.b.id));
    const cols = [0, 1, 2]
      .map((c) => g.nodes.filter((n) => col.get(n.id) === c))
      .filter((c) => c.length);
    const PITCH = 174, ROW = 52, rows = Math.max(...cols.map((c) => c.length));
    const lone = g.nodes.length === 1, top = lone ? 12 : 26;   // no edge label
    const W = 224 + (cols.length > 2 ? PITCH : 0);
    const H = top + 38 + (rows - 1) * ROW;
    cols.forEach((c, x) => c.forEach((n, y) => {
      n.x = 22 + x * PITCH;
      n.y = top + ((rows - c.length) / 2 + y) * ROW;
      n.col = x;
    }));
    const NS = "http://www.w3.org/2000/svg";
    const svg = (tag, attrs, text) => {
      const e = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
      if (text) e.textContent = text;
      return e;
    };
    const pic = svg("svg", { class: "fpl-g", width: W, height: H,
      viewBox: `0 0 ${W} ${H}`, role: "group" });
    const pen = document.createElement("canvas").getContext("2d");
    pen.font = `600 11px ${getComputedStyle(document.body).fontFamily}`;
    const boxes = [];   // what a word may not cover: dots and names
    const free = (q) => !boxes.some((o) => q[0] < o[2] && o[0] < q[2]
      && q[1] < o[3] && o[1] < q[3]);
    const last = cols.length - 1;
    for (const n of g.nodes) {
      const r = all.find((x) => x.id === n.id), name = nodeName(n.id, id);
      const hue = typeof r?.text === "string" ? (r.mine ? "mine" : "vers") : "";
      const rel = !!r && relates(r) && typeof r.text !== "string"
        && RELATIONS.has(r.labels?.[0]);
      const node = svg("g", { class: `fpl-gnode ${hue}`, tabindex: 0,
        role: "button", "aria-label": `Ga naar ${name}` });
      node.append(rel
        ? svg("path", { d: `M${n.x} ${n.y - 6}l6 6-6 6-6-6z` })
        : svg("circle", { cx: n.x, cy: n.y, r: n.id === id ? 7 : 5 }));
      const end = n.col === last && last > 0;
      const word = clip(name, last > 1 ? 18 : 24);
      const lx = n.col === 0 ? n.x - 18 : end ? n.x + 14 : n.x;
      const lw = pen.measureText(word).width;
      const x0 = n.col === 0 ? lx : end ? lx - lw : lx - lw / 2;
      boxes.push([n.x - 8, n.y - 8, n.x + 8, n.y + 8],
        [x0, n.y + 16, x0 + lw, n.y + 29]);
      node.append(svg("text", { class: "fpl-gl", y: n.y + 26, x: lx,
        "text-anchor": n.col === 0 ? "start" : end ? "end" : "middle" }, word));
      node.onclick = () => goTo(n.id, close);
      node.onkeydown = (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        ev.preventDefault();
        goTo(n.id, close);
      };
      pic.append(node);
    }
    /*
     * The edges, under the nodes; a verb stands above its edge's middle
     * (board J), else at the first of a few places along it, above or
     * under, where it covers no dot, name or other verb.
     */
    const ALONG = [0.5, 0.35, 0.65, 0.25, 0.75];
    for (const e of g.edges) {   // the same column: a bow to the right
      const { a, b } = e, bow = a.col === b.col;
      const via = bow ? `Q${a.x + 40} ${(a.y + b.y) / 2} ` : "L";
      pic.prepend(svg("path", { class: "fpl-gx",
        d: `M${a.x} ${a.y}${via}${b.x} ${b.y}` }));
      if (!e.label) continue;
      const word = clip(VERB[e.label] ?? e.label, 18);
      const w = pen.measureText(word).width;
      const spots = ALONG.flatMap((t) => [-8, 15].map((dy) => [
        bow ? a.x + 30 : a.x + t * (b.x - a.x), a.y + t * (b.y - a.y) + dy]));
      const [sx, sy] = spots.find(([x, y]) =>
        free([x - w / 2, y - 9, x + w / 2, y + 3])) ?? spots[0];
      boxes.push([sx - w / 2, sy - 9, sx + w / 2, sy + 3]);
      pic.append(svg("text", { class: "fpl-ge", x: sx, y: sy,
        "text-anchor": "middle" }, word));
    }
    const nn = g.nodes.length, ne = g.edges.length;
    const own = g.edges.filter((e) => e.a.id === id || e.b.id === id).length;
    const hint = ne > own || ne > 1 ? null
      : `${ne ? "Verder nog" : "Nog"} niets verbonden. Sleep het `
        + "bolletje achter de span naar een andere span.";
    const x = el("button", { type: "button", className: "fpl-ib",
      ariaLabel: "Sluit de graph", title: "Sluit", onclick: () => close() },
    ico("clear"));
    const panel = el("section", { role: "dialog",
      className: "fpl-annot-ui fpl-graph fpl-around",
      ariaLabel: "Graph rond deze kaart" },
    el("header", { className: "fpl-bar" },
      el("b", {}, `Rond “${clip(said(id), 24)}”`), x),
    el("div", { className: "fpl-sub" },
      el("span", {}, `${nn} ${nn === 1 ? "knoop" : "knopen"} · `
        + `${ne} ${ne === 1 ? "kant" : "kanten"}`),
      button("Hele pagina", () => { close(); graph(null); }, "fpl-link")),
    pic, hint ? el("p", {}, hint) : null);
    panel.dataset.id = id;
    panel.style.width = `${W + 26}px`;
    const opener = document.activeElement;
    const off = (ev) => {
      if (!panel.contains(ev.target) && !btn?.contains(ev.target)) close();
    };
    const close = () => {
      panel.remove();
      around.id = null;
      hot(null);
      removeEventListener("pointerdown", off, true);
      if (btn) btn.ariaExpanded = "false";
      const at = document.activeElement;
      if (!at || at === document.body || panel.contains(at))
        opener?.focus?.({ preventScroll: true });
    };
    panel.close = close;
    panel.tabIndex = -1;
    document.body.append(panel);
    const r = card?.getBoundingClientRect(), w = W + 26;
    const left = r && r.left - 8 - w >= 8;
    const under = (btn ?? card)?.getBoundingClientRect();
    const right = under ? Math.min(under.right, innerWidth - 8)
      : innerWidth - 16;
    const x0 = left ? r.left - 8 - w : Math.max(8, right - w);
    const y0 = left ? r.top - 6 : under ? under.bottom + 6 : 120;
    panel.style.left = `${scrollX + x0}px`;
    panel.style.top = `${scrollY + y0}px`;
    if (btn) btn.ariaExpanded = "true";
    around.id = id;
    hot(id);
    addEventListener("pointerdown", off, true);
    panel.focus({ preventScroll: true });
    log("graph", id);
  }

  /**
   * Open a card's graph (around), or the page's over the page; Esc or a
   * click outside closes it.
   */
  async function graph(id) {
    if (id) return around(id);
    await coded;   // the code graph first: a panel drawn before it came would lack the chunks
    document.querySelector(".fpl-graph")?.close();
    const g = graphOf();
    const css = getComputedStyle(document.documentElement);
    const color = (n) => css.getPropertyValue({ chunk: "--fpl-fg", file: "--fpl-mine", span: "--fpl-vers", argument: "--fpl-con", tfa: "--fpl-lost",
      coref: "--fpl-mine", relation: "--fpl-mute", address: "--fpl-mute", elders: "--fpl-rule" }[n.kind] ?? "--fpl-fg").trim() || "#888";
    const W = Math.max(320, Math.min(innerWidth - 32, 1100)), H = Math.max(240, Math.min(innerHeight - 96, 760)), dpr = devicePixelRatio || 1;
    const opener = document.activeElement;
    const cv = el("canvas", { width: W * dpr, height: H * dpr });
    cv.style.width = `${W}px`; cv.style.height = `${H}px`;
    const panel = el("div", { className: "fpl-annot-ui fpl-graph", role: "dialog", "aria-label": "Graph" },
      el("div", { className: "fpl-bar" }, el("b", {}, "Graph van de pagina"),
        el("span", { className: "fpl-mute" }, ` · ${g.nodes.length} knopen · ${g.edges.length} kanten`), el("span", { className: "fpl-space" }),
        button("Sluit", () => close())), cv);
    const close = () => { panel.remove(); opener?.focus?.(); };
    const go = (n) => goTo(n.id, close);
    settleGraph(g, W, H);
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.font = "11px system-ui, sans-serif";
    ctx.lineWidth = 1;
    for (const e of g.edges) {
      ctx.strokeStyle = css.getPropertyValue("--fpl-rule").trim() || "#ccc";
      ctx.lineWidth = e.lines ? 1 + Math.log2(e.lines) : e.w ? e.w : 1;
      ctx.beginPath(); ctx.moveTo(e.a.x, e.a.y); ctx.lineTo(e.b.x, e.b.y); ctx.stroke();
      if (e.label) { ctx.fillStyle = css.getPropertyValue("--fpl-mute").trim() || "#777"; ctx.fillText(e.label, (e.a.x + e.b.x) / 2 + 3, (e.a.y + e.b.y) / 2 - 3); }
    }
    for (const n of g.nodes) {
      ctx.fillStyle = color(n);
      const rel = n.kind === "relation" || n.kind === "argument" && all.find((x) => x.id === n.id && typeof x.text !== "string" && (x.targets ?? []).length > 1);
      ctx.beginPath();
      if (rel) { ctx.moveTo(n.x, n.y - 6); ctx.lineTo(n.x + 6, n.y); ctx.lineTo(n.x, n.y + 6); ctx.lineTo(n.x - 6, n.y); ctx.closePath(); }
      else ctx.arc(n.x, n.y, 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.fillStyle = css.getPropertyValue("--fpl-fg").trim() || "#222";
      // a chunk or file by its name, a row by its words, never an id
      const name = n.label ?? nodeName(n.id, null);
      if (n.kind === "chunk" || n.kind === "file") { ctx.fillStyle = color(n); ctx.fillRect(n.x - 4, n.y - 4, 8, 8); ctx.fillStyle = css.getPropertyValue("--fpl-fg").trim() || "#222"; }
      ctx.fillText(name.length > 28 ? name.slice(0, 27) + "…" : name, n.x + 8, n.y + 4);
    }
    cv.onclick = (ev) => {
      const r = cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
      const hit = g.nodes.find((n) => Math.hypot(n.x - x, n.y - y) < 9);
      if (hit) go(hit);
    };
    // the same nodes as buttons, for a keyboard or a screen reader: the canvas is pixels only
    cv.setAttribute("aria-hidden", "true");
    panel.append(el("details", { className: "fpl-graph-list" }, el("summary", {}, "Knopen als lijst"),
      el("div", { className: "fpl-chips" }, ...g.nodes.map((n) => button(`${n.id} · ${n.kind}`, () => go(n), "fpl-link")))));
    panel.close = close;
    panel.tabIndex = -1;
    document.body.append(panel);
    panel.focus();
    panel.dataset.nodes = g.nodes.map((n) => `${n.id}@${Math.round(n.x)},${Math.round(n.y)}`).join(" ");   // for tests: where each node landed
    log("graph", null);
  }

  /** Download this browser's rows as <stem>.annot.json. */
  function exportRows() {
    log("exporteer rijen", null);
    const blob = new Blob([JSON.stringify(local(), null, 1) + "\n"],
      { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: `${stem}.annot.json` });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /** Download the log as <stem>.log.json; the export is its last entry. */
  function exportLog() {
    log("exporteer logboek", null);
    const blob = new Blob([JSON.stringify(journal, null, 1) + "\n"],
      { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob),
      download: `${stem}.log.json` });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /** Merge a file of rows for this page into this browser's, by id. */
  function merge(text) {
    let got;
    try { got = JSON.parse(text); } catch (e) {
      refuse("importeer", null, `Geen JSON: ${e.message}`);
      return;
    }
    if (!Array.isArray(got)) {
      refuse("importeer", null, "Geen lijst van rijen");
      return;
    }
    const by = new Map(local().map((r) => [r.id, r]));
    let n = 0;
    for (const r of got) if (r && r.item === item && typeof r.id === "string") { by.set(r.id, r); n++; }
    keep([...by.values()]);
    did("importeer", null, `${n} rijen ingelezen`);
    draw();
  }

  function toast(text) {
    const t = el("div", { className: "fpl-annot-ui fpl-toast" }, text);
    document.body.append(t);
    setTimeout(() => t.remove(), 1800);
  }

  /* ---- the editor ---- */

  /**
   * The editor of a row: what it is about on one line, the note, the six
   * labels most used as chips (and those the row has) plus a field for
   * one more, which completes from every label known; ⌘↩ saves, esc
   * closes.
   */
  function editor(row, onDone) {
    const on = new Set(row.labels ?? []);
    // Maps, not objects: a label may be any name, __proto__ and constructor too
    const used = new Map(), t = new Map(Object.entries(tally()));
    for (const r of all) for (const l of r.labels ?? []) used.set(l, (used.get(l) ?? 0) + 1);
    const rank = (l) => (used.get(l) ?? 0) + (Number(t.get(l)) || 0);
    const seen = [...new Set([...LABELS, ...used.keys(), ...t.keys()])]
      .map((l, i) => [l, i]).sort((a, b) => rank(b[0]) - rank(a[0]) || a[1] - b[1]).map(([l]) => l);   // by use, then seed order
    const note = el("textarea", { placeholder: "Notitie", value: row.note ?? "", rows: 2 });
    const chips = el("div", { className: "fpl-chips" });
    const more = el("input", { placeholder: "ander label…", autocomplete: "off", title: "Een label, of naam/sub" });
    const known = el("datalist", { id: `fpl-labels-${Date.now().toString(36)}` }, ...seen.map((l) => el("option", { value: l })));
    more.setAttribute("list", known.id);
    const render = () => chips.replaceChildren(
      ...[...new Set([...seen.slice(0, 6), ...on])].map((l) => {
        const b = chip(l, on.has(l) ? "is-on" : "");
        b.onclick = () => { on.has(l) ? on.delete(l) : on.add(l); render(); };
        b.tabIndex = 0;
        b.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); b.onclick(); } };
        return b;
      }), more);
    render();
    const add = () => {
      const l = more.value.trim();
      if (!LABEL.test(l)) {
        refuse("label", l,
          "Een label is naam/scope/…: geen spatie, geen leeg stuk");
        return;
      }
      on.add(l); more.value = ""; render(); more.focus();
    };
    more.onkeydown = (e) => { if (e.key === "Enter" && more.value.trim()) { e.preventDefault(); add(); } };
    more.oninput = (e) => { if (!e.inputType || e.inputType === "insertReplacementText") add(); };   // a pick from the list
    const keys = el("div", { className: "fpl-bar fpl-keys" },
      row.id ? button("Verwijder", () => onDone("delete")) : null,
      el("span", { className: "fpl-space" }),
      button("Annuleer", () => onDone(null)),
      el("button", { type: "submit", className: "fpl-go" }, "Bewaar ", el("kbd", {}, "⌘↩")));
    // the head says what the fact is about by its text, never by an id
    const t0 = row.targets?.[0] ?? "", parent = all.find((r) => r.id === t0);
    const said = (parent ? (typeof parent.text === "string"
      ? plain(parent.text) : parent.note || (parent.labels ?? []).join(" "))
      : document.getElementById(t0)?.textContent ?? "")
      .replace(/\s+/g, " ").trim();
    const about = typeof row.text === "string" ? row.text
      : parent ? `Reactie op “${clip(said, 140)}”`
      : said ? clip(said, 140) : named(t0) || "een plek op de pagina";
    const fast = typeof row.text !== "string" && !row.id && quick().length
      ? el("div", { className: "fpl-chips fpl-quick" }, el("small", {}, "snel"),
        ...quick().map((l) => { const b = chip(l, "is-on"); b.tabIndex = 0;
          b.onclick = () => onDone({ note: note.value.trim(), labels: [...new Set([l, ...on])] });
          b.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.stopPropagation(); b.onclick(); } };
          return b; }))
      : null;
    // el, not form.append: append writes a null kid (no quick chips yet) as the text "null"
    const head = el("div", { className: "fpl-head" }, el("span", { className: "fpl-dot" }), el("span", { className: "fpl-q", title: about }, about));
    const form = el("form", { className: "fpl-editor" }, head, fast, note, chips, known, keys);
    form.onsubmit = (ev) => { ev.preventDefault(); onDone({ note: note.value.trim(), labels: [...on] }); };
    form.onkeydown = (e) => {
      if (e.key === "Escape") { e.stopPropagation(); onDone(null); disarm(); }
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) form.requestSubmit();
    };
    setTimeout(() => note.focus(), 0);
    return form;
  }

  /** Save the editor's result on a new row (no id) or one of ours. */
  function save(row, got) {
    const mine = local();
    if (got === "delete") {
      keep(mine.filter((r) => r.id !== row.id));
      return row.id;
    }
    const now = Date.now();
    const done = { ...row, ...got, updatedAt: now };
    delete done.mine;
    const rand = Math.random().toString(36).slice(2, 6);
    const id = row.id || `a-${now.toString(36)}${rand}`;
    if (row.id) mine[mine.findIndex((r) => r.id === row.id)] = done;
    else mine.push({ id, item, commit, by: by() || undefined, targets: [],
      ...done, createdAt: now });
    keep(mine);
    const l = layerOf(done), off = offLayers();
    if (off.delete(l)) { offLayers(off); did("laag", l, `Laag ${l} weer aan`); }
    return id;
  }
  /** A save from the editor: what the reader typed or picked counts toward the ranking and the offer. */
  function typed(row, got) {
    log(got === "delete" ? "verwijder" : "bewaar", save(row, got));
    if (got === "delete") return;
    const t = new Map(Object.entries(tally())), added = (got.labels ?? []).filter((x) => !(row.labels ?? []).includes(x));
    for (const x of added) t.set(x, (Number(t.get(x)) || 0) + 1);
    tally(Object.fromEntries(t));
    offer(added);
  }
  /**
   * Offer a label as a quick chip once three rows of the page carry it
   * (VIKI: the tool recognises a type, the user confirms it). The offer
   * stays until answered, one at a time; a yes and a no are both kept,
   * so a label is asked about until it has an answer, then never again.
   */
  function offer(labels) {
    if (document.querySelector(".fpl-offer")) return;
    const rowsNow = rows();
    const l = labels.find((x) => !quick().includes(x) && !declined().includes(x)
      && rowsNow.filter((r) => r.labels?.includes(x)).length >= 3);
    if (!l) return;
    const say = (yes) => {
      (yes ? quick : declined)([...(yes ? quick() : declined()), l]);
      box.remove();
      if (yes) did("snelchip", l, `${l} is een snelchip`);
      else log("geen snelchip", l);
    };
    const box = el("div", { className: "fpl-annot-ui fpl-toast fpl-offer" }, `Drie keer ${l}: als snelchip op een adres?`,
      button("Ja", () => say(true)), button("Nee", () => say(false)));
    document.body.append(box);
  }

  /** Open the editor for a row, in its card or in a new card at the given height. */
  function edit(row, card, rect) {
    closeEditor();
    const done = (got) => { closeEditor(); if (got) { typed(row, got); draw(); } else layout(); };
    const form = editor(row, done);
    if (wide()) {
      const c = card ?? el("div", { className: "fpl-card mine fpl-editing" });
      c.classList.add("fpl-editing");
      c.replaceChildren(form);
      if (!card) {
        margin.append(c);
        const at = marksOf("draft").length ? reach("draft") : null;   // the selection, lit while written
        if (at) c.dataset.id = "draft";
        c.style.top = `${(at ? at.y - HEAD : rect.top + scrollY) - top0()}px`;
      }
      editing = c;
      makeRoom(c);
      drawLines();
    } else {
      pop.replaceChildren(form);
      pop.hidden = false;
      const r = rect ?? card.getBoundingClientRect();
      pop.style.top = `${scrollY + r.bottom + 8}px`;
      pop.style.left = `${Math.max(8, Math.min(scrollX + r.left, scrollX + innerWidth - pop.offsetWidth - 8))}px`;
      editing = pop;
    }
  }

  /**
   * The card being written is a card in the stack: it stands below the
   * cards above it, and those below move down out of its way, so it never
   * covers one and the order of the lines holds; layout puts them back.
   */
  function makeRoom(c) {
    const cards = [...margin.querySelectorAll(".fpl-card")].filter((o) => o !== c).sort((a, b) => a.offsetTop - b.offsetTop);
    const above = cards.filter((o) => o.offsetTop < c.offsetTop);
    c.style.top = `${Math.max(c.offsetTop, ...above.map((o) => o.offsetTop + o.offsetHeight + GAP))}px`;
    let floor = c.offsetTop + c.offsetHeight + GAP;
    for (const o of cards.filter((o) => !above.includes(o))) {
      const y = Math.max(o.offsetTop, floor);
      o.style.top = `${y}px`;
      floor = y + o.offsetHeight + GAP;
    }
    margin.style.minHeight = `${Math.max(parseFloat(margin.style.minHeight) || 0, floor)}px`;
  }

  let editing = null;
  const open = new Set();   // the spans whose card is open in the spans stand
  function closeEditor() {
    if (!editing) return;
    if (editing === pop) pop.hidden = true;
    else editing.remove();
    editing = null;
    const drafts = marksOf("draft");
    if (drafts.length) { for (const m of drafts) m.replaceWith(...m.childNodes); body.normalize(); }
  }

  /* ---- the margin: cards at the height of their span, lines between ---- */

  const margin = el("div", { className: "fpl-annot-ui fpl-margin" });
  const lines = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  lines.setAttribute("class", "fpl-annot-ui fpl-lines");
  /** A press on a knob: a click arms a pick, as l does; a drag (on touch, after HOLD) carries the knob to the other end. */
  lines.addEventListener("pointerdown", (ev) => {
    const k = ev.target.closest?.(".fpl-knob");
    if (!k || ev.button > 0) return;
    ev.preventDefault();   // no selection starts and no mouse events follow: pointerDone and the pick's click stay out
    if (mode() !== "kantlijn") {
      refuse("verbind", k.dataset.id, LINKS);
      return;
    }
    if (picking) unpick();
    drag = { from: k.dataset.id, id: ev.pointerId, x: ev.clientX, y: ev.clientY, live: false, touch: ev.pointerType === "touch" };
    if (drag.touch) drag.timer = setTimeout(() => drag && !drag.moved && carry(), HOLD);
    for (const [t, f] of DRAG) addEventListener(t, f);
  });
  lines.addEventListener("contextmenu", (ev) => { if (ev.target.closest?.(".fpl-knob")) ev.preventDefault(); });   // a long press carries, it opens no menu
  // a touch on a knob is the knob's: the page does not pan under it (touch-action does not reach into an svg)
  lines.addEventListener("touchstart", (ev) => { if (ev.target.closest?.(".fpl-knob")) ev.preventDefault(); }, { passive: false });
  // a stretch by keys holds while its knob has the focus; the focus gone, it is put back
  lines.addEventListener("focusout", (ev) => {
    const k = ev.target.closest?.(".fpl-knob");
    if (!stretching?.keys || k?.dataset.id !== stretching.id) return;
    const id = stretching.id;
    dropStretch();
    refuse("rek", id, "Niet bewaard: teruggezet");
  });
  for (const [t, on] of [["pointerover", true], ["pointerout", false], ["focusin", true], ["focusout", false]])
    lines.addEventListener(t, (ev) => { const k = ev.target.closest?.(".fpl-knob"); if (k && !editing) hot(on ? k.dataset.id : null); });
  const pop = el("div", { className: "fpl-annot-ui fpl-pop", hidden: true });

  /** The margin's left edge, in the window: RAIL past the text column (main), wherever Quarto's own margin column starts. */
  const rail = () => body.getBoundingClientRect().right + RAIL;
  /** The margin's width: RIGHT from the window's edge, at most a CARD and the gutter's 28px. */
  const reserve = () => Math.min(document.documentElement.clientWidth - RIGHT - rail(), 28 + CARD);
  /** Cards stand in the margin while Quarto shows its column and a card there is NARROW or more; else they fold in. */
  const wide = () => !!column && column.offsetWidth > 120 && reserve() >= 28 + NARROW;
  const top0 = () => margin.getBoundingClientRect().top + scrollY;

  /** Lay every card out: the head, the lost rows, then one card per span in page order. */
  function layout() {
    closeEditor();
    drawBar();
    document.body.classList.toggle("fpl-numbered", mode() !== "lezen");
    for (const c of body.querySelectorAll(".fpl-inline")) c.remove();
    scrunch();
    if (reading?.closest(".fpl-scrunched")) read(null);   // folded away: nothing to read or write on
    heat();
    lens();   // now as well as at the end: an early return below must not leave the lens of another stand
    margin.replaceChildren();
    lines.replaceChildren();
    unbar();
    margin.style.minHeight = "";
    margin.classList.toggle("is-narrow", !wide());
    const full = mode() === "kantlijn";
    if (wide()) {
      column.classList.add("fpl-column");
      if (margin.parentElement !== column) column.append(margin);
      // the margin starts RAIL past the text, under the bar's left edge, and ends where the bar ends, past Quarto's narrow column
      margin.style.width = `${reserve()}px`;
      margin.style.marginLeft = `${rail() - column.getBoundingClientRect().left}px`;
      if (lines.parentElement !== document.body) document.body.append(lines);
    } else {
      column?.classList.remove("fpl-column");
      if (lines.parentElement !== document.body) document.body.append(lines);
      margin.style.width = margin.style.marginLeft = "";
      // under the title block (board K), not above the page's title
      const top = body.querySelector(":scope > #title-block-header");
      const there = top ? margin.previousElementSibling === top
        : margin.parentElement === body;
      if (!there) top ? top.after(margin) : body.prepend(margin);
    }
    if (mode() === "lezen") return;
    const y0 = wide() ? Math.max(0, bar.getBoundingClientRect().bottom + GAP - top0()) : 0;   // the first card clears the bar
    const heads = new Set();   // one card per address: its other rows are readings in it
    const spans = all.filter((r) => (typeof r.text === "string" || addressed(r) || orphan(r) || r.labels?.[0] === "parts") && shows(r) && passes(r) && (full || open.has(r.id)))
      .filter((r) => typeof r.text === "string" || r.labels?.[0] === "parts" ? !partsOf(r.id) : orphan(r) || (!heads.has(r.targets[0]) && heads.add(r.targets[0])));
    if (!spans.length) {
      if (!full) return;
      const h = margin.appendChild(hint());
      if (wide()) h.style.top = `${y0 + 10}px`;   // board A: 22px under the bar's rule, where a card would stand 12px under it
      return;
    }
    const lost = spans.filter((r) => state[r.id] !== "vers" || orphan(r));
    // by the line each draws: a card's order is its line's, so no two lines cross
    const found = spans.map((r) => ({ r, at: reach(r.id) })).filter((x) => x.at).sort((a, b) => a.at.y - b.at.y);
    if (wide()) {
      let y = y0;
      for (const r of lost) {
        const c = cardOf(r);
        margin.append(c);
        c.style.top = `${y}px`;
        y += c.offsetHeight + GAP;
      }
      const base = top0();
      for (const { r, at } of found) {   // at its line, its dot on it; pushed down only, by the card above
        const c = cardOf(r);
        margin.append(c);
        c.dataset.y = at.y;
        y = Math.max(at.y - base - HEAD, y);
        c.style.top = `${y}px`;
        y += c.offsetHeight + GAP;
      }
      margin.style.minHeight = `${y}px`;
      drawLines();
    } else {
      for (const r of lost) margin.append(cardOf(r));
      for (const { r, at: { m } } of found) {
        const c = cardOf(r);
        c.classList.add("fpl-inline");
        (m.closest("p, li, pre, h1, h2, h3, h4, td, th, blockquote") ?? m).after(c);
      }
      drawLines();   // no lines between a span and the card under it: knobs
    }
    lens();   // last: the cards placed inline move the clauses it measures
    fade();
    drawAim();
  }

  /**
   * Where a span meets the gutter, in page coordinates: y, the middle of
   * its last line, where its line leaves and its card's dot stands; top
   * and bottom, its first and last line; end and foot, the end of its
   * last line, where the knob sits on the underline; tail, the mark (or
   * element) that line ends in, a bundle's last piece; and long, a span
   * over three lines or more, which the gutter marks with a bar instead
   * of an underline on every line. A folded span is its band's.
   */
  function reach(id) {
    const ms = anchorsOf(id).map(seen);
    if (!ms.length) return null;
    const rs = ms.flatMap((m) => [...m.getClientRects()].map((r) => Object.assign(r, { m })));
    if (!rs.length) rs.push(Object.assign(ms[0].getBoundingClientRect(), { m: ms[0] }));
    const last = rs.reduce((a, r) => (r.bottom > a.bottom + 1 || (r.bottom > a.bottom - 1 && r.right > a.right) ? r : a));
    const top = Math.min(...rs.map((r) => r.top));
    const rows = rs.map((r) => r.bottom).sort((a, b) => a - b).filter((b, i, a) => !i || b - a[i - 1] > 4).length;
    return { m: ms[0], tail: last.m, y: last.bottom - Math.min(last.height, 24) / 2 + scrollY, top: top + scrollY, bottom: last.bottom + scrollY,
      end: last.right + scrollX, foot: last.bottom - 2 + scrollY, long: rows >= 3 || last.bottom - top > LONG && rs.length === 1 };
  }
  const unbar = () => { for (const m of body.querySelectorAll("mark.fpl-long")) m.classList.remove("fpl-long"); };
  const svg = (tag, attrs, id) => {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    n.dataset.id = id;
    return lines.appendChild(n);
  };

  /**
   * A line from each span to its card, in the span's colour, all in the
   * gutter: a short stub at the text's edge at the span's last line, then
   * one curve to the card's dot. Every line has the same x geometry and
   * the cards stand in the order of their lines, pushed only down, so
   * the lines never cross and never run through the text. A long span
   * has its bar at the stub; the knob sits at the end of every saved span.
   */
  function drawLines() {
    const h = Math.max(document.documentElement.scrollHeight, body.getBoundingClientRect().bottom + scrollY);
    lines.setAttribute("width", document.documentElement.scrollWidth);
    lines.setAttribute("height", h);
    lines.replaceChildren();
    unbar();
    // a narrow screen folds each card in under its block: no line runs
    // to it, but its span keeps the knob, to connect and to stretch
    const gx = gutter(), w = wide();
    const cards = w ? margin.querySelectorAll(".fpl-card[data-id]")
      : body.querySelectorAll(".fpl-card.fpl-inline[data-id]");
    for (const c of cards) {
      const id = c.dataset.id, at = reach(id);
      if (!at) continue;
      const cls = c.classList.contains("mine") ? "mine" : "";
      if (w) svg("path", { d: curve(at.y, c), class: `fpl-line ${cls}` }, id);
      if (w && at.long) {   // narrow, a long span keeps its underline
        for (const m of anchorsOf(id)) if (m.matches("mark.fact")) m.classList.add("fpl-long");
        svg("rect", { x: gx - 1.25, y: at.top, width: 2.5, height: at.bottom - at.top, rx: 1.25, class: `fpl-stretch ${cls}` }, id);
      }
      if (id === "draft") continue;   // a selection being written has nothing to drag yet (board B)
      const knob = svg("circle", { cx: at.end + 3, cy: at.foot, r: 4, class: `fpl-knob ${cls}`, tabindex: 0, role: "button",
        "aria-label": `Bolletje van “${clip(said(id), 40)}”: sleep het naar een andere span, kaart of feit, of druk l; langs de tekst, of met Shift en de pijlen, rek je de span` }, id);
      knob.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "title")).textContent = "Sleep naar een span, kaart of feit om te verbinden, of langs de tekst om te rekken";
    }
    drawAim();
    paintStretch();   // a layout in the middle of a stretch draws it again
  }
  /** The line from a span's stub, at the height y of its last line, to the dot of its card c: the same x geometry for every line. */
  function curve(y, c) {
    const gx = gutter(), cr = c.getBoundingClientRect(), x2 = cr.left + scrollX - 1, y2 = cr.top + scrollY + HEAD, k = Math.max(0, x2 - gx - 6) / 2;
    return `M${gx},${y} h6 C${gx + 6 + k},${y} ${x2 - k},${y2} ${x2},${y2}`;
  }

  /** The span, card and line of one row light up together. */
  function hot(id) {
    if (link) id = link.from;   // while a connect is in flight its start stays lit, whatever the pointer passes
    else id ??= around.id;   // while a card's graph is up, that card is lit
    const group = new Set(id ? groupOf(id) : []);   // a piece lights its whole, the whole its pieces
    // a card folded in under its block (a narrow screen) is in the body
    for (const n of [...body.querySelectorAll("mark.fact, .is-hot, .fpl-card"),
      ...margin.querySelectorAll(".fpl-card"), ...lines.children])
      n.classList.toggle("is-hot", group.has(n.dataset.id));
    if (id) for (const e of anchorsOf(id)) if (!e.matches("mark.fact")) e.classList.add("is-hot");
    for (const n of body.querySelectorAll(".fpl-coref")) n.classList.remove("fpl-coref");
    if (id) for (const t of corefOf(id)) for (const e of [...marksOf(t), document.getElementById(t)])
      if (e && body.contains(e)) e.classList.add("fpl-coref");
  }
  /** The other ids a coref row (in a shown layer) groups with an id. */
  function corefOf(id) {   // the whole chain: sets sharing a member are one referent
    const sets = all.filter((r) => r.labels?.[0] === "coref" && shows(r) && Array.isArray(r.targets));
    const got = new Set([id]);
    for (let grew = true; grew;) {
      grew = false;
      for (const r of sets) if (r.targets.some((t) => got.has(t)))
        for (const t of r.targets) if (!got.has(t)) { got.add(t); grew = true; }
    }
    got.delete(id);
    return got;
  }

  /* ---- the tfa lens: t, c, f on clauses, and the resumes arcs ---- */

  const TFA = ["tfa/t", "tfa/c", "tfa/f"];
  /** Mark each clause with its value and draw the arcs; nothing in Lezen or with the tfa layer off. */
  /**
   * The coref chains in the layers shown: sets that share a member are
   * one chain (union-find), each chain its members in page order, the
   * chains numbered by where their first member stands.
   */
  function chains() {
    const up = new Map(), find = (x) => { while (up.get(x) !== x) { up.set(x, up.get(up.get(x))); x = up.get(x); } return x; };
    for (const r of all.filter((x) => x.labels?.[0] === "coref" && shows(x) && Array.isArray(x.targets)))
      for (const t of r.targets) { if (!up.has(t)) up.set(t, t); up.set(find(t), find(r.targets[0])); }
    const groups = new Map();
    for (const x of up.keys()) groups.set(find(x), [...(groups.get(find(x)) ?? []), x]);
    const at = (id) => anchorsOf(id)[0] ?? place(id);   // page order is document order; a member not on the page goes last
    const order = (a, b) => {
      const x = at(a), y = at(b);
      if (!x || !y) return !x - !y;
      return x === y ? 0 : x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    };
    return [...groups.values()].map((g) => g.sort(order)).sort((a, b) => order(a[0], b[0]));
  }
  /** Number each member of each chain on the page; off in Lezen or with the coref layer off. */
  function chainMarks() {
    for (const e of body.querySelectorAll(".fpl-chain")) e.remove();
    if (mode() === "lezen" || offLayers().has("coref")) return;
    const got = new Map();   // element -> its chain numbers
    chains().forEach((g, i) => {
      for (const id of g) {
        const e = anchorsOf(id).at(-1) ?? place(id);   // a span split in marks, a whole of pieces, an address: its last anchor
        if (e && body.contains(e)) got.set(e, [...(got.get(e) ?? []), i + 1]);
      }
    });
    // a number of its own (fpl-annot-ui: no text of the page), so no pseudo-element of the page is taken over
    for (const [e, ns] of got) {
      const sup = el("sup", { className: "fpl-annot-ui fpl-chain" }, ns.join(","));
      e.matches(".fpl-p") ? e.append(sup) : e.after(sup);
    }
  }
  function lens() {
    chainMarks();
    for (const e of body.querySelectorAll("[data-tfa]")) { delete e.dataset.tfa; delete e.dataset.tfaRow; }
    document.querySelector(".fpl-arcs")?.remove();
    if (mode() === "lezen" || offLayers().has("tfa")) return;
    for (const r of all) {
      const v = TFA.includes(r.labels?.[0]) && r.labels[0], e = v && document.getElementById(r.targets?.[0]);
      if (e && body.contains(e)) { e.dataset.tfa = v.slice(4); e.dataset.tfaRow = r.id; }
    }
    const arcs = all.filter((r) => r.labels?.[0] === "resumes" && r.targets?.length === 2 && shows(r))
      .map((r) => [r, ...r.targets.map((t) => document.getElementById(t))])
      .filter(([, a, b]) => a && b && body.contains(a) && body.contains(b) && seen(a) !== seen(b));   // one band: no arc
    if (!arcs.length) return;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("fpl-arcs");
    const H = document.documentElement.scrollHeight;
    svg.setAttribute("width", "100%"); svg.setAttribute("height", H);
    const left = Math.max(body.getBoundingClientRect().left + scrollX - 8, 44);
    for (const [r, a, b] of arcs) {
      const [ya, yb] = [a, b].map((e) => { const r = seen(e).getBoundingClientRect(); return r.top + scrollY + r.height / 2; });
      const bow = Math.min(40, 8 + Math.abs(ya - yb) / 12);
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M ${left} ${ya} C ${left - bow} ${ya}, ${left - bow} ${yb}, ${left} ${yb}`);
      path.dataset.id = r.id;
      path.append(Object.assign(document.createElementNS("http://www.w3.org/2000/svg", "title"),
        { textContent: `${r.targets[0]} resumes ${r.targets[1]}${r.mine ? " (klik: weg)" : ""}` }));
      if (r.mine) path.onclick = () => {
        keep(local().filter((x) => x.id !== r.id));
        draw();
        did("verwijder", r.id, `${r.id} weg`);
      };
      svg.append(path);
    }
    document.body.append(svg);
  }
  /** Alt-click a clause: its value goes t, c, f, none; one row of this browser per clause holds it. */
  function cycle(id) {
    const marks = (r) => r.targets?.[0] === id && TFA.includes(r.labels?.[0]);
    const mine = local(), at = mine.findIndex(marks);
    const filed = sidecar.some(marks);   // the sidecar's value is cleared there, not here
    const cur = [...all].reverse().find(marks)?.labels[0] ?? null;
    const next = TFA[(TFA.indexOf(cur) + 1)] ?? (filed ? TFA[0] : null);
    if (at >= 0) mine.splice(at, 1);
    keep(mine);
    if (next) save({ targets: [id] }, { note: "", labels: [next] });
    draw();
    did("tfa", id, next ? `${id}: ${next}` : `${id}: geen tfa`);
  }

  /* ---- bands: blocks folded into a seam, the page one scroll ---- */

  const SCRUNCH = "fpl-annot:scrunch:" + item;
  /**
   * The bands, oldest first, each the ids of its first and last block:
   * the URL's ?scrunch= when it has one, else this browser's for the page
   * (a single id is a band of one block). scrunch() keeps it settled:
   * resolved, each pair in page order, no two overlapping.
   */
  let bands = (() => {
    let s = new URLSearchParams(location.search).get("scrunch");
    if (s == null) try { s = localStorage.getItem(SCRUNCH); } catch { /* no storage */ }
    return (s || "").split(",").filter(Boolean).map((p) => { const [a, b = a] = p.split(".."); return [a, b]; });
  })();

  /** The addressed blocks (essay.lua's fpl-p), in page order: a band's ends are two of them. */
  const units = () => [...body.querySelectorAll(".fpl-p")];
  /** Every block of the page, addressed or not (headings, lists, tables), in page order. */
  const leaves = () => [...body.querySelectorAll(":scope > *, section > *")]
    .filter((e) => !e.matches("section, script, style, .fpl-annot-ui, .fpl-card"));
  /** The band a folded element is in, or null; seen() is where an element shows. */
  const bandOf = (e) => {
    const l = e.closest(".fpl-scrunched");
    return l && body.querySelector(`.fpl-band[data-k="${l.dataset.band}"]`);
  };
  const seen = (e) => bandOf(e) ?? e;
  /** A block's address as the page numbers it: 1.2.1.3 §4, or §5:C for code. */
  const addr = (u) => `${u.dataset.addr ?? ""} §${u.dataset.n}${u.dataset.kind === "C" ? ":C" : ""}`.trim();

  /** The bands as [first, last] indices into us; unresolved ones dropped, one overlapped merged into the later. */
  function settle(us) {
    const out = [];
    for (const ends of bands) {
      let [i, j] = ends.map((id) => us.indexOf(document.getElementById(id)?.closest(".fpl-p"))).sort((x, y) => x - y);
      if (i < 0) continue;
      for (let k = out.length - 1; k >= 0; k--) {
        const [p, q] = out[k];
        if (p <= j && i <= q) { i = Math.min(i, p); j = Math.max(j, q); out.splice(k, 1); }
      }
      out.push([i, j]);
    }
    return out;
  }

  /**
   * Draw the bands (board G, feedback 3). Every element from a band's
   * first block to its last is hidden (fpl-scrunched, data-band = the
   * band's index) and a seam stands before the first of them: a button
   * of SEAM pixels, two hairlines across the column and at their left
   * its range, "1.2.1.3 §9 – 1.2.1.4 §7 · 25 blokken". However much it
   * folds, a seam is that high, so a fold never leaves a field of lines
   * to read and both ends of a long jump fit in one view. A click (or
   * Enter) opens it; under the mouse or the focus it darkens and a tip
   * under it says how to fold further, and nothing moves.
   */
  function scrunch() {
    for (const b of body.querySelectorAll(".fpl-band")) b.remove();
    const us = units(), ls = leaves(), got = settle(us);
    bands = got.map(([i, j]) => [us[i].id, us[j].id]);
    for (const l of ls) l.classList.remove("fpl-scrunched");
    got.forEach(([i, j], k) => {
      const fold = ls.slice(ls.indexOf(us[i]), ls.indexOf(us[j]) + 1);
      const n = j - i + 1, to = j > i ? ` – ${addr(us[j])}` : "";
      const range = `${addr(us[i])}${to} · ${n} blok${n > 1 ? "ken" : ""}`;
      const seam = el("button", {
        type: "button", className: "fpl-annot-ui fpl-band",
        ariaExpanded: "false",
        ariaLabel: `Ingevouwen: ${range}. Klik om te openen.`,
        onclick: () => setBands(bands.filter((_, x) => x !== k)) },
      el("span", { className: "fpl-seam" }, ico("shift"), range),
      el("span", { className: "fpl-tip", ariaHidden: "true" },
        "Klik opent · ", el("kbd", {}, "Shift"),
        " + scroll boven de tekst vouwt verder, terug scrollen opent"));
      Object.assign(seam.dataset, { k, range });
      for (const l of fold) { l.classList.add("fpl-scrunched"); l.dataset.band = k; }
      fold[0].before(seam);
    });
  }

  /** Write the bands to the URL (?scrunch=a..b,c..d, kept readable) and to this browser. */
  let persisted = null;   // the bands last kept, so a fold is logged once
  function persist() {
    const s = bands.map(([a, b]) => (a === b ? a : `${a}..${b}`)).join(","), u = new URL(location.href);
    if (s) u.searchParams.set("scrunch", s); else u.searchParams.delete("scrunch");
    u.search = u.search.replace(/%2[CF]/gi, decodeURIComponent);
    history.replaceState(history.state, "", u);
    try { if (s) localStorage.setItem(SCRUNCH, s); else localStorage.removeItem(SCRUNCH); } catch { /* no storage */ }
    if (s !== persisted && (persisted !== null || s)) log("vouw", s || null);
    persisted = s;
  }
  /** Take a new list of bands: lay the page out with them, then keep them. */
  function setBands(list) { bands = list; layout(); persist(); }

  /** Where an id shows on the page: a row's span, else the element with that id; null when neither. */
  const place = (id) => {
    const e = anchorsOf(id)[0] ?? document.getElementById(id);
    return e && body.contains(e) ? e : null;
  };
  /**
   * Toon beide: fold every block between a row's span and another place
   * into a band, so both are in view. A band over either end opens, also
   * when nothing lies between to fold; bands between the two join the
   * new one (settle).
   */
  function both(from, to) {
    const us = units();
    const [i, j] = [from, to].map((id) => us.indexOf(place(id)?.closest(".fpl-p"))).sort((x, y) => x - y);
    if (i < 0) { refuse("toon beide", to, "Niet op deze pagina"); return; }
    const covers = (b, x) => { const [p, q] = b.map((id) => us.indexOf(document.getElementById(id))); return p <= x && x <= q; };
    const kept = bands.filter((b) => !covers(b, i) && !covers(b, j));
    const fold = j - i >= 2 ? [[us[i + 1].id, us[j - 1].id]] : [];
    if (!fold.length && kept.length === bands.length) {
      refuse("toon beide", to, "Ze staan al samen in beeld");
      return;
    }
    setBands([...kept, ...fold]);
    (fold.length ? bandOf(us[i + 1]) : us[i]).scrollIntoView({ block: "center", behavior: "smooth" });
  }

  /**
   * Vouw tot de spans, in the menu (LiquidText's merged highlights): fold
   * every run of blocks further than context blocks from a span the filter
   * lets through and the query finds, so those spans stand together with
   * their surroundings. Chosen again while the bands are just that, it
   * opens them all; a new context refolds them at once.
   */
  const CONTEXT = "fpl-annot:context";
  let context = (() => { try { const n = localStorage.getItem(CONTEXT); return n != null && /^[0-3]$/.test(n) ? +n : 1; } catch { return 1; } })();
  /**
   * The runs of blocks further than n blocks from a drawn span the query
   * did not fade, as bands; null when no such span is drawn.
   */
  function runsNear(n) {
    const us = units(), near = new Set();
    for (const m of body.querySelectorAll("mark.fact:not(.fpl-faded)")) {
      const i = us.indexOf(m.closest(".fpl-p"));
      if (i >= 0) for (let t = i - n; t <= i + n; t++) near.add(t);
    }
    if (!near.size) return null;
    const runs = [];
    for (let i = 0; i < us.length; i++)
      if (!near.has(i)) { const a = i; while (i + 1 < us.length && !near.has(i + 1)) i++; runs.push([us[a].id, us[i].id]); }
    return runs;
  }
  /** Whether a list of bands (the bands now, by default) is just these runs. */
  const folded = (runs, list = bands) => !!runs && runs.length === list.length
    && runs.every(([a, b], x) => a === list[x][0] && b === list[x][1]);
  const NOSPAN = () => (mode() === "lezen"
    ? "Lezen onderstreept niets: kies Spans of Kantlijn"
    : "Geen span in beeld om tot te vouwen");
  function squeeze() {
    const runs = runsNear(context);
    if (!runs) { refuse("vouw tot spans", null, NOSPAN()); return; }
    const same = folded(runs);
    setBands(same ? [] : runs);
    did("vouw tot spans", null, same ? "Alles open" : "");
  }
  function setContext(n) {
    const was = folded(runsNear(context));
    context = n;
    try { localStorage.setItem(CONTEXT, n); } catch { /* no storage */ }
    log("context", String(n));
    if (was) setBands(runsNear(n));
  }

  /**
   * The fold of a gesture, from the moment it began (g) and how far it has
   * gone (s, pixels; less than 0 back). On: g.base with the blocks around
   * g.mid folded, the block itself first and then one more a side by
   * turns, as many as s covers of their heights g.h (a block already
   * folded costs nothing, so a fold grows through a band), none at or
   * past the bounds g.i and g.j. Back past OPEN: g.base without the bands
   * g.open. A pinch and a Shift+wheel both fold so.
   */
  const OPEN = 40;
  function fold(g, s) {
    if (s < -OPEN && g.open.length)
      return g.base.filter((b) => !g.open.includes(b));
    if (s <= 0 || g.mid < 0) return g.base;
    const { us, h, i, j } = g;
    let a = g.mid, b = a - 1, sum = 0;   // [a, b], empty, grows by turns
    const fits = (t) => t > i && t < j && sum + h[t] <= s;
    for (let left = false; ; left = !left) {
      const t = left ? a - 1 : b + 1;
      if (fits(t)) { sum += h[t]; left ? a-- : b++; }
      else if (!fits(left ? b + 1 : a - 1)) break;
    }
    return a <= b ? [...g.base, [us[a].id, us[b].id]] : g.base;
  }
  /**
   * What folding each block takes away as the page shows now: down to the
   * next block shown, headings and tables between included; 0 when folded.
   */
  function heights(us) {
    const r = us.map((u) => (u.classList.contains("fpl-scrunched")
      ? null : u.getBoundingClientRect()));
    return r.map((x, t) => {
      const n = r.findIndex((y, u) => u > t && y);
      return !x ? 0 : n < 0 ? x.height : Math.max(0, r[n].top - x.top);
    });
  }
  /** The first block shown whose bottom is at or below window y, or -1. */
  const blockAt = (us, y) => us.findIndex((u) =>
    !u.classList.contains("fpl-scrunched")
    && u.getBoundingClientRect().bottom >= y);

  /**
   * Pinch (the paper's gesture): two fingers on the text, drawn together,
   * fold the blocks between them from the middle outward, as many whole
   * blocks as the fingers have closed by; drawn apart over a band, they
   * open it. The fold shows while the fingers move and is kept when they
   * lift. Only a two-finger move is cancelled, so one finger still
   * scrolls, and the page does not zoom under a pinch.
   */
  let pinch = null;
  const ys = (ts) => [...ts].map((t) => t.clientY).sort((a, b) => a - b);
  function pinchMove(ev) {
    if (!pinch || ev.touches.length !== 2) return;
    ev.preventDefault();
    const [y0, y1] = ys(ev.touches), next = fold(pinch, pinch.d0 - (y1 - y0));
    const key = JSON.stringify(next);
    if (key !== pinch.key) { pinch.key = key; bands = next; layout(); }
  }
  function pinchEnd(ev) {
    if (!pinch || ev.touches.length > 1) return;
    for (const x of pinch.at) for (const [t, f] of PINCH) x.removeEventListener(t, f);
    if (pinch.key) persist();
    pinch = null;
  }
  /** On the elements the fingers came down on: a band is drawn anew under them, and an event on a detached element never reaches body. */
  const PINCH = [["touchmove", pinchMove], ["touchend", pinchEnd], ["touchcancel", pinchEnd]];
  body.addEventListener("touchstart", (ev) => {
    if (pinch) pinchEnd({ touches: [] });
    if (ev.touches.length !== 2 || [...ev.touches].some((t) => t.target.closest?.(".fpl-card, .fpl-topbar, .fpl-menu"))) return;
    const [y0, y1] = ys(ev.touches), us = units();
    const i = blockAt(us, y0), j1 = blockAt(us, y1);
    const j = j1 < 0 ? us.length : j1;
    const between = [...body.querySelectorAll(".fpl-band")].filter((b) => { const r = b.getBoundingClientRect(); return r.bottom >= y0 && r.top <= y1; });
    // i < 0: the fingers are below the last block
    const mid = i >= 0 && j - i > 1 ? Math.floor((i + j) / 2) : -1;
    pinch = { d0: y1 - y0, base: bands, us, i, j, mid, h: heights(us),
      open: between.map((b) => bands[+b.dataset.k]), key: "", at: new Set([...ev.touches].map((t) => t.target)) };
    for (const x of pinch.at) for (const [t, f] of PINCH) x.addEventListener(t, f, { passive: false });
  }, { passive: true });

  /**
   * Shift+wheel over the text, LiquidText's gesture at a desk (board G,
   * feedback 3): turned on, the wheel folds the blocks around the pointer,
   * the block under it first (fold), as far as it has turned; turned back
   * past OPEN, it opens the band under the pointer, else the nearest one
   * in the window. With a filter or a query on, the same turn folds to
   * the spans they let through, at the menu's Context (Vouw tot de spans),
   * and back opens what that folded. The fold shows while the wheel turns,
   * what was under the pointer stays under it, and IDLE ms without a turn
   * keep it (the URL and this browser). macOS sends a Shift+wheel as a
   * sideways turn, so the larger delta counts; Shift+wheel over a wide
   * code block folds rather than scrolls it, a sideways swipe still does.
   * A turn that can do nothing says why, once.
   */
  const IDLE = 250;
  let wheel = null;
  const filtering = () => !!found || hidden().size + offLayers().size > 0;
  /** A wheel gesture begins at window height y: what it folds from. */
  function wheelStart(y) {
    const us = units(), seams = [...body.querySelectorAll(".fpl-band")];
    const box = (b) => b.getBoundingClientRect();
    const dist = (b) => Math.max(0, box(b).top - y, y - box(b).bottom);
    const near = seams
      .filter((b) => box(b).bottom > 0 && box(b).top < innerHeight)
      .sort((a, b) => dist(a) - dist(b))[0];
    const over = near && dist(near) === 0 ? bands[+near.dataset.k] : null;
    const mid = over
      ? us.indexOf(document.getElementById(over[0])) : blockAt(us, y);
    return { base: bands, us, i: -1, j: us.length, mid, h: heights(us),
      s: 0, key: JSON.stringify(bands), said: false,
      open: near ? [bands[+near.dataset.k]] : [],
      runs: filtering() ? runsNear(context) : undefined };
  }
  /** The bands a wheel gesture asks for now, or a reason it can do nothing. */
  function wheelFold(g) {
    const to = g.runs !== undefined;   // a filter or a query: to its spans
    if (to && g.s > OPEN) return g.runs ?? NOSPAN();
    if (to && g.s < -OPEN && folded(g.runs, g.base)) return [];
    if (to && g.s > 0) return g.base;
    if (g.s > 0 && g.mid < 0)
      return "Onder het laatste blok valt niets te vouwen";
    if (g.s < -OPEN && !g.open.length) return "Geen band in beeld om te openen";
    return fold(g, g.s);
  }
  function wheelEnd() {
    if (wheel && wheel.key !== JSON.stringify(wheel.base)) persist();
    wheel = null;
  }
  body.addEventListener("wheel", (ev) => {
    if (!ev.shiftKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.target.closest?.(".fpl-card, .fpl-inline")) return;
    ev.preventDefault();
    const d = Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
    wheel ??= wheelStart(ev.clientY);
    clearTimeout(wheel.t);
    wheel.t = setTimeout(wheelEnd, IDLE);
    wheel.s += d * [1, 16, innerHeight][ev.deltaMode];   // pixels, lines, pages
    const next = wheelFold(wheel);
    if (typeof next === "string") {   // nothing to do: why, once a gesture
      if (!wheel.said) refuse("vouw", null, next);
      wheel.said = true;
      return;
    }
    const key = JSON.stringify(next);
    if (key === wheel.key) return;
    // what was under the pointer stays under it: the block it folds from
    const at = wheel.us[wheel.mid];
    const y = at && seen(at).getBoundingClientRect().top;
    wheel.key = key;
    bands = next;
    layout();
    if (at) scrollBy(0, seen(at).getBoundingClientRect().top - y);
  }, { passive: false });

  /* ---- density: how many rows each block carries, in its gutter ---- */

  /** The row a thread hangs from: a fact or reply followed up its first target to a span's or an address's row. */
  function trunk(r, been = new Set()) {
    const up = typeof r.text !== "string" && all.find((x) => x.id === r.targets?.[0]);
    return up && !been.has(r.id) ? trunk(up, been.add(r.id)) : r;
  }

  /**
   * Shade each block's gutter bar by the rows that hang from it: a span's
   * row, the facts about it and their replies, all depths, of the threads
   * whose root the filter lets through (as layout draws them). A folded block counts toward its band's
   * bar. The three greys are cut at the terciles of the page's non-zero
   * block counts, so a shade ranks a block against this page, not against
   * a fixed scale; a band's sum may pass the top cut and is then darkest.
   * Off in Lezen, which shows nothing.
   */
  function heat() {
    for (const h of body.querySelectorAll(".fpl-heat")) h.remove();
    if (mode() === "lezen") return;
    const per = new Map();
    for (const r of all) {
      const t = trunk(r), b = shows(r) && layerOf(r) !== "tfa" && passes(t) && anchorsOf(t.id)[0]?.closest(".fpl-p");   // passes: as the stand draws it
      if (b) per.set(b, (per.get(b) ?? 0) + 1);
    }
    const c = [...per.values()].sort((x, y) => x - y), cut = (q) => c[Math.ceil(q * c.length) - 1];
    const [t1, t2] = [cut(1 / 3), cut(2 / 3)], where = new Map();
    for (const [b, n] of per) where.set(seen(b), (where.get(seen(b)) ?? 0) + n);
    for (const [at, n] of where) {
      const bar = el("span", { className: "fpl-annot-ui fpl-heat", title: `${n} ${n === 1 ? "rij" : "rijen"}` });
      bar.dataset.level = n <= t1 ? 1 : n <= t2 ? 2 : 3;
      at.prepend(bar);
    }
  }

  /* ---- close reading: a cursor on one sentence, moved by keystroke ---- */

  let reading = null;   // the sentence the cursor is on (fpl-here), or null
  /**
   * Put the cursor on a sentence, or take it away (null); the hash names
   * it. The page scrolls only when the sentence has left the window (or
   * slid under a fixed bar at its top, EDGE pixels), and then brings it to
   * the middle, so the next steps read on without scrolling.
   */
  const EDGE = 64;
  function read(s) {
    mark(s);
    history.replaceState(history.state, "", s ? `#${s.id}` : location.pathname + location.search);
    const r = s?.getBoundingClientRect();
    if (r && (r.top < EDGE || r.bottom > innerHeight)) s.scrollIntoView({ block: "center" });
  }
  /** The cursor alone moved, hash and scroll left as they are. */
  function mark(s) {
    reading?.classList.remove("fpl-here");
    reading = s;
    s?.classList.add("fpl-here");
  }
  /**
   * The cursor follows the hash wherever it changes: at load, on in-page
   * navigation (hashchange), after a click on a number (replaceState,
   * which fires nothing). A hash that is not a showing sentence takes the
   * cursor away and stays.
   */
  function sync() {
    const e = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    mark(e?.matches(".fpl-s") && !e.closest(".fpl-scrunched") ? e : null);
  }
  addEventListener("hashchange", sync);
  /**
   * The cursor to the next (d = 1) or previous (d = -1) sentence that
   * shows: folded ones are passed over, so a band is jumped. Without a
   * cursor (or with one in a fold) it starts at the first sentence in view.
   */
  function step(d) {
    const ss = [...body.querySelectorAll(".fpl-s")].filter((s) => !s.closest(".fpl-scrunched"));
    const i = ss.indexOf(reading);
    if (i < 0) read(ss.find((s) => s.getBoundingClientRect().bottom > 0) ?? ss.at(-1) ?? null);
    else read(ss[Math.max(0, Math.min(ss.length - 1, i + d))]);
  }

  /* ---- selecting and clicking ---- */

  const WORD = /[\p{L}\p{N}_]/u;
  /**
   * A selection's [s, e) grown to whole words: a quote never starts or
   * ends inside a word ("he module … a docst" is "The module … a
   * docstring"), as a reader means it and as the knob stretches.
   */
  function whole(ix, [s, e]) {
    const w = (i) => WORD.test(ix.flat[i] ?? "");
    if (s >= e) return [s, e];
    while (s > 0 && w(s - 1) && w(s)) s--;
    while (e < ix.flat.length && w(e - 1) && w(e)) e++;
    return [s, e];
  }
  /** The shown index of a range's first character and past its last. */
  function bounds(ix, range) {
    const first = (after) => {
      let lo = 0, hi = ix.from.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1, [n, o] = ix.from[mid];
        if (range.comparePoint(n, o) >= after) hi = mid; else lo = mid + 1;
      }
      return lo;
    };
    let s = first(0), e = first(1);
    while (s < e && ix.flat[s] === " ") s++;
    while (e > s && ix.flat[e - 1] === " ") e--;
    return [s, e];
  }

  /** A selection in the body opens the editor for a new quote row; a click on a mark lights or edits it. */
  function pointerDone(ev) {
    if (picking || performance.now() - picked < 500) return;   // a pick owns its whole gesture
    const target = ev.target instanceof Element ? ev.target : null;
    if (target?.closest(".fpl-annot-ui")) return;
    const sel = getSelection();
    if (ev.altKey) { if (sel.rangeCount && !sel.isCollapsed) piece(sel); return; }   // Alt: a piece, or an Alt-click
    if (!sel.rangeCount || sel.isCollapsed) {
      const m = target?.closest("mark.fact");
      if (!m) { if (editing) { closeEditor(); layout(); } return; }
      const own = all.find((r) => r.id === m.dataset.id), row = wholeOf(own.id) ?? own;   // a piece answers for its whole
      if (mode() !== "kantlijn") {
        open.has(row.id) ? open.delete(row.id) : (open.clear(), open.add(row.id));
        layout();
        hot(row.id);
        return;
      }
      hot(row.id);
      const card = margin.querySelector(`.fpl-card[data-id="${CSS.escape(row.id)}"]`);
      if (row.mine) { edit(row, card, m.getBoundingClientRect()); hot(row.id); }
      else if (card && wide()) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
      return;
    }
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) return;
    // the copy is untouched; the toast says why no span
    if (mode() !== "kantlijn") {
      const here = mode() === "lezen" ? "Lezen" : "Spans";
      refuse("selectie", null,
        `In ${here} maakt een selectie geen span: kies Kantlijn (a)`);
      return;
    }
    if ([...body.querySelectorAll(".fpl-scrunched")].some((l) => range.intersectsNode(l))) {
      // shown() keeps folded text (the quote finder needs it whole), so the quote would hold what was never seen
      sel.removeAllRanges();
      refuse("selectie", null,
        "De selectie loopt door een band: open die eerst");
      return;
    }
    const ix = shown(), [s, e] = whole(ix, bounds(ix, range));
    if (s >= e) return;
    const seed = { text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s),
      suffix: ix.flat.slice(e, e + AROUND) };
    const at = range.getBoundingClientRect();
    sel.removeAllRanges();
    wrap(ix, s, e, { id: "draft", mine: true });   // the span stays lit while its fact is written
    edit(seed, null, at);
    hot("draft");
  }
  let pieces = [];   // the span rows Alt-selected so far, bundled by Enter
  let pieced = 0;    // when the last piece was taken
  let adding = null; // the id of a parts row of ours the next pieces join, armed by "Deel erbij…"
  /** Esc, Enter, the editor's Esc or leaving Kantlijn: the armed parts row takes no more pieces. */
  function disarm() {
    if (!adding) return;
    const n = local().find((r) => r.id === adding)?.targets.length ?? 0;
    did("breek af", adding, `Gestopt: ${adding} heeft ${n} delen`);
    adding = null;
  }
  /** "Deel erbij…": the next Alt-selects join this parts row, until Esc or Enter. */
  function arm(id) {
    if (mode() !== "kantlijn") { refuse("deel erbij", id, PARTS); return; }
    if (picking) unpick();
    const loose = pieces.length ? ": de losse delen blijven losse spans" : "";
    pieces = [];
    adding = id;
    did("deel erbij", id, `Delen erbij voor ${id}${loose} · ${NEXT}`);
  }
  /** Alt-select: the selection becomes a span row of this browser, the next piece of a discontinuous span. */
  function piece(sel) {
    pieced = performance.now();   // this gesture is a selection, whatever comes of it: its click is no Alt-click
    if (mode() !== "kantlijn") {
      sel.removeAllRanges();
      refuse("deel", null, PARTS);
      return;
    }
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) {
      sel.removeAllRanges();
      return;
    }
    if ([...body.querySelectorAll(".fpl-scrunched")]
      .some((l) => range.intersectsNode(l))) {
      sel.removeAllRanges();
      refuse("deel", null, "Het deel loopt door een band: open die eerst");
      return;
    }
    const ix = shown(), [s, e] = whole(ix, bounds(ix, range));
    sel.removeAllRanges();
    if (s >= e) return;
    const pr = adding && local().find((r) => r.id === adding);
    if (adding && !pr) adding = null;   // the bundle went meanwhile: this starts a new one
    // a fresh row is in no bundle, so the test is by place: text a piece of a whole already covers
    const hit = all.filter((r) => r.labels?.[0] === "parts" && !partsOf(r.id) && (shows(r) || r.id === pr?.id)).filter((p) => leavesOf(p).some((t) => {
      const r = all.find((x) => x.id === t), at = typeof r?.text === "string" && find(ix, r);
      return Array.isArray(at) && at[0] < e && s < at[1];
    }));
    const mine = pr ? (wholeOf(pr.id) ?? pr).id : null;   // the selection touches the bundle being made: refused, whatever else it touches
    if (hit.some((h) => h.id === mine || pieces.includes(h.id))) {
      refuse("deel", pr?.id ?? null,
        `Dat is al een deel van ${pr?.id ?? "deze bundel"}`);
      return;
    }
    if (hit.length > 1) {
      refuse("deel", null, `Dat loopt over ${hit.length} bundels: kies er één`);
      return;
    }
    const owner = hit[0];
    if (owner) {   // a piece of a piece: the whole that text is in joins as one piece
      if (pr) {
        save(pr, { targets: [...pr.targets, owner.id] });
        draw();
        const k = pr.targets.length + 1;
        did("deel", owner.id,
          `Bundel ${owner.id} is deel ${k} van ${pr.id} · ${NEXT}`);
        return;
      }
      pieces.push(owner.id);
      draw();
      const more = pieces.length > 1 ? " · Enter bundelt" : "";
      did("deel", owner.id,
        `Deel ${pieces.length}: bundel ${owner.id}${more} · ${NEXT}`);
      return;
    }
    save({ text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s), suffix: ix.flat.slice(e, e + AROUND) },
      { note: "", labels: [] });
    const id = local().at(-1).id;
    if (pr) {
      save(pr, { targets: [...pr.targets, id] });
      draw();
      did("deel", id, `Deel ${pr.targets.length + 1} van ${pr.id} · ${NEXT}`);
      return;
    }
    pieces.push(id);
    draw();
    const more = pieces.length > 1 ? ": Enter bundelt" : "";
    did("deel", id, `Deel ${pieces.length}${more} · ${NEXT}`);
  }
  /** Enter: the pieces become one span, a parts row, and the editor opens for a fact about it. */
  function bundle() {
    const live = new Set([...local().filter((r) => typeof r.text === "string"), ...all.filter((r) => r.labels?.[0] === "parts" && !partsOf(r.id))].map((r) => r.id));
    const ps = pieces.filter((id) => live.has(id));   // a piece deleted meanwhile is no piece
    pieces = [];
    if (ps.length < 2) {
      refuse("bundel", null, "Minder dan twee delen over: niets gebundeld");
      draw();
      return;
    }
    const id = save({ targets: ps }, { note: "", labels: ["parts"] });
    log("bundel", id);
    draw();
    const m = anchorsOf(id)[0];
    edit({ targets: [id] }, null, (m ?? body).getBoundingClientRect());
  }

  /** The address under a click on a number drawn before a block or sentence, or null. */
  function numberAt(ev) {
    const t = ev.target instanceof Element ? ev.target : null;
    const unit = t?.closest(".fpl-s, .fpl-p");
    if (!unit || !document.body.classList.contains("fpl-numbered")) return null;
    const before = getComputedStyle(unit, "::before");
    const w = parseFloat(before.width) || 0;
    if (!w || before.display === "none") return null;
    const r = unit.getClientRects()[0];
    if (!r) return null;
    if (unit.classList.contains("fpl-p")) {   // the number stands in the left gutter
      const gap = parseFloat(before.marginRight) || 0;
      return ev.clientX < r.left - gap && ev.clientX > r.left - gap - w - 4 ? unit.id : null;
    }
    return ev.clientX >= r.left - 2 && ev.clientX <= r.left + w + 2 && ev.clientY >= r.top && ev.clientY <= r.bottom ? unit.id : null;
  }
  /** Alt-click a clause cycles its tfa value; Alt-Shift-click arms a resumes pick from it. */
  document.addEventListener("click", (ev) => {
    if (!ev.altKey || picking || mode() === "lezen" || performance.now() - pieced < 500) return;
    const c = ev.target.closest?.(".fpl-c[id]") ?? ev.target.closest?.(".fpl-s[id]");   // a one-clause sentence has no .fpl-c
    if (!c || !body.contains(c)) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    if (!ev.shiftKey) { cycle(c.id); return; }
    adding = null;   // one armed gesture at a time
    picking = { from: c.id, kind: "resumes" };
    document.body.classList.add("fpl-picking");
    did("kies eind", c.id,
      `Klik de eerdere bijzin die ${c.id} weer opneemt. Esc breekt af.`);
  }, true);
  document.addEventListener("click", (ev) => {
    const id = numberAt(ev);
    if (!id) return;
    ev.preventDefault();
    getSelection()?.removeAllRanges();
    history.replaceState(null, "", `#${id}`);
    sync();
    const url = location.href;
    navigator.clipboard?.writeText(url).then(
      () => did("adres", id, `Adres gekopieerd: #${id}`),
      () => refuse("adres", id, `Niet op het klembord: #${id}`));
    if (mode() === "kantlijn") edit({ targets: [id] }, null, document.getElementById(id).getBoundingClientRect());
  });
  document.addEventListener("mouseup", pointerDone);
  document.addEventListener("touchend", (ev) => setTimeout(() => pointerDone(ev), 0));
  body.addEventListener("mouseover", (ev) => { const m = ev.target.closest?.("mark.fact"); if (m && !editing) hot(m.dataset.id); });
  body.addEventListener("mouseout", (ev) => { if (ev.target.closest?.("mark.fact") && !editing) hot(null); });
  body.addEventListener("mouseover", (ev) => {   // an address in a coref row lights its chain too
    const u = !ev.target.closest?.("mark.fact") && ev.target.closest?.(".fpl-c[id], .fpl-s[id], .fpl-p[id]");
    for (const n of body.querySelectorAll(".fpl-coref")) n.classList.remove("fpl-coref");
    if (u) for (const t of corefOf(u.id)) for (const e of [...marksOf(t), document.getElementById(t)])
      if (e && body.contains(e)) e.classList.add("fpl-coref");
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && drag?.live && !drag.cancelled) { ev.preventDefault(); cancelDrag(); return; }
    if (picking && !picking.kind && cardMenu.hidden && !ev.metaKey && !ev.ctrlKey && !ev.altKey
      && !ev.target.closest?.("input, textarea, select, [contenteditable]") && walk(ev)) return;
    if (stretching?.keys && (ev.key === "Escape" || ev.key === "Enter")) {   // a stretch by keys: Enter saves, Esc puts back
      ev.preventDefault();
      const id = stretching.id;
      if (ev.key === "Enter") keepStretch();
      else { dropStretch(); did("breek af", id, "Teruggezet"); }
      lines.querySelector(`.fpl-knob[data-id="${CSS.escape(id)}"]`)?.focus({ preventScroll: true });
      return;
    }
    const knobId = document.activeElement?.closest?.(".fpl-knob")?.dataset.id;
    if (knobId && ev.shiftKey && (ev.key === "ArrowRight" || ev.key === "ArrowLeft") && !ev.metaKey && !ev.ctrlKey && !ev.altKey && !drag) {
      ev.preventDefault();
      nudge(knobId, ev.key === "ArrowRight" ? 1 : -1);
      return;
    }
    if (ev.key === "Escape" && !cardMenu.hidden) {   // a card's menu: closed, focus back on its ⋯
      const id = menuOf;
      shut();
      if (id) cardEl(id)?.querySelector(".fpl-card-more")?.focus({ preventScroll: true });
      return;
    }
    if (ev.key === "Escape" && (!menu.hidden || !panel.hidden)) {   // an open popover first, focus back to its button
      const back = menu.hidden ? filterBtn : moreBtn, inside = menu.contains(document.activeElement) || panel.contains(document.activeElement);
      shut();
      if (inside) back.focus();
      return;
    }
    const g = document.querySelector(".fpl-graph");   // an open graph takes Esc first, wherever focus is
    if (ev.key === "Escape" && g) { g.close(); return; }
    if (ev.key === "Escape" && editing) { closeEditor(); layout(); disarm(); return; }
    if (ev.key === "Escape" && picking) {
      const from = picking.from;
      unpick();
      did("breek af", from, "Afgebroken");
      return;
    }
    if (ev.key === "Escape" && openId && !ev.target.closest?.("input, textarea, [contenteditable]")) { openId = null; layout(); return; }
    if (adding && (ev.key === "Escape" || ev.key === "Enter") && !ev.defaultPrevented
      && !ev.target.closest?.(ev.key === "Enter" ? "input, textarea, select, [contenteditable], button, a, [role=button], .fpl-chip, summary"
        : "input, textarea, select, [contenteditable]")) {
      ev.preventDefault();
      disarm();
      return;
    }
    if (pieces.length && (ev.key === "Escape" || ev.key === "Enter") && !ev.defaultPrevented
      && !ev.target.closest?.("input, textarea, select, [contenteditable], button, a, [role=button], .fpl-chip, summary")) {
      ev.preventDefault();
      if (ev.key === "Enter" && pieces.length > 1) bundle();
      else {
        did("breek af", null, pieces.length > 1
          ? "Gestopt: de delen blijven losse spans" : "Gestopt");
        pieces = [];
      }
      return;
    }
    if (ev.key === "Escape" && bands.length && !ev.target.closest?.("input, textarea, [contenteditable]")) {
      setBands(bands.slice(0, -1));
      return;
    }
    const typing = ev.defaultPrevented || ev.target.closest?.("input, textarea, select, [contenteditable], .fpl-editor");
    if (ev.key === "Escape" && reading && !typing) { read(null); return; }
    if (ev.key === "?" && !typing && !ev.metaKey && !ev.ctrlKey && !ev.altKey) { ev.preventDefault(); menu.hidden || !menu.classList.contains("fpl-keysheet") ? keysheet() : shut(); return; }
    // "/" before the Shift test: some layouts type it with Shift. Quarto
    // opens its search on the keyup, and leaves it be: the field has focus
    if (ev.key === "/" && mode() === "kantlijn" && !typing
      && !ev.metaKey && !ev.ctrlKey && !ev.altKey) {
      ev.preventDefault();
      seek();
      return;
    }
    if (typing || ev.metaKey || ev.ctrlKey || ev.altKey || ev.shiftKey) return;
    if (ev.key === "z") { ev.preventDefault(); seek(); return; }
    if (ev.key === "l") {   // Verbind met…: the knob or card holding the focus, else the card under the mouse
      ev.preventDefault();
      if (mode() !== "kantlijn") { refuse("verbind", null, LINKS); return; }
      const c = margin.querySelector(".fpl-card:focus-within[data-id], .fpl-card.is-hot[data-id]");
      const id = document.activeElement?.closest?.(".fpl-knob")?.dataset.id ?? c?.dataset.id;
      if (!id || id === "draft") {
        refuse("verbind", null,
          "l verbindt de kaart onder de muis: wijs er eerst een aan");
        return;
      }
      pick(id);
      return;
    }
    if (ev.key === "j" || ev.key === "k") { ev.preventDefault(); step(ev.key === "j" ? 1 : -1); return; }
    if (ev.key === "Enter" && reading && !ev.target.closest?.("button, a, [role=button]")) {
      ev.preventDefault();
      if (mode() === "kantlijn") edit({ targets: [reading.id] }, null, reading.getBoundingClientRect());
      else refuse("feit", reading.id,
        "Een feit schrijf je in de stand Kantlijn (a)");
      return;
    }
    if (ev.key === "a" && !ev.metaKey && !ev.ctrlKey && !ev.altKey
      && !ev.target.closest?.("input, textarea, [contenteditable]")) {
      stand(MODES[(MODES.indexOf(mode()) + 1) % MODES.length]);
    }
  });

  let timer = 0;
  // not while editing: a phone's keyboard resizes the window, and the draft would go
  const relayout = () => { clearTimeout(timer); timer = setTimeout(() => { if (!editing) layout(); }, 120); };
  addEventListener("resize", relayout);
  document.fonts?.ready.then(relayout);

  document.body.append(pop, menu, panel, cardMenu);
  const decisions = (snap ? Promise.resolve(snap.decisions ?? "") : fetch(`${stem}.decisions.tsv`).then((r) => (r.ok ? r.text() : "")))
    .catch(() => "");
  Promise.all([(snap ? Promise.resolve(snap.rows) : fetch(`${stem}.facts.json`).then((r) => (r.ok ? r.json() : []))).catch(() => []), decisions])
    .then(([got, tsv]) => { ledger = readLedger(tsv); sidecar = Array.isArray(got) ? got : []; draw(); persist();
      sync(); });
})();

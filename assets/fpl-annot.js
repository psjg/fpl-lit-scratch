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
 * by is who wrote the row: the name this browser was given in the head
 * of the margin (localStorage["fpl-annot:by"]), or, for a row an agent
 * imported with lit, that agent's model id. A reply is a row without
 * text whose first target is the fact it answers; it shows nested under
 * that fact, with its author, as deep as the thread goes.
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
 * browser's rows for that page; the sidecar is never written here. Export
 * downloads that array as <stem>.annot.json (JSON.stringify(rows, null,
 * 1)); Import merges a file of rows into it by id; Clear empties it.
 *
 * Finding a quote. The page's text nodes are read into one string, the
 * shown text: a backtick dropped, a curly quote read as a straight one,
 * every run of space or "|" one space, each character remembering the
 * node and offset it came from. A row's text is read the way lit reads
 * markdown (`name' as name, [text](url) as text, heading marks dropped)
 * and searched for in it; found once it is drawn, more than once it is
 * dubbel, nowhere stale. Both get a card at the top of the margin, not
 * a span.
 *
 * A saved copy. A page saved with its overlay (the snapshot artifact PSJ
 * annotates) has no site URL and no sidecar beside it; it sets
 * window.FPL_SNAPSHOT = { item, commit, rows } before this script, and
 * the overlay runs on that instead.
 *
 * The margin. Quarto's right column (#quarto-margin-sidebar) is empty
 * once fpl-nav.js has moved the page's sections to the left, and holds
 * the cards; where the column is hidden (a narrow window) each card
 * folds under the block its span is in, and the editor is a popover.
 *
 * Three stands, chosen with the control floating at the top right of
 * the window and with the key "a": lezen shows
 * nothing; spans underlines the spans whose labels pass the filter, a
 * row of label chips under the control, and a click on a span opens
 * its card alone; kantlijn shows every card, the lines and the editor.
 * A line carries the type of the edge it draws: the first label of the
 * first fact about the span, else the span's own. localStorage["fpl-annot:mode"] keeps the stand
 * and "fpl-annot:hide" the labels switched off, for the whole site.
 *
 * Bands (after LiquidText's collapse, Tashman & Edwards, CHI 2011). A
 * band folds the blocks from one block address to another, both ends
 * included, into one hairline per text line they showed, so the reader
 * still sees how much is folded and where, and the page stays one
 * scroll. Headings, lists and tables between the two blocks fold with
 * them. Its grips, at its top and bottom edge, fold blocks in or let
 * them out a whole block at a time as the pointer passes them; a click
 * opens it, Escape opens the newest. The bands are in the URL as
 * ?scrunch=a..b,c..d (block ids such as the-plan/b3) and in
 * localStorage["fpl-annot:scrunch:" + item]; at load the URL wins. A
 * card whose row points at another place on the page has "Toon beide",
 * which folds what lies between the two so both are in view. A span
 * inside a band draws its line, and places its card, at the band.
 * On a touch screen two fingers drawn together fold the blocks between
 * them, from the middle out, as many as the fingers closed by; drawn
 * apart over a band they open it. Knijp tot, under the label chips,
 * folds every block further than its context (0-3 blocks, kept in
 * localStorage["fpl-annot:context"]) from a span the filter shows;
 * pressed again it opens them.
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
 * attack. "Steunt…" and "Valt aan…" on a card arm a pick: the next
 * click on a span, a card, a fact or a branch of a tree is the end.
 *
 * Layers, after the Prague Dependency Treebank's stacked annotation:
 * only a span anchors in the text, every other row names an id. A row's
 * layer is read from what it is, as lit's facts.layer reads it (span,
 * fact, thread, argument, tfa, coref, relation), and a row of chips
 * under the label filter hides a layer. A coref row groups ids that name
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
 * editor ranks its chips by use, on this page and in this browser across
 * the site; the seeds under fn/ only start the list and sink, never go.
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
 * about. "Graph" in the margin's head shows the page, "Graph" on a card
 * that row and what lies within two steps; a click on a node goes there.
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
 * links. "Zelfde als…" on a card arms a pick; its end joins the chain.
 *
 * Querying across the layers (after PML-TQ, Pajas and Stepanek 2009):
 * a field under the filters takes terms [!]key:value, all to hold, in
 * groups apart by "|" of which one must hold, and has:R+N or gives:R+N
 * for a chain of at least N R edges; the same language as lit facts
 * --query (facts.parse_query, facts.query) and tested against the same
 * cases (tests/query_cases.json): what it finds stays, the rest fades.
 */
(() => {
  "use strict";
  const LABELS = ["reason", "claim", "question", "history", "slop", "good",
    "because", "supports", "attacks", "contradicts", "cites", "checkedBy",
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
  const RELATIONS = new Set(["because", "supports", "attacks", "contradicts", "supersedes", "checkedBy", "cites", "resumes"]);
  const AROUND = 32;
  const SKIP = "script, style, button, .fpl-annot-ui";
  const QUOTE = { "‘": "'", "’": "'", "“": '"', "”": '"' };
  const GAP = 12;

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
      const p = wholeOf(row.id);   // a piece shows when its whole does
      if (typeof at !== "string" && mode() !== "lezen" && (p ? passes(p) : passes(row))) wrap(ix, at[0], at[1], row);
    }
    for (const row of all) if (addressed(row)) state[row.id] = "vers";
    for (const p of all.filter((r) => r.labels?.[0] === "parts"))   // a whole is found only when every piece is
      state[p.id] = leavesOf(p).every((t) => state[t] === "vers") ? "vers" : "stale";
    layout();
  }

  /** The control: three stands, and under it the labels to show. */
  const control = el("div", { className: "fpl-annot-ui fpl-mode" });
  function drawControl() {
    const spans = all.filter((r) => typeof r.text === "string"), cur = mode();
    const seg = el("div", { className: "fpl-seg", role: "radiogroup" },
      ...MODES.map((m) => button(m === "lezen" ? "Lezen" : m === "spans" ? `Spans · ${spans.length}` : "Kantlijn",
        () => { if (m !== "kantlijn") disarm(); mode(m); draw(); }, m === cur ? "is-on" : "")));
    control.replaceChildren(seg);
    if (cur === "lezen") return;
    const off = hidden();
    const bySegment = (a, b) => {   // children right after their scope: slop, slop/beeld, slop-ish
      const x = a.split("/"), y = b.split("/");
      for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i].localeCompare(y[i]);
      return x.length - y.length;
    };
    const labels = [...new Set(all.filter((r) => typeof r.text === "string" || addressed(r))   // spans and rows on addresses
      .flatMap((r) => [...labelsOf(r)].flatMap(scopes)))]
      .sort((a, b) => a === NONE ? 1 : b === NONE ? -1 : bySegment(a, b));
    const row = el("div", { className: "fpl-chips fpl-filter" },
      ...labels.map((l) => { const struck = [...off].some((h) => under(l, h));
        const c = chip(l, struck ? "is-off" : "is-on"); c.tabIndex = 0;
        c.style.marginLeft = `${(l.split("/").length - 1) * 0.6}rem`;
        c.onclick = () => {
          const o = hidden(), above = [...o].find((h) => h !== l && under(l, h));
          if (above) { toast(`Zet eerst ${above} aan`); return; }   // struck by its scope: the scope decides
          o.has(l) ? o.delete(l) : o.add(l); hidden(o); draw();
        };
        c.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); c.onclick(); } };
        return c; }),
      off.size ? button("alles", () => { hidden(new Set()); draw(); }, "fpl-link") : null);
    const offL = offLayers(), present = new Set(all.map(layerOf));
    const layers = el("div", { className: "fpl-chips fpl-filter fpl-layers" }, el("small", {}, "lagen"),
      ...LAYERS.filter((l) => present.has(l) && l !== "span").map((l) => {
        const c = chip(l, offL.has(l) ? "is-off" : "is-on"); c.tabIndex = 0;
        c.onclick = () => { const o = offLayers(); o.has(l) ? o.delete(l) : o.add(l); offLayers(o); draw(); };
        c.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); c.onclick(); } };
        return c; }));
    const field = el("input", { className: "fpl-query", placeholder: "zoek: label:claim !has:attacks", value: asked, autocomplete: "off", spellcheck: false });
    const said = el("small", { className: "fpl-query-said" }, found ? `${found.size} gevonden` : "");
    const ask = () => {
      asked = field.value.replace(/^ +| +$/g, "");   // only U+0020 apart, as the parser
      try { found = asked ? new Set(QUERY.query(all, asked)) : null; field.classList.remove("is-bad"); field.title = ""; }
      catch (e) { found = null; fade(); field.classList.add("is-bad"); field.title = e.message; said.textContent = e.message; return; }
      layout();
      control.querySelector(".fpl-query")?.focus();
    };
    field.onkeydown = (e) => {
      e.stopPropagation();   // j, k, a and Esc belong to the page, not while typing a query
      if (e.key === "Enter") ask();
      if (e.key === "Escape") { field.value = ""; ask(); }
    };
    const squeezer = el("div", { className: "fpl-chips fpl-squeeze" }, button("Knijp tot", squeeze),
      button(`context ${context}`, () => { context = (context + 1) % 4; try { localStorage.setItem(CONTEXT, context); } catch { /* no storage */ } drawControl(); }, "fpl-link"));
    control.append(row, layers, squeezer, el("div", { className: "fpl-query-row" }, field, said));
  }

  /* ---- what a card shows ---- */

  const chip = (label, cls) => {
    const [head, sub] = label.split(/\/(.*)/);
    return el("span", { className: "fpl-chip " + cls }, head, sub ? el("small", {}, "/" + sub) : null);
  };
  // a parts row names its pieces, it says nothing about the first one
  const facts = (id) => all.filter((r) => typeof r.text !== "string" && r.labels?.[0] !== "parts" && r.targets?.[0] === id && shows(r));

  /** A fact about something: a relation line or labels, its note, and the facts about it. */
  const reply = (id, at) => button("Reageer", (ev) => {
    ev.stopPropagation();
    edit({ targets: [id] }, null, (at ?? ev.target).getBoundingClientRect());
  }, "fpl-reply");
  function factView(r, cls) {
    const f = el("div", { className: "fpl-fact" });
    f.dataset.fact = r.id;
    if (r.by || r.mine) f.append(el("div", { className: "fpl-who" }, el("span", {}, r.by || "?")));
    const rest = (r.targets ?? []).slice(1);
    if (rest.length)
      f.append(el("div", { className: "fpl-rel" }, el("b", {}, (r.labels ?? []).join(" ") || "→"), " ",
        ...rest.flatMap((t, i) => [i ? ", " : "", el("code", {}, t)])));
    else if (r.labels?.length)
      f.append(el("div", { className: "fpl-chips" }, ...r.labels.map((l) => chip(l, cls))));
    if (r.note) f.append(el("p", { className: "fpl-note" }, r.note));
    const box = argBox(r.id);
    if (box) f.append(box);
    f.append(reply(r.id));
    for (const sub of facts(r.id)) f.append(Object.assign(factView(sub, cls), { className: "fpl-fact fpl-sub" }));
    return f;
  }

  /** The card of a span: its labels and note, then the facts about it. */
  function cardOf(row) {
    const gone = orphan(row), st = gone ? "weg" : state[row.id], cls = row.mine ? "is-mine" : "is-vers";
    const card = el("div", { className: `fpl-card ${row.mine ? "mine" : ""} ${st !== "vers" ? "lost" : ""}` });
    card.dataset.id = row.id;
    card.append(el("div", { className: "fpl-who" }, el("span", { className: "fpl-dot" }), el("span", {}, row.id),
      row.by ? el("span", { className: "fpl-by" }, row.by) : null,
      st === "stale" ? el("span", { className: "fpl-lost" }, "niet meer gevonden")
        : st === "dubbel" ? el("span", { className: "fpl-lost" }, "meer dan één keer gevonden")
        : gone ? el("span", { className: "fpl-lost" }, "wijst nergens heen") : null));
    if (row.labels?.[0] === "parts") card.append(piecesOf(row, card));
    else if (gone) card.append(el("div", { className: "fpl-excerpt" }, el("code", {}, row.targets[0]), " bestaat niet meer"));
    else if (st !== "vers") card.append(el("div", { className: "fpl-excerpt" }, plain(row.text)));
    else if (typeof row.text !== "string") card.append(el("div", { className: "fpl-excerpt" },
      `${row.targets[0]}: ${anchorsOf(row.id)[0].textContent.replace(/\s+/g, " ").trim().slice(0, 140)}`));
    const readings = typeof row.text === "string" ? []
      : all.filter((r) => r !== row && addressed(r) && shows(r) && r.targets[0] === row.targets[0]);
    if (readings.length) {
      const differ = new Set([row, ...readings].map((r) => r.labels?.[0] ?? "")).size > 1;
      card.append(el("div", { className: "fpl-rel" }, el("b", {}, `${readings.length + 1} ${differ ? "lezingen" : "rijen"}`)),
        // each reading is a whole fact: its replies, its argument, data-fact for a pick
        el("div", { className: "fpl-readings" }, ...[row, ...readings].map((r) => {
          const v = factView(r, r.mine ? "is-mine" : "is-vers");
          v.className = "fpl-fact fpl-reading" + (r.mine ? " mine" : "");
          if (r.mine) v.onclick = (ev) => { if (picking || ev.target.closest("button, a, details")) return; ev.stopPropagation(); edit(r, card); };
          return v;
        })));
    } else {
      if (row.labels?.length) card.append(el("div", { className: "fpl-chips" }, ...row.labels.map((l) => chip(l, cls))));
      if (row.note) card.append(el("p", { className: "fpl-note" }, row.note));
    }
    const fs = readings.length ? [] : facts(row.id), plainFacts = fs.filter((r) => !(r.targets ?? []).slice(1).length && r.labels?.length);
    const tops = new Set(plainFacts.map((r) => r.labels[0]));
    if (plainFacts.length > 1 && tops.size > 1) {   // facts on one span with different labels: readings
      card.append(el("div", { className: "fpl-rel" }, el("b", {}, `${plainFacts.length} lezingen`)),
        el("div", { className: "fpl-readings" }, ...plainFacts.map((r) => Object.assign(factView(r, cls), { className: "fpl-fact fpl-reading" }))));
      for (const r of fs.filter((x) => !plainFacts.includes(x))) card.append(factView(r, cls));
    } else for (const r of fs) card.append(factView(r, cls));
    if (row.labels?.[0] === "parts")   // a bundle inside has no card: its facts hang here, under its name
      for (const d of treeOf(row).slice(1).filter(bundleOf)) for (const r of facts(d)) {
        const v = factView(r, cls);
        v.prepend(el("div", { className: "fpl-rel" }, "over deel ", el("code", {}, d)));
        card.append(v);
      }
    const box = readings.length ? null : argBox(row.id);   // a reading's factView drew it
    if (box) card.append(box);
    const ends = (r) => (r.targets ?? []).slice(typeof r.text === "string" ? 0 : 1);
    for (const t of new Set([row, ...readings, ...facts(row.id)].flatMap(ends)))
      if (place(t)) card.append(button(`Toon beide · ${t}`, (ev) => { ev.stopPropagation(); both(row.id, t); }, "fpl-reply"));
    card.append(el("div", { className: "fpl-bar fpl-argue" }, reply(row.id, card), argue(row.id, "supports"), argue(row.id, "attacks"), argue(row.id, "coref"),
      row.labels?.[0] === "parts" && row.mine ? button("Deel erbij…", (ev) => { ev.stopPropagation(); arm(row.id); }, "fpl-reply fpl-arm") : null,
      button("Graph", (ev) => { ev.stopPropagation(); graph(row.id); }, "fpl-reply")));
    card.onmouseenter = () => hot(row.id);
    card.onmouseleave = () => hot(null);
    card.onclick = (ev) => {
      if (ev.target.closest("button, a, .fpl-editor, .fpl-ask")) return;
      const m = anchorsOf(row.id)[0];
      m && seen(m).scrollIntoView({ block: "center", behavior: "smooth" });
      if (row.mine && (m || gone)) edit(row, card);   // a lost fact of ours: open it to delete or rewrite
    };
    return card;
  }

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
        if (rest.length > 1) { save(row, { targets: rest }); draw(); return; }
        if (card.querySelector(".fpl-ask")) return;
        const n = all.filter((r) => typeof r.text !== "string" && r.targets?.[0] === row.id).length;   // kept, they name nothing then
        const left = n ? ` ${n} ${n > 1 ? "feiten" : "feit"} over de bundel ${n > 1 ? "blijven" : "blijft"} bewaard maar ${n > 1 ? "wijzen" : "wijst"} dan nergens heen.` : "";
        const ask = el("div", { className: "fpl-bar fpl-ask" }, `Dan blijft één deel over: de bundel opheffen?${left}`,
          button("Ja, hef op", () => { save(row, "delete"); if (adding === row.id) adding = null; draw();
            toast(`Bundel opgeheven: de delen zijn losse spans${n ? ` · ${n} ${n > 1 ? "feiten wijzen" : "feit wijst"} nergens heen` : ""}`); }, "fpl-go"),
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
        e ? seen(e).scrollIntoView({ block: "center", behavior: "smooth" }) : toast(`${src} staat niet op deze pagina`);
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

  let picking = null;   // {from, kind}: the next click on a row ends a new supports or attacks row from it
  let picked = 0;       // when the last pick landed: the gesture's late touchend (pointerDone) is swallowed
  const ASK = { supports: ["Steunt…", "steunt"], attacks: ["Valt aan…", "aanvalt"], coref: ["Zelfde als…", "zelfde is als"] };
  const argue = (from, kind) => button(ASK[kind][0], (ev) => {
    ev.stopPropagation();
    adding = null;   // one armed gesture at a time
    picking = { from, kind };
    document.body.classList.add("fpl-picking");
    toast(`Klik wat ${from} ${ASK[kind][1]}: een span, kaart, feit, tak of bijzin. Esc breekt af.`);
  }, "fpl-reply");
  const unpick = () => { picking = null; document.body.classList.remove("fpl-picking"); };
  /** The pick's click: the row under it, from the innermost of a branch, a fact, a card, a span or a block. */
  document.addEventListener("click", (ev) => {
    if (!picking || ev.target.closest?.(".fpl-arm")) return;   // "Deel erbij…" ends the pick itself (arm)
    const at = ev.target.closest?.(picking.kind === "resumes" ? ".fpl-c[id], .fpl-s[id]:not(:has(.fpl-c))"
      : "li[data-id], [data-fact], .fpl-card, mark.fact, .fpl-c[id], .fpl-s[id], .fpl-p[id]");
    if (!at) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();   // the Alt listener below must not see a pick's click
    const to = at.dataset.fact ?? (at.matches(".fpl-p, .fpl-s, .fpl-c") ? at.id : at.dataset.id);
    const { from, kind } = picking;
    unpick();
    picked = performance.now();
    if (to === from) { toast("Een rij argumenteert niet over zichzelf"); return; }
    if (all.some((r) => r.labels?.[0] === kind && r.targets?.[0] === from && r.targets?.[1] === to)) { toast("Die rij is er al"); return; }
    save({ targets: [from, to] }, { note: "", labels: [kind] });
    opened.add(to);
    draw();
    toast(`${from} ${kind} ${to}`);
  }, true);

  /* ---- the graph: rows and what they name, laid out by force ---- */

  /* query: begin. Self-contained: tests/test_query_js.py runs this block in node against tests/query_cases.json. */
  const QUERY = (() => {
    const RELS = new Set(["because", "supports", "attacks", "contradicts", "supersedes", "checkedBy", "cites", "resumes"]);
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
  /** Open the graph over the page: all of it, or the part around an id. Esc or a click outside closes it. */
  async function graph(id) {
    await coded;   // the code graph first: a panel drawn before it came would lack the chunks
    document.querySelector(".fpl-graph")?.remove();
    const g = id ? near(graphOf(), id) : graphOf();
    const css = getComputedStyle(document.documentElement);
    const color = (n) => css.getPropertyValue({ chunk: "--fpl-fg", file: "--fpl-mine", span: "--fpl-vers", argument: "--fpl-con", tfa: "--fpl-lost",
      coref: "--fpl-mine", relation: "--fpl-mute", address: "--fpl-mute", elders: "--fpl-rule" }[n.kind] ?? "--fpl-fg").trim() || "#888";
    const W = Math.max(320, Math.min(innerWidth - 32, 1100)), H = Math.max(240, Math.min(innerHeight - 96, 760)), dpr = devicePixelRatio || 1;
    const opener = document.activeElement;
    const cv = el("canvas", { width: W * dpr, height: H * dpr });
    cv.style.width = `${W}px`; cv.style.height = `${H}px`;
    const panel = el("div", { className: "fpl-annot-ui fpl-graph", role: "dialog", "aria-label": "Graph" },
      el("div", { className: "fpl-bar" }, el("b", {}, id ? `Graph rond ${id}` : "Graph van de pagina"),
        el("span", { className: "fpl-mute" }, ` · ${g.nodes.length} knopen · ${g.edges.length} kanten`), el("span", { className: "fpl-space" }),
        button("Sluit", () => close())), cv);
    const close = () => { panel.remove(); opener?.focus?.(); };
    /** Where a node goes: its own place, else that of what it is about, followed up its first targets. */
    const goal = (nid, been = new Set()) => {
      const e = place(nid) ?? chunkBlock(nid);
      if (e || been.has(nid)) return e;
      been.add(nid);
      const r = all.find((x) => x.id === nid);
      return r?.targets?.[0] ? goal(r.targets[0], been) : null;
    };
    const go = (n) => {
      const e = goal(n.id);
      if (!e) { toast(`${n.id} staat niet op deze pagina`); return; }
      close();
      seen(e).scrollIntoView({ block: "center", behavior: "smooth" });
      hot(n.id);
    };
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
      else ctx.arc(n.x, n.y, n.id === id ? 8 : 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.fillStyle = css.getPropertyValue("--fpl-fg").trim() || "#222";
      const name = n.label ?? n.id;   // a chunk or file by its name, a row by its id
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
  }

  /** The head of the margin: counts and the three buttons. */
  function head() {
    const spans = all.filter((r) => typeof r.text === "string" || addressed(r));
    const lost = spans.filter((r) => state[r.id] !== "vers").length + all.filter(orphan).length, mine = local().length;
    const file = el("input", { type: "file", accept: ".json", hidden: true });
    file.onchange = () => file.files[0]?.text().then(merge);
    const cmd = el("div", { className: "fpl-cmd", hidden: true });
    const h = el("div", { className: "fpl-head" },
      el("div", { className: "fpl-count" },
        `${spans.length} spans · ${all.length - spans.length} relaties`,
        lost ? el("span", { className: "fpl-lost" }, ` · ${lost} kwijt`) : null,
        mine ? el("span", { className: "fpl-mine" }, ` · ${mine} lokaal`) : null),
      el("div", { className: "fpl-bar" },
        el("input", { className: "fpl-byme", value: by(), placeholder: "jij", title: "Wie schrijft: komt als by op elke rij",
          onchange: (ev) => by(ev.target.value.trim()) }),
        button("Graph", () => graph(null)),
        button("Export", () => { exportRows(); cmd.hidden = false; }),
        button("Import", () => file.click()),
        mine ? button("Clear", () => clear(h)) : null, file),
      cmd);
    cmd.append("Dan, vanuit 01-bootstrap/: ",
      el("code", {}, `lit facts --import ${stem}.annot.json --item ${item}=${item}@${commit}`));
    return h;
  }

  /** Clear asks once, in the head itself. */
  function clear(h) {
    const ask = el("div", { className: "fpl-bar fpl-ask" }, "De lokale rijen van deze pagina vergeten?",
      button("Ja, vergeet", () => { localStorage.removeItem(key); draw(); }, "fpl-go"),
      button("Nee", () => ask.remove()));
    h.append(ask);
  }

  /** Download this browser's rows as <stem>.annot.json. */
  function exportRows() {
    const blob = new Blob([JSON.stringify(local(), null, 1) + "\n"],
      { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: `${stem}.annot.json` });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /** Merge a file of rows for this page into this browser's, by id. */
  function merge(text) {
    let got;
    try { got = JSON.parse(text); } catch (e) { toast(`Geen JSON: ${e.message}`); return; }
    if (!Array.isArray(got)) { toast("Geen lijst van rijen"); return; }
    const by = new Map(local().map((r) => [r.id, r]));
    let n = 0;
    for (const r of got) if (r && r.item === item && typeof r.id === "string") { by.set(r.id, r); n++; }
    keep([...by.values()]);
    toast(`${n} rijen ingelezen`);
    draw();
  }

  function toast(text) {
    const t = el("div", { className: "fpl-annot-ui fpl-toast" }, text);
    document.body.append(t);
    setTimeout(() => t.remove(), 1800);
  }

  /* ---- the editor ---- */

  /**
   * The editor of a row: the note first, labels as chips (the known ones
   * and the sidecar's) plus a field for one more, ⌘↩ saves, esc closes.
   */
  function editor(row, onDone) {
    const on = new Set(row.labels ?? []);
    // Maps, not objects: a label may be any name, __proto__ and constructor too
    const used = new Map(), t = new Map(Object.entries(tally()));
    for (const r of all) for (const l of r.labels ?? []) used.set(l, (used.get(l) ?? 0) + 1);
    const rank = (l) => (used.get(l) ?? 0) + (Number(t.get(l)) || 0);
    const seen = [...new Set([...LABELS, ...used.keys(), ...t.keys()])]
      .map((l, i) => [l, i]).sort((a, b) => rank(b[0]) - rank(a[0]) || a[1] - b[1]).map(([l]) => l);   // by use, then seed order
    const form = el("form", { className: "fpl-editor" });
    const note = el("textarea", { placeholder: "Notitie", value: row.note ?? "", rows: 2 });
    const chips = el("div", { className: "fpl-chips" });
    const more = el("input", { placeholder: "label/sub…", autocomplete: "off" });
    const render = () => chips.replaceChildren(
      ...[...new Set([...seen, ...on])].map((l) => {
        const b = chip(l, on.has(l) ? "is-on" : "");
        b.onclick = () => { on.has(l) ? on.delete(l) : on.add(l); render(); };
        b.tabIndex = 0;
        b.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); b.onclick(); } };
        return b;
      }), more);
    render();
    more.onkeydown = (e) => {
      if (e.key !== "Enter" || !more.value.trim()) return;
      e.preventDefault();
      const l = more.value.trim();
      if (!LABEL.test(l)) { toast("Een label is naam/scope/…: geen spatie, geen leeg stuk"); return; }
      on.add(l); more.value = ""; render();
    };
    const keys = el("div", { className: "fpl-bar fpl-keys" },
      row.id ? button("Verwijder", () => onDone("delete")) : null,
      el("span", { className: "fpl-space" }),
      button("Annuleer", () => onDone(null)),
      el("button", { type: "submit", className: "fpl-go" }, "Bewaar ", el("kbd", {}, "⌘↩")));
    const t0 = row.targets?.[0] ?? "", parent = all.find((r) => r.id === t0);
    const about = typeof row.text === "string" ? row.text
      : parent ? `Reactie op ${t0}: ${(parent.note || parent.text || (parent.labels ?? []).join(" ")).replace(/\s+/g, " ").slice(0, 140)}`
      : `${t0}: ${document.getElementById(t0)?.textContent.replace(/\s+/g, " ").trim().slice(0, 140) ?? ""}`;
    const fast = typeof row.text !== "string" && !row.id && quick().length
      ? el("div", { className: "fpl-chips fpl-quick" }, el("small", {}, "snel"),
        ...quick().map((l) => { const b = chip(l, "is-on"); b.tabIndex = 0;
          b.onclick = () => onDone({ note: note.value.trim(), labels: [...new Set([l, ...on])] });
          b.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.stopPropagation(); b.onclick(); } };
          return b; }))
      : null;
    form.append(el("div", { className: "fpl-excerpt" }, about), fast, note, chips, keys);
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
    if (got === "delete") { keep(mine.filter((r) => r.id !== row.id)); return; }
    const now = Date.now();
    const done = { ...row, ...got, updatedAt: now };
    delete done.mine;
    if (row.id) mine[mine.findIndex((r) => r.id === row.id)] = done;
    else mine.push({ id: `a-${now.toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      item, commit, by: by() || undefined, targets: [], ...done, createdAt: now });
    keep(mine);
    const l = layerOf(done), off = offLayers();
    if (off.delete(l)) { offLayers(off); toast(`Laag ${l} weer aan`); }
  }
  /** A save from the editor: what the reader typed or picked counts toward the ranking and the offer. */
  function typed(row, got) {
    save(row, got);
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
    const say = (yes) => { (yes ? quick : declined)([...(yes ? quick() : declined()), l]); box.remove(); if (yes) toast(`${l} is een snelchip`); };
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
        c.style.top = `${rect.top + scrollY - top0()}px`;
        if (marksOf("draft").length) c.dataset.id = "draft";   // the selection, lit while written
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

  /** The cards below the one being written move down out of its way, and back on close (layout). */
  function makeRoom(c) {
    const top = c.offsetTop, bottom = top + c.offsetHeight + GAP;
    let floor = bottom;
    const below = [...margin.querySelectorAll(".fpl-card")].filter((o) => o !== c && o.offsetTop + o.offsetHeight > top)
      .sort((a, b) => a.offsetTop - b.offsetTop);
    for (const o of below) {
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
  const pop = el("div", { className: "fpl-annot-ui fpl-pop", hidden: true });

  const wide = () => !!column && column.offsetWidth > 120;
  const top0 = () => margin.getBoundingClientRect().top + scrollY;

  /** Lay every card out: the head, the lost rows, then one card per span in page order. */
  function layout() {
    closeEditor();
    drawControl();
    document.body.classList.toggle("fpl-numbered", mode() !== "lezen");
    for (const c of body.querySelectorAll(".fpl-inline")) c.remove();
    scrunch();
    if (reading?.closest(".fpl-scrunched")) read(null);   // folded away: nothing to read or write on
    heat();
    lens();   // now as well as at the end: an early return below must not leave the lens of another stand
    margin.replaceChildren();
    lines.replaceChildren();
    margin.style.minHeight = "";
    const full = mode() === "kantlijn";
    if (control.parentElement !== document.body) document.body.append(control);
    if (wide()) {
      column.classList.add("fpl-column");
      if (margin.parentElement !== column) column.append(margin);
      if (lines.parentElement !== document.body) document.body.append(lines);
    } else {
      column?.classList.remove("fpl-column");
      lines.remove();
      if (margin.parentElement !== body) body.prepend(margin);
    }
    if (mode() === "lezen") return;
    if (full) margin.append(head());
    const heads = new Set();   // one card per address: its other rows are readings in it
    const spans = all.filter((r) => (typeof r.text === "string" || addressed(r) || orphan(r) || r.labels?.[0] === "parts") && shows(r) && passes(r) && (full || open.has(r.id)))
      .filter((r) => typeof r.text === "string" || r.labels?.[0] === "parts" ? !partsOf(r.id) : orphan(r) || (!heads.has(r.targets[0]) && heads.add(r.targets[0])));
    if (!spans.length) return;
    const lost = spans.filter((r) => state[r.id] !== "vers" || orphan(r));
    const found = spans.map((r) => ({ r, m: anchorsOf(r.id)[0] })).filter((x) => x.m)
      .map((x) => ({ r: x.r, m: seen(x.m) }))
      .sort((a, b) => a.m.getBoundingClientRect().top - b.m.getBoundingClientRect().top);
    if (wide()) {
      let y = full ? margin.firstElementChild.offsetHeight + GAP : 0;
      for (const r of lost) {
        const c = cardOf(r);
        margin.append(c);
        c.style.top = `${y}px`;
        y += c.offsetHeight + GAP;
      }
      const base = top0();
      for (const { r, m } of found) {
        const c = cardOf(r);
        margin.append(c);
        const want = m.getBoundingClientRect().top + scrollY - base;
        y = Math.max(want, y);
        c.style.top = `${y}px`;
        y += c.offsetHeight + GAP;
      }
      margin.style.minHeight = `${y}px`;
      drawLines();
    } else {
      for (const r of lost) margin.append(cardOf(r));
      for (const { r, m } of found) {
        const c = cardOf(r);
        c.classList.add("fpl-inline");
        (m.closest("p, li, pre, h1, h2, h3, h4, td, th, blockquote") ?? m).after(c);
      }
    }
    lens();   // last: the cards placed inline move the clauses it measures
    fade();
  }

  /** A line from the end of each span to its card, in the span's colour. */
  function drawLines() {
    const h = Math.max(document.documentElement.scrollHeight, body.getBoundingClientRect().bottom + scrollY);
    lines.setAttribute("width", document.documentElement.scrollWidth);
    lines.setAttribute("height", h);
    lines.replaceChildren();
    for (const c of margin.querySelectorAll(".fpl-card[data-id]")) {
      const rects = anchorsOf(c.dataset.id).map(seen).flatMap((m) => [...m.getClientRects()]);
      if (!rects.length) continue;
      const last = rects[rects.length - 1], cr = c.getBoundingClientRect();
      // from under the end of the span, along the gap below its line out of
      // the text, then in one curve to the card; the type sits before the card
      const x1 = last.right + scrollX + 2, y1 = last.bottom + scrollY - 1, yb = y1 + 4;
      const x2 = cr.left + scrollX - 1, y2 = cr.top + scrollY + 10;
      const gx = Math.max(x1 + 8, body.getBoundingClientRect().right + scrollX + 6);
      const dx = Math.max(16, (x2 - gx) / 2);
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", `M${x1},${yb} H${gx} C${gx + dx},${yb} ${x2 - dx},${y2} ${x2},${y2}`);
      p.setAttribute("class", `fpl-line ${c.classList.contains("mine") ? "mine" : ""}`);
      p.dataset.id = c.dataset.id;
      lines.append(p);
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");   // the lollipop at the span
      dot.setAttribute("cx", x1);
      dot.setAttribute("cy", yb);
      dot.setAttribute("r", 2.5);
      dot.setAttribute("class", `fpl-knob ${c.classList.contains("mine") ? "mine" : ""}`);
      dot.dataset.id = c.dataset.id;
      lines.append(dot);
      const type = edgeType(c.dataset.id);
      if (type) {   // just before the card, where the line arrives, in a halo that breaks the line
        const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
        t.setAttribute("x", x2 - 6);
        t.setAttribute("y", y2);
        t.setAttribute("class", `fpl-edge ${c.classList.contains("mine") ? "mine" : ""}`);
        t.dataset.id = c.dataset.id;
        t.textContent = type + " ›";
        lines.append(t);
      }
    }
  }

  /** The type of the edge from a span to its card: the first fact's first label, else the span's. */
  function edgeType(id) {
    const row = all.find((r) => r.id === id), first = facts(id)[0];
    return first?.labels?.[0] ?? row?.labels?.[0] ?? "";
  }

  /** The span, card and line of one row light up together. */
  function hot(id) {
    const group = new Set(id ? groupOf(id) : []);   // a piece lights its whole, the whole its pieces
    for (const n of [...body.querySelectorAll("mark.fact, .is-hot"), ...margin.querySelectorAll(".fpl-card"), ...lines.children])
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
      if (r.mine) path.onclick = () => { keep(local().filter((x) => x.id !== r.id)); draw(); toast(`${r.id} weg`); };
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
    toast(next ? `${id}: ${next}` : `${id}: geen tfa`);
  }

  /* ---- bands: blocks folded to a hairline per line, the page one scroll ---- */

  const SCRUNCH = "fpl-annot:scrunch:" + item;
  /**
   * A hairline every PITCH pixels, unless the band would be taller than
   * TALL of the window: then its lines draw closer, so that a band never
   * keeps its two ends (Toon beide) out of one view.
   */
  const PITCH = 3, TALL = 0.3;
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
  let held = false;   // a grip is down: the click that ends its drag does not open the band

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

  /**
   * The text lines a block shows now: for each paragraph or code block in
   * it (else the block itself, a heading or a list) its height over its
   * line height.
   */
  function linesOf(e) {
    const parts = e.querySelectorAll("p, pre");
    let n = 0;
    for (const x of parts.length ? parts : [e]) {
      const cs = getComputedStyle(x);
      n += Math.round(x.offsetHeight / (parseFloat(cs.lineHeight) || 1.2 * parseFloat(cs.fontSize)));
    }
    return Math.max(1, n);
  }

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
   * Draw the bands. Every element from a band's first block to its last
   * is measured at the page's current width, then hidden (fpl-scrunched,
   * data-band = the band's index, data-lines = its count), and the band
   * stands before the first of them: --lines hairlines --fpl-pitch apart,
   * its range in data-range for the hover. All of it within one task, so
   * the reader never sees the blocks unfold; a resize or a font load
   * counts afresh.
   */
  function scrunch() {
    for (const b of body.querySelectorAll(".fpl-band")) b.remove();
    const us = units(), ls = leaves(), got = settle(us);
    bands = got.map(([i, j]) => [us[i].id, us[j].id]);
    const folds = got.map(([i, j]) => ls.slice(ls.indexOf(us[i]), ls.indexOf(us[j]) + 1));
    for (const l of ls) l.classList.remove("fpl-scrunched");
    for (const l of folds.flat()) l.dataset.lines = linesOf(l);   // unfolded for the measure, folded below before a paint
    folds.forEach((fold, k) => {
      const [i, j] = got[k], n = fold.reduce((s, l) => s + +l.dataset.lines, 0);
      const range = `${addr(us[i])} – ${addr(us[j])} · ${j - i + 1} blok${j > i ? "ken" : ""}, ${n} regels`;
      const open = () => setBands(bands.filter((_, x) => x !== k));
      const band = el("div", { className: "fpl-annot-ui fpl-band", tabIndex: 0, role: "button", ariaLabel: `Band ${range}: open`,
        onclick: () => { if (!held) open(); },
        onkeydown: (ev) => { if (ev.target === band && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); open(); } } },
      grip(k, "top"), grip(k, "bottom"));
      Object.assign(band.dataset, { k, range });
      band.style.setProperty("--lines", n);
      band.style.setProperty("--fpl-pitch", `${Math.min(PITCH, (TALL * innerHeight) / n)}px`);
      for (const l of fold) { l.classList.add("fpl-scrunched"); l.dataset.band = k; }
      fold[0].before(band);
    });
  }

  /**
   * A grip on a band's top or bottom edge. Dragged, the edge moves to the
   * block boundary nearest the pointer's travel since the press: outward
   * over the blocks as they stood then, inward over the band's hairlines.
   * It stops before another band, so bands never merge under the pointer.
   * The drag follows its band by its ends, not its place in the list, and
   * lets go when the band is gone (Escape, a click elsewhere). Focused,
   * the arrow keys move the edge one block.
   */
  function grip(k, edge) {
    const g = el("span", { className: `fpl-grip fpl-grip-${edge}`, tabIndex: 0, role: "button",
      ariaLabel: `${edge === "top" ? "Boven" : "Onder"}rand van de band: pijltjes schuiven een blok` });
    g.onkeydown = (ev) => {
      const d = { ArrowUp: -1, ArrowDown: 1 }[ev.key];
      if (!d) return;
      ev.preventDefault();
      ev.stopPropagation();
      const us = units(), [i, j] = bands[k].map((id) => us.indexOf(document.getElementById(id)));
      const [a, b] = edge === "top" ? [i + d, j] : [i, j + d], grows = (edge === "top") === (d < 0);
      const t = edge === "top" ? a : b;
      if (a > b || !us[t] || (grows && us[t].classList.contains("fpl-scrunched"))) return;
      setBands(bands.map((x, y) => (y === k ? [us[a].id, us[b].id] : x)));
      body.querySelector(`.fpl-band[data-k="${k}"] .fpl-grip-${edge}`)?.focus();
    };
    g.onpointerdown = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const band = g.parentElement, r = band.getBoundingClientRect(), y0 = ev.clientY;
      const us = units(), ls = leaves(), [i, j] = bands[k].map((id) => us.indexOf(document.getElementById(id)));
      const pitch = parseFloat(band.style.getPropertyValue("--fpl-pitch"));
      const base = ls.indexOf(us[i]), y = [0];   // y[x]: the hairlines above the band's x-th element
      for (let x = base; x <= ls.indexOf(us[j]); x++) y.push(y.at(-1) + +ls[x].dataset.lines * pitch);
      const stops = [];   // [travel from the press, first block, last block]
      for (let t = i; t <= j; t++)
        stops.push(edge === "top" ? [y[ls.indexOf(us[t]) - base], t, j] : [y[ls.indexOf(us[t]) - base + 1] - y.at(-1), i, t]);
      const free = (t) => us[t] && !us[t].classList.contains("fpl-scrunched");
      if (edge === "top") for (let t = i - 1; free(t); t--) stops.push([us[t].getBoundingClientRect().top - r.top, t, j]);
      else for (let t = j + 1; free(t); t++) stops.push([us[t].getBoundingClientRect().bottom - r.bottom, i, t]);
      held = true;
      let ends = bands[k];
      const move = (e) => {
        const at = bands.findIndex(([p, q]) => p === ends[0] && q === ends[1]);
        if (at < 0 || pinch) { up(); return; }   // gone, or a second finger made it a pinch
        const dy = e.clientY - y0;
        const [, a, b] = stops.reduce((best, s) => (Math.abs(s[0] - dy) < Math.abs(best[0] - dy) ? s : best));
        if (us[a].id === ends[0] && us[b].id === ends[1]) return;
        bands[at] = ends = [us[a].id, us[b].id];
        layout();
      };
      const up = () => {
        removeEventListener("pointermove", move);
        removeEventListener("pointerup", up);
        removeEventListener("pointercancel", up);
        persist();
        setTimeout(() => { held = false; });
      };
      addEventListener("pointermove", move);
      addEventListener("pointerup", up);
      addEventListener("pointercancel", up);
    };
    return g;
  }

  /** Write the bands to the URL (?scrunch=a..b,c..d, kept readable) and to this browser. */
  function persist() {
    const s = bands.map(([a, b]) => (a === b ? a : `${a}..${b}`)).join(","), u = new URL(location.href);
    if (s) u.searchParams.set("scrunch", s); else u.searchParams.delete("scrunch");
    u.search = u.search.replace(/%2[CF]/gi, decodeURIComponent);
    history.replaceState(history.state, "", u);
    try { if (s) localStorage.setItem(SCRUNCH, s); else localStorage.removeItem(SCRUNCH); } catch { /* no storage */ }
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
    if (i < 0) { toast("Niet op deze pagina"); return; }
    const covers = (b, x) => { const [p, q] = b.map((id) => us.indexOf(document.getElementById(id))); return p <= x && x <= q; };
    const kept = bands.filter((b) => !covers(b, i) && !covers(b, j));
    const fold = j - i >= 2 ? [[us[i + 1].id, us[j - 1].id]] : [];
    if (!fold.length && kept.length === bands.length) { toast("Ze staan al samen in beeld"); return; }
    setBands([...kept, ...fold]);
    (fold.length ? bandOf(us[i + 1]) : us[i]).scrollIntoView({ block: "center", behavior: "smooth" });
  }

  /**
   * Knijp tot (LiquidText's merged highlights): fold every run of blocks
   * further than context blocks from a span the filter lets through, so
   * the spans stand together with their surroundings. Pressed again while
   * the bands are just that, it opens them all.
   */
  const CONTEXT = "fpl-annot:context";
  let context = (() => { try { const n = localStorage.getItem(CONTEXT); return n != null && /^[0-3]$/.test(n) ? +n : 1; } catch { return 1; } })();
  function squeeze() {
    const us = units(), near = new Set();
    for (const m of body.querySelectorAll("mark.fact")) {
      const i = us.indexOf(m.closest(".fpl-p"));
      if (i >= 0) for (let t = i - context; t <= i + context; t++) near.add(t);
    }
    if (!near.size) { toast("Geen spans om tot te knijpen"); return; }
    const runs = [];
    for (let i = 0; i < us.length; i++)
      if (!near.has(i)) { const a = i; while (i + 1 < us.length && !near.has(i + 1)) i++; runs.push([us[a].id, us[i].id]); }
    const same = runs.length === bands.length && runs.every(([a, b], x) => a === bands[x][0] && b === bands[x][1]);
    setBands(same ? [] : runs);
    if (same) toast("Alles open");
  }

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
    const [y0, y1] = ys(ev.touches), { d0, base, us, i, j, h, open } = pinch, s = d0 - (y1 - y0);
    let next = base;
    if (s < -40 && open.length) next = base.filter((b) => !open.includes(b));
    else if (s > 0 && i >= 0 && j - i > 1) {   // i < 0: the fingers are below the last block
      let a = Math.floor((i + j) / 2), b = a - 1, sum = 0;   // [a, b], empty, grows a block a side by turns
      const fits = (t) => t > i && t < j && sum + h[t] <= s;
      for (let left = false; ; left = !left) {
        const t = left ? a - 1 : b + 1;
        if (fits(t)) { sum += h[t]; left ? a-- : b++; } else if (!fits(left ? b + 1 : a - 1)) break;
      }
      if (a <= b) next = [...base, [us[a].id, us[b].id]];
    }
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
    if (ev.touches.length !== 2 || [...ev.touches].some((t) => t.target.closest?.(".fpl-card, .fpl-mode"))) return;
    const [y0, y1] = ys(ev.touches), us = units();
    const at = (y) => us.findIndex((u) => !u.classList.contains("fpl-scrunched") && u.getBoundingClientRect().bottom >= y);
    const i = at(y0), j = at(y1) < 0 ? us.length : at(y1);
    const between = [...body.querySelectorAll(".fpl-band")].filter((b) => { const r = b.getBoundingClientRect(); return r.bottom >= y0 && r.top <= y1; });
    const r = us.map((u) => (u.classList.contains("fpl-scrunched") ? null : u.getBoundingClientRect()));
    const h = r.map((x, t) => {   // what folding block t takes away: down to the next block shown, headings and tables between included
      const n = r.findIndex((y, u) => u > t && y);
      return !x ? 0 : n < 0 ? x.height : Math.max(0, r[n].top - x.top);
    });
    pinch = { d0: y1 - y0, base: bands, us, i, j, h,
      open: between.map((b) => bands[+b.dataset.k]), key: "", at: new Set([...ev.touches].map((t) => t.target)) };
    for (const x of pinch.at) for (const [t, f] of PINCH) x.addEventListener(t, f, { passive: false });
  }, { passive: true });

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
    if (mode() !== "kantlijn") return;
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) return;
    if ([...body.querySelectorAll(".fpl-scrunched")].some((l) => range.intersectsNode(l))) {
      // shown() keeps folded text (the quote finder needs it whole), so the quote would hold what was never seen
      sel.removeAllRanges();
      toast("De selectie loopt door een band: open die eerst");
      return;
    }
    const ix = shown(), [s, e] = bounds(ix, range);
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
    toast(`Gestopt: ${adding} heeft ${local().find((r) => r.id === adding)?.targets.length ?? 0} delen`);
    adding = null;
  }
  /** "Deel erbij…": the next Alt-selects join this parts row, until Esc or Enter. */
  function arm(id) {
    if (mode() !== "kantlijn") { toast("Delen schrijf je in de stand Kantlijn (a)"); return; }
    if (picking) unpick();
    const loose = pieces.length ? ": de losse delen blijven losse spans" : "";
    pieces = [];
    adding = id;
    toast(`Delen erbij voor ${id}${loose} · Alt-selecteer het volgende · Esc stopt`);
  }
  /** Alt-select: the selection becomes a span row of this browser, the next piece of a discontinuous span. */
  function piece(sel) {
    pieced = performance.now();   // this gesture is a selection, whatever comes of it: its click is no Alt-click
    if (mode() !== "kantlijn") { sel.removeAllRanges(); toast("Delen schrijf je in de stand Kantlijn (a)"); return; }
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)
      || [...body.querySelectorAll(".fpl-scrunched")].some((l) => range.intersectsNode(l))) { sel.removeAllRanges(); return; }
    const ix = shown(), [s, e] = bounds(ix, range);
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
    if (hit.some((h) => h.id === mine || pieces.includes(h.id))) { toast(`Dat is al een deel van ${pr?.id ?? "deze bundel"}`); return; }
    if (hit.length > 1) { toast(`Dat loopt over ${hit.length} bundels: kies er één`); return; }
    const owner = hit[0];
    if (owner) {   // a piece of a piece: the whole that text is in joins as one piece
      if (pr) {
        save(pr, { targets: [...pr.targets, owner.id] });
        draw();
        toast(`Bundel ${owner.id} is deel ${pr.targets.length + 1} van ${pr.id} · Alt-selecteer het volgende · Esc stopt`);
        return;
      }
      pieces.push(owner.id);
      draw();
      toast(`Deel ${pieces.length}: bundel ${owner.id}${pieces.length > 1 ? " · Enter bundelt" : ""} · Alt-selecteer het volgende · Esc stopt`);
      return;
    }
    save({ text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s), suffix: ix.flat.slice(e, e + AROUND) },
      { note: "", labels: [] });
    const id = local().at(-1).id;
    if (pr) {
      save(pr, { targets: [...pr.targets, id] });
      draw();
      toast(`Deel ${pr.targets.length + 1} van ${pr.id} · Alt-selecteer het volgende · Esc stopt`);
      return;
    }
    pieces.push(id);
    draw();
    toast(`Deel ${pieces.length}${pieces.length > 1 ? ": Enter bundelt" : ""} · Alt-selecteer het volgende · Esc stopt`);
  }
  /** Enter: the pieces become one span, a parts row, and the editor opens for a fact about it. */
  function bundle() {
    const live = new Set([...local().filter((r) => typeof r.text === "string"), ...all.filter((r) => r.labels?.[0] === "parts" && !partsOf(r.id))].map((r) => r.id));
    const ps = pieces.filter((id) => live.has(id));   // a piece deleted meanwhile is no piece
    pieces = [];
    if (ps.length < 2) { toast("Minder dan twee delen over: niets gebundeld"); draw(); return; }
    save({ targets: ps }, { note: "", labels: ["parts"] });
    const id = local().at(-1).id;
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
    toast(`Klik de eerdere bijzin die ${c.id} weer opneemt. Esc breekt af.`);
  }, true);
  document.addEventListener("click", (ev) => {
    const id = numberAt(ev);
    if (!id) return;
    ev.preventDefault();
    getSelection()?.removeAllRanges();
    history.replaceState(null, "", `#${id}`);
    sync();
    const url = location.href;
    navigator.clipboard?.writeText(url).then(() => toast(`Adres gekopieerd: #${id}`), () => toast(`#${id}`));
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
    const g = document.querySelector(".fpl-graph");   // an open graph takes Esc first, wherever focus is
    if (ev.key === "Escape" && g) { g.close(); return; }
    if (ev.key === "Escape" && editing) { closeEditor(); layout(); disarm(); return; }
    if (ev.key === "Escape" && picking) { unpick(); toast("Afgebroken"); return; }
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
      else { toast(pieces.length > 1 ? "Gestopt: de delen blijven losse spans" : "Gestopt"); pieces = []; }
      return;
    }
    if (ev.key === "Escape" && bands.length && !ev.target.closest?.("input, textarea, [contenteditable]")) {
      setBands(bands.slice(0, -1));
      return;
    }
    const typing = ev.defaultPrevented || ev.target.closest?.("input, textarea, select, [contenteditable], .fpl-editor");
    if (ev.key === "Escape" && reading && !typing) { read(null); return; }
    if (typing || ev.metaKey || ev.ctrlKey || ev.altKey || ev.shiftKey) return;
    if (ev.key === "j" || ev.key === "k") { ev.preventDefault(); step(ev.key === "j" ? 1 : -1); return; }
    if (ev.key === "Enter" && reading && !ev.target.closest?.("button, a, [role=button]")) {
      ev.preventDefault();
      if (mode() === "kantlijn") edit({ targets: [reading.id] }, null, reading.getBoundingClientRect());
      else toast("Een feit schrijf je in de stand Kantlijn (a)");
      return;
    }
    if (ev.key === "a" && !ev.metaKey && !ev.ctrlKey && !ev.altKey
      && !ev.target.closest?.("input, textarea, [contenteditable]")) {
      const m = MODES[(MODES.indexOf(mode()) + 1) % MODES.length];
      if (m !== "kantlijn") disarm();
      mode(m);
      draw();
    }
  });

  let timer = 0;
  // not while editing: a phone's keyboard resizes the window, and the draft would go
  const relayout = () => { clearTimeout(timer); timer = setTimeout(() => { if (!editing) layout(); }, 120); };
  addEventListener("resize", relayout);
  document.fonts?.ready.then(relayout);

  document.body.append(pop);
  (snap ? Promise.resolve(snap.rows) : fetch(`${stem}.facts.json`).then((r) => (r.ok ? r.json() : [])))
    .catch(() => [])
    .then((got) => { sidecar = Array.isArray(got) ? got : []; draw(); persist();
      sync(); });
})();

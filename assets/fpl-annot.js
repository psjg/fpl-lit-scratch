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
 *   { id: "a-" + base36 time + random, item, commit,
 *     text,            the selection as shown, whitespace made one space
 *     prefix, suffix,  32 characters of shown text either side of it
 *     labels: [], note, targets: [], createdAt, updatedAt }  (times in ms)
 *
 * A quote row has no offsets: lit finds it in the raw page by text, and
 * prefix and suffix choose among several hits. Rows of the sidecar keep
 * their own shape and are drawn by their text the same way. A row without
 * text is a fact about its first target: it is shown on the card of the
 * span it hangs from, nested under the fact it is about.
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
 * The margin. Quarto's right column (#quarto-margin-sidebar) is empty
 * once fpl-nav.js has moved the page's sections to the left, and holds
 * the cards; where the column is hidden (a narrow window) each card
 * folds under the block its span is in, and the editor is a popover.
 */
(() => {
  "use strict";
  const LABELS = ["reason", "claim", "question", "history", "slop", "good",
    "because", "supports", "contradicts", "cites", "checkedBy"];
  const AROUND = 32;
  const SKIP = "script, style, button, .fpl-annot-ui";
  const QUOTE = { "‘": "'", "’": "'", "“": '"', "”": '"' };
  const GAP = 12;

  const root = new URL("../", document.currentScript.src).href;
  const here = location.href.split(/[?#]/)[0];
  const meta = (name) =>
    document.querySelector(`meta[name="${name}"]`)?.content ?? "";
  const commit = meta("fpl-commit");
  if (!here.startsWith(root) || !here.endsWith(".html") || !commit) return;
  const page = decodeURIComponent(here.slice(root.length));
  const item = page.replace(/\.html$/, ".md");
  const stem = page.slice(page.lastIndexOf("/") + 1, -".html".length);
  const key = "fpl-annot:" + item;
  const body = document.querySelector("main") || document.body;
  const column = document.getElementById("quarto-margin-sidebar");

  let sidecar = [];

  /** This browser's rows for the page; [] when none or unreadable. */
  const local = () => {
    try { return JSON.parse(localStorage.getItem(key) || "[]"); }
    catch { return []; }
  };
  const keep = (rows) => localStorage.setItem(key, JSON.stringify(rows));

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

  /** Every row, the sidecar's first, each marked mine when it is local. */
  const rows = () => [...sidecar, ...local().map((r) => ({ ...r, mine: true }))];
  let all = [], state = {};

  /** Remove the marks, draw every row again, and lay the margin out. */
  function draw() {
    for (const m of body.querySelectorAll("mark.fact")) m.replaceWith(...m.childNodes);
    body.normalize();
    all = rows();
    state = {};
    for (const row of all) {
      if (typeof row.text !== "string" || !row.text.trim()) continue;
      const ix = shown(), at = find(ix, row);
      state[row.id] = typeof at === "string" ? at : "vers";
      if (typeof at !== "string") wrap(ix, at[0], at[1], row);
    }
    layout();
  }

  /* ---- what a card shows ---- */

  const chip = (label, cls) => {
    const [head, sub] = label.split(/\/(.*)/);
    return el("span", { className: "fpl-chip " + cls }, head, sub ? el("small", {}, "/" + sub) : null);
  };
  const facts = (id) => all.filter((r) => typeof r.text !== "string" && r.targets?.[0] === id);

  /** A fact about something: a relation line or labels, its note, and the facts about it. */
  function factView(r, cls) {
    const f = el("div", { className: "fpl-fact" });
    const rest = (r.targets ?? []).slice(1);
    if (rest.length)
      f.append(el("div", { className: "fpl-rel" }, el("b", {}, (r.labels ?? []).join(" ") || "→"), " ",
        ...rest.flatMap((t, i) => [i ? ", " : "", el("code", {}, t)])));
    else if (r.labels?.length)
      f.append(el("div", { className: "fpl-chips" }, ...r.labels.map((l) => chip(l, cls))));
    if (r.note) f.append(el("p", { className: "fpl-note" }, r.note));
    for (const sub of facts(r.id)) f.append(Object.assign(factView(sub, cls), { className: "fpl-fact fpl-sub" }));
    return f;
  }

  /** The card of a span: its labels and note, then the facts about it. */
  function cardOf(row) {
    const st = state[row.id], cls = row.mine ? "is-mine" : "is-vers";
    const card = el("div", { className: `fpl-card ${row.mine ? "mine" : ""} ${st !== "vers" ? "lost" : ""}` });
    card.dataset.id = row.id;
    card.append(el("div", { className: "fpl-who" }, el("span", { className: "fpl-dot" }), el("span", {}, row.id),
      st === "stale" ? el("span", { className: "fpl-lost" }, "niet meer gevonden")
        : st === "dubbel" ? el("span", { className: "fpl-lost" }, "meer dan één keer gevonden") : null));
    if (st !== "vers") card.append(el("div", { className: "fpl-excerpt" }, plain(row.text)));
    if (row.labels?.length) card.append(el("div", { className: "fpl-chips" }, ...row.labels.map((l) => chip(l, cls))));
    if (row.note) card.append(el("p", { className: "fpl-note" }, row.note));
    for (const r of facts(row.id)) card.append(factView(r, cls));
    card.onmouseenter = () => hot(row.id);
    card.onmouseleave = () => hot(null);
    card.onclick = (ev) => {
      if (ev.target.closest("button, a, .fpl-editor")) return;
      const m = marksOf(row.id)[0];
      m?.scrollIntoView({ block: "center", behavior: "smooth" });
      if (row.mine && m) edit(row, card);
    };
    return card;
  }

  /** The head of the margin: counts and the three buttons. */
  function head() {
    const spans = all.filter((r) => typeof r.text === "string");
    const lost = spans.filter((r) => state[r.id] !== "vers").length, mine = local().length;
    const file = el("input", { type: "file", accept: ".json", hidden: true });
    file.onchange = () => file.files[0]?.text().then(merge);
    const cmd = el("div", { className: "fpl-cmd", hidden: true });
    const h = el("div", { className: "fpl-head" },
      el("div", { className: "fpl-count" },
        `${spans.length} spans · ${all.length - spans.length} relaties`,
        lost ? el("span", { className: "fpl-lost" }, ` · ${lost} kwijt`) : null,
        mine ? el("span", { className: "fpl-mine" }, ` · ${mine} lokaal`) : null),
      el("div", { className: "fpl-bar" },
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
    const seen = [...new Set([...LABELS, ...sidecar.flatMap((r) => r.labels ?? [])])];
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
      if (e.key === "Enter" && more.value.trim()) { e.preventDefault(); on.add(more.value.trim()); more.value = ""; render(); }
    };
    const keys = el("div", { className: "fpl-bar fpl-keys" },
      row.id ? button("Verwijder", () => onDone("delete")) : null,
      el("span", { className: "fpl-space" }),
      button("Annuleer", () => onDone(null)),
      el("button", { type: "submit", className: "fpl-go" }, "Bewaar ", el("kbd", {}, "⌘↩")));
    form.append(el("div", { className: "fpl-excerpt" }, row.text), note, chips, keys);
    form.onsubmit = (ev) => { ev.preventDefault(); onDone({ note: note.value.trim(), labels: [...on] }); };
    form.onkeydown = (e) => {
      if (e.key === "Escape") { e.stopPropagation(); onDone(null); }
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
      item, commit, ...done, targets: [], createdAt: now });
    keep(mine);
  }

  /** Open the editor for a row, in its card or in a new card at the given height. */
  function edit(row, card, rect) {
    closeEditor();
    const done = (got) => { closeEditor(); if (got) { save(row, got); draw(); } else layout(); };
    const form = editor(row, done);
    if (wide()) {
      const c = card ?? el("div", { className: "fpl-card mine fpl-editing" });
      c.classList.add("fpl-editing");
      c.replaceChildren(form);
      if (!card) { margin.append(c); c.style.top = `${rect.top + scrollY - top0()}px`; }
      editing = c;
    } else {
      pop.replaceChildren(form);
      pop.hidden = false;
      const r = rect ?? card.getBoundingClientRect();
      pop.style.top = `${scrollY + r.bottom + 8}px`;
      pop.style.left = `${Math.max(8, Math.min(scrollX + r.left, scrollX + innerWidth - pop.offsetWidth - 8))}px`;
      editing = pop;
    }
  }

  let editing = null;
  function closeEditor() {
    if (!editing) return;
    if (editing === pop) pop.hidden = true;
    else editing.remove();
    editing = null;
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
    for (const c of body.querySelectorAll(".fpl-inline")) c.remove();
    margin.replaceChildren(head());
    lines.replaceChildren();
    const spans = all.filter((r) => typeof r.text === "string");
    const lost = spans.filter((r) => state[r.id] !== "vers");
    const found = spans.map((r) => ({ r, m: marksOf(r.id)[0] })).filter((x) => x.m)
      .sort((a, b) => a.m.getBoundingClientRect().top - b.m.getBoundingClientRect().top);
    if (wide()) {
      column.classList.add("fpl-column");
      if (margin.parentElement !== column) column.append(margin);
      if (lines.parentElement !== document.body) document.body.append(lines);
      let y = margin.firstElementChild.offsetHeight + GAP;
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
      column?.classList.remove("fpl-column");
      lines.remove();
      if (margin.parentElement !== body) body.prepend(margin);
      for (const r of lost) margin.append(cardOf(r));
      for (const { r, m } of found) {
        const c = cardOf(r);
        c.classList.add("fpl-inline");
        (m.closest("p, li, pre, h1, h2, h3, h4, td, th, blockquote") ?? m).after(c);
      }
    }
  }

  /** A line from the end of each span to its card, in the span's colour. */
  function drawLines() {
    const h = Math.max(document.documentElement.scrollHeight, body.getBoundingClientRect().bottom + scrollY);
    lines.setAttribute("width", document.documentElement.scrollWidth);
    lines.setAttribute("height", h);
    lines.replaceChildren();
    for (const c of margin.querySelectorAll(".fpl-card[data-id]")) {
      const ms = marksOf(c.dataset.id);
      if (!ms.length) continue;
      const rects = [...ms].flatMap((m) => [...m.getClientRects()]);
      const last = rects[rects.length - 1], cr = c.getBoundingClientRect();
      const x1 = last.right + scrollX + 2, y1 = last.bottom + scrollY - 1;
      const x2 = cr.left + scrollX - 1, y2 = cr.top + scrollY + 10;
      const dx = Math.max(24, (x2 - x1) / 2);
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`);
      p.setAttribute("class", `fpl-line ${c.classList.contains("mine") ? "mine" : ""}`);
      p.dataset.id = c.dataset.id;
      lines.append(p);
    }
  }

  /** The span, card and line of one row light up together. */
  function hot(id) {
    for (const n of [...body.querySelectorAll("mark.fact"), ...margin.querySelectorAll(".fpl-card"), ...lines.children])
      n.classList.toggle("is-hot", !!id && n.dataset.id === id);
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
    const target = ev.target instanceof Element ? ev.target : null;
    if (target?.closest(".fpl-annot-ui")) return;
    const sel = getSelection();
    if (!sel.rangeCount || sel.isCollapsed) {
      const m = target?.closest("mark.fact");
      if (!m) { if (editing) { closeEditor(); layout(); } return; }
      const row = all.find((r) => r.id === m.dataset.id);
      hot(row.id);
      const card = margin.querySelector(`.fpl-card[data-id="${CSS.escape(row.id)}"]`);
      if (row.mine) edit(row, card, m.getBoundingClientRect());
      else if (card && wide()) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
      return;
    }
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) return;
    const ix = shown(), [s, e] = bounds(ix, range);
    if (s >= e) return;
    edit({ text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s),
      suffix: ix.flat.slice(e, e + AROUND) }, null, range.getBoundingClientRect());
  }
  document.addEventListener("mouseup", pointerDone);
  document.addEventListener("touchend", (ev) => setTimeout(() => pointerDone(ev), 0));
  body.addEventListener("mouseover", (ev) => { const m = ev.target.closest?.("mark.fact"); if (m) hot(m.dataset.id); });
  body.addEventListener("mouseout", (ev) => { if (ev.target.closest?.("mark.fact") && !editing) hot(null); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && editing) { closeEditor(); layout(); } });

  let timer = 0;
  // not while editing: a phone's keyboard resizes the window, and the draft would go
  const relayout = () => { clearTimeout(timer); timer = setTimeout(() => { if (!editing) layout(); }, 120); };
  addEventListener("resize", relayout);
  document.fonts?.ready.then(relayout);

  document.body.append(pop);
  fetch(`${stem}.facts.json`)
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => [])
    .then((got) => { sidecar = Array.isArray(got) ? got : []; draw(); });
})();

/*
 * fpl-annot.js: annotate a published literate page in the browser.
 *
 * The page's fact sidecar (<stem>.facts.json, shipped beside it) is drawn
 * as marks; a reader selects text, gives it labels and a note, and the row
 * is kept in this browser until it is exported and imported into the
 * sidecar by lit. Nothing is sent anywhere.
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
 * their own shape and are drawn by their text the same way.
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
 * dubbel, nowhere stale. Both are listed, not drawn.
 */
(() => {
  "use strict";
  const LABELS = ["reason", "claim", "history", "question", "slop", "good",
    "because", "supports", "contradicts", "cites", "checkedBy"];
  const AROUND = 32;
  const SKIP = "script, style, button, .fpl-annot-ui";
  const QUOTE = { "‘": "'", "’": "'", "“": '"', "”": '"' };

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

  /** Every row, the sidecar's first, each marked mine when it is local. */
  const rows = () => [...sidecar, ...local().map((r) => ({ ...r, mine: true }))];

  /** Remove the marks, draw every row again, and list them in the panel. */
  function draw() {
    for (const m of body.querySelectorAll("mark.fact")) m.replaceWith(...m.childNodes);
    body.normalize();
    const all = rows(), state = {};
    for (const row of all) {
      if (typeof row.text !== "string" || !row.text.trim()) continue;
      const ix = shown(), at = find(ix, row);
      state[row.id] = typeof at === "string" ? at : "vers";
      if (typeof at !== "string") wrap(ix, at[0], at[1], row);
    }
    list(all, state);
  }

  const el = (tag, props = {}, ...kids) => {
    const e = Object.assign(document.createElement(tag), props);
    e.append(...kids);
    return e;
  };

  const ui = el("aside", { className: "fpl-annot-ui fpl-annot-panel" });
  const pop = el("form", { className: "fpl-annot-ui fpl-annot-pop", hidden: true });

  /** The panel: buttons, the import line, and one entry per row. */
  function list(all, state) {
    const cited = {};
    for (const r of all) for (const t of r.targets ?? []) (cited[t] ??= []).push(r.id);
    const file = el("input", { type: "file", accept: ".json", hidden: true });
    file.onchange = () => file.files[0]?.text().then(merge);
    const entries = all.map((r) => {
      const st = state[r.id] ?? "";
      const li = el("li", { className: `fact-${st}`, title: r.mine ? "local" : "sidecar" },
        el("b", {}, r.id), st ? ` ${st}` : "",
        r.labels?.length ? ` [${r.labels.join(", ")}]` : "",
        r.note ? el("div", {}, r.note) : "",
        r.targets?.length
          ? el("div", {}, `${(r.labels ?? []).join(" ") || "→"}: ${r.targets.join(" → ")}`) : "",
        cited[r.id] ? el("div", {}, `cited by ${cited[r.id].join(", ")}`) : "");
      li.onclick = () => {
        const m = body.querySelector(`mark.fact[data-id="${CSS.escape(r.id)}"]`);
        m?.scrollIntoView({ block: "center" });
        if (r.mine && m) open(r, m.getBoundingClientRect());
      };
      return li;
    });
    const cmd = `lit facts --import ${stem}.annot.json --item ${item}=${item}@${commit}`;
    ui.replaceChildren(el("details", { open: ui.querySelector("details")?.open ?? false },
      el("summary", {}, `Facts ${all.length} (${local().length} local)`),
      el("div", { className: "fpl-annot-bar" },
        button("Export", exportRows), button("Import", () => file.click()),
        button("Clear local", () => confirm("Forget this page's local rows?")
          && (localStorage.removeItem(key), draw())), file),
      el("p", { className: "fpl-annot-help" }, "Select text to annotate. Export, then into the sidecar (.harness/tools/lit/README.md): ",
        el("code", {}, cmd)),
      el("ol", {}, ...entries)));
  }

  const button = (text, onclick) => el("button", { type: "button", onclick }, text);

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
    try { got = JSON.parse(text); } catch (e) { alert(`Not JSON: ${e.message}`); return; }
    if (!Array.isArray(got)) { alert("Not an array of rows"); return; }
    const by = new Map(local().map((r) => [r.id, r]));
    for (const r of got) if (r && r.item === item && typeof r.id === "string") by.set(r.id, r);
    keep([...by.values()]);
    draw();
  }

  /**
   * The popover, for a new row (row.id unset) or for one of ours. Its
   * label field offers the sidecar's labels and the known ones.
   */
  function open(row, rect) {
    const seen = new Set([...LABELS, ...sidecar.flatMap((r) => r.labels ?? [])]);
    const labels = el("input", { name: "labels", value: (row.labels ?? []).join(" "),
      placeholder: "labels", autocomplete: "off" });
    labels.setAttribute("list", "fpl-annot-labels");
    const note = el("textarea", { name: "note", value: row.note ?? "", placeholder: "note", rows: 2 });
    pop.replaceChildren(
      el("datalist", { id: "fpl-annot-labels" }, ...[...seen].map((l) => el("option", { value: l }))),
      el("q", {}, row.text), labels, note,
      el("div", { className: "fpl-annot-bar" },
        el("button", { type: "submit" }, "Save"),
        row.id ? button("Delete", () => { keep(local().filter((r) => r.id !== row.id)); close(); }) : "",
        button("Cancel", () => close(false))));
    pop.onsubmit = (ev) => {
      ev.preventDefault();
      const now = Date.now(), mine = local();
      const done = { ...row, labels: labels.value.split(/[\s,]+/).filter(Boolean),
        note: note.value.trim(), updatedAt: now };
      delete done.mine;
      if (row.id) mine[mine.findIndex((r) => r.id === row.id)] = done;
      else mine.push({ id: `a-${now.toString(36)}${Math.random().toString(36).slice(2, 6)}`,
        item, commit, ...done, targets: [], createdAt: now });
      keep(mine);
      close();
    };
    pop.hidden = false;
    pop.style.top = `${scrollY + rect.bottom + 6}px`;
    pop.style.left = `${Math.max(8, Math.min(scrollX + rect.left, scrollX + innerWidth - 340))}px`;
    labels.focus();
  }

  function close(redraw = true) {
    pop.hidden = true;
    if (redraw) draw();
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

  /** A selection in the body opens the popover for a new quote row. */
  document.addEventListener("mouseup", (ev) => {
    if (ev.target.closest(".fpl-annot-ui")) return;
    const sel = getSelection();
    if (!sel.rangeCount || sel.isCollapsed) {
      const m = ev.target.closest("mark.fact");
      const row = m && local().find((r) => r.id === m.dataset.id);
      if (row) open(row, m.getBoundingClientRect());
      return;
    }
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) return;
    const ix = shown(), [s, e] = bounds(ix, range);
    if (s >= e) return;
    open({ text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s),
      suffix: ix.flat.slice(e, e + AROUND) }, range.getBoundingClientRect());
  });

  document.body.append(ui, pop);
  fetch(`${stem}.facts.json`)
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => [])
    .then((got) => { sidecar = Array.isArray(got) ? got : []; draw(); });
})();

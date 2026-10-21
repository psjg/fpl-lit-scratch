/**
 * /try playground + kata UI. Buffer is pure FPL; runtime wraps fpl.run.default.src.
 * Playground: Monaco Quokka ghosts + Tab-commit to `; |-` notes; Miller path-browser;
 * dockable Paths/Edit/Term via fpl-dock.js (progressive enhancement).
 * Katas: textarea.
 */
import { runFpl, traceFpl, checkExpected, learnBase } from "./fpl-runtime.js";
import { mountStepper } from "./fpl-stepper.js";
import { initDock } from "./fpl-dock.js";

const RESULT_PREFIX = "|- ";
const TRAILING_NOTE = /[\t ]*(?:;|⍝)[ \t]*(.*)$/u;

const DEFAULT_SRC = `\
;;; ── frames ──
1 | 1 2 3 +\t; |- 2 3 4
1 2 3 +\t; |- [1‿2‿3 +]
2 | 3 +\t; |- 5
1 | 1 2 3 [-] swap-args\t; |- 1 2 3 - 1

;;; ── paths (Miller columns) ──
demo/
	math/
		inc : n -- n
			1 +
		twice : n -- n
			dup *
	greet : --
		;;; say hi
`;

const LIVE_MS = 300;
const OUTLINE_MS = 200;
const MONACO_VER = "0.52.2";
const MONACO_BASE = `https://cdn.jsdelivr.net/npm/monaco-editor@${MONACO_VER}/min/vs`;

function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error("missing #" + id);
  return el;
}

function readHash() {
  const h = location.hash.startsWith("#") ? location.hash.slice(1) : location.hash;
  const params = new URLSearchParams(h);
  return params.get("c");
}

function writeHash(src) {
  const params = new URLSearchParams();
  params.set("c", src);
  const next = "#" + params.toString();
  if (location.hash !== next) {
    history.replaceState(null, "", next);
  }
}

function setOut(el, text, ok) {
  el.textContent = text || "(no output)";
  el.dataset.ok = ok ? "1" : "0";
  el.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
}

/** Ghost decoration payload: leading spaces + `|- ` + value. */
function formatGhost(value) {
  return `  ${RESULT_PREFIX}${value}`;
}

/** Committed trailing note (valid FPL NOTE; `|-` is convention inside it). */
function formatNote(value) {
  return `\t; ${RESULT_PREFIX}${value}`;
}

/** Body of a trailing `;` / `⍝` note, with optional `|- ` stripped; else null. */
function resultNoteBody(line) {
  const m = String(line).match(TRAILING_NOTE);
  if (!m) return null;
  let body = m[1];
  if (body.startsWith(RESULT_PREFIX)) body = body.slice(RESULT_PREFIX.length);
  else if (body.startsWith("|-")) body = body.slice(2).replace(/^[ \t]+/u, "");
  return body;
}

/** Drop a trailing result note so a fresh `; |- …` can be appended. */
function stripResultNote(line) {
  return String(line).replace(TRAILING_NOTE, "").replace(/[ \t]+$/u, "");
}

/**
 * Pair stdout lines 1:1 with non-blank, non-;;; source lines.
 * Matching committed `; |-` (or legacy `;`) notes → kind "committed" (no ghost).
 */
function pairLineResults(src, stdout) {
  const lines = String(src).split("\n");
  const outs = String(stdout)
    .replace(/\s+$/u, "")
    .split("\n")
    .filter((l) => l.length > 0);
  const codeIdx = [];
  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim();
    if (t === "" || t.startsWith(";;;")) continue;
    codeIdx.push(i);
  }
  if (codeIdx.length !== outs.length) return null;
  /** @type {{ text: string, kind: "result" | "committed" | "skip" | "empty" }[]} */
  const cells = lines.map((line) => {
    const t = line.trim();
    if (t === "") return { text: "", kind: "empty" };
    if (t.startsWith(";;;")) return { text: "", kind: "skip" };
    return { text: "", kind: "empty" };
  });
  for (let j = 0; j < codeIdx.length; j++) {
    const i = codeIdx[j];
    const value = outs[j];
    const note = resultNoteBody(lines[i]);
    const kind = note === value ? "committed" : "result";
    cells[i] = { text: value, kind };
  }
  return cells;
}

/** @returns {Promise<typeof import("monaco-editor")>} */
function loadMonaco() {
  if (window.monaco) return Promise.resolve(window.monaco);
  return new Promise((resolve, reject) => {
    window.require = { paths: { vs: MONACO_BASE } };
    const script = document.createElement("script");
    script.src = `${MONACO_BASE}/loader.js`;
    script.async = true;
    script.onload = () => {
      window.require(["vs/editor/editor.main"], () => {
        resolve(window.monaco);
      });
    };
    script.onerror = () => reject(new Error("failed to load Monaco loader"));
    document.head.appendChild(script);
  });
}

/**
 * @param {import("monaco-editor").editor.IStandaloneCodeEditor} editor
 * @param {import("monaco-editor")} monaco
 * @param {{ text: string, kind: string }[] | null} cells
 * @param {string[]} prevIds
 */
function applyQuokkaDecorations(editor, monaco, cells, prevIds) {
  if (!cells) {
    return editor.deltaDecorations(prevIds, []);
  }
  const model = editor.getModel();
  if (!model) return editor.deltaDecorations(prevIds, []);

  /** @type {import("monaco-editor").editor.IModelDeltaDecoration[]} */
  const next = [];
  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i];
    if (cell.kind !== "result" || !cell.text) continue;
    const line = i + 1;
    if (line > model.getLineCount()) break;
    const col = model.getLineMaxColumn(line);
    next.push({
      range: new monaco.Range(line, col, line, col),
      options: {
        after: {
          content: formatGhost(cell.text),
          inlineClassName: "fpl-quokka-after",
          cursorStops: monaco.editor.InjectedTextCursorStops.None,
        },
        showIfCollapsed: true,
      },
    });
  }
  return editor.deltaDecorations(prevIds, next);
}

/**
 * @param {import("monaco-editor").editor.ITextModel} model
 * @param {import("monaco-editor")} monaco
 * @param {number} lineIdx 0-based
 * @param {string} value
 */
function commitResultNote(model, monaco, lineIdx, value) {
  const lineNo = lineIdx + 1;
  if (lineNo > model.getLineCount()) return;
  const old = model.getLineContent(lineNo);
  const next = stripResultNote(old) + formatNote(value);
  if (next === old) return;
  model.pushEditOperations(
    [],
    [
      {
        range: new monaco.Range(
          lineNo,
          1,
          lineNo,
          model.getLineMaxColumn(lineNo),
        ),
        text: next,
      },
    ],
    () => null,
  );
}

/** Line with trailing notes stripped; leading tabs kept. */
function codeLine(line) {
  return stripResultNote(line);
}

function tabCount(line) {
  let n = 0;
  while (line[n] === "\t") n += 1;
  return n;
}

/**
 * @typedef {{
 *   kind: "root" | "dir" | "def" | "phrase",
 *   name: string,
 *   start: number,
 *   end: number,
 *   headEnd: number,
 *   children: OutlineNode[],
 * }} OutlineNode
 */

/** @returns {{ kind: string, name: string }} */
function classifyCode(code) {
  const body = code.replace(/^\t+/u, "");
  if (body === "" || body.startsWith(";;;")) return { kind: "skip", name: "" };
  if (/^[A-Za-z_][\w./-]*\/$/u.test(body)) {
    return { kind: "dir", name: body };
  }
  const def = body.match(/^([A-Za-z_][\w./-]*)\s*:/u);
  if (def) return { kind: "def", name: def[1] };
  const label = body.length > 28 ? `${body.slice(0, 28)}…` : body;
  return { kind: "phrase", name: label };
}

/**
 * @param {string[]} lines
 * @param {number} from
 * @param {number} to
 * @param {number} baseIndent
 * @returns {OutlineNode[]}
 */
function parseLevel(lines, from, to, baseIndent) {
  /** @type {OutlineNode[]} */
  const out = [];
  let i = from;
  while (i < to) {
    const code = codeLine(lines[i]);
    if (code.trim() === "") {
      i += 1;
      continue;
    }
    const ind = tabCount(code);
    if (ind < baseIndent) break;
    if (ind > baseIndent) {
      i += 1;
      continue;
    }
    const kinded = classifyCode(code);
    if (kinded.kind === "skip") {
      i += 1;
      continue;
    }
    let j = i + 1;
    while (j < to) {
      const next = codeLine(lines[j]);
      if (next.trim() === "") {
        j += 1;
        continue;
      }
      if (tabCount(next) <= baseIndent) break;
      j += 1;
    }
    if (kinded.kind === "dir") {
      out.push({
        kind: "dir",
        name: kinded.name,
        start: i,
        end: j,
        headEnd: i + 1,
        children: parseLevel(lines, i + 1, j, baseIndent + 1),
      });
    } else {
      out.push({
        kind: kinded.kind === "def" ? "def" : "phrase",
        name: kinded.name,
        start: i,
        end: j,
        headEnd: i + 1,
        children: [],
      });
    }
    i = j;
  }
  return out;
}

/** @param {string} src @returns {OutlineNode} */
function parseOutline(src) {
  const lines = String(src).split("\n");
  return {
    kind: "root",
    name: "(buffer)",
    start: 0,
    end: lines.length,
    headEnd: 0,
    children: parseLevel(lines, 0, lines.length, 0),
  };
}

/** @param {string[]} lines @param {OutlineNode} node */
function bodyIndentOf(lines, node) {
  const from = node.kind === "dir" ? node.headEnd : node.start;
  let min = Infinity;
  for (let i = from; i < node.end; i++) {
    const code = codeLine(lines[i]);
    if (code.trim() === "") continue;
    min = Math.min(min, tabCount(code));
  }
  return Number.isFinite(min) ? min : tabCount(codeLine(lines[node.start]));
}

/** @param {string[]} lines @param {OutlineNode} node */
function extractBody(lines, node) {
  const from = node.kind === "dir" ? node.headEnd : node.start;
  const indent = bodyIndentOf(lines, node);
  return lines
    .slice(from, node.end)
    .map((line) => {
      let n = 0;
      while (n < indent && line[n] === "\t") n += 1;
      return line.slice(n);
    })
    .join("\n");
}

/** @param {string} body @param {number} tabs */
function indentBody(body, tabs) {
  const prefix = "\t".repeat(tabs);
  return body
    .split("\n")
    .map((line) => (line === "" ? line : prefix + line))
    .join("\n");
}

/**
 * @param {OutlineNode | null | undefined} a
 * @param {OutlineNode | null | undefined} b
 */
function sameOutlineNode(a, b) {
  return (
    a != null &&
    b != null &&
    a.name === b.name &&
    a.kind === b.kind &&
    a.start === b.start
  );
}

/**
 * @param {HTMLElement} host
 * @param {OutlineNode} root
 * @param {OutlineNode[]} path
 * @param {(col: number, node: OutlineNode, ev: MouseEvent) => void} onPick
 */
function renderMiller(host, root, path, onPick) {
  host.replaceChildren();
  /** @type {OutlineNode[][]} */
  const columns = [root.children];
  // Commit-by-depth: open children only for path nodes we have moved past
  // (path continues). Tip sits in the rightmost column among its siblings.
  for (let i = 0; i < path.length - 1; i++) {
    const node = path[i];
    if (node.kind === "dir" && node.children.length > 0) {
      columns.push(node.children);
    }
  }
  const last = columns.length - 1;
  columns.forEach((items, col) => {
    const colEl = document.createElement("div");
    colEl.className =
      "fpl-miller-col" + (col === last ? " fpl-miller-col-active" : "");
    colEl.setAttribute("role", "listbox");
    colEl.setAttribute("aria-label", `Column ${col + 1}`);
    for (const item of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fpl-miller-item" + (item.kind === "dir" ? " dir" : "");
      btn.textContent = item.name;
      btn.title = item.name;
      btn.setAttribute("role", "option");
      if (sameOutlineNode(path[col], item)) btn.classList.add("selected");
      btn.addEventListener("click", (ev) => onPick(col, item, ev));
      btn.addEventListener("dblclick", (ev) => {
        ev.preventDefault();
        onPick(col, item, ev);
      });
      colEl.appendChild(btn);
    }
    host.appendChild(colEl);
  });
}

async function bootPlayground() {
  const host = $("fpl-editor");
  const out = $("fpl-out");
  const runBtn = /** @type {HTMLButtonElement} */ ($("fpl-run"));
  const clearBtn = /** @type {HTMLButtonElement} */ ($("fpl-clear"));
  const resetBtn = /** @type {HTMLButtonElement} */ ($("fpl-reset"));
  const acceptBtn = /** @type {HTMLButtonElement | null} */ (
    document.getElementById("fpl-accept")
  );
  const miller = $("fpl-miller");
  const millerHint = $("fpl-miller-hint");
  const focusBtn = /** @type {HTMLButtonElement} */ ($("fpl-focus"));
  const unfocusBtn = /** @type {HTMLButtonElement} */ ($("fpl-unfocus"));
  const browserToggle = /** @type {HTMLButtonElement | null} */ (
    document.getElementById("fpl-browser-toggle")
  );
  const pathsSection = miller.closest("[data-dock='paths']");
  const browser = pathsSection || miller.closest(".fpl-browser");
  const BROWSER_COLLAPSE_KEY = "fpl-try-browser-collapsed";

  const monaco = await loadMonaco();
  const fromHash = readHash();
  const initial =
    fromHash != null && fromHash !== "" ? fromHash : DEFAULT_SRC;

  const editor = monaco.editor.create(host, {
    value: initial,
    language: "plaintext",
    theme: "vs-dark",
    fontSize: 14,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    lineNumbers: "on",
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: "off",
    automaticLayout: true,
    renderLineHighlight: "line",
    padding: { top: 12 },
    tabSize: 4,
    insertSpaces: false,
  });

  // Dock after Monaco so panel show/resize can call editor.layout().
  const dock = await initDock({
    onLayout: () => {
      try {
        editor.layout();
      } catch {
        /* editor disposed */
      }
    },
  });

  let decoIds = /** @type {string[]} */ ([]);
  /** @type {{ text: string, kind: string }[] | null} */
  let lastCells = null;
  let timer = 0;
  let outlineTimer = 0;
  let gen = 0;
  let muteLive = false;
  let mode = "paths";
  /** @type {OutlineNode} */
  let outline = parseOutline(initial);
  /** @type {OutlineNode[]} */
  let path = [];
  /** @type {{
   *   node: OutlineNode,
   *   bodyIndent: number,
   *   prefix: string,
   *   suffix: string,
   * } | null} */
  let focus = null;
  let navDeco = /** @type {string[]} */ ([]);

  const selected = () => path[path.length - 1] || null;

  const getSrc = () => {
    if (!focus) return editor.getValue();
    const body = indentBody(editor.getValue(), focus.bodyIndent);
    return focus.prefix + body + focus.suffix;
  };

  const setFocusChrome = () => {
    const on = focus != null;
    unfocusBtn.hidden = !on;
    focusBtn.hidden = on;
    focusBtn.disabled = !selected();
    millerHint.textContent = on
      ? "Focused · Miller retargets scope · Escape exits"
      : mode === "examples"
        ? "Examples library next — switch back to Buffer paths"
        : "↑↓ pick · → commit deeper · ← up · Enter/Focus scope · → Edit at leaf";
  };

  const clearNavDeco = () => {
    navDeco = editor.deltaDecorations(navDeco, []);
  };

  /** Select the whole focused body (Monaco selection only — no nav-range wash). */
  const paintScopeSelection = () => {
    const model = editor.getModel();
    if (!model) return;
    clearNavDeco();
    const endLine = model.getLineCount();
    const range = new monaco.Range(
      1,
      1,
      endLine,
      model.getLineMaxColumn(endLine),
    );
    editor.setSelection(range);
  };

  /**
   * Rematch a selection path onto a freshly parsed outline by name+kind.
   * @param {OutlineNode} root
   * @param {OutlineNode[]} oldPath
   * @returns {OutlineNode[]}
   */
  const rematchPath = (root, oldPath) => {
    /** @type {OutlineNode[]} */
    const nextPath = [];
    let cursor = root;
    for (const old of oldPath) {
      const hit = cursor.children.find(
        (c) => c.name === old.name && c.kind === old.kind,
      );
      if (!hit) break;
      nextPath.push(hit);
      cursor = hit;
    }
    return nextPath;
  };

  /**
   * Keep Focus on: stitch edits, reparse outline, show the tip's body.
   * Call after miller path updates while `focus` is set.
   */
  const retargetFocus = () => {
    const full = getSrc();
    outline = parseOutline(full);
    path = rematchPath(outline, path);
    const tip = selected();
    if (!tip) {
      focus = null;
      muteLive = true;
      try {
        editor.setValue(full);
      } finally {
        muteLive = false;
      }
      writeHash(full);
      setFocusChrome();
      paintMiller();
      scheduleLive();
      return;
    }
    const lines = full.split("\n");
    const from = tip.kind === "dir" ? tip.headEnd : tip.start;
    const bodyIndent = bodyIndentOf(lines, tip);
    const prefix = lines.slice(0, from).join("\n") + (from > 0 ? "\n" : "");
    const suffix =
      tip.end < lines.length ? "\n" + lines.slice(tip.end).join("\n") : "";
    focus = { node: tip, bodyIndent, prefix, suffix };
    muteLive = true;
    try {
      editor.setValue(extractBody(lines, tip));
      paintScopeSelection();
      decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    } finally {
      muteLive = false;
    }
    writeHash(full);
    setFocusChrome();
    paintMiller();
    scheduleLive();
  };

  const navigateTo = (node) => {
    if (focus) {
      retargetFocus();
      return;
    }
    const model = editor.getModel();
    if (!model) return;
    const start = Math.min(node.start + 1, model.getLineCount());
    const endLine = Math.min(Math.max(node.end, node.start + 1), model.getLineCount());
    const range = new monaco.Range(
      start,
      1,
      endLine,
      model.getLineMaxColumn(endLine),
    );
    editor.revealLineInCenter(start);
    editor.setSelection(range);
    navDeco = editor.deltaDecorations(navDeco, [
      {
        range,
        options: {
          className: "fpl-nav-range",
          isWholeLine: true,
        },
      },
    ]);
    focusBtn.disabled = false;
  };

  const paintMiller = () => {
    if (mode === "examples") {
      miller.replaceChildren();
      const empty = document.createElement("div");
      empty.className = "fpl-miller-empty";
      empty.textContent =
        "Kata / examples library next. Use Buffer paths for now.";
      miller.appendChild(empty);
      setFocusChrome();
      dock?.syncPathsWidth?.();
      return;
    }
    renderMiller(miller, outline, path, (col, node, ev) => {
      path = path.slice(0, col);
      path.push(node);
      // Clicking a dir commits into its children (blue pick in the new column).
      if (node.kind === "dir" && node.children.length > 0) {
        path.push(node.children[0]);
      }
      paintMiller();
      const tip = selected();
      if (tip) navigateTo(tip);
      if (ev.type === "dblclick") enterFocus();
    });
    setFocusChrome();
    dock?.syncPathsWidth?.();
    focusSelectedMillerItem();
  };

  /** Focus the selected miller button so further arrows stay on Paths. */
  const focusSelectedMillerItem = () => {
    const btns = miller.querySelectorAll(".fpl-miller-item.selected");
    const last = btns[btns.length - 1];
    if (last instanceof HTMLElement) {
      last.focus({ preventScroll: true });
    }
  };

  /**
   * Siblings of the path tip in its column (root children if path empty).
   * @returns {{ items: OutlineNode[], index: number }}
   */
  const siblingsOfTip = () => {
    const parent = path.length > 1 ? path[path.length - 2] : outline;
    const items = parent.children;
    const tip = selected();
    if (!tip) return { items, index: -1 };
    const index = items.findIndex(
      (c) => c.name === tip.name && c.kind === tip.kind && c.start === tip.start,
    );
    return { items, index };
  };

  /**
   * @param {OutlineNode[]} items
   * @param {number} index
   */
  const selectSiblingAt = (items, index) => {
    if (!items.length) return;
    const i = ((index % items.length) + items.length) % items.length;
    const node = items[i];
    path = path.length === 0 ? [node] : path.slice(0, -1).concat(node);
    paintMiller();
    navigateTo(node);
  };

  /**
   * → / Enter: into first child; on leaf → focuses Monaco, Enter enters scope-Focus.
   * @param {"editor" | "scope"} leafAction
   */
  const millerDescend = (leafAction) => {
    const tip = selected();
    if (!tip) {
      if (outline.children.length) selectSiblingAt(outline.children, 0);
      return;
    }
    if (tip.kind === "dir" && tip.children.length > 0) {
      path = path.concat(tip.children[0]);
      paintMiller();
      navigateTo(tip.children[0]);
      return;
    }
    if (leafAction === "editor") {
      editor.focus();
      return;
    }
    enterFocus();
  };

  const millerBack = () => {
    if (path.length === 0) return;
    path = path.slice(0, -1);
    paintMiller();
    const tip = selected();
    if (tip) navigateTo(tip);
    else if (focus) retargetFocus();
    else clearNavDeco();
  };

  const refreshOutline = () => {
    outline = parseOutline(getSrc());
    path = rematchPath(outline, path);
    paintMiller();
  };

  const scheduleOutline = () => {
    window.clearTimeout(outlineTimer);
    outlineTimer = window.setTimeout(refreshOutline, OUTLINE_MS);
  };

  const enterFocus = () => {
    const node = selected();
    if (!node || focus) return;
    const full = getSrc();
    const lines = full.split("\n");
    const from = node.kind === "dir" ? node.headEnd : node.start;
    const bodyIndent = bodyIndentOf(lines, node);
    const prefix = lines.slice(0, from).join("\n") + (from > 0 ? "\n" : "");
    const suffix =
      node.end < lines.length ? "\n" + lines.slice(node.end).join("\n") : "";
    focus = { node, bodyIndent, prefix, suffix };
    muteLive = true;
    try {
      editor.setValue(extractBody(lines, node));
      paintScopeSelection();
      decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    } finally {
      muteLive = false;
    }
    setFocusChrome();
    scheduleLive();
  };

  const exitFocus = () => {
    if (!focus) return;
    const full = getSrc();
    focus = null;
    muteLive = true;
    try {
      editor.setValue(full);
    } finally {
      muteLive = false;
    }
    writeHash(full);
    setFocusChrome();
    refreshOutline();
    const tip = selected();
    if (tip) navigateTo(tip);
    else clearNavDeco();
    scheduleLive();
  };

  const runOnce = async (btn, { share = false } = {}) => {
    if (btn) btn.disabled = true;
    out.textContent = "Loading…";
    out.dataset.ok = "1";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    const src = getSrc();
    try {
      const { ok, text } = await runFpl(src);
      setOut(out, text, ok);
      if (ok && !focus) {
        lastCells = pairLineResults(src, text);
        decoIds = applyQuokkaDecorations(editor, monaco, lastCells, decoIds);
      } else {
        lastCells = null;
        decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
      }
      if (share) writeHash(src);
    } catch (err) {
      setOut(out, String(err), false);
      lastCells = null;
      decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  const scheduleLive = () => {
    if (muteLive) return;
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      const my = ++gen;
      runOnce(null, { share: false }).then(() => {
        if (my !== gen) return;
      });
    }, LIVE_MS);
  };

  const acceptIndices = (indices) => {
    if (focus) return;
    const model = editor.getModel();
    if (!model || !lastCells) return;
    const ordered = [...indices].sort((a, b) => b - a);
    muteLive = true;
    try {
      for (const i of ordered) {
        const cell = lastCells[i];
        if (!cell || cell.kind !== "result" || !cell.text) continue;
        commitResultNote(model, monaco, i, cell.text);
      }
    } finally {
      muteLive = false;
    }
    writeHash(getSrc());
    scheduleLive();
  };

  for (const btn of document.querySelectorAll(".fpl-browser-mode")) {
    btn.addEventListener("click", () => {
      mode = btn.getAttribute("data-mode") || "paths";
      for (const b of document.querySelectorAll(".fpl-browser-mode")) {
        const on = b === btn;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      }
      paintMiller();
    });
  }

  focusBtn.addEventListener("click", () => enterFocus());
  unfocusBtn.addEventListener("click", () => exitFocus());

  // Collapse Hide columns only when docking did not enhance (static fallback).
  if (!dock && browserToggle && browser) {
    const setBrowserCollapsed = (collapsed) => {
      browser.classList.toggle("collapsed", collapsed);
      browserToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      browserToggle.textContent = collapsed ? "Show columns" : "Hide columns";
      try {
        localStorage.setItem(BROWSER_COLLAPSE_KEY, collapsed ? "1" : "0");
      } catch {
        /* private mode */
      }
    };
    browserToggle.addEventListener("click", () => {
      setBrowserCollapsed(!browser.classList.contains("collapsed"));
    });
    try {
      setBrowserCollapsed(localStorage.getItem(BROWSER_COLLAPSE_KEY) === "1");
    } catch {
      setBrowserCollapsed(false);
    }
  }

  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && focus) {
      ev.preventDefault();
      exitFocus();
      return;
    }
    if (mode !== "paths") return;
    const t = /** @type {HTMLElement | null} */ (ev.target);
    if (!t || !t.closest || !t.closest("#fpl-miller, [data-dock='paths']")) {
      return;
    }
    if (
      t.closest(".monaco-editor") ||
      t.closest("#fpl-out") ||
      t.tagName === "TEXTAREA" ||
      t.tagName === "INPUT"
    ) {
      return;
    }
    if (ev.key === "ArrowUp" || ev.key === "ArrowDown") {
      ev.preventDefault();
      const { items, index } = siblingsOfTip();
      if (!items.length) return;
      if (index < 0) {
        selectSiblingAt(items, ev.key === "ArrowUp" ? items.length - 1 : 0);
      } else {
        selectSiblingAt(items, index + (ev.key === "ArrowUp" ? -1 : 1));
      }
      return;
    }
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      millerDescend("editor");
      return;
    }
    if (ev.key === "Enter") {
      ev.preventDefault();
      millerDescend("scope");
      return;
    }
    if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      millerBack();
    }
  });

  runBtn.addEventListener("click", () => runOnce(runBtn, { share: true }));

  // Reduction stepper: record the run once, then move over it with the keyboard.
  const stepPanel = document.getElementById("fpl-step");
  const stepBtn = /** @type {HTMLButtonElement | null} */ (document.getElementById("fpl-step-open"));
  if (stepPanel && stepBtn) {
    let stepDeco = /** @type {string[]} */ ([]);
    const stepper = mountStepper(stepPanel, {
      onFrame: (f) => {
        stepDeco = editor.deltaDecorations(
          stepDeco,
          f ? [{ range: new monaco.Range(f.line, 1, f.line, 1),
                 options: { isWholeLine: true, className: "fpl-step-line" } }] : [],
        );
        if (f) editor.revealLineInCenterIfOutsideViewport(f.line);
      },
    });
    stepBtn.addEventListener("click", async () => {
      stepBtn.disabled = true;
      stepPanel.hidden = false;
      try {
        stepper.load(await traceFpl(getSrc()));
        stepper.focus();
      } catch (err) {
        stepper.load({ error: String(err) });
      } finally {
        stepBtn.disabled = false;
      }
    });
  }
  clearBtn.addEventListener("click", () => {
    window.clearTimeout(timer);
    gen += 1;
    focus = null;
    muteLive = true;
    try {
      editor.setValue("");
    } finally {
      muteLive = false;
    }
    out.textContent = "";
    out.removeAttribute("data-ok");
    lastCells = null;
    decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    clearNavDeco();
    writeHash("");
    path = [];
    setFocusChrome();
    refreshOutline();
  });
  resetBtn.addEventListener("click", () => {
    window.clearTimeout(timer);
    focus = null;
    muteLive = true;
    try {
      editor.setValue(DEFAULT_SRC);
    } finally {
      muteLive = false;
    }
    out.textContent = "";
    out.removeAttribute("data-ok");
    lastCells = null;
    decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    clearNavDeco();
    writeHash(DEFAULT_SRC);
    path = [];
    setFocusChrome();
    refreshOutline();
    scheduleLive();
  });
  if (acceptBtn) {
    acceptBtn.addEventListener("click", () => {
      if (!lastCells || focus) return;
      const idxs = [];
      for (let i = 0; i < lastCells.length; i++) {
        if (lastCells[i].kind === "result" && lastCells[i].text) idxs.push(i);
      }
      acceptIndices(idxs);
    });
  }

  editor.onDidChangeModelContent(() => {
    if (focus) writeHash(getSrc());
    scheduleOutline();
    scheduleLive();
  });
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
    window.clearTimeout(timer);
    runOnce(runBtn, { share: true });
  });
  // ← at column 1: hand focus back to the Miller selection.
  editor.onKeyDown((ev) => {
    if (ev.keyCode !== monaco.KeyCode.LeftArrow) return;
    if (mode !== "paths") return;
    const pos = editor.getPosition();
    if (!pos || pos.column !== 1) return;
    ev.preventDefault();
    ev.stopPropagation();
    if (!selected()) {
      if (outline.children.length) selectSiblingAt(outline.children, 0);
      else return;
    } else {
      focusSelectedMillerItem();
    }
  });
  editor.addCommand(monaco.KeyCode.Tab, () => {
    const pos = editor.getPosition();
    if (pos && lastCells && !focus) {
      const cell = lastCells[pos.lineNumber - 1];
      if (cell && cell.kind === "result" && cell.text) {
        acceptIndices([pos.lineNumber - 1]);
        return;
      }
    }
    editor.trigger("keyboard", "type", { text: "\t" });
  });

  paintMiller();
  scheduleLive();
}

async function fetchText(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.text();
}

function showSideTab(name) {
  for (const btn of document.querySelectorAll(".fpl-side-tab")) {
    const on = btn.dataset.tab === name;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  }
  for (const panel of document.querySelectorAll(".fpl-side-panel")) {
    const on = panel.id === "fpl-tab-" + name;
    panel.classList.toggle("active", on);
    panel.hidden = !on;
  }
}

function wireSideTabs() {
  for (const btn of document.querySelectorAll(".fpl-side-tab")) {
    btn.addEventListener("click", () => showSideTab(btn.dataset.tab || "instructions"));
  }
}

function setResults(pass, detail) {
  const box = document.getElementById("fpl-results");
  if (!box) return;
  const card = document.createElement("div");
  card.className = "fpl-results-card " + (pass ? "pass" : "fail");
  const h = document.createElement("h2");
  h.textContent = pass ? "All checks passed" : "Check failed";
  const pre = document.createElement("pre");
  pre.textContent = detail;
  card.append(h, pre);
  box.replaceChildren(card);
  showSideTab("results");
}

async function bootKata() {
  wireSideTabs();
  const params = new URLSearchParams(location.search);
  const slug = params.get("id");
  const listEl = $("fpl-kata-list");
  const promptEl = $("fpl-kata-prompt");
  const editor = /** @type {HTMLTextAreaElement} */ ($("fpl-editor"));
  const out = $("fpl-out");
  const runBtn = /** @type {HTMLButtonElement} */ ($("fpl-run"));
  const checkBtn = /** @type {HTMLButtonElement} */ ($("fpl-check"));
  const resetBtn = /** @type {HTMLButtonElement} */ ($("fpl-reset"));

  const index = await fetch(learnBase() + "kata/index.json").then((r) => {
    if (!r.ok) throw new Error("kata index: " + r.status);
    return r.json();
  });

  listEl.innerHTML = "";
  for (const item of index.katas || []) {
    const a = document.createElement("a");
    a.href = "kata.html?id=" + encodeURIComponent(item.id);
    a.textContent = item.title || item.id;
    if (item.id === slug) a.classList.add("active");
    listEl.appendChild(a);
  }

  if (!slug) {
    promptEl.innerHTML =
      "<p><strong>Pick a kata</strong></p><p>Editor holds pure FPL on the left; instructions on the right. Run to try; Check grades against expected stdout.</p>";
    editor.value = "";
    editor.disabled = true;
    runBtn.disabled = true;
    checkBtn.disabled = true;
    resetBtn.disabled = true;
    return;
  }

  const base = learnBase() + "kata/" + encodeURIComponent(slug) + "/";
  const [promptMd, starter, expected] = await Promise.all([
    fetchText(base + "prompt.md"),
    fetchText(base + "starter.fpl"),
    fetchText(base + "expected"),
  ]);

  promptEl.innerHTML = '<pre class="fpl-prompt-md"></pre>';
  // The prompt is an OKF note: its frontmatter is for the bundle, not the reader.
  promptEl.querySelector("pre").textContent = promptMd.replace(/^---\n[\s\S]*?\n---\n+/, "");

  let starterSrc = starter;
  editor.value = starterSrc;
  editor.disabled = false;

  const runKata = async (btn) => {
    btn.disabled = true;
    out.textContent = "Loading…";
    out.dataset.ok = "1";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    try {
      const { ok, text } = await runFpl(editor.value);
      setOut(out, text, ok);
    } catch (err) {
      setOut(out, String(err), false);
    } finally {
      btn.disabled = false;
    }
  };

  runBtn.addEventListener("click", () => runKata(runBtn));
  resetBtn.addEventListener("click", () => {
    editor.value = starterSrc;
    out.textContent = "";
    out.removeAttribute("data-ok");
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
  });
  editor.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
      ev.preventDefault();
      runKata(runBtn);
    }
  });
  checkBtn.addEventListener("click", async () => {
    checkBtn.disabled = true;
    runBtn.disabled = true;
    out.textContent = "Loading…";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    try {
      const { text } = await runFpl(editor.value);
      const { pass, actual, expected: exp } = checkExpected(text, expected);
      if (pass) {
        out.textContent = actual;
        out.dataset.ok = "1";
        out.classList.add("fpl-live-check-pass");
        setResults(true, actual);
      } else {
        const detail =
          "--- actual ---\n" + actual + "--- expected ---\n" + exp;
        out.textContent = detail;
        out.dataset.ok = "0";
        out.classList.add("fpl-live-check-fail");
        setResults(false, detail);
      }
    } catch (err) {
      setOut(out, String(err), false);
      setResults(false, String(err));
    } finally {
      checkBtn.disabled = false;
      runBtn.disabled = false;
    }
  });
}

const page = document.body?.dataset?.fplPage;
if (page === "playground") {
  bootPlayground().catch((err) => {
    const out = document.getElementById("fpl-out");
    if (out) setOut(out, String(err), false);
    else console.error(err);
  });
} else if (page === "kata") {
  bootKata().catch((err) => {
    const out = document.getElementById("fpl-out");
    if (out) setOut(out, String(err), false);
    else console.error(err);
  });
}

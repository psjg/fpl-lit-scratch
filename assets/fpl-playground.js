/**
 * /try playground + kata UI. Buffer is pure FPL; runtime wraps fpl.run.default.src.
 * Playground: Monaco Quokka ghosts + Tab-commit to `; |-` notes. Katas: textarea.
 */
import { runFpl, checkExpected, learnBase } from "./fpl-runtime.js";

const RESULT_PREFIX = "|- ";
const TRAILING_NOTE = /[\t ]*(?:;|⍝)[ \t]*(.*)$/u;

const DEFAULT_SRC = `\
;;; ── frames ──
1 | 1 2 3 +\t; |- 2 3 4
1 2 3 +\t; |- [1‿2‿3 +]
2 | 3 +\t; |- 5
1 | 1 2 3 [-] swap-args\t; |- 1 2 3 - 1
`;

const LIVE_MS = 300;
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

async function bootPlayground() {
  const host = $("fpl-editor");
  const out = $("fpl-out");
  const runBtn = /** @type {HTMLButtonElement} */ ($("fpl-run"));
  const clearBtn = /** @type {HTMLButtonElement} */ ($("fpl-clear"));
  const resetBtn = /** @type {HTMLButtonElement} */ ($("fpl-reset"));
  const acceptBtn = /** @type {HTMLButtonElement | null} */ (
    document.getElementById("fpl-accept")
  );

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

  let decoIds = /** @type {string[]} */ ([]);
  /** @type {{ text: string, kind: string }[] | null} */
  let lastCells = null;
  let timer = 0;
  let gen = 0;
  let muteLive = false;

  const getSrc = () => editor.getValue();

  const runOnce = async (btn, { share = false } = {}) => {
    if (btn) btn.disabled = true;
    out.textContent = "Loading…";
    out.dataset.ok = "1";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    const src = getSrc();
    try {
      const { ok, text } = await runFpl(src);
      setOut(out, text, ok);
      if (ok) {
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

  runBtn.addEventListener("click", () => runOnce(runBtn, { share: true }));
  clearBtn.addEventListener("click", () => {
    window.clearTimeout(timer);
    gen += 1;
    editor.setValue("");
    out.textContent = "";
    out.removeAttribute("data-ok");
    lastCells = null;
    decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    writeHash("");
  });
  resetBtn.addEventListener("click", () => {
    window.clearTimeout(timer);
    editor.setValue(DEFAULT_SRC);
    out.textContent = "";
    out.removeAttribute("data-ok");
    lastCells = null;
    decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    writeHash(DEFAULT_SRC);
    scheduleLive();
  });
  if (acceptBtn) {
    acceptBtn.addEventListener("click", () => {
      if (!lastCells) return;
      const idxs = [];
      for (let i = 0; i < lastCells.length; i++) {
        if (lastCells[i].kind === "result" && lastCells[i].text) idxs.push(i);
      }
      acceptIndices(idxs);
    });
  }

  editor.onDidChangeModelContent(() => scheduleLive());
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
    window.clearTimeout(timer);
    runOnce(runBtn, { share: true });
  });
  editor.addCommand(monaco.KeyCode.Tab, () => {
    const pos = editor.getPosition();
    if (pos && lastCells) {
      const cell = lastCells[pos.lineNumber - 1];
      if (cell && cell.kind === "result" && cell.text) {
        acceptIndices([pos.lineNumber - 1]);
        return;
      }
    }
    editor.trigger("keyboard", "type", { text: "\t" });
  });

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
  promptEl.querySelector("pre").textContent = promptMd;

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

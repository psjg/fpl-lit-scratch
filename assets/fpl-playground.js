/**
 * /try playground + kata UI. Buffer is pure FPL; runtime wraps fpl.run.default.src.
 * Playground: Monaco + Quokka-style after-text decorations. Katas: textarea.
 */
import { runFpl, checkExpected, learnBase } from "./fpl-runtime.js";

const DEFAULT_SRC = `\
;;; ── frames ──
1 | 1 2 3 +\t; 2 3 4
1 2 3 +\t; [1‿2‿3 +]
2 | 3 +\t; 5
1 | 1 2 3 [-] swap-args\t; 1 2 3 - 1
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

/** Pair stdout lines 1:1 with non-blank, non-;;; source lines. */
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
  /** @type {{ text: string, kind: "result" | "skip" | "empty" }[]} */
  const cells = lines.map((line) => {
    const t = line.trim();
    if (t === "") return { text: "", kind: "empty" };
    if (t.startsWith(";;;")) return { text: "", kind: "skip" };
    return { text: "", kind: "empty" };
  });
  for (let j = 0; j < codeIdx.length; j++) {
    cells[codeIdx[j]] = { text: outs[j], kind: "result" };
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
          content: `  ${cell.text}`,
          inlineClassName: "fpl-quokka-after",
          cursorStops: monaco.editor.InjectedTextCursorStops.None,
        },
        showIfCollapsed: true,
      },
    });
  }
  return editor.deltaDecorations(prevIds, next);
}

async function bootPlayground() {
  const host = $("fpl-editor");
  const out = $("fpl-out");
  const runBtn = /** @type {HTMLButtonElement} */ ($("fpl-run"));
  const clearBtn = /** @type {HTMLButtonElement} */ ($("fpl-clear"));
  const resetBtn = /** @type {HTMLButtonElement} */ ($("fpl-reset"));

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
  let timer = 0;
  let gen = 0;

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
        const cells = pairLineResults(src, text);
        decoIds = applyQuokkaDecorations(editor, monaco, cells, decoIds);
      } else {
        decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
      }
      if (share) writeHash(src);
    } catch (err) {
      setOut(out, String(err), false);
      decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  const scheduleLive = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      const my = ++gen;
      runOnce(null, { share: false }).then(() => {
        if (my !== gen) return;
      });
    }, LIVE_MS);
  };

  runBtn.addEventListener("click", () => runOnce(runBtn, { share: true }));
  clearBtn.addEventListener("click", () => {
    window.clearTimeout(timer);
    gen += 1;
    editor.setValue("");
    out.textContent = "";
    out.removeAttribute("data-ok");
    decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    writeHash("");
  });
  resetBtn.addEventListener("click", () => {
    window.clearTimeout(timer);
    editor.setValue(DEFAULT_SRC);
    out.textContent = "";
    out.removeAttribute("data-ok");
    decoIds = applyQuokkaDecorations(editor, monaco, null, decoIds);
    writeHash(DEFAULT_SRC);
    scheduleLive();
  });

  editor.onDidChangeModelContent(() => scheduleLive());
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
    window.clearTimeout(timer);
    runOnce(runBtn, { share: true });
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

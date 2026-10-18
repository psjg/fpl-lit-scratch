/**
 * /try playground + kata UI. Uses shared fpl-runtime.js.
 */
import { runSource, checkExpected, learnBase } from "./fpl-runtime.js";

const DEFAULT_SRC = `frames = "\\n".join(
    [
        ";;; ── frames ──",
        "1 | 1 2 3 +\\t; 2 3 4",
        "1 2 3 +\\t; [1‿2‿3 +]",
        "2 | 3 +\\t; 5",
        "1 | 1 2 3 [-] swap-args\\t; 1 2 3 - 1",
    ]
)
print(fpl.run.default.src(frames), end="")
`;

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

async function runEditor(editor, out, btn, { share = false } = {}) {
  btn.disabled = true;
  out.textContent = "Loading…";
  out.dataset.ok = "1";
  out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
  try {
    const { ok, text } = await runSource(editor.value);
    setOut(out, text, ok);
    if (share) writeHash(editor.value);
  } catch (err) {
    setOut(out, String(err), false);
  } finally {
    btn.disabled = false;
  }
}

function bootPlayground() {
  const editor = /** @type {HTMLTextAreaElement} */ ($("fpl-editor"));
  const out = $("fpl-out");
  const runBtn = /** @type {HTMLButtonElement} */ ($("fpl-run"));
  const clearBtn = /** @type {HTMLButtonElement} */ ($("fpl-clear"));
  const resetBtn = /** @type {HTMLButtonElement} */ ($("fpl-reset"));

  const fromHash = readHash();
  editor.value = fromHash != null && fromHash !== "" ? fromHash : DEFAULT_SRC;

  runBtn.addEventListener("click", () =>
    runEditor(editor, out, runBtn, { share: true }),
  );
  clearBtn.addEventListener("click", () => {
    editor.value = "";
    out.textContent = "";
    out.removeAttribute("data-ok");
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    writeHash("");
  });
  resetBtn.addEventListener("click", () => {
    editor.value = DEFAULT_SRC;
    out.textContent = "";
    out.removeAttribute("data-ok");
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    writeHash(DEFAULT_SRC);
  });

  editor.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
      ev.preventDefault();
      runEditor(editor, out, runBtn, { share: true });
    }
  });
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
      "<p><strong>Pick a kata</strong></p><p>Editor fills the left of the screen; instructions stay on the right (Exercism-style). Run to try; Check grades against expected stdout.</p>";
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
    fetchText(base + "starter.py"),
    fetchText(base + "expected"),
  ]);

  promptEl.innerHTML = '<pre class="fpl-prompt-md"></pre>';
  promptEl.querySelector("pre").textContent = promptMd;

  let starterSrc = starter;
  editor.value = starterSrc;
  editor.disabled = false;

  runBtn.addEventListener("click", () => runEditor(editor, out, runBtn));
  resetBtn.addEventListener("click", () => {
    editor.value = starterSrc;
    out.textContent = "";
    out.removeAttribute("data-ok");
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
  });
  editor.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
      ev.preventDefault();
      runEditor(editor, out, runBtn);
    }
  });
  checkBtn.addEventListener("click", async () => {
    checkBtn.disabled = true;
    runBtn.disabled = true;
    out.textContent = "Loading…";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    try {
      const { text } = await runSource(editor.value);
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
  bootPlayground();
} else if (page === "kata") {
  bootKata().catch((err) => {
    const out = document.getElementById("fpl-out");
    if (out) setOut(out, String(err), false);
    else console.error(err);
  });
}

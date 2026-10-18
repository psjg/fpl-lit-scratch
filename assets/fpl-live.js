/**
 * Editable Quarto fences (class `live`) with a play button.
 * Loads one shared Pyodide and installs fpl-walker from werkbank/pypi/.
 */
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.6/full/pyodide.mjs";

const WHEELS = [
  "lark-1.3.1-py3-none-any.whl",
  "icontract-2.7.3-py3-none-any.whl",
  "asttokens-2.4.1-py2.py3-none-any.whl",
  "typing_extensions-4.16.0-py3-none-any.whl",
  "six-1.17.0-py2.py3-none-any.whl",
  "comm-0.2.3-py3-none-any.whl",
  "fpl_walker-0.0.0-py3-none-any.whl",
];

/** @type {Promise<any> | null} */
let pyodideReady = null;

function pypiBase() {
  return new URL("werkbank/pypi/", document.baseURI || location.href).href;
}

async function ensurePyodide() {
  if (!pyodideReady) {
    pyodideReady = (async () => {
      const { loadPyodide } = await import(PYODIDE_URL);
      const pyodide = await loadPyodide();
      await pyodide.loadPackage("micropip");
      const micropip = pyodide.pyimport("micropip");
      const base = pypiBase();
      await micropip.install(
        WHEELS.map((w) => base + w),
        { deps: false },
      );
      await pyodide.runPythonAsync("import fpl");
      return pyodide;
    })();
  }
  return pyodideReady;
}

function sourceBlocks() {
  return [...document.querySelectorAll("div.sourceCode.live, pre.sourceCode.live")];
}

function codeEl(block) {
  return block.querySelector("code") || block;
}

function ensureWrap(block) {
  if (block.parentElement?.classList.contains("fpl-live-wrap")) {
    return block.parentElement;
  }
  const wrap = document.createElement("div");
  wrap.className = "fpl-live-wrap";
  block.parentNode.insertBefore(wrap, block);
  wrap.appendChild(block);
  return wrap;
}

function ensureOut(wrap) {
  let out = wrap.querySelector(".fpl-live-out");
  if (!out) {
    out = document.createElement("pre");
    out.className = "fpl-live-out";
    wrap.appendChild(out);
  }
  return out;
}

function findToolbar(block) {
  const outer = block.closest(".code-copy-outer") || block.parentElement;
  return (
    outer?.querySelector(".code-copy-button")?.parentElement ||
    outer?.querySelector("[class*='code-copy']")?.parentElement ||
    null
  );
}

function attachPlay(block) {
  const wrap = ensureWrap(block);
  const code = codeEl(block);
  code.setAttribute("contenteditable", "true");
  code.spellcheck = false;

  if (wrap.querySelector(".fpl-live-play")) return;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "fpl-live-play";
  btn.title = "Run";
  btn.setAttribute("aria-label", "Run code");

  const toolbar = findToolbar(block);
  if (toolbar) {
    toolbar.insertBefore(btn, toolbar.firstChild);
  } else {
    btn.style.position = "absolute";
    btn.style.top = "0.35rem";
    btn.style.right = "2.5rem";
    wrap.style.position = "relative";
    wrap.appendChild(btn);
  }

  const out = ensureOut(wrap);

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    out.textContent = "Loading…";
    out.dataset.ok = "1";
    try {
      const pyodide = await ensurePyodide();
      const src = code.innerText.replace(/\u00a0/g, " ");
      pyodide.globals.set("_fpl_live_src", src);
      const result = await pyodide.runPythonAsync(`
import io, sys, traceback
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
_err = None
try:
    exec(_fpl_live_src, globals(), globals())
except Exception:
    _err = traceback.format_exc()
finally:
    sys.stdout = _old
_out = _buf.getvalue()
if _err:
    _out = (_out + ("\\n" if _out else "") + _err)
    _ok = 0
else:
    _ok = 1
(_ok, _out)
`);
      const ok = Number(result.get(0));
      const text = String(result.get(1));
      result.destroy?.();
      out.textContent = text || "(no output)";
      out.dataset.ok = ok ? "1" : "0";
    } catch (err) {
      out.textContent = String(err);
      out.dataset.ok = "0";
    } finally {
      btn.disabled = false;
    }
  });
}

function boot() {
  for (const block of sourceBlocks()) {
    attachPlay(block);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}

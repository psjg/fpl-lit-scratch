/**
 * Shared Pyodide + fpl-walker loader for live fences and the /try playground.
 * Wheel URLs are resolved from this module's location (assets/ → ../werkbank/pypi/).
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

export function siteRoot() {
  return new URL("../", import.meta.url).href;
}

export function pypiBase() {
  return new URL("../werkbank/pypi/", import.meta.url).href;
}

export function learnBase() {
  return new URL("../learn/", import.meta.url).href;
}

export async function ensurePyodide() {
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

/**
 * Exec Python source under a captured stdout. Returns { ok, text }.
 * @param {string} src
 * @returns {Promise<{ ok: boolean, text: string }>}
 */
export async function runSource(src) {
  const pyodide = await ensurePyodide();
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
  const ok = Boolean(Number(result.get(0)));
  const text = String(result.get(1));
  result.destroy?.();
  return { ok, text };
}

/** Normalize trailing newlines for kata checks. */
export function normalizeOut(s) {
  return String(s).replace(/\s+$/u, "") + "\n";
}

/**
 * @param {string} actual
 * @param {string} expected
 */
export function checkExpected(actual, expected) {
  const a = normalizeOut(actual);
  const e = normalizeOut(expected);
  return { pass: a === e, actual: a, expected: e };
}

/**
 * The /pad/ page's backend: fpl.pad, the walker's own pad engine, under
 * Pyodide, behind the routes of fpl/pad_web.py (01-bootstrap/fpl/pad.js
 * reads them). No server: the pad lives in the page's Python.
 *
 * fpl.pad is the bootstrap walker's, not the tangled one the runtime's wheel
 * installs as `fpl`, so it comes from fpl-bootstrap.zip
 * (01-bootstrap/ide/pack_analysis.py), imported beside the wheel's `fpl` as
 * assets/fpl-service.js imports ide/analysis.py.
 */
import { ensurePyodide, pypiBase } from "./fpl-runtime.js";

const BOOT = `
import sys, zipfile, io, json
from pyodide.http import pyfetch
async def _pad_load(url):
    data = await (await pyfetch(url)).bytes()
    zipfile.ZipFile(io.BytesIO(data)).extractall("/bs")
    mine = lambda k: k == "fpl" or k.startswith("fpl.")
    saved = {k: sys.modules.pop(k) for k in [k for k in sys.modules if mine(k)]}
    sys.path.insert(0, "/bs")
    try:
        from fpl.pad import context
        from fpl.pad_web import Pad, shown
    finally:
        sys.path.remove("/bs")
        for k in [k for k in sys.modules if mine(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    pad = Pad((), context({}))
    def change(route, body):
        if not pad.change(route, json.loads(body)):
            raise KeyError(route)
        return json.dumps(shown(pad))
    return change
`;

/** @type {Promise<any> | null} */
let change = null;

function loaded() {
  if (!change) {
    change = (async () => {
      const py = await ensurePyodide();
      await py.runPythonAsync(BOOT);
      py.globals.set("_pad_url", pypiBase() + "fpl-bootstrap.zip");
      return py.runPythonAsync("await _pad_load(_pad_url)");
    })();
  }
  return change;
}

export const pyodide = {
  async load() {
    await loaded();
    return [];
  },
  async change(route, body) {
    const call = await loaded();
    return JSON.parse(call(route, JSON.stringify(body))).cells;
  },
};

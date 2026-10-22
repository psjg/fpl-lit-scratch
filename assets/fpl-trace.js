/**
 * Runs FPL under fpl.trace and opens the Chrome trace-event JSON in the
 * Perfetto UI. Protocol: open ui.perfetto.dev, send "PING" until it
 * answers "PONG", then post {perfetto: {buffer, title}}.
 *   https://perfetto.dev/docs/visualization/deep-linking-to-perfetto-ui
 */

import { ensurePyodide } from "./fpl-runtime.js";
import { span, recordPasses } from "./fpl-telemetry.js";

const PERFETTO = "https://ui.perfetto.dev";

/**
 * @param {string} src
 * @returns {Promise<{ out: string, json: string, events: any[] }>}
 */
export async function runTraced(src) {
  const pyodide = await ensurePyodide();
  return span("fpl.run", "fpl", async () => {
    pyodide.globals.set("_fpl_buf", src);
    const r = await pyodide.runPythonAsync(
      "import fpl_trace as _t\n_t.traced(_fpl_buf)",
    );
    const out = String(r.get(0));
    const json = String(r.get(1));
    r.destroy?.();
    const events = JSON.parse(json).traceEvents;
    recordPasses(events);
    return { out, json, events };
  });
}

/**
 * Opens the trace in Perfetto. Call from a click handler (popups).
 * @param {string} json
 * @param {string} [title]
 * @param {number} [timeoutMs]
 */
export function openInPerfetto(json, title = "FPL run", timeoutMs = 20000) {
  const win = window.open(PERFETTO);
  if (!win) throw new Error("popup blocked");
  const buffer = new TextEncoder().encode(json).buffer;
  return new Promise((resolve, reject) => {
    const ping = setInterval(() => win.postMessage("PING", PERFETTO), 50);
    const stop = setTimeout(() => done(reject, new Error("no PONG")), timeoutMs);
    /** @param {MessageEvent} e */
    const onMsg = (e) => {
      if (e.origin !== PERFETTO || e.data !== "PONG") return;
      win.postMessage({ perfetto: { buffer, title, fileName: "fpl.trace.json" } }, PERFETTO);
      done(resolve, undefined);
    };
    /** @param {Function} f @param {any} v */
    const done = (f, v) => {
      clearInterval(ping);
      clearTimeout(stop);
      window.removeEventListener("message", onMsg);
      f(v);
    };
    window.addEventListener("message", onMsg);
  });
}

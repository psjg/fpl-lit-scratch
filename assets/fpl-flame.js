/**
 * Trace panel for the playground dock: a timeline of one traced run from
 * the Chrome trace events of the .wasm tracer (fpl_trace). Lanes: passes, run lines (width =
 * wall time, label = fuel), calls (a tick per call of a defined word), and
 * the fuel spent as a line. Hover reads the numbers; the button hands the
 * same JSON to Perfetto.
 */

import { maxOf } from "./fpl-max.js";

const NS = "http://www.w3.org/2000/svg";
const LANES = [
  { key: "pass", label: "passes", y: 4, h: 22 },
  { key: "run", label: "lines", y: 32, h: 22 },
  { key: "call", label: "calls", y: 60, h: 18 },
  { key: "fuel", label: "fuel", y: 84, h: 40 },
];

/**
 * @param {string} tag
 * @param {Record<string, string|number>} attrs
 */
function el(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
}

/**
 * @param {HTMLElement} host
 * @param {{ onPerfetto?: () => void }} [opts]
 */
export function createFlamePanel(host, opts = {}) {
  host.textContent = "";
  const bar = document.createElement("div");
  bar.className = "fpl-flame-bar";
  const info = document.createElement("span");
  info.className = "fpl-flame-info";
  info.textContent = "Press Trace to record a run.";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "fpl-btn";
  open.textContent = "Open in Perfetto";
  open.disabled = true;
  open.addEventListener("click", () => opts.onPerfetto?.());
  bar.append(info, open);
  const svgHost = document.createElement("div");
  svgHost.className = "fpl-flame-svg";
  host.append(bar, svgHost);

  /** @param {any[]} events @param {string|null} failure */
  function render(events, failure) {
    svgHost.textContent = "";
    const xs = events.filter((e) => e.ph === "X");
    const end = maxOf(xs.map((e) => e.ts + (e.dur || 0)), 1);
    const calls = events.filter((e) => e.cat === "call");
    const maxFuel = maxOf(calls.map((e) => e.args.fuel || 0), 1);
    const W = 1000;
    const x = (t) => (t / end) * W;
    const svg = el("svg", {
      viewBox: `0 0 ${W} 130`,
      preserveAspectRatio: "none",
      class: "fpl-flame",
      role: "img",
      "aria-label": "Trace timeline",
    });
    const tip = (g, text) => {
      const t = el("title", {});
      t.textContent = text;
      g.append(t);
    };
    for (const e of xs) {
      const lane = LANES.find((l) => l.key === e.cat);
      if (!lane) continue;
      const g = el("g", { class: `fpl-flame-${e.cat}` });
      g.append(
        el("rect", {
          x: x(e.ts),
          y: lane.y,
          width: Math.max(0.6, x(e.dur || 0)),
          height: lane.h,
          rx: 2,
        }),
      );
      const fuel = e.args?.fuel != null ? `, fuel ${e.args.fuel}` : "";
      tip(g, `${e.name}: ${((e.dur || 0) / 1000).toFixed(3)} ms${fuel}`);
      svg.append(g);
    }
    for (const e of calls) {
      const g = el("g", { class: "fpl-flame-call" });
      g.append(el("rect", { x: x(e.ts), y: 60, width: 0.8, height: 18 }));
      tip(g, `${e.name} at ${(e.ts / 1000).toFixed(3)} ms, fuel ${e.args.fuel}`);
      svg.append(g);
    }
    if (calls.length) {
      const pts = calls
        .map((e) => `${x(e.ts).toFixed(1)},${(124 - ((e.args.fuel || 0) / maxFuel) * 38).toFixed(1)}`)
        .join(" ");
      svg.append(el("polyline", { points: pts, class: "fpl-flame-fuelline", fill: "none" }));
    }
    svgHost.append(svg);
    const lanes = document.createElement("div");
    lanes.className = "fpl-flame-lanes";
    lanes.textContent = LANES.map((l) => l.label).join(" · ");
    svgHost.append(lanes);
    const ms = (end / 1000).toFixed(2);
    info.textContent =
      `${ms} ms · ${calls.length} word calls · peak fuel ${maxFuel}` +
      (failure ? ` · refused: ${failure}` : "");
    open.disabled = false;
  }

  return { render };
}

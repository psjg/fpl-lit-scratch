/**
 * Optional Sentry tracing for the playground. Off unless
 * window.FPL_CONFIG.sentryDsn is set (build time, .wasm/assemble.sh from
 * FPL_SENTRY_DSN); no DSN is committed. `span` is a plain call when off.
 *
 * Docs: Sentry.startSpan / startInactiveSpan
 *   https://docs.sentry.io/platforms/javascript/tracing/instrumentation/custom-instrumentation/
 * CDN bundle with tracing + init
 *   https://docs.sentry.io/platforms/javascript/install/loader/
 */

const SENTRY_VERSION = "10.20.0";
const SENTRY_SRC = `https://browser.sentry-cdn.com/${SENTRY_VERSION}/bundle.tracing.min.js`;
const SENTRY_SRI = "sha384-+9wUXHfFUeGwAnEesSxSFwKwBHDbnc32jfpX3HN0aB9RHa4lbS1rqsSnM6DI9/LM";

/** @type {any} */
let Sentry = null;

/** @returns {Promise<boolean>} whether Sentry is active */
export async function initTelemetry() {
  const dsn = globalThis.FPL_CONFIG?.sentryDsn;
  if (!dsn || Sentry) return Boolean(Sentry);
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SENTRY_SRC;
    s.integrity = SENTRY_SRI;
    s.crossOrigin = "anonymous";
    s.onload = resolve;
    s.onerror = reject;
    document.head.append(s);
  }).catch(() => {});
  if (!globalThis.Sentry) return false;
  Sentry = globalThis.Sentry;
  Sentry.init({
    dsn,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: globalThis.FPL_CONFIG.tracesSampleRate ?? 1.0,
  });
  return true;
}

/**
 * Runs fn inside a span (async-aware); a plain call when telemetry is off.
 * @template T
 * @param {string} name
 * @param {string} op
 * @param {() => Promise<T> | T} fn
 * @param {Record<string, string|number|boolean>} [attributes]
 * @returns {Promise<T>}
 */
export async function span(name, op, fn, attributes) {
  if (!Sentry) return fn();
  return Sentry.startSpan({ name, op, attributes }, fn);
}

/**
 * Records finished Python-side pass slices (Chrome trace "X" events, us)
 * as child spans of the active span, so Sentry shows lex/parse/...
 * @param {Array<{name: string, cat?: string, ph: string, ts: number, dur?: number}>} events
 */
export function recordPasses(events) {
  if (!Sentry) return;
  const origin = performance.timeOrigin / 1000 + performance.now() / 1000;
  const parent = Sentry.getActiveSpan();
  const t1 = origin; // seconds, "now"; passes are laid back from the end of the run
  const end = Math.max(...events.filter((e) => e.ph === "X").map((e) => e.ts + (e.dur || 0)), 0);
  for (const e of events) {
    if (e.ph !== "X" || e.cat !== "pass") continue;
    const s = Sentry.startInactiveSpan({
      name: e.name,
      op: "fpl.pass",
      startTime: t1 - (end - e.ts) / 1e6,
      parentSpan: parent,
    });
    s.end(t1 - (end - e.ts - (e.dur || 0)) / 1e6);
  }
}

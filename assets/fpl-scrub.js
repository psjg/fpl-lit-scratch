/**
 * Pure scrubbers for telemetry. The playground keeps the editor source in
 * the URL fragment (`#c=...`, assets/fpl-playground.js), so any URL Sentry
 * records (event request URL, navigation breadcrumbs, span data) could
 * carry the user's program. Everything here drops the fragment.
 */

/**
 * A URL without its fragment.
 * @param {unknown} url
 * @returns {unknown} the input unchanged unless it is a string with a '#'
 */
export function stripFragment(url) {
  if (typeof url !== "string") return url;
  const i = url.indexOf("#");
  return i < 0 ? url : url.slice(0, i);
}

/**
 * Recursively strips fragments from every string that holds one after a
 * URL-ish prefix, and drops `data` keys named like a source payload.
 * Mutates and returns `value`.
 * @template T
 * @param {T} value
 * @returns {T}
 */
function scrubDeep(value) {
  if (Array.isArray(value)) {
    value.forEach((v, i) => (value[i] = scrubDeep(v)));
  } else if (value && typeof value === "object") {
    for (const k of Object.keys(value)) {
      const v = /** @type {any} */ (value)[k];
      if (typeof v === "string") {
        /** @type {any} */ (value)[k] = /^(https?:|\/|[^\s#]*#c=)/.test(v) || k === "url" || k === "from" || k === "to"
          ? stripFragment(v)
          : v;
      } else {
        scrubDeep(v);
      }
    }
  }
  return value;
}

/**
 * Sentry `beforeSend` / `beforeSendTransaction`.
 * @param {any} event
 * @returns {any}
 */
export function scrubEvent(event) {
  if (event?.request) scrubDeep(event.request);
  if (event?.breadcrumbs) scrubDeep(event.breadcrumbs);
  if (event?.spans) scrubDeep(event.spans);
  if (event?.contexts) scrubDeep(event.contexts);
  if (event?.transaction) event.transaction = stripFragment(event.transaction);
  return event;
}

/**
 * Sentry `beforeBreadcrumb`.
 * @param {any} crumb
 * @returns {any}
 */
export function scrubBreadcrumb(crumb) {
  if (crumb?.data) scrubDeep(crumb.data);
  if (typeof crumb?.message === "string") crumb.message = stripFragment(crumb.message);
  return crumb;
}

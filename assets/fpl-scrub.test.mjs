// node --test assets/fpl-scrub.test.mjs : telemetry scrubbing and the Math.max loops.
import test from "node:test";
import assert from "node:assert/strict";
import { scrubEvent, scrubBreadcrumb, stripFragment } from "./fpl-scrub.js";

const SRC = "https://try.example/try/#c=1%202%20Add%2F2";

test("stripFragment drops the fragment and passes non-strings through", () => {
  assert.equal(stripFragment(SRC), "https://try.example/try/");
  assert.equal(stripFragment("https://x/y?q=1"), "https://x/y?q=1");
  assert.equal(stripFragment(undefined), undefined);
});

test("scrubEvent clears the request URL, breadcrumbs and spans", () => {
  const ev = scrubEvent({
    request: { url: SRC, headers: { Referer: SRC } },
    transaction: SRC,
    breadcrumbs: [{ category: "navigation", data: { from: SRC, to: SRC + "x" } }],
    spans: [{ data: { url: SRC } }],
  });
  assert.doesNotMatch(JSON.stringify(ev), /#c=|Add/);
});

test("scrubBreadcrumb clears fetch urls and messages", () => {
  const c = scrubBreadcrumb({ message: SRC, data: { url: SRC, status: 200 } });
  assert.doesNotMatch(JSON.stringify(c), /#c=/);
  assert.equal(c.data.status, 200);
});
import { maxOf } from "./fpl-max.js";

test("maxOf survives 200k elements where Math.max(...xs) throws", () => {
  const xs = Array.from({ length: 200_000 }, (_, i) => i);
  assert.throws(() => Math.max(...xs), RangeError);
  assert.equal(maxOf(xs), 199_999);
  assert.equal(maxOf([], 1), 1);
  assert.equal(maxOf([0.5], 1), 1);
});

// node --test assets/fpl-stepper.test.mjs : the Stepper model, no DOM.
import test from "node:test";
import assert from "node:assert/strict";
import { Stepper } from "./fpl-stepper.js";

const frames = [
  { n: 0, node: "start", line: 1, col: 1, stack: "", waiting: 2 },
  { n: 1, node: "push", line: 1, col: 1, stack: "1", waiting: 1 },
  { n: 2, node: "+", line: 1, col: 3, stack: "2", waiting: 0 },
];

test("back and forward are clamped and report movement", () => {
  const s = new Stepper(frames);
  assert.equal(s.back(), false);
  assert.equal(s.forward(), true);
  assert.equal(s.forward(), true);
  assert.equal(s.forward(), false);
  assert.equal(s.at, 2);
  assert.equal(s.back(), true);
  assert.equal(s.at, 1);
});

test("announcements grow with the level and name the end", () => {
  const s = new Stepper(frames, "done");
  s.go(2);
  assert.equal(s.announce("terse"), "Step 2 of 2. End of run");
  assert.match(s.announce("normal"), /Step 2 of 2, \+\. Stack: 2\. End of run/);
  assert.match(s.announce("full"), /Before: 1\. After: 2\. 0 to run/);
});

test("a refused run says why at its last frame", () => {
  const s = new Stepper(frames, "error", "out of fuel");
  s.go(2);
  assert.match(s.announce("terse"), /Stopped: out of fuel/);
});

test("valuetext names the step", () => {
  const s = new Stepper(frames);
  s.go(1);
  assert.equal(s.valuetext(), "step 1 of 2: push");
});

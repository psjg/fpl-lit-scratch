/**
 * Reduction stepper for /try: back/forward over the recorded evaluation of
 * one run line. The model is plain data (frames from fpl_steprec.py); `Stepper`
 * holds position and announcement text with no DOM, so it can be tested
 * under node; `mountStepper` is the keyboard-first, screen-reader-aware view.
 *
 * Accessibility rules followed (design note 02.04.04):
 *  - all operations are native buttons, a range input and a select: one
 *    tab stop each, no custom key handling beyond Escape and Alt+Arrows;
 *  - announcements go to one role=status region, never by moving focus;
 *  - autoplay announces only "playing" and "paused at step N of M";
 *  - verbosity (terse / normal / full) is the user's setting;
 *  - the whole trace is also a plain ordered list, readable linearly.
 */

export const VERBOSITY = ["terse", "normal", "full"];

export class Stepper {
  /** @param {{n:number,node:string,line:number,col:number,stack:string,waiting:number}[]} frames */
  constructor(frames, end = "done", error = "") {
    this.frames = frames;
    this.end = end;
    this.error = error;
    this.at = 0;
  }

  get last() {
    return this.frames.length - 1;
  }

  /** Move to `n`, clamped; returns whether the position changed. */
  go(n) {
    const next = Math.max(0, Math.min(this.last, n));
    const moved = next !== this.at;
    this.at = next;
    return moved;
  }

  forward() {
    return this.go(this.at + 1);
  }

  back() {
    return this.go(this.at - 1);
  }

  get frame() {
    return this.frames[this.at];
  }

  /** The value text for aria-valuetext on the position slider. */
  valuetext() {
    return `step ${this.at} of ${this.last}: ${this.frame.node}`;
  }

  /**
   * What a screen reader hears after a move: the delta, not the whole
   * state, unless verbosity is "full".
   * @param {"terse"|"normal"|"full"} level
   */
  announce(level = "normal") {
    const f = this.frame;
    const head = `Step ${f.n} of ${this.last}`;
    const edge =
      this.at === this.last
        ? this.end === "error"
          ? `. Stopped: ${this.error}`
          : this.end === "cut"
            ? ". Recording cut here"
            : ". End of run"
        : "";
    if (level === "terse") return head + edge;
    const stack = f.stack === "" ? "empty" : f.stack;
    if (level === "normal") return `${head}, ${f.node}. Stack: ${stack}${edge}`;
    const prev = this.at > 0 ? this.frames[this.at - 1].stack || "empty" : "none";
    return `${head}, ${f.node} at line ${f.line} column ${f.col}. Before: ${prev}. After: ${stack}. ${f.waiting} to run${edge}`;
  }
}

function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  node.append(...kids);
  return node;
}

/**
 * Build the stepper UI inside `root` and return { load(result), hide() }.
 * @param {HTMLElement} root
 * @param {{ onFrame?: (f: object|null) => void }} opts
 */
export function mountStepper(root, opts = {}) {
  let model = /** @type {Stepper|null} */ (null);
  let runs = [];
  let timer = 0;
  let level = "normal";

  const status = el("div", { role: "status", class: "fpl-step-status" });
  const info = el("p", { class: "fpl-step-info" });
  const runSel = el("select", { id: "fpl-step-run", "aria-label": "Run line" });
  const verb = el(
    "select",
    { id: "fpl-step-verb", "aria-label": "Announcement detail" },
    ...VERBOSITY.map((v) => el("option", { value: v }, v)),
  );
  verb.value = level;
  const slider = el("input", {
    type: "range", min: "0", max: "0", value: "0", id: "fpl-step-pos",
    "aria-label": "Step",
  });
  const mk = (label, title, fn) => el("button", { type: "button", class: "fpl-btn", title, onclick: fn }, label);
  const bStart = mk("Start", "Back to step 0", () => move(() => model.go(0)));
  const bBack = mk("Back", "One step back", () => move(() => model.back()));
  const bFwd = mk("Forward", "One step forward", () => move(() => model.forward()));
  const bEnd = mk("End", "Jump to the last step", () => move(() => model.go(model.last)));
  const bPlay = mk("Play", "Play forward, announcing only the pause", () => play());
  const list = el("ol", { start: "0", class: "fpl-step-list", "aria-label": "Every step of this run" });

  root.replaceChildren(
    el("div", { class: "fpl-step-bar" },
      el("label", { for: "fpl-step-run" }, "Line "), runSel,
      bStart, bBack, bFwd, bEnd, bPlay,
      el("label", { for: "fpl-step-verb" }, "Detail "), verb),
    el("div", { class: "fpl-step-pos" }, el("label", { for: "fpl-step-pos" }, "Step "), slider),
    info, status, list,
  );
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && timer) { stop(); say(`Paused at step ${model.at} of ${model.last}`); }
    else if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); move(() => model.forward()); }
    else if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); move(() => model.back()); }
  });

  function say(text) {
    // Replacing the text drops a pending message instead of queueing a burst.
    status.textContent = "";
    setTimeout(() => { status.textContent = text; }, 30);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = 0;
    bPlay.textContent = "Play";
  }

  function play() {
    if (!model) return;
    if (timer) { stop(); say(`Paused at step ${model.at} of ${model.last}`); return; }
    if (model.at === model.last) model.go(0);
    bPlay.textContent = "Pause";
    say("Playing");
    timer = setInterval(() => {
      if (!model.forward()) { stop(); say(model.announce(level)); }
      render(false);
    }, 400);
  }

  function move(fn) {
    if (!model) return;
    stop();
    const moved = fn();
    render(true, moved);
  }

  function render(speak, moved = true) {
    if (!model) return;
    const f = model.frame;
    slider.max = String(model.last);
    slider.value = String(model.at);
    slider.setAttribute("aria-valuetext", model.valuetext());
    bStart.disabled = bBack.disabled = model.at === 0;
    bEnd.disabled = bFwd.disabled = model.at === model.last;
    info.textContent = `${model.valuetext()}. Stack: ${f.stack || "empty"}`;
    for (const li of list.children) li.removeAttribute("aria-current");
    const cur = list.children[model.at];
    if (cur) {
      cur.setAttribute("aria-current", "step");
      cur.scrollIntoView?.({ block: "nearest" });
    }
    opts.onFrame?.(f);
    if (speak) say(moved ? model.announce(level) : model.announce("terse") + ". No further.");
  }

  function pick(i) {
    const r = runs[i];
    model = new Stepper(r.frames, r.end, r.error);
    list.replaceChildren(...r.frames.map((f, n) =>
      el("li", { onclick: () => move(() => model.go(n)) },
        el("span", { class: "fpl-step-node" }, f.node), " ", el("code", {}, f.stack || "empty"))));
    render(false);
  }

  slider.addEventListener("input", () => move(() => model.go(Number(slider.value))));
  verb.addEventListener("change", () => { level = verb.value; });
  runSel.addEventListener("change", () => { stop(); pick(Number(runSel.value)); say(`Run line ${runs[Number(runSel.value)].line}, ${model.last} steps`); });

  return {
    /** Show a trace result from traceFpl. */
    load(result) {
      stop();
      if (result.error || !result.runs?.length) {
        model = null; runs = [];
        info.textContent = result.error || "No run lines to step.";
        list.replaceChildren(); opts.onFrame?.(null);
        say(info.textContent);
        return;
      }
      runs = result.runs;
      runSel.replaceChildren(...runs.map((r, i) => el("option", { value: String(i) }, `${r.line} (${r.frames.length - 1} steps)`)));
      pick(0);
      say(`${runs.length} run line${runs.length === 1 ? "" : "s"} recorded. ${model.announce("terse")}`);
    },
    focus() { slider.focus(); },
  };
}

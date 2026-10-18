/**
 * Editable Quarto fences (class `live`) with a play button.
 * Optional `kata="slug"` loads pure FPL from learn/kata/<slug>/starter.fpl and uses runFpl.
 * Plain .live fences still exec Python via runSource.
 */
import { runSource, runFpl, checkExpected, learnBase } from "./fpl-runtime.js";

function sourceBlocks() {
  return [...document.querySelectorAll("div.sourceCode.live, pre.sourceCode.live")];
}

function codeEl(block) {
  return block.querySelector("code") || block;
}

function kataSlug(block) {
  let el = block;
  for (let i = 0; i < 5 && el; i++) {
    const raw =
      el.getAttribute?.("data-kata") ||
      el.getAttribute?.("kata") ||
      el.dataset?.kata ||
      "";
    if (raw) return String(raw).trim();
    el = el.parentElement;
  }
  const cls = `${block.className || ""} ${block.parentElement?.className || ""}`;
  const m = /\bkata-([a-z0-9-]+)\b/i.exec(cls);
  return m ? m[1] : "";
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

function placeBtn(btn, block, wrap, toolbar) {
  if (toolbar) {
    toolbar.insertBefore(btn, toolbar.firstChild);
  } else {
    btn.style.position = "absolute";
    btn.style.top = "0.35rem";
    btn.style.right = wrap.querySelector(".fpl-live-play") ? "4.5rem" : "2.5rem";
    wrap.style.position = "relative";
    wrap.appendChild(btn);
  }
}

async function loadKata(slug) {
  const base = learnBase() + "kata/" + encodeURIComponent(slug) + "/";
  const [starter, expected] = await Promise.all([
    fetch(base + "starter.fpl").then((r) => {
      if (!r.ok) throw new Error(`kata starter ${slug}: ${r.status}`);
      return r.text();
    }),
    fetch(base + "expected").then((r) => {
      if (!r.ok) throw new Error(`kata expected ${slug}: ${r.status}`);
      return r.text();
    }),
  ]);
  return { starter, expected };
}

function attachPlay(block) {
  const wrap = ensureWrap(block);
  const code = codeEl(block);
  code.setAttribute("contenteditable", "true");
  code.spellcheck = false;

  if (wrap.querySelector(".fpl-live-play")) return;

  const toolbar = findToolbar(block);
  const out = ensureOut(wrap);
  const slug = kataSlug(block);
  const run = slug ? runFpl : runSource;

  const play = document.createElement("button");
  play.type = "button";
  play.className = "fpl-live-play";
  play.title = "Run";
  play.setAttribute("aria-label", "Run code");
  placeBtn(play, block, wrap, toolbar);

  play.addEventListener("click", async () => {
    play.disabled = true;
    out.textContent = "Loading…";
    out.dataset.ok = "1";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    try {
      const src = code.innerText.replace(/\u00a0/g, " ");
      const { ok, text } = await run(src);
      out.textContent = text || "(no output)";
      out.dataset.ok = ok ? "1" : "0";
    } catch (err) {
      out.textContent = String(err);
      out.dataset.ok = "0";
    } finally {
      play.disabled = false;
    }
  });

  if (!slug) return;

  wrap.dataset.kata = slug;
  let expectedText = null;

  loadKata(slug)
    .then(({ starter, expected }) => {
      expectedText = expected;
      if (!code.innerText.trim()) {
        code.textContent = starter;
      }
    })
    .catch((err) => {
      out.textContent = String(err);
      out.dataset.ok = "0";
    });

  const check = document.createElement("button");
  check.type = "button";
  check.className = "fpl-live-check";
  check.title = "Check";
  check.setAttribute("aria-label", "Check against expected");
  check.textContent = "✓";
  placeBtn(check, block, wrap, toolbar);

  check.addEventListener("click", async () => {
    check.disabled = true;
    play.disabled = true;
    out.textContent = "Loading…";
    out.classList.remove("fpl-live-check-pass", "fpl-live-check-fail");
    try {
      if (expectedText == null) {
        const k = await loadKata(slug);
        expectedText = k.expected;
        if (!code.innerText.trim()) code.textContent = k.starter;
      }
      const src = code.innerText.replace(/\u00a0/g, " ");
      const { text } = await runFpl(src);
      const { pass, actual, expected } = checkExpected(text, expectedText);
      if (pass) {
        out.textContent = "PASS\n" + actual;
        out.dataset.ok = "1";
        out.classList.add("fpl-live-check-pass");
      } else {
        out.textContent =
          "FAIL\n--- actual ---\n" + actual + "--- expected ---\n" + expected;
        out.dataset.ok = "0";
        out.classList.add("fpl-live-check-fail");
      }
    } catch (err) {
      out.textContent = String(err);
      out.dataset.ok = "0";
    } finally {
      check.disabled = false;
      play.disabled = false;
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

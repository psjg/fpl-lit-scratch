/**
 * Sparse 2D tile host for /try: discrete camera, edge-peek, per-tile buffers.
 * scaleE is always 0 in this MVP (locked ZUI door left open).
 * Trackpad/wheel moves tiles when focus is outside Monaco/Term (no edge-jank).
 */
const STORAGE_KEY = "fpl-try-tiles-v1";
const PEEK_PX = 40;
const WHEEL_THRESHOLD = 100;
const WHEEL_COOLDOWN_MS = 220;
const PEEK_SETTLE_MS = 150;
/** @typedef {"center" | "N" | "E" | "S" | "W"} Peek */
/** @typedef {{ i: number, j: number, peek: Peek, scaleE: number }} Camera */

/**
 * @typedef {{
 *   move: (di: number, dj: number) => void,
 *   home: () => void,
 *   persistActive: () => void,
 *   focus: () => { i: number, j: number },
 * }} FplTiles
 */

/**
 * @param {{
 *   getSrc: () => string,
 *   setSrc: (src: string) => void,
 *   onLayout?: () => void,
 *   initialSrc?: string,
 * }} opts
 * @returns {FplTiles | null}
 */
export function initTiles(opts) {
  const viewport = document.getElementById("fpl-viewport");
  const world = document.getElementById("fpl-world");
  const dock = document.getElementById("fpl-dock");
  if (!viewport || !world || !dock) return null;

  const state = loadState(opts.initialSrc ?? "");
  /** @type {Camera} */
  let cam = {
    i: state.focus.i | 0,
    j: state.focus.j | 0,
    // Full dock by default (ignore stale directional peek from buggy builds).
    peek: "center",
    scaleE: 0,
  };
  /** @type {Record<string, { src: string }>} */
  let tiles = { ...state.tiles };
  ensureTile(tiles, cam.i, cam.j, opts.initialSrc ?? "");

  let peekTimer = 0;
  let wheelCooldownUntil = 0;
  let accX = 0;
  let accY = 0;

  const keyOf = (i, j) => `${i},${j}`;

  const ensureDomTile = (i, j) => {
    const key = keyOf(i, j);
    let el = world.querySelector(`[data-tile="${key}"]`);
    if (el instanceof HTMLElement) return el;
    el = document.createElement("div");
    el.className = "fpl-tile";
    el.dataset.tile = key;
    el.setAttribute("aria-label", `Tile ${key}`);
    const chrome = document.createElement("div");
    chrome.className = "fpl-tile-chrome";
    chrome.setAttribute("aria-hidden", "true");
    chrome.textContent = key;
    const stub = document.createElement("div");
    stub.className = "fpl-tile-stub";
    stub.textContent = "Empty tile · move here to edit";
    el.append(chrome, stub);
    world.appendChild(el);
    return el;
  };

  const materializeNeighbors = () => {
    ensureDomTile(cam.i, cam.j);
    ensureDomTile(cam.i + 1, cam.j);
    ensureDomTile(cam.i - 1, cam.j);
    ensureDomTile(cam.i, cam.j + 1);
    ensureDomTile(cam.i, cam.j - 1);
  };

  const placeDock = () => {
    const focusEl = ensureDomTile(cam.i, cam.j);
    const stub = focusEl.querySelector(".fpl-tile-stub");
    if (stub) stub.remove();
    if (dock.parentElement !== focusEl) {
      focusEl.appendChild(dock);
    }
    for (const el of world.querySelectorAll(".fpl-tile")) {
      const on = el === focusEl;
      el.classList.toggle("fpl-tile-focus", on);
      if (!on && !el.querySelector(".fpl-tile-stub") && !el.contains(dock)) {
        const s = document.createElement("div");
        s.className = "fpl-tile-stub";
        const k = el.dataset.tile || "?";
        const t = tiles[k];
        s.textContent =
          t && t.src
            ? `Buffer (${t.src.split("\n").length} lines) · ${k}`
            : "Empty tile · move here to edit";
        el.appendChild(s);
      }
    }
  };

  const paint = () => {
    const vw = Math.max(viewport.clientWidth, 320);
    const vh = Math.max(viewport.clientHeight, 240);
    const cellW = vw;
    const cellH = vh;
    materializeNeighbors();
    placeDock();

    for (const el of world.querySelectorAll(".fpl-tile")) {
      const raw = el.getAttribute("data-tile") || "0,0";
      const [is, js] = raw.split(",");
      const i = Number(is);
      const j = Number(js);
      el.style.width = `${cellW}px`;
      el.style.height = `${cellH}px`;
      el.style.left = `${i * cellW}px`;
      el.style.top = `${j * cellH}px`;
    }

    // Focus fills the viewport; directional peek shows ~PEEK_PX of the neighbor.
    let scrollX = cam.i * cellW;
    let scrollY = cam.j * cellH;
    switch (cam.peek) {
      case "E":
        scrollX = cam.i * cellW + PEEK_PX;
        break;
      case "W":
        scrollX = cam.i * cellW - PEEK_PX;
        break;
      case "S":
        scrollY = cam.j * cellH + PEEK_PX;
        break;
      case "N":
        scrollY = cam.j * cellH - PEEK_PX;
        break;
      default:
        break;
    }
    world.style.transform = `translate(${-scrollX}px, ${-scrollY}px)`;
    world.style.width = `${cellW}px`;
    world.style.height = `${cellH}px`;

    const coord = document.getElementById("fpl-tile-coord");
    if (coord) coord.textContent = `${cam.i},${cam.j}`;
    if (opts.onLayout) opts.onLayout();
  };

  const persist = () => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          focus: { i: cam.i, j: cam.j },
          peek: cam.peek,
          scaleE: 0,
          tiles,
        }),
      );
    } catch {
      /* private mode */
    }
  };

  const persistActive = () => {
    ensureTile(tiles, cam.i, cam.j, "");
    tiles[keyOf(cam.i, cam.j)] = { src: opts.getSrc() };
    persist();
  };

  const settlePeekCenter = () => {
    window.clearTimeout(peekTimer);
    peekTimer = window.setTimeout(() => {
      if (cam.peek === "center") return;
      cam = { ...cam, peek: "center", scaleE: 0 };
      paint();
      persist();
    }, PEEK_SETTLE_MS);
  };

  /**
   * @param {number} di
   * @param {number} dj
   */
  const move = (di, dj) => {
    if (di === 0 && dj === 0) return;
    persistActive();
    const ni = cam.i + di;
    const nj = cam.j + dj;
    ensureTile(tiles, ni, nj, "");
    cam = {
      i: ni,
      j: nj,
      peek: peekFromDelta(di, dj, "center"),
      scaleE: 0,
    };
    opts.setSrc(tiles[keyOf(ni, nj)].src);
    paint();
    persist();
    settlePeekCenter();
  };

  const home = () => {
    window.clearTimeout(peekTimer);
    persistActive();
    ensureTile(tiles, 0, 0, "");
    cam = { i: 0, j: 0, peek: "center", scaleE: 0 };
    opts.setSrc(tiles["0,0"].src);
    paint();
    persist();
  };

  // Seed editor if store had a different active tile than hash/default already loaded.
  const activeKey = keyOf(cam.i, cam.j);
  if (tiles[activeKey] && tiles[activeKey].src !== opts.getSrc()) {
    tiles[activeKey] = { src: opts.getSrc() };
  }

  const actions = document.getElementById("fpl-tile-actions");
  if (actions) actions.hidden = false;

  const bind = (id, fn) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener("click", fn);
  };
  bind("fpl-tile-n", () => move(0, -1));
  bind("fpl-tile-s", () => move(0, 1));
  bind("fpl-tile-w", () => move(-1, 0));
  bind("fpl-tile-e", () => move(1, 0));
  bind("fpl-tile-home", () => home());

  /** @param {EventTarget | null} t */
  const isEditorScrollTarget = (t) => {
    if (!(t instanceof Element)) return false;
    if (t.closest(".monaco-editor")) return true;
    if (t.closest("#fpl-out")) return true;
    const tag = t.tagName;
    return tag === "TEXTAREA" || tag === "INPUT";
  };

  window.addEventListener("keydown", (ev) => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (isEditorScrollTarget(ev.target)) return;
    if (ev.key === "ArrowUp") {
      ev.preventDefault();
      move(0, -1);
    } else if (ev.key === "ArrowDown") {
      ev.preventDefault();
      move(0, 1);
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      move(-1, 0);
    } else if (ev.key === "ArrowRight") {
      ev.preventDefault();
      move(1, 0);
    } else if (ev.key === "Home") {
      ev.preventDefault();
      home();
    }
  });

  viewport.addEventListener(
    "wheel",
    (ev) => {
      if (isEditorScrollTarget(ev.target)) return;
      // Also respect focus inside Monaco even if the wheel target is a child overlay.
      const ae = document.activeElement;
      if (ae && isEditorScrollTarget(ae)) return;

      ev.preventDefault();
      const now = performance.now();
      if (now < wheelCooldownUntil) return;

      accX += ev.deltaX;
      accY += ev.deltaY;
      if (Math.abs(accX) < WHEEL_THRESHOLD && Math.abs(accY) < WHEEL_THRESHOLD) {
        return;
      }
      if (Math.abs(accX) >= Math.abs(accY)) {
        const di = accX > 0 ? 1 : -1;
        accX = 0;
        accY = 0;
        wheelCooldownUntil = now + WHEEL_COOLDOWN_MS;
        move(di, 0);
      } else {
        const dj = accY > 0 ? 1 : -1;
        accX = 0;
        accY = 0;
        wheelCooldownUntil = now + WHEEL_COOLDOWN_MS;
        move(0, dj);
      }
    },
    { passive: false },
  );

  const ro = new ResizeObserver(() => paint());
  ro.observe(viewport);

  document.documentElement.classList.add("fpl-tiles-ready");
  paint();
  persist();

  return {
    move,
    home,
    persistActive,
    focus: () => ({ i: cam.i, j: cam.j }),
  };
}

/**
 * Active tile source from storage (for boot before Monaco).
 * @param {string} fallback
 */
export function peekActiveTileSrc(fallback) {
  const state = loadState(fallback);
  const key = `${state.focus.i | 0},${state.focus.j | 0}`;
  const t = state.tiles[key];
  return t && typeof t.src === "string" ? t.src : fallback;
}

/**
 * @param {string} fallback
 */
function loadState(fallback) {
  /** @type {{ focus: { i: number, j: number }, peek: Peek, tiles: Record<string, { src: string }> }} */
  const empty = {
    focus: { i: 0, j: 0 },
    peek: "center",
    tiles: { "0,0": { src: fallback } },
  };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return empty;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object") return empty;
    const i = Number(data.focus?.i) || 0;
    const j = Number(data.focus?.j) || 0;
    /** @type {Record<string, { src: string }>} */
    const tiles = {};
    if (data.tiles && typeof data.tiles === "object") {
      for (const [k, v] of Object.entries(data.tiles)) {
        if (v && typeof v === "object" && typeof v.src === "string") {
          tiles[k] = { src: v.src };
        }
      }
    }
    if (!tiles[`${i},${j}`]) tiles[`${i},${j}`] = { src: fallback };
    return {
      focus: { i, j },
      peek: "center",
      tiles,
    };
  } catch {
    return empty;
  }
}

/**
 * @param {Record<string, { src: string }>} tiles
 * @param {number} i
 * @param {number} j
 * @param {string} seed
 */
function ensureTile(tiles, i, j, seed) {
  const k = `${i},${j}`;
  if (!tiles[k]) tiles[k] = { src: seed };
}

/**
 * @param {number} di
 * @param {number} dj
 * @param {Peek} prev
 * @returns {Peek}
 */
function peekFromDelta(di, dj, prev) {
  if (di > 0) return "E";
  if (di < 0) return "W";
  if (dj > 0) return "S";
  if (dj < 0) return "N";
  return prev;
}

/**
 * Progressive docking for /try: dockview over the curlable Paths/Edit/Term shell.
 * Fail → leave the static CSS grid; success → html.fpl-dock-ready.
 * When Paths sits beside Edit, panel width stays fixed (default / drag / layout);
 * Miller columns scroll horizontally inside the panel.
 */
const DOCKVIEW_VER = "8.6.0";
// dockview's main.esm.mjs is `export * from "dockview-core"` (bare specifier — breaks
// in the browser). Import the self-contained dockview-core ESM; CSS stays on `dockview`.
const DOCKVIEW_ESM = `https://cdn.jsdelivr.net/npm/dockview-core@${DOCKVIEW_VER}/dist/package/main.esm.mjs`;
const STORAGE_KEY = "fpl-try-dock-v2";
const PANEL_IDS = /** @type {const} */ (["paths", "edit", "term"]);
const TITLES = { paths: "Paths", edit: "Edit", term: "Term" };
/** Floor so Paths cannot be crushed empty (~12rem). */
const PATHS_MIN_W = 192;
/** Default Paths width when side-docked (~2 columns); user may drag wider/narrower. */
const PATHS_DEFAULT_W = 352;

/**
 * @typedef {{
 *   reset: () => void,
 *   showPaths: () => void,
 *   syncPathsWidth: () => void,
 *   dispose: () => void,
 * }} FplDock
 */

/**
 * @param {{ onLayout?: () => void }} [opts]
 * @returns {Promise<FplDock | null>}
 */
export async function initDock(opts = {}) {
  const host = document.getElementById("fpl-dock");
  if (!host) return null;

  /** @type {Record<string, HTMLElement>} */
  const sections = {};
  for (const id of PANEL_IDS) {
    const el = host.querySelector(`[data-dock="${id}"]`);
    if (!(el instanceof HTMLElement)) return null;
    sections[id] = el;
  }

  let mod;
  try {
    mod = await import(DOCKVIEW_ESM);
  } catch (err) {
    console.warn("fpl-dock: dockview failed to load; static layout kept", err);
    return null;
  }

  const { createDockview, themeDark } = mod;
  if (typeof createDockview !== "function") {
    console.warn("fpl-dock: createDockview missing");
    return null;
  }

  for (const el of Object.values(sections)) el.remove();

  const onLayout = opts.onLayout;
  /** @type {ReturnType<typeof createDockview> | null} */
  let api = null;
  let saveTimer = 0;
  let applying = false;

  const renderer = (id) => {
    const el = sections[id];
    el.classList.add("fpl-dock-mounted");
    return {
      element: el,
      init() {},
      layout() {
        if (id === "edit" && onLayout) onLayout();
      },
      onShow() {
        if (id === "edit" && onLayout) {
          requestAnimationFrame(() => onLayout());
        }
        syncPathsButton();
        if (id === "paths") {
          requestAnimationFrame(() => syncPathsWidth());
        }
      },
      dispose() {},
    };
  };

  try {
    api = createDockview(host, {
      theme: themeDark,
      createComponent: (options) => {
        const name = options.name;
        if (PANEL_IDS.includes(/** @type {*} */ (name))) {
          return renderer(name);
        }
        const fallback = document.createElement("div");
        fallback.textContent = `Unknown panel: ${name}`;
        return { element: fallback, init() {}, dispose() {} };
      },
    });
  } catch (err) {
    console.warn("fpl-dock: createDockview failed; restoring static shell", err);
    restoreStatic(host, sections);
    return null;
  }

  const syncPathsButton = () => {
    const btn = document.getElementById("fpl-dock-paths");
    if (!(btn instanceof HTMLButtonElement) || !api) return;
    const open = api.getPanel("paths") != null;
    btn.disabled = open;
    btn.setAttribute("aria-pressed", open ? "true" : "false");
  };

  const persist = () => {
    if (!api || applying) return;
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(api.toJSON()));
      } catch {
        /* private mode */
      }
    }, 200);
  };

  /**
   * Paths beside Edit/Term (same vertical band, side-by-side).
   * @returns {boolean}
   */
  const isPathsHorizontal = () => {
    const pathsEl = sections.paths;
    const editEl = sections.edit;
    const termEl = sections.term;
    if (!pathsEl.isConnected) return false;
    const pr = pathsEl.getBoundingClientRect();
    if (pr.width < 2 || pr.height < 2) return false;
    for (const other of [editEl, termEl]) {
      if (!other.isConnected) continue;
      const or_ = other.getBoundingClientRect();
      if (or_.width < 2) continue;
      const overlapY =
        Math.min(pr.bottom, or_.bottom) - Math.max(pr.top, or_.top);
      const band = Math.min(pr.height, or_.height);
      if (band <= 0 || overlapY < band * 0.45) continue;
      const gap = Math.min(
        Math.abs(pr.right - or_.left),
        Math.abs(or_.right - pr.left),
      );
      if (gap < 48) return true;
    }
    return false;
  };

  /**
   * When Paths is beside Edit: mark side layout + scroll Miller to tip.
   * Does not resize the Paths panel — width stays default / drag / saved layout.
   */
  const syncPathsWidth = () => {
    if (!api || applying) return;
    const panel = api.getPanel("paths");
    if (!panel) {
      document.documentElement.classList.remove("fpl-paths-side");
      return;
    }
    // Prefer geometry; if rects are not ready yet, assume side layout after default/left add.
    let horizontal = isPathsHorizontal();
    if (!horizontal && panel.api) {
      // Default and reopen use direction left — treat as side until geometry says otherwise.
      const pr = sections.paths.getBoundingClientRect();
      const er = sections.edit.getBoundingClientRect();
      if (pr.width > 2 && er.width > 2 && Math.abs(pr.top - er.top) < 80) {
        horizontal = true;
      }
    }
    document.documentElement.classList.toggle("fpl-paths-side", horizontal);
    try {
      panel.api.setConstraints({
        minimumWidth: PATHS_MIN_W,
        maximumWidth: Number.MAX_SAFE_INTEGER,
      });
    } catch {
      /* older binding */
    }
    if (!horizontal) return;
    const miller = document.getElementById("fpl-miller");
    if (miller instanceof HTMLElement) {
      // Keep the deepest column in view (Finder-style).
      miller.scrollLeft = miller.scrollWidth;
    }
    if (onLayout) requestAnimationFrame(() => onLayout());
  };

  /**
   * Default: Paths left of Edit (fixed width), Term right of Edit.
   * @param {NonNullable<typeof api>} dock
   */
  const applyDefault = (dock) => {
    applying = true;
    try {
      dock.clear();
      dock.addPanel({
        id: "edit",
        component: "edit",
        title: TITLES.edit,
      });
      dock.addPanel({
        id: "paths",
        component: "paths",
        title: TITLES.paths,
        initialWidth: PATHS_DEFAULT_W,
        minimumWidth: PATHS_MIN_W,
        position: { referencePanel: "edit", direction: "left" },
      });
      dock.addPanel({
        id: "term",
        component: "term",
        title: TITLES.term,
        position: { referencePanel: "edit", direction: "right" },
      });
    } finally {
      applying = false;
    }
    syncPathsButton();
    requestAnimationFrame(() => {
      syncPathsWidth();
      if (onLayout) onLayout();
    });
  };

  const tryRestore = () => {
    let raw = null;
    try {
      raw = localStorage.getItem(STORAGE_KEY);
    } catch {
      raw = null;
    }
    if (!raw) {
      applyDefault(api);
      return;
    }
    try {
      applying = true;
      api.fromJSON(JSON.parse(raw));
    } catch (err) {
      console.warn("fpl-dock: bad saved layout; resetting", err);
      applyDefault(api);
      return;
    } finally {
      applying = false;
    }
    if (!api.getPanel("edit") || !api.getPanel("term")) {
      applyDefault(api);
      return;
    }
    syncPathsButton();
    requestAnimationFrame(() => {
      syncPathsWidth();
      if (onLayout) onLayout();
    });
  };

  const layoutHost = () => {
    if (!api) return;
    const rect = host.getBoundingClientRect();
    api.layout(rect.width, rect.height);
    if (onLayout) onLayout();
  };

  tryRestore();
  layoutHost();
  requestAnimationFrame(() => syncPathsWidth());

  api.onDidLayoutChange(() => {
    persist();
    if (onLayout) onLayout();
    syncPathsButton();
  });
  api.onDidRemovePanel(() => {
    syncPathsButton();
    document.documentElement.classList.remove("fpl-paths-side");
  });
  api.onDidAddPanel(() => {
    syncPathsButton();
    requestAnimationFrame(() => syncPathsWidth());
  });

  const ro = new ResizeObserver(() => {
    layoutHost();
    syncPathsWidth();
  });
  ro.observe(host);

  document.documentElement.classList.add("fpl-dock-ready");
  host.classList.add("fpl-dock--ready");

  const actions = document.getElementById("fpl-dock-actions");
  if (actions) actions.hidden = false;

  const resetBtn = document.getElementById("fpl-dock-reset");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* private mode */
      }
      applyDefault(api);
      persist();
    });
  }

  const pathsBtn = document.getElementById("fpl-dock-paths");
  if (pathsBtn) {
    pathsBtn.addEventListener("click", () => {
      if (!api || api.getPanel("paths")) return;
      const ref = api.getPanel("edit") || api.getPanel("term");
      api.addPanel({
        id: "paths",
        component: "paths",
        title: TITLES.paths,
        initialWidth: PATHS_DEFAULT_W,
        minimumWidth: PATHS_MIN_W,
        position: ref
          ? { referencePanel: ref.id, direction: "left" }
          : undefined,
      });
      syncPathsButton();
      requestAnimationFrame(() => syncPathsWidth());
      persist();
    });
  }

  return {
    reset: () => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* private mode */
      }
      applyDefault(api);
      persist();
    },
    showPaths: () => pathsBtn?.click(),
    syncPathsWidth: () => {
      // Two frames: column DOM + dockview geometry both need to settle.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => syncPathsWidth());
      });
    },
    dispose: () => {
      window.clearTimeout(saveTimer);
      ro.disconnect();
      api?.dispose();
      document.documentElement.classList.remove("fpl-dock-ready");
      document.documentElement.classList.remove("fpl-paths-side");
      host.classList.remove("fpl-dock--ready");
    },
  };
}

/**
 * @param {HTMLElement} host
 * @param {Record<string, HTMLElement>} sections
 */
function restoreStatic(host, sections) {
  for (const id of PANEL_IDS) {
    const el = sections[id];
    if (el && !el.isConnected) host.appendChild(el);
  }
}

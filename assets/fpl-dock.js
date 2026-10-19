/**
 * Progressive docking for /try: dockview over the curlable Paths/Edit/Term shell.
 * Fail → leave the static CSS grid; success → html.fpl-dock-ready.
 */
const DOCKVIEW_VER = "8.6.0";
// dockview's main.esm.mjs is `export * from "dockview-core"` (bare specifier — breaks
// in the browser). Import the self-contained dockview-core ESM; CSS stays on `dockview`.
const DOCKVIEW_ESM = `https://cdn.jsdelivr.net/npm/dockview-core@${DOCKVIEW_VER}/dist/package/main.esm.mjs`;
const STORAGE_KEY = "fpl-try-dock-v1";
const PANEL_IDS = /** @type {const} */ (["paths", "edit", "term"]);
const TITLES = { paths: "Paths", edit: "Edit", term: "Term" };

/**
 * @typedef {{
 *   reset: () => void,
 *   showPaths: () => void,
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
   * Default: Paths on top (~30%), Edit | Term below.
   * @param {NonNullable<typeof api>} dock
   */
  const applyDefault = (dock) => {
    applying = true;
    try {
      dock.clear();
      const h = Math.max(host.clientHeight, 240);
      const pathsH = Math.round(h * 0.3);
      dock.addPanel({
        id: "paths",
        component: "paths",
        title: TITLES.paths,
        initialHeight: pathsH,
      });
      dock.addPanel({
        id: "edit",
        component: "edit",
        title: TITLES.edit,
        position: { referencePanel: "paths", direction: "below" },
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
    if (onLayout) requestAnimationFrame(() => onLayout());
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
    // Ensure every known panel still has a component binding.
    for (const id of PANEL_IDS) {
      if (!api.getPanel(id) && id !== "paths") {
        // Missing edit/term → full reset; paths alone may be closed on purpose.
        if (id === "edit" || id === "term") {
          applyDefault(api);
          return;
        }
      }
    }
    if (!api.getPanel("edit") || !api.getPanel("term")) {
      applyDefault(api);
      return;
    }
    syncPathsButton();
    if (onLayout) requestAnimationFrame(() => onLayout());
  };

  const layoutHost = () => {
    if (!api) return;
    const rect = host.getBoundingClientRect();
    api.layout(rect.width, rect.height);
    if (onLayout) onLayout();
  };

  tryRestore();
  layoutHost();

  api.onDidLayoutChange(() => {
    persist();
    if (onLayout) onLayout();
    syncPathsButton();
  });
  api.onDidRemovePanel(() => syncPathsButton());
  api.onDidAddPanel(() => syncPathsButton());

  const ro = new ResizeObserver(() => layoutHost());
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
      const h = Math.max(host.clientHeight, 240);
      api.addPanel({
        id: "paths",
        component: "paths",
        title: TITLES.paths,
        initialHeight: Math.round(h * 0.3),
        position: ref
          ? { referencePanel: ref.id, direction: "above" }
          : undefined,
      });
      syncPathsButton();
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
    dispose: () => {
      window.clearTimeout(saveTimer);
      ro.disconnect();
      api?.dispose();
      document.documentElement.classList.remove("fpl-dock-ready");
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

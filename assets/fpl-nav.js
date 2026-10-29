/*
 * fpl-nav.js: the page's own sections live in the sidebar, under its
 * entry, not in a column of their own.
 *
 * Quarto writes the page's table of contents into the right margin
 * (#quarto-margin-sidebar > #TOC) and marks the page's entry in the left
 * sidebar active. This moves the TOC under that entry, as a nested list
 * in the sidebar's own style, so the right margin is free for the facts
 * (fpl-annot.js). The links are the same elements, so Quarto's scroll
 * tracking (quarto.js, which took hold of them at load) keeps marking
 * the current section.
 *
 * A section with subsections gets a chevron like the sidebar's own; its
 * list is open while the section or one of its subsections is current,
 * or when the chevron was clicked.
 */
(() => {
  "use strict";
  const toc = document.querySelector("#quarto-margin-sidebar #TOC");
  const here = document.querySelector("#quarto-sidebar .sidebar-link.active");
  const list = toc?.querySelector("ul");
  if (!toc || !here || !list) return;
  const item = here.closest("li.sidebar-item");
  if (!item) return;
  list.className = "fpl-toc list-unstyled";
  for (const li of list.querySelectorAll("li")) {
    const sub = li.querySelector(":scope > ul");
    if (!sub) continue;
    sub.className = "fpl-toc list-unstyled";
    const toggle = document.createElement("a");
    toggle.className = "sidebar-item-toggle text-start fpl-toc-toggle";
    toggle.setAttribute("role", "button");
    toggle.setAttribute("aria-label", "Toggle section");
    toggle.innerHTML = '<i class="bi bi-chevron-right ms-2"></i>';
    toggle.onclick = (ev) => { ev.preventDefault(); li.classList.toggle("is-open"); };
    li.insertBefore(toggle, sub);
  }
  toc.querySelector("#toc-title")?.remove();
  item.append(list);
  toc.remove();
})();

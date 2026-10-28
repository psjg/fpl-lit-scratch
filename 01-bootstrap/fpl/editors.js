/**
 * The editors a pad cell can be typed in. Each factory has `ready()`, which
 * loads what the editor needs once, and `make(host, text, hooks)`, which puts
 * an editor for `text` into `host` and returns {value(), focus(caret)}. The
 * hooks are the pad's keys, the same for every editor:
 *
 *   input()     the text changed
 *   evaluate()  Shift+Enter, Ctrl+Enter or Cmd+Enter
 *   up()        ArrowUp on the first line; down() ArrowDown on the last
 *   remove()    Backspace in an empty cell
 *
 * `plain` is a textarea with the tokens of fpl-language.js painted behind it
 * (highlight.js), so it needs nothing beyond this page. The palette is the
 * playground's dark theme (assets/fpl-playground.js), with a light twin.
 * The editor also gives cursor() and set(text, caret), for a page that
 * rewrites the buffer and puts the caret where the evaluation went.
 */

import {fplMonarch} from "./fpl-language.js";
import {painted} from "./highlight.js";

/** Colours by token prefix, for the dark and the light scheme. */
export const PALETTE = {
	dark: {
		"comment.doc": {color: "#7ec699", style: "italic"},
		"comment.section": {color: "#7ec699", weight: "bold"},
		"comment.file": {color: "#7ec699", weight: "bold"},
		"comment": {color: "#6a737d", style: "italic"},
		"string": {color: "#ce9178"},
		"string.raw": {color: "#d7ba7d"},
		"number": {color: "#b5cea8"},
		"keyword.sigil": {color: "#c586c0"},
		"operator.modifier": {color: "#dcdcaa"},
		"type.path": {color: "#4ec9b0"},
		"delimiter.bar": {color: "#569cd6", weight: "bold"},
		"delimiter.island": {color: "#d7ba7d"},
	},
	light: {
		"comment.doc": {color: "#22863a", style: "italic"},
		"comment.section": {color: "#22863a", weight: "bold"},
		"comment.file": {color: "#22863a", weight: "bold"},
		"comment": {color: "#6a737d", style: "italic"},
		"string": {color: "#a31515"},
		"string.raw": {color: "#9a6700"},
		"number": {color: "#098658"},
		"keyword.sigil": {color: "#af00db"},
		"operator.modifier": {color: "#795e26"},
		"type.path": {color: "#267f99"},
		"delimiter.bar": {color: "#0451a5", weight: "bold"},
		"delimiter.island": {color: "#9a6700"},
	},
};

/** The scheme the page shows now. */
export function scheme() {
	return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** The textarea editor, its text painted by highlight.js. */
export const plain = {
	async ready() {},

	make(host, text, hooks) {
		host.className = "editor plain";
		const paint = document.createElement("pre");
		paint.className = "paint";
		paint.setAttribute("aria-hidden", "true");
		const area = document.createElement("textarea");
		area.spellcheck = false;
		area.value = text;
		host.append(paint, area);

		function fit() {
			area.rows = Math.max(1, area.value.split("\n").length);
			painted(paint, fplMonarch, area.value, PALETTE[scheme()]);
		}

		function insert(snippet) {
			if (!document.execCommand("insertText", false, snippet)) {
				area.setRangeText(snippet, area.selectionStart, area.selectionEnd, "end");
			}
			fit();
		}

		function keyed(event) {
			const before = area.value.slice(0, area.selectionStart);
			const after = area.value.slice(area.selectionEnd);
			const line = before.slice(before.lastIndexOf("\n") + 1);
			if (event.key === "Enter" && (event.shiftKey || event.ctrlKey || event.metaKey)) {
				event.preventDefault();
				hooks.evaluate();
			} else if (event.key === "Enter") {
				event.preventDefault();
				insert("\n" + line.match(/^\t*/)[0]);
			} else if (event.key === "Tab" && !event.shiftKey) {
				event.preventDefault();
				insert("\t");
			} else if (event.key === "Tab") {
				event.preventDefault();
				const start = before.length - line.length;
				if (area.value[start] === "\t") {
					area.setRangeText("", start, start + 1, "preserve");
					fit();
				}
			} else if (event.key === "ArrowUp" && !before.includes("\n")) {
				if (hooks.up()) event.preventDefault();
			} else if (event.key === "ArrowDown" && !after.includes("\n")) {
				if (hooks.down()) event.preventDefault();
			} else if (event.key === "Backspace" && area.value === "") {
				if (hooks.remove()) event.preventDefault();
			}
		}

		area.addEventListener("input", () => { fit(); hooks.input(); });
		area.addEventListener("keydown", keyed);
		fit();
		return {
			value: () => area.value,
			cursor: () => area.selectionStart,
			set(text, caret) {
				area.value = text;
				fit();
				area.focus();
				area.setSelectionRange(caret, caret);
			},
			focus(caret) {
				area.focus();
				const at = caret === "start" ? 0 : area.value.length;
				area.setSelectionRange(at, at);
				area.scrollIntoView({block: "nearest"});
			},
		};
	},
};

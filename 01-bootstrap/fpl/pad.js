/**
 * The pad's page: cells stacked top to bottom, the draft cell last.
 *
 * The page holds only what is typed and not yet run; the pad itself lives
 * behind a backend, which takes the routes of fpl/pad_web.py and answers
 * with the pad, {cells: [{source, status, bar, turns, changes}], bar}: each
 * cell under its REPL phrase bar, and the bar of the cell to come.
 *
 *   load()               the pad as it stands
 *   change(route, body)  "/run" {index, source}, "/remove" {index}, "/reset"
 *
 * `http` is the backend of `python -m fpl pad`; the site's /pad/ page passes
 * one that runs fpl.pad under Pyodide (assets/fpl-pad.js). Both pages share
 * this file, so they share the keys, which the cell editor (editors.js, or
 * monaco.js when the page is opened with ?editor=monaco) turns into the
 * hooks below:
 *
 *   Shift+Enter, Ctrl+Enter, Cmd+Enter  evaluate the cell, and every cell below
 *   Enter                               a newline, with the line's tabs
 *   Tab, Shift+Tab                      a tab in, one leading tab out
 *   ArrowUp / ArrowDown at the edge     the cell above / below
 *   Backspace in an empty cell          remove the cell
 */

import {plain} from "./editors.js";

/** The cell editor the page's URL asks for: `?editor=monaco`, else plain. */
export async function chosen(search) {
	const name = new URLSearchParams(search).get("editor");
	return name === "monaco" ? (await import("./monaco.js")).monaco : plain;
}

/** The backend of `python -m fpl pad`: the routes over HTTP. */
export const http = {
	async load() {
		return answer(await fetch("pad"));
	},
	async change(route, body) {
		return answer(await fetch(route.slice(1), {
			method: "POST",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify(body),
		}));
	},
};

async function answer(response) {
	if (!response.ok) throw new Error(await response.text());
	return response.json();
}

/**
 * Draw the pad into `root`, with `said` for messages, on `backend`, each
 * cell typed in an `editor` of editors.js.
 * @param {{load(): Promise<object>, change(route: string, body: object): Promise<object>}} backend
 */
export async function mount(backend, root, said, editor = plain) {
	let cells = [];
	let next = "";
	let editors = [];

	function texts() {
		return editors.map(each => each.value());
	}

	function render(typed, focus, caret) {
		const staleBy = {};
		cells.forEach((cell, j) => cell.changes.forEach(i => (staleBy[i] = j)));
		const drafted = {source: "", status: "draft", bar: next, turns: [], changes: []};
		editors.forEach(each => each.dispose?.());
		editors = [];
		root.replaceChildren(...[...cells, drafted].map(
			(cell, i) => drawn(cell, i, typed[i] ?? cell.source, staleBy[i])));
		move(Math.min(focus, cells.length), caret);
	}

	function drawn(cell, i, text, staleBy) {
		const section = document.createElement("section");
		section.className = "cell";
		section.dataset.status = cell.status;
		const bar = document.createElement("div");
		bar.className = "bar";
		bar.textContent = cell.bar;
		const host = document.createElement("div");
		const typed = editor.make(host, text, {
			input: () => section.classList.toggle(
				"edited", i < cells.length && typed.value() !== cell.source),
			evaluate: () => evaluate(i, typed.value()),
			up: () => i > 0 && move(i - 1, "end"),
			down: () => i < cells.length && move(i + 1, "start"),
			remove: () => i < cells.length && remove(i),
		});
		editors[i] = typed;
		const turns = document.createElement("pre");
		turns.className = "turns";
		const lines = cell.turns.map(line => [line, line.startsWith(";;") ? "note" : ""]);
		if (staleBy !== undefined) {
			lines.push([`;; cell ${staleBy + 1} changed this result`, "stale"]);
		}
		for (const [line, kind] of lines) {
			const span = document.createElement("span");
			span.className = kind;
			span.textContent = line + "\n";
			turns.append(span);
		}
		section.append(bar, host, turns);
		return section;
	}

	async function changed(route, body, typed, focus, caret) {
		try {
			({cells, bar: next} = await backend.change(route, body));
		} catch (error) {
			said.textContent = String(error);
			return;
		}
		said.textContent = "";
		render(typed, focus, caret);
	}

	function evaluate(i, source) {
		const typed = texts();
		const appended = i === cells.length;
		if (appended && !source.trim()) return;
		changed("/run", {index: i, source}, appended ? [...typed, ""] : typed, i + 1, "end");
	}

	function remove(i) {
		const typed = texts();
		typed.splice(i, 1);
		changed("/remove", {index: i}, typed, Math.max(0, i - 1), "end");
		return true;
	}

	function move(i, caret) {
		editors[i].focus(caret);
		return true;
	}

	await editor.ready();
	return {
		reset: () => changed("/reset", {}, [""], 0, "end"),
		ready: (async () => {
			({cells, bar: next} = await backend.load());
			render([], cells.length, "end");
		})(),
	};
}

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
 * this file, so they share the keys:
 *
 *   Shift+Enter, Ctrl+Enter, Cmd+Enter  evaluate the cell, and every cell below
 *   Enter                               a newline, with the line's tabs
 *   Tab, Shift+Tab                      a tab in, one leading tab out
 *   ArrowUp / ArrowDown at the edge     the cell above / below
 *   Backspace in an empty cell          remove the cell
 */

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
 * Draw the pad into `root`, with `said` for messages, on `backend`.
 * @param {{load(): Promise<object>, change(route: string, body: object): Promise<object>}} backend
 */
export async function mount(backend, root, said) {
	let cells = [];
	let next = "";

	function texts() {
		return [...root.querySelectorAll("textarea")].map(area => area.value);
	}

	function fit(area) {
		area.rows = Math.max(1, area.value.split("\n").length);
	}

	function render(typed, focus, caret) {
		const staleBy = {};
		cells.forEach((cell, j) => cell.changes.forEach(i => (staleBy[i] = j)));
		const drafted = {source: "", status: "draft", bar: next, turns: [], changes: []};
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
		const area = document.createElement("textarea");
		area.spellcheck = false;
		area.value = text;
		const edited = () => section.classList.toggle(
			"edited", i < cells.length && area.value !== cell.source);
		area.addEventListener("input", () => { fit(area); edited(); });
		area.addEventListener("keydown", event => keyed(event, area, i));
		fit(area);
		edited();
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
		section.append(bar, area, turns);
		return section;
	}

	function insert(area, text) {
		if (!document.execCommand("insertText", false, text)) {
			area.setRangeText(text, area.selectionStart, area.selectionEnd, "end");
		}
		fit(area);
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

	function keyed(event, area, i) {
		const before = area.value.slice(0, area.selectionStart);
		const after = area.value.slice(area.selectionEnd);
		const line = before.slice(before.lastIndexOf("\n") + 1);
		if (event.key === "Enter" && (event.shiftKey || event.ctrlKey || event.metaKey)) {
			event.preventDefault();
			evaluate(i, area.value);
		} else if (event.key === "Enter") {
			event.preventDefault();
			insert(area, "\n" + line.match(/^\t*/)[0]);
		} else if (event.key === "Tab" && !event.shiftKey) {
			event.preventDefault();
			insert(area, "\t");
		} else if (event.key === "Tab") {
			event.preventDefault();
			const start = before.length - line.length;
			if (area.value[start] === "\t") {
				area.setRangeText("", start, start + 1, "preserve");
				fit(area);
			}
		} else if (event.key === "ArrowUp" && !before.includes("\n") && i > 0) {
			event.preventDefault();
			move(i - 1, "end");
		} else if (event.key === "ArrowDown" && !after.includes("\n") && i < cells.length) {
			event.preventDefault();
			move(i + 1, "start");
		} else if (event.key === "Backspace" && area.value === "" && i < cells.length) {
			event.preventDefault();
			const typed = texts();
			typed.splice(i, 1);
			changed("/remove", {index: i}, typed, Math.max(0, i - 1), "end");
		}
	}

	function move(i, caret) {
		const area = root.querySelectorAll("textarea")[i];
		area.focus();
		const at = caret === "start" ? 0 : area.value.length;
		area.setSelectionRange(at, at);
		area.scrollIntoView({block: "nearest"});
	}

	return {
		reset: () => changed("/reset", {}, [""], 0, "end"),
		ready: (async () => {
			({cells, bar: next} = await backend.load());
			render([], cells.length, "end");
		})(),
	};
}

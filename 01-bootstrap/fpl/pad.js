/**
 * The pad's page: one buffer, the session as text.
 *
 * The buffer is the transcript the REPL would print: a `;;!` phrase bar, the
 * input under it, its `|-` result lines and `;;!` notes, the next bar, and so
 * on, with the bar of the cell to come at the end. One composes in it as in
 * an editor. Shift+Enter (or Ctrl+Enter, Cmd+Enter) hands the whole buffer
 * to the backend, which reads it as the REPL reads a paste (the loop's own
 * lines drop away, fpl.repl.written), evaluates what changed and every cell
 * below it, and answers with the buffer written anew and where the caret
 * goes: the start of the cell after the one it was in.
 *
 * The backend takes the routes of fpl/pad_web.py and answers with the pad,
 * {cells: [{source, status, bar, turns, changes}], buffer, caret}:
 *
 *   load(body)           the pad as it stands, "/pad" {indent}
 *   change(route, body)  "/buffer" {text, cursor, indent}, "/reset" {indent}
 *
 * `indent` is what each result line is set in by: "" at the margin as the
 * REPL writes, "\t" set in as BQNPad does; the page opened as
 * `?results=indented` asks for the tab.
 *
 * While one types, the page asks for a ghost, a preview of the cell under
 * the cursor on the state the cells above leave, which the pad keeps nothing
 * of; it is answered {ghost: {line, kind, text} | null}:
 *
 *   change("/preview", {text, cursor})
 *
 * The editor paints it faded at the end of the cell's last text line, beside
 * the text; the page never sets the buffer from a preview. One preview is in
 * flight at a time, the latest text wins, and an answer to text that has
 * changed since, or to a buffer a commit has set, is dropped. Shift+Enter
 * commits as before, and the real result lines take the ghost's place.
 *
 * `http` is the backend of `python -m fpl pad`; the site's /pad/ page passes
 * one that runs fpl.pad under Pyodide (assets/fpl-pad.js). The keys are the
 * editor's (editors.js): Enter a newline with the line's tabs, Tab a tab.
 */

import {plain} from "./editors.js";

/** The quiet after a keystroke before a preview is asked, as the playground waits. */
const QUIET_MS = 300;

/** The backend of `python -m fpl pad`: the routes over HTTP. */
export const http = {
	async load(body) {
		return http.change("/pad", body);
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

/** The indent the page's URL asks for: a tab under `?results=indented`. */
export function indented(search) {
	return new URLSearchParams(search).get("results") === "indented" ? "\t" : "";
}

/**
 * Put the buffer into `root`, with `said` for messages, on `backend`, the
 * result lines set in by `indent`.
 * @param {{load(body: object): Promise<object>, change(route: string, body: object): Promise<object>}} backend
 */
export async function mount(backend, root, said, indent = "") {
	let cells = [];
	let timer = 0, flying = false, dirty = false, epoch = 0;
	const host = document.createElement("div");
	root.replaceChildren(host);
	const editor = plain.make(host, "", {
		input: () => {
			clearTimeout(timer);
			timer = setTimeout(ask, QUIET_MS);
		},
		evaluate: () => sync("/buffer", {text: editor.value(), cursor: editor.cursor(), indent}),
		up: () => false,
		down: () => false,
		remove: () => false,
	});

	/** Ask for the ghost of the cell under the cursor; paint it if it still holds. */
	async function ask() {
		if (flying) {
			dirty = true;
			return;
		}
		flying = true;
		const asked = epoch, text = editor.value();
		let ghost;
		try {
			({ghost} = await backend.change("/preview", {text, cursor: editor.cursor()}));
		} catch {
			ghost = null;
		}
		flying = false;
		if (dirty) {
			dirty = false;
			ask();
			return;
		}
		if (asked === epoch && text === editor.value()) {
			editor.shade(ghost && {...ghost, text: indent + ghost.text});
		}
	}

	async function sync(route, body) {
		clearTimeout(timer);
		dirty = false;
		epoch += 1;
		let buffer;
		let caret;
		try {
			({cells, buffer, caret} = await backend.change(route, body));
		} catch (error) {
			said.textContent = String(error);
			return;
		}
		said.textContent = "";
		editor.set(buffer, caret);
	}

	await plain.ready();
	return {
		reset: () => sync("/reset", {indent}),
		copy: async () => {
			await navigator.clipboard.writeText(editor.value());
			said.textContent = `copied ${cells.length} cells`;
		},
		ready: (async () => {
			let buffer;
			let caret;
			({cells, buffer, caret} = await backend.load({indent}));
			editor.set(buffer, caret);
		})(),
	};
}

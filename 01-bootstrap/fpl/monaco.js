/**
 * Monaco as the pad's cell editor: the playground's editor
 * (assets/fpl-playground.js), from the same CDN pin, with the generated
 * language of fpl-language.js and the palette of editors.js as its theme.
 * One editor per cell, sized to its lines, no gutter. It needs the network,
 * as the playground does; `plain` in editors.js does not.
 *
 * Same interface as editors.js: ready() loads Monaco once; make(host, text,
 * hooks) gives {value(), focus(caret), dispose()}. The keys are read in
 * onKeyDown, per editor, so that cells do not hear each other's keys.
 */

import {PALETTE, scheme} from "./editors.js";
import {registerFpl} from "./fpl-language.js";

const VERSION = "0.52.2";
const BASE = `https://cdn.jsdelivr.net/npm/monaco-editor@${VERSION}/min/vs`;

/** @type {Promise<any> | null} */
let loading = null;

/** Monaco, loaded through its AMD loader as the playground loads it. */
function loaded() {
	if (!loading) {
		loading = new Promise((resolve, reject) => {
			if (window.monaco) return resolve(window.monaco);
			window.require = {paths: {vs: BASE}};
			const script = document.createElement("script");
			script.src = `${BASE}/loader.js`;
			script.onload = () => window.require(["vs/editor/editor.main"], () => resolve(window.monaco));
			script.onerror = () => reject(new Error("Monaco did not load from " + BASE));
			document.head.append(script);
		});
	}
	return loading;
}

/** Define fpl-dark and fpl-light from the pad's palette, on the page's background. */
function themed(monaco) {
	for (const [name, base] of [["dark", "vs-dark"], ["light", "vs"]]) {
		monaco.editor.defineTheme(`fpl-${name}`, {
			base,
			inherit: true,
			colors: {"editor.background": "#00000000"},
			rules: Object.entries(PALETTE[name]).map(([token, look]) => ({
				token,
				foreground: look.color.slice(1),
				fontStyle: [look.style, look.weight].filter(Boolean).join(" ") || undefined,
			})),
		});
	}
}

export const monaco = {
	async ready() {
		const api = await loaded();
		if (!api.languages.getLanguages().some(language => language.id === "fpl")) {
			registerFpl(api);
			themed(api);
		}
		api.editor.setTheme(`fpl-${scheme()}`);
	},

	make(host, text, hooks) {
		const api = window.monaco;
		host.className = "editor monaco";
		const editor = api.editor.create(host, {
			value: text,
			language: "fpl",
			fontSize: 15,
			fontFamily: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
			lineNumbers: "off",
			lineNumbersMinChars: 0,
			lineDecorationsWidth: 0,
			glyphMargin: false,
			folding: false,
			minimap: {enabled: false},
			overviewRulerLanes: 0,
			overviewRulerBorder: false,
			hideCursorInOverviewRuler: true,
			scrollbar: {vertical: "hidden", horizontal: "auto", alwaysConsumeMouseWheel: false},
			scrollBeyondLastLine: false,
			renderLineHighlight: "none",
			wordWrap: "off",
			insertSpaces: false,
			detectIndentation: false,
			tabSize: 4,
			autoIndent: "keep",
			autoClosingBrackets: "never",
			autoClosingQuotes: "never",
			quickSuggestions: false,
			suggestOnTriggerCharacters: false,
			contextmenu: false,
			guides: {indentation: false},
			automaticLayout: true,
			fixedOverflowWidgets: true,
		});

		function fit() {
			host.style.height = `${editor.getContentHeight()}px`;
			editor.layout();
		}
		editor.onDidContentSizeChange(fit);
		fit();
		editor.onDidChangeModelContent(() => hooks.input());

		const key = api.KeyCode;
		editor.onKeyDown(event => {
			const line = editor.getPosition().lineNumber;
			const last = editor.getModel().getLineCount();
			const modified = event.shiftKey || event.ctrlKey || event.metaKey;
			const taken = (event.keyCode === key.Enter && modified && (hooks.evaluate(), true))
				|| (event.keyCode === key.UpArrow && line === 1 && hooks.up())
				|| (event.keyCode === key.DownArrow && line === last && hooks.down())
				|| (event.keyCode === key.Backspace && editor.getValue() === "" && hooks.remove());
			if (taken) {
				event.preventDefault();
				event.stopPropagation();
			}
		});

		return {
			value: () => editor.getValue(),
			focus(caret) {
				editor.focus();
				const model = editor.getModel();
				const last = model.getLineCount();
				editor.setPosition(caret === "start"
					? {lineNumber: 1, column: 1}
					: {lineNumber: last, column: model.getLineMaxColumn(last)});
				host.scrollIntoView({block: "nearest"});
			},
			dispose: () => editor.dispose(),
		};
	},
};

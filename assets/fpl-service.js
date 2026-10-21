/**
 * The FPL language service for the playground's Monaco: ide/analysis.py (the
 * code the pygls server runs) under Pyodide, behind Monaco's own providers:
 * semantic tokens, diagnostics (markers), hover, go to definition, completion
 * and rename. No LSP transport: Monaco's providers are the client, one
 * function call is the server. The bootstrap `fpl` package ships as
 * fpl-bootstrap.zip (01-bootstrap/ide/pack_analysis.py) and is imported beside
 * the playground's own `fpl` by moving that out of sys.modules for the import.
 * Without the zip the playground keeps its Monarch colours.
 */
import { ensurePyodide, pypiBase } from "./fpl-runtime.js";

export const LEGEND = {
  tokenTypes: ["variable", "function", "number", "namespace", "operator", "parameter"],
  tokenModifiers: ["declaration"],
};

const BOOT = `
import sys, zipfile, io
from pyodide.http import pyfetch
async def _load(url):
    data = await (await pyfetch(url)).bytes()
    zipfile.ZipFile(io.BytesIO(data)).extractall("/bs")
    mine = lambda k: k == "fpl" or k.startswith("fpl.")
    saved = {k: sys.modules.pop(k) for k in [k for k in sys.modules if mine(k)]}
    sys.path.insert(0, "/bs")
    try:
        from ide import analysis
    finally:
        sys.path.remove("/bs")
        for k in [k for k in sys.modules if mine(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return analysis
`;

/** @type {Promise<any> | null} */
let analysis = null;

function load() {
  if (!analysis) {
    analysis = (async () => {
      const py = await ensurePyodide();
      await py.runPythonAsync(BOOT);
      py.globals.set("_bs_url", pypiBase() + "fpl-bootstrap.zip");
      return py.runPythonAsync("await _load(_bs_url)");
    })().catch((e) => {
      console.warn("fpl language service unavailable:", e);
      return null;
    });
  }
  return analysis;
}

/** One call into analysis.serve; positions are Monaco's, converted to 0-based. */
async function call(op, model, pos, arg = "") {
  const mod = await load();
  if (!mod) return null;
  const text = mod.serve(op, model.getValue(), pos ? pos.lineNumber - 1 : 0, pos ? pos.column - 1 : 0, arg);
  return JSON.parse(text);
}

/** @param {import("monaco-editor")} monaco */
export function registerService(monaco) {
  const L = "fpl";
  const range = (r, c0, c1) => new monaco.Range(r + 1, c0 + 1, r + 1, c1 + 1);

  monaco.languages.registerDocumentSemanticTokensProvider(L, {
    getLegend: () => LEGEND,
    async provideDocumentSemanticTokens(model) {
      const data = await call("tokens", model);
      return data ? { data: Uint32Array.from(data) } : null;
    },
    releaseDocumentSemanticTokens() {},
  });

  monaco.languages.registerHoverProvider(L, {
    async provideHover(model, pos) {
      const md = await call("hover", model, pos);
      return md ? { contents: [{ value: md }] } : null;
    },
  });

  monaco.languages.registerDefinitionProvider(L, {
    async provideDefinition(model, pos) {
      const hit = await call("goto", model, pos);
      return hit ? [{ uri: model.uri, range: range(hit[0], hit[1], hit[2]) }] : null;
    },
  });

  monaco.languages.registerCompletionItemProvider(L, {
    async provideCompletionItems(model, pos) {
      const items = await call("complete", model, pos);
      if (!items) return { suggestions: [] };
      const word = model.getWordUntilPosition(pos);
      const r = new monaco.Range(pos.lineNumber, word.startColumn, pos.lineNumber, word.endColumn);
      const K = monaco.languages.CompletionItemKind;
      return {
        suggestions: items.map(([label, kind, detail]) => ({
          label,
          kind: kind === "parameter" ? K.Variable : K.Function,
          detail,
          insertText: label,
          range: r,
        })),
      };
    },
  });

  monaco.languages.registerRenameProvider(L, {
    async provideRenameEdits(model, pos, newName) {
      const edits = await call("rename", model, pos, newName);
      if (!edits || !edits.length) return { edits: [], rejectReason: "not a defined name or parameter" };
      return {
        edits: edits.map(([r, c0, c1, text]) => ({
          resource: model.uri,
          versionId: undefined,
          textEdit: { range: range(r, c0, c1), text },
        })),
      };
    },
  });

  /** Markers: the interpreter's own refusal, 300 ms after the last edit. */
  function watch(model) {
    if (model.getLanguageId() !== L) return;
    let timer = 0;
    const mark = async () => {
      const found = await call("diagnose", model);
      if (!found || model.isDisposed()) return;
      monaco.editor.setModelMarkers(
        model,
        "fpl",
        found.map(([r, c0, c1, message]) => ({
          severity: monaco.MarkerSeverity.Error,
          message,
          startLineNumber: r + 1,
          startColumn: c0 + 1,
          endLineNumber: r + 1,
          endColumn: c1 + 1,
          source: "fpl",
        })),
      );
    };
    mark();
    model.onDidChangeContent(() => {
      clearTimeout(timer);
      timer = setTimeout(mark, 300);
    });
  }
  monaco.editor.getModels().forEach(watch);
  monaco.editor.onDidCreateModel(watch);
}

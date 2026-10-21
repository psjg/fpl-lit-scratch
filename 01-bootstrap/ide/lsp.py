"""
A minimal FPL language server over stdio: diagnostics on open and change,
full-document semantic tokens. Everything it knows comes from
ide/analysis.py; this file only speaks the protocol (pygls).

    uv run --with pygls --with lark --with icontract python -m ide.lsp

from 01-bootstrap/ (PYTHONPATH there, so `fpl` imports).
"""

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from ide import analysis

server = LanguageServer("fpl-ls", "0.0.1")
LEGEND = types.SemanticTokensLegend(
    token_types=list(analysis.LEGEND_TYPES),
    token_modifiers=list(analysis.LEGEND_MODIFIERS),
)


def publish(ls: LanguageServer, uri: str) -> None:
    """
    Diagnose the open text of `uri` and send the result.
    """
    text = ls.workspace.get_text_document(uri).source
    rows = analysis._rows(text)
    found = [
        types.Diagnostic(
            range=types.Range(
                types.Position(d.line, analysis.utf16(rows[d.line], d.start)),
                types.Position(d.line, analysis.utf16(rows[d.line], d.end)),
            ),
            message=d.message,
            severity=types.DiagnosticSeverity.Error,
            source="fpl",
        )
        for d in analysis.diagnose(text)
    ]
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(uri=uri, diagnostics=found)
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def opened(
    ls: LanguageServer, params: types.DidOpenTextDocumentParams
) -> None:
    """
    A document opened.
    """
    publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def changed(
    ls: LanguageServer, params: types.DidChangeTextDocumentParams
) -> None:
    """
    A document changed.
    """
    publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, LEGEND)
def semantic(
    ls: LanguageServer, params: types.SemanticTokensParams
) -> types.SemanticTokens:
    """
    Every word of the document, classified.
    """
    text = ls.workspace.get_text_document(params.text_document.uri).source
    return types.SemanticTokens(data=analysis.encode(units))


if __name__ == "__main__":
    server.start_io()

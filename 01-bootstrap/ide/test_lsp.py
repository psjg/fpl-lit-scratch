"""
The language server's semantic-tokens handler answers with the same integers
as `analysis.lsp_data`; it once raised NameError on every request.

    PYTHONPATH=. python -m pytest ide -q -p no:cacheprovider
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("pygls")

from lsprotocol import types  # noqa: E402

from ide import analysis, lsp  # noqa: E402


def test_semantic_tokens_handler_returns_the_analysis_encoding() -> None:
    source = "1 2 Add\n"
    uri = "file:///t.fpl"
    ls = SimpleNamespace(
        workspace=SimpleNamespace(
            get_text_document=lambda u: SimpleNamespace(source=source)
        )
    )
    params = types.SemanticTokensParams(
        text_document=types.TextDocumentIdentifier(uri=uri)
    )
    got = lsp.semantic(ls, params)  # type: ignore[arg-type]
    assert got.data == analysis.lsp_data(source)
    assert got.data

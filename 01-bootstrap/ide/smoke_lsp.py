"""
Drives ide/lsp.py over stdio with raw JSON-RPC: initialize, open a broken
and a good document, ask for semantic tokens. Exit 1 on any surprise.

    PYTHONPATH=. uv run --no-project --with pygls --with lark --with icontract python ide/smoke_lsp.py
"""

import json
import subprocess
import sys

BAD = "[ 1 2\n"
GOOD = open(
    "../03-fpl/OLD/03.01-features/draft2/examples/02-currying.fpl"
).read()


def send(proc: subprocess.Popen, msg: dict) -> None:
    """Write one framed message."""
    body = json.dumps(msg).encode()
    proc.stdin.write(b"Content-Length: %d\r\n\r\n%s" % (len(body), body))
    proc.stdin.flush()


def recv(proc: subprocess.Popen) -> dict:
    """Read one framed message."""
    size = 0
    while line := proc.stdout.readline().strip():
        if line.lower().startswith(b"content-length"):
            size = int(line.split(b":")[1])
    return json.loads(proc.stdout.read(size))


def until(proc: subprocess.Popen, pick) -> dict:
    """Read messages until `pick` accepts one."""
    while True:
        msg = recv(proc)
        if pick(msg):
            return msg


def main() -> int:
    """Run the dialogue."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "ide.lsp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"capabilities": {}},
        },
    )
    init = until(proc, lambda m: m.get("id") == 1)
    legend = init["result"]["capabilities"]["semanticTokensProvider"]["legend"]
    send(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
    for uri, text in (("file:///bad.fpl", BAD), ("file:///good.fpl", GOOD)):
        send(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "fpl",
                        "version": 1,
                        "text": text,
                    }
                },
            },
        )
        diag = until(
            proc,
            lambda m: m.get("method") == "textDocument/publishDiagnostics",
        )
        print(
            uri,
            "diagnostics:",
            [d["message"] for d in diag["params"]["diagnostics"]],
        )
        if (uri.endswith("bad.fpl")) != bool(diag["params"]["diagnostics"]):
            return 1
    send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/semanticTokens/full",
            "params": {"textDocument": {"uri": "file:///good.fpl"}},
        },
    )
    data = until(proc, lambda m: m.get("id") == 2)["result"]["data"]
    print("legend:", legend["tokenTypes"], "data:", data)
    ok = bool(data) and len(data) % 5 == 0
    send(proc, {"jsonrpc": "2.0", "id": 3, "method": "shutdown"})
    proc.terminate()
    return 0 if ok else 1


sys.exit(main())

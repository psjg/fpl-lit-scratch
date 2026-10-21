#!/usr/bin/env bash
#
# .harness/scripts/serve-try.sh [PORT] — serve the /try playground from this worktree.
#
# Builds the fpl-walker wheel and fetches the pinned pure-Python wheels the page loads
# (assets/fpl-runtime.js WHEELS) into a scratch site under .git/try-site, then serves it.
# Pyodide and Monaco come from their CDNs, so the browser needs internet.
# Open: http://localhost:PORT/try/index.html   (default PORT 8765)
set -euo pipefail
top="$(git rev-parse --show-toplevel)"
site="$(git rev-parse --git-dir)/try-site"
port="${1:-8765}"

mkdir -p "$site/werkbank/pypi" "$top/.wasm/wheels"
ln -sfn ../01-bootstrap/python/fpl "$top/.wasm/fpl"
trap 'rm -f "$top/.wasm/fpl"' EXIT
(cd "$top/.wasm" && uv build --wheel -o wheels >/dev/null)
cp "$top"/.wasm/wheels/fpl_walker-*.whl "$site/werkbank/pypi/"
if ! compgen -G "$site/werkbank/pypi/lark-*.whl" >/dev/null; then
  uvx pip download --only-binary=:all: --no-deps -d "$site/werkbank/pypi" \
    lark==1.3.1 icontract==2.7.3 asttokens==2.4.1 typing_extensions==4.16.0 six==1.17.0 comm==0.2.3 >/dev/null
fi
rm -rf "$site/try" "$site/assets" "$site/learn"
cp -R "$top/assets/try" "$site/try"
cp -R "$top/assets" "$site/assets"
cp -R "$top/learn" "$site/learn"
echo "Serving $site"
echo "Open http://localhost:$port/try/index.html"
exec python3 -m http.server "$port" --directory "$site"

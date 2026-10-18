#!/usr/bin/env bash
# Build the Pyodide try notebook and JupyterLite workbench into .site/,
# then render the Quarto essay around them.
set -euo pipefail
top="$(git rev-parse --show-toplevel)"
cd "$top"

wheel="fpl_walker-0.0.0-py3-none-any.whl"

mkdir -p .wasm/wheels .site
ln -sfn ../01-bootstrap/python/fpl .wasm/fpl
rm -f .wasm/wheels/fpl-*.whl .wasm/wheels/fpl_walker-*.whl
(cd .wasm && uv build --wheel -o wheels)
test -f ".wasm/wheels/$wheel"

rm -rf .site/try
(cd .wasm && uvx --from marimo marimo export html-wasm try.py -o ../.site/try --mode edit -f)

(cd .wasm && python3 export_modules.py)

mkdir -p .wasm/lite/pypi
rm -f .wasm/lite/pypi/fpl-*.whl .wasm/lite/pypi/fpl_walker-*.whl
cp ".wasm/wheels/$wheel" .wasm/lite/pypi/
# Pure-Python deps for the walker + jupyterlite gaps (comm) that
# micropip otherwise tries to fetch when PyPI fallback is off/flaky.
need_download=0
for w in lark-*.whl icontract-*.whl comm-*.whl; do
  if ! compgen -G ".wasm/lite/pypi/$w" >/dev/null; then
    need_download=1
    break
  fi
done
if [[ "$need_download" -eq 1 ]]; then
  (cd .wasm/lite/pypi && uvx pip download lark icontract 'comm>=0.2' -d . --only-binary=:all:)
fi

rm -rf .site/werkbank
(
  cd .wasm/lite
  uvx --from 'jupyterlite-core[libarchive]' \
    --with jupyter-server \
    --with jupyterlab_server \
    --with jupyterlite-pyodide-kernel \
    jupyter lite build \
    --contents content \
    --output-dir ../../.site/werkbank \
    --XPipliteAddon.piplite_urls=pypi \
    -y --force
)

# Quarto clears .site/; keep the browser runtimes aside, then put them back.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mv .site/try "$tmp/try"
mv .site/werkbank "$tmp/werkbank"

python3 .harness/scripts/homepage.py
export PYTHONPATH="$top/01-bootstrap/python${PYTHONPATH:+:$PYTHONPATH}"
quarto render

mv "$tmp/try" .site/try
mv "$tmp/werkbank" .site/werkbank

echo "Open .site/ with: python3 -m http.server --directory .site"

#!/usr/bin/env bash
set -euo pipefail

if grep -q 'numpy>=2.5.1' pyproject.toml; then
  echo 'Dependency refresh already generated; validation is handled by normal PR workflows.'
  exit 0
fi

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

python - <<'PY'
from pathlib import Path

path = Path('pyproject.toml')
text = path.read_text(encoding='utf-8')
replacements = {
    '"numpy>=2.4.6"': '"numpy>=2.5.1"',
    '"structlog>=25.5.0"': '"structlog>=26.1.0"',
    '"anyio>=4.12.0"': '"anyio>=4.14.2"',
    '"bandit[toml]>=1.8.0"': '"bandit[toml]>=1.9.4"',
    '"import-linter>=2.9"': '"import-linter>=2.13"',
    '"pytest>=9.0.2"': '"pytest>=9.1.1"',
    '"pyright>=1.1.407"': '"pyright>=1.1.411"',
    '"ruff>=0.14.10"': '"ruff>=0.16.0"',
    '"typer>=0.21.0"': '"typer>=0.27.1"',
    '"guessit>=3.8.0"': '"guessit>=4.1.0"',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f'Missing expected declaration: {old}')
    text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
PY

uv lock \
  --upgrade-package numpy \
  --upgrade-package structlog \
  --upgrade-package anyio \
  --upgrade-package bandit \
  --upgrade-package import-linter \
  --upgrade-package pytest \
  --upgrade-package pyright \
  --upgrade-package ruff \
  --upgrade-package typer \
  --upgrade-package guessit
uv lock --check

uv sync --group dev --group docs --frozen
uv run --no-sync ruff check .
uv run --no-sync ruff format --check src tests scripts tools
uv run --no-sync pytest -q tests/cli tests/e2e/test_cli_version.py tests/services/test_metadata_parsing.py

uv_digest="$(docker buildx imagetools inspect ghcr.io/astral-sh/uv:0.12.2 | awk '/^Digest:/ {print $2; exit}')"
python_digest="$(docker buildx imagetools inspect python:3.13.14-slim-trixie | awk '/^Digest:/ {print $2; exit}')"
[[ "$uv_digest" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$python_digest" =~ ^sha256:[0-9a-f]{64}$ ]]

zip="$RUNNER_TEMP/python-3.13.14-embed-amd64.zip"
curl --fail --silent --show-error --location \
  https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip \
  --output "$zip"
zip_sha="$(sha256sum "$zip" | awk '{print $1}')"
zip_bytes="$(stat --format='%s' "$zip")"

UV_DIGEST="$uv_digest" PYTHON_DIGEST="$python_digest" ZIP_SHA="$zip_sha" ZIP_BYTES="$zip_bytes" python - <<'PY'
from pathlib import Path
import json
import os
import re

dockerfile = Path('Dockerfile')
text = dockerfile.read_text(encoding='utf-8')
text, uv_count = re.subn(
    r'ghcr\.io/astral-sh/uv:0\.11\.31@sha256:[0-9a-f]{64}',
    f"ghcr.io/astral-sh/uv:0.12.2@{os.environ['UV_DIGEST']}",
    text,
)
text, py_count = re.subn(
    r'python:3\.13\.13-slim-trixie@sha256:[0-9a-f]{64}',
    f"python:3.13.14-slim-trixie@{os.environ['PYTHON_DIGEST']}",
    text,
)
if uv_count != 1 or py_count != 2:
    raise SystemExit(f'Unexpected Docker pin counts: uv={uv_count}, python={py_count}')
dockerfile.write_text(text, encoding='utf-8')

for path in map(Path, [
    '.github/workflows/ci.yml',
    '.github/workflows/docs.yml',
    '.github/workflows/windows-portable-build.yml',
]):
    data = path.read_text(encoding='utf-8')
    if 'version: "0.11.31"' not in data:
        raise SystemExit(f'{path}: uv pin missing')
    path.write_text(data.replace('version: "0.11.31"', 'version: "0.12.2"'), encoding='utf-8')

windows = Path('.github/workflows/windows-portable-build.yml')
data = windows.read_text(encoding='utf-8')
if data.count('3.13.13') != 2:
    raise SystemExit('Unexpected Windows workflow Python pin count')
windows.write_text(data.replace('3.13.13', '3.13.14'), encoding='utf-8')

docs_test = Path('tests/workflows/test_docs_workflow.py')
data = docs_test.read_text(encoding='utf-8')
if data.count('version: "0.11.31"') != 1:
    raise SystemExit('Unexpected docs workflow test uv pin count')
docs_test.write_text(data.replace('version: "0.11.31"', 'version: "0.12.2"'), encoding='utf-8')

getting_started = Path('docs/getting-started/index.md')
data = getting_started.read_text(encoding='utf-8')
if data.count('Python 3.13.13') != 1:
    raise SystemExit('Unexpected docs Python pin count')
getting_started.write_text(data.replace('Python 3.13.13', 'Python 3.13.14'), encoding='utf-8')

manifest_path = Path('tools/windows_portable/manifest.windows-x64.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['bundle']['python_version'] = '3.13.14'
artifact = next(x for x in manifest['artifacts'] if x['id'] == 'python-embed-amd64')
artifact.update({
    'version': '3.13.14',
    'url': 'https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip',
    'source_url': 'https://www.python.org/ftp/python/3.13.14/Python-3.13.14.tgz',
    'sha256': os.environ['ZIP_SHA'],
    'bytes': int(os.environ['ZIP_BYTES']),
})
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
PY

uv lock --check
uv sync --group dev --group docs --frozen
uv run --no-sync ruff check .
uv run --no-sync ruff format --check src tests scripts tools
uv run --no-sync pyright --warnings
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync pytest -q
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
uv build --out-dir dist

grep -q 'VAPOURSYNTH_VERSION=76' Dockerfile
grep -q 'ARG VS_PLACEBO_VERSION=2.0.2' Dockerfile
grep -q 'ARG LSMASH_REF=v2.14.5' Dockerfile
grep -q '"vs_ref": "R76"' tools/windows_portable/manifest.windows-x64.json
grep -q '"version": "1282.0.0.0"' tools/windows_portable/manifest.windows-x64.json
grep -q '"version": "2.0.2"' tools/windows_portable/manifest.windows-x64.json

git add \
  pyproject.toml uv.lock Dockerfile \
  .github/workflows/ci.yml \
  .github/workflows/docs.yml \
  .github/workflows/windows-portable-build.yml \
  tests/workflows/test_docs_workflow.py \
  docs/getting-started/index.md \
  tools/windows_portable/manifest.windows-x64.json

git commit -m 'build(deps): refresh non-media dependencies [dependency-refresh-result]'
git push origin "HEAD:refs/heads/${REFRESH_BRANCH}"

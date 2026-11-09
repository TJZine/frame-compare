#!/usr/bin/env bash
# Exercise Docker's real ignore and COPY behavior with harmless synthetic inputs.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
probe="$(mktemp -d)"
trap 'rm -rf -- "$probe"' EXIT
context="$probe/context"
mkdir -p "$context/src/frame_compare" "$context/tools/windows_portable" "$context/tests"
cp "$repo_root/Dockerfile" "$repo_root/.dockerignore" "$context/"

marker=frame-compare-synthetic-context-sentinel
for path in .env src/frame_compare/.env.local src/frame_compare/private-key.pem; do
  printf '%s\n' "$marker" > "$context/$path"
done
for path in README.md LICENSE pyproject.toml uv.lock src/frame_compare/__init__.py \
  tools/windows_portable/update_public_key.xml tests/fixture.txt; do
  printf '%s\n' 'harmless context control' > "$context/$path"
done

# Only the disposable context is sent to this deliberately broad probe.
docker buildx build --file - --output "type=local,dest=$probe/filtered" "$context" <<'EOF'
FROM scratch
COPY . /
EOF
for path in .env src/frame_compare/.env.local src/frame_compare/private-key.pem; do
  if [[ -e "$probe/filtered/$path" ]]; then
    echo "ERROR: secret sentinel entered the Docker context: $path" >&2
    exit 1
  fi
done
test -f "$probe/filtered/src/frame_compare/__init__.py"
test -f "$probe/filtered/tools/windows_portable/update_public_key.xml"
test -f "$probe/filtered/tests/fixture.txt"

# Export the actual stage copied into the runtime application layer. Its
# complete input tree is expected to contain only these package inputs.
docker buildx build --target application-inputs --output "type=local,dest=$probe/application" "$context"
actual="$(cd "$probe/application" && find . -type f | LC_ALL=C sort)"
expected=$'./LICENSE\n./README.md\n./src/frame_compare/__init__.py'
if [[ "$actual" != "$expected" ]]; then
  echo "ERROR: unexpected files in Docker application input layer" >&2
  printf '%s\n' "$actual" >&2
  exit 1
fi
echo "DOCKER_PROOF context_secrets_excluded=ok application_layer_inputs=ok"

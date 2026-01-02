#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_integration.sh [--service NAME] [--no-build] [--no-cache]

Runs integration tests inside the Docker image where VapourSynth + FFmpeg are installed.
Fails if any tests are skipped (the “real deps work” gate).

Defaults:
  --service frame-compare-test
  Runs: pytest -v -m "integration or vs_required" tests/integration/

Options:
  --service NAME   Docker Compose service to run (default: frame-compare-test)
  --no-build       Do not run "docker compose build" before tests
  --no-cache       Add "--no-cache" to "docker compose build"
EOF
}

service="frame-compare-test"
run_build="1"
no_cache="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      service="${2:-}"
      shift 2
      ;;
    --no-build)
      run_build="0"
      shift
      ;;
    --no-cache)
      no_cache="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH" >&2
  exit 127
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose is not available (need Docker Desktop or compose plugin)" >&2
  exit 127
fi

build_args=()
if [[ "$no_cache" == "1" ]]; then
  build_args+=(--no-cache)
fi

if [[ "$run_build" == "1" ]]; then
  # bash 3.2 + `set -u` can treat empty `${array[@]}` expansions as unbound.
  if [[ "${#build_args[@]}" -gt 0 ]]; then
    docker compose build "${build_args[@]}" "$service"
  else
    docker compose build "$service"
  fi
fi

tmp_log="$(mktemp)"
cleanup() { rm -f "$tmp_log"; }
trap cleanup EXIT

docker_cmd=(
  docker compose run
  --rm
  "$service"
  -c
)

# Note: keep this robust even if the image doesn't include pytest yet.
container_cmd=$(
  cat <<'EOF'
python -c "import pytest" >/dev/null 2>&1 || python -m pip install --user -q pytest &&
python -m pytest -v -m "integration or vs_required" tests/integration/
EOF
)

set +e
"${docker_cmd[@]}" "$container_cmd" 2>&1 | tee "$tmp_log"
exit_code="${PIPESTATUS[0]}"
set -e

if [[ "$exit_code" != "0" ]]; then
  echo "ERROR: docker integration tests failed (exit $exit_code)" >&2
  exit "$exit_code"
fi

if grep -Eq '([1-9][0-9]* skipped|skipped=[1-9][0-9]*)' "$tmp_log"; then
  echo "ERROR: docker integration tests reported skipped tests; this gate requires zero skips" >&2
  exit 3
fi

echo "OK: docker integration tests passed with zero skips"

#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_integration.sh [--service NAME] [--no-build] [--no-cache] [--pytest-path PATH]

Runs integration tests inside the Docker image where VapourSynth + FFmpeg are installed.
Fails if any tests are skipped (the “real deps work” gate).

Defaults:
  --service frame-compare-test
  Runs: pytest -v tests/integration/ tests/vs/

Environment:
  FRAME_COMPARE_REQUIRE_LIBPLACEBO=1  Require app-level libplacebo tonemap to succeed.

Options:
  --service NAME   Docker Compose service to run (default: frame-compare-test)
  --no-build       Do not run "docker compose build" before tests
  --no-cache       Add "--no-cache" to "docker compose build"
  --pytest-path    Repeat to override default pytest paths with a focused subset
EOF
}

service="frame-compare-test"
run_build="1"
no_cache="0"
use_custom_pytest_paths="0"
pytest_paths=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "ERROR: --service requires a value" >&2
        usage >&2
        exit 2
      fi
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
    --pytest-path)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "ERROR: --pytest-path requires a value" >&2
        usage >&2
        exit 2
      fi
      if [[ "$use_custom_pytest_paths" == "0" ]]; then
        pytest_paths=()
        use_custom_pytest_paths="1"
      fi
      pytest_paths+=("${2:-}")
      shift 2
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

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker daemon is not running; start Docker Desktop or your Docker daemon and retry" >&2
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
)

docker_env_args=()
if [[ "${FRAME_COMPARE_REQUIRE_LIBPLACEBO:-}" == "1" ]]; then
  docker_env_args+=(-e FRAME_COMPARE_REQUIRE_LIBPLACEBO=1)
fi

if [[ "${#docker_env_args[@]}" -gt 0 ]]; then
  docker_cmd+=("${docker_env_args[@]}")
fi

if [[ "${#pytest_paths[@]}" -eq 0 ]]; then
  pytest_paths=(tests/integration/ tests/vs/)
fi

printf -v pytest_args ' %q' "${pytest_paths[@]}"

docker_cmd+=(
  "$service"
  -c
)

# Note: keep this robust even if the image doesn't include pytest yet.
container_cmd=$(
  cat <<'EOF'
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
icd="$(ls /usr/share/vulkan/icd.d/lvp_icd.*.json 2>/dev/null | head -n 1 || true)"
if [[ -n "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
pytest_cache_dir=""
media_path="$(mktemp /tmp/frame-compare-docker-proof.XXXXXX.mp4)"
trap 'rm -f "$media_path"; if [[ -n "${pytest_cache_dir:-}" ]]; then rm -rf "$pytest_cache_dir"; fi' EXIT
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=32x32:rate=1 \
  -frames:v 1 -pix_fmt yuv420p -y "$media_path"
python - "$media_path" <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

import vapoursynth as vs

from frame_compare.vs.env import candidate_lsmas_plugin_path_details, try_load_lsmas_plugin


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


media_path = Path(sys.argv[1])
assert_true(media_path.is_file(), f"proof media missing: {media_path}")

core = vs.core
version = getattr(vs, "__version__", None)
version_major = getattr(version, "release_major", None)
version_minor = getattr(version, "release_minor", None)
version_label = f"R{version_major}" if version_major is not None else str(version)
plugin_dir = Path(vs.get_plugin_dir())
extra_plugin_path = os.environ.get("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "")
plugins = list(core.plugins())
plugin_namespaces = sorted(plugin.namespace for plugin in plugins)

assert_true(
    version_major == 76 and version_minor == 0,
    f"expected VapourSynth R76, got {version!r}",
)
assert_true(plugin_dir.is_dir(), f"vapoursynth.get_plugin_dir() is not a directory: {plugin_dir}")
assert_true(plugin_namespaces, "core.plugins() returned no plugins")
assert_true(extra_plugin_path, "VAPOURSYNTH_EXTRA_PLUGIN_PATH is not set")

lsmas_loaded_path = None
if not (
    hasattr(core, "lsmas")
    and hasattr(core.lsmas, "LWLibavSource")
    or hasattr(core, "lw")
    and hasattr(core.lw, "LWLibavSource")
):
    lsmas_loaded_path = try_load_lsmas_plugin(core)

if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
    source_namespace = "lsmas"
    source_loader = core.lsmas.LWLibavSource
elif hasattr(core, "lw") and hasattr(core.lw, "LWLibavSource"):
    source_namespace = "lw"
    source_loader = core.lw.LWLibavSource
else:
    candidates = [
        {"source": candidate.source, "path": candidate.path}
        for candidate in candidate_lsmas_plugin_path_details()
    ]
    raise AssertionError(f"LWLibavSource missing from core.lsmas/core.lw; candidates={candidates}")

assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
assert_true(hasattr(core.placebo, "Tonemap"), "core.placebo.Tonemap missing")

clip = source_loader(str(media_path))
frame = clip.get_frame(0)
assert_true(frame.width == 32 and frame.height == 32, "LWLibavSource frame render failed")

tonemap_clip = core.std.BlankClip(
    width=16,
    height=16,
    format=vs.RGB48,
    length=1,
    color=[32768, 32768, 32768],
)
tonemap_clip = tonemap_clip.std.SetFrameProps(
    _Matrix=0,
    _Range=0,
    _Transfer=16,
    _Primaries=9,
)
tonemap_out = core.placebo.Tonemap(
    tonemap_clip,
    src_max=1000,
    dst_max=203,
    tone_mapping_function=2,
    dst_csp=0,
    dst_prim=1,
    src_csp=1,
)
tonemap_frame = tonemap_out.get_frame(0)
assert_true(tonemap_frame.width == 16 and tonemap_frame.height == 16, "placebo frame render failed")

print(f"DOCKER_PROOF vapoursynth_import=ok version={version_label}")
print(f"DOCKER_PROOF plugin_dir={plugin_dir}")
print(f"DOCKER_PROOF extra_plugin_path={extra_plugin_path}")
print(f"DOCKER_PROOF core_plugins={','.join(plugin_namespaces)}")
print(f"DOCKER_PROOF lwlibavsource=ok namespace={source_namespace} loaded_path={lsmas_loaded_path}")
print("DOCKER_PROOF placebo_tonemap=ok")
print("DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,placebo")
PY
rm -f "$media_path"
python -c "import pytest, pytest_mock" >/dev/null 2>&1 || python -m pip install --user -q pytest pytest-mock &&
pytest_cache_dir="$(mktemp -d /tmp/frame-compare-pytest-cache.XXXXXX)"
EOF
)
container_cmd+=$'\n'"python -m pytest -v -o cache_dir=\"\$pytest_cache_dir\"${pytest_args}"

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

required_proof_markers=(
  "DOCKER_PROOF vapoursynth_import=ok version=R76"
  "DOCKER_PROOF plugin_dir="
  "DOCKER_PROOF extra_plugin_path=/opt/vapoursynth-extra-plugins"
  "DOCKER_PROOF core_plugins="
  "DOCKER_PROOF lwlibavsource=ok"
  "DOCKER_PROOF placebo_tonemap=ok"
  "DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,placebo"
)

for proof_marker in "${required_proof_markers[@]}"; do
  if ! grep -Fq "$proof_marker" "$tmp_log"; then
    echo "ERROR: docker runtime proof marker missing: $proof_marker" >&2
    exit 4
  fi
done

echo "OK: docker runtime proof and integration tests passed with zero skips"

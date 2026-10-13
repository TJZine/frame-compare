#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_integration.sh [--service NAME] [--no-build] [--no-cache] [--pytest-path PATH]

Runs integration tests inside the Docker image where VapourSynth + FFmpeg are installed.
Fails if any tests are skipped, xfailed, or xpassed (the “real deps work” gate).

Defaults:
  --service frame-compare-test
  Runs: pytest -n 10 --dist loadgroup -v --ignore=tests/integration/test_alignment_streaming_resources.py \
    tests/e2e/ tests/integration/ tests/vs/

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

if ! cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."; then
  echo "ERROR: unable to change to the Frame Compare repository root" >&2
  exit 2
fi

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

# Ensure the host bind-mount source exists before Compose creates any container.
# This keeps the generated-data proof writable by the invoking host user on
# Linux daemons that otherwise create a missing bind source as root.
mkdir -p generated

# Each invocation owns one fresh artifact directory.  Keep previous runs
# available for debugging and let the workflow upload the complete retained
# tree after the verifier exits, including when the test command fails.
mkdir -p generated/e2e
e2e_artifact_dir="$(mktemp -d generated/e2e/run.XXXXXX)"
e2e_artifact_name="$(basename "$e2e_artifact_dir")"
echo "Docker E2E artifacts: $e2e_artifact_dir"

build_args=()
if [[ "$no_cache" == "1" ]]; then
  build_args+=(--no-cache)
fi
build_services=("$service")
if [[ "$service" != "frame-compare-run" ]]; then
  build_services+=("frame-compare-run")
fi

if [[ "$run_build" == "1" ]]; then
  # bash 3.2 + `set -u` can treat empty `${array[@]}` expansions as unbound.
  if [[ "${#build_args[@]}" -gt 0 ]]; then
    docker compose build "${build_args[@]}" "${build_services[@]}"
  else
    docker compose build "${build_services[@]}"
  fi
fi

tmp_log="$(mktemp)"
production_log="$(mktemp)"
proof_dir=""
cleanup() {
  rm -f "$tmp_log" "$production_log"
  if [[ "$proof_dir" == generated/.docker-integration-proof.* && -d "$proof_dir" ]]; then
    rm -rf -- "$proof_dir"
  fi
}
trap cleanup EXIT

docker_cmd=(
  docker compose run
  --rm
)

if ! test_host_uid="$(id -u)" || ! test_host_gid="$(id -g)"; then
  echo "ERROR: unable to determine the invoking user's UID/GID for the Docker test run" >&2
  exit 2
fi
docker_cmd+=(--user "$test_host_uid:$test_host_gid")

docker_env_args=(
  -e HOME=/tmp/framecompare-home
  -e PYTHONUSERBASE=/home/framecompare/.local
  -e FRAME_COMPARE_E2E_REQUIRE_MEDIA=1
  -e FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/e2e/$e2e_artifact_name
  -e FRAME_COMPARE_TEST_MEDIA_CACHE=/workspace/generated/test-media-cache
)
if [[ "${FRAME_COMPARE_REQUIRE_LIBPLACEBO:-}" == "1" ]]; then
  docker_env_args+=(-e FRAME_COMPARE_REQUIRE_LIBPLACEBO=1)
fi

if [[ "${#docker_env_args[@]}" -gt 0 ]]; then
  docker_cmd+=("${docker_env_args[@]}")
fi

pytest_cli_args=()
if [[ "${#pytest_paths[@]}" -eq 0 ]]; then
  pytest_paths=(tests/e2e/ tests/integration/ tests/vs/)
  pytest_cli_args+=(--ignore=tests/integration/test_alignment_streaming_resources.py)
fi
pytest_cli_args+=("${pytest_paths[@]}")

printf -v pytest_args ' %q' "${pytest_cli_args[@]}"

docker_cmd+=(
  "$service"
  -c
)

# Note: keep this robust even if the image doesn't include pytest yet.
container_cmd=$(
  cat <<'EOF'
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
export PATH="/home/framecompare/.local/bin:${PATH}"
icd="/usr/share/vulkan/icd.d/lvp_icd.json"
if [[ -f "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
pytest_cache_dir=""
media_path="$(mktemp /tmp/frame-compare-docker-proof.XXXXXX.mp4)"
doctor_path="$(mktemp /tmp/frame-compare-doctor.XXXXXX.json)"
ffindex_path="$(mktemp -u /tmp/frame-compare-docker-proof.XXXXXX.ffindex)"
cleanup_runtime_proof() {
  rm -f "$media_path" "$doctor_path" "$ffindex_path"
  rm -f "${media_path}.frame-compare-"*.lwi
  if [[ -n "${pytest_cache_dir:-}" ]]; then
    rm -rf "$pytest_cache_dir"
  fi
}
trap cleanup_runtime_proof EXIT

frame-compare --help >/tmp/frame-compare-help.txt
frame-compare version >/tmp/frame-compare-version.txt
frame-compare doctor --json >"$doctor_path"
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=64x48:rate=24000/1001 \
  -frames:v 12 -pix_fmt yuv420p -c:v libx264 -x264-params range=tv \
  -color_range tv -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -y "$media_path"

if [[ -f "$icd" ]]; then
  vulkaninfo --summary >/tmp/frame-compare-vulkan-summary.txt
else
  echo "ERROR: Mesa software Vulkan ICD is missing from the Docker runtime" >&2
  exit 10
fi

native_ldd_log="$(mktemp /tmp/frame-compare-native-ldd.XXXXXX.txt)"
for library in \
  /opt/vapoursynth-extra-plugins/lsmas/libvslsmashsource.so \
  /opt/vapoursynth-extra-plugins/ffms2/libffms2.so \
  /usr/local/lib/libobuparse.so.2 \
  /usr/local/lib/liblsmash.so \
  /usr/local/lib/libffms2.so; do
  test -e "$library"
  echo "### $library" >>"$native_ldd_log"
  ldd "$library" >>"$native_ldd_log"
done
if grep -Fq 'not found' "$native_ldd_log"; then
  cat "$native_ldd_log" >&2
  echo "ERROR: native media runtime has unresolved shared-library dependencies" >&2
  exit 11
fi
if ! grep -Eq 'libobuparse\.so\.2 => /usr/local/lib/libobuparse\.so\.2' "$native_ldd_log"; then
  cat "$native_ldd_log" >&2
  echo "ERROR: selected L-SMASH runtime is not linked to staged OBUParse SONAME" >&2
  exit 12
fi

python /home/framecompare/frame-compare/tools/docker_runtime_smoke.py "$media_path" "$doctor_path" "$ffindex_path"
python -c "import pytest, pytest_mock, xdist" >/dev/null 2>&1 || {
  echo "ERROR: pytest, pytest-mock, or pytest-xdist is missing from the Docker runtime image" >&2
  exit 13
}
pytest_cache_dir="$(mktemp -d /tmp/frame-compare-pytest-cache.XXXXXX)"
EOF
)
container_cmd+=$'\n'"python -m pytest -n 10 --dist loadgroup -v -o cache_dir=\"\$pytest_cache_dir\"${pytest_args}"

set +e
"${docker_cmd[@]}" "$container_cmd" 2>&1 | tee "$tmp_log"
exit_code="${PIPESTATUS[0]}"
set -e

if [[ "$exit_code" != "0" ]]; then
  echo "ERROR: docker integration tests failed (exit $exit_code)" >&2
  exit "$exit_code"
fi

if grep -Eq '([1-9][0-9]* (skipped|xfailed|xpassed)|(skipped|xfailed|xpassed)=[1-9][0-9]*)' "$tmp_log"; then
  echo "ERROR: docker integration tests reported skipped, xfailed, or xpassed tests; this gate requires zero non-passing outcomes" >&2
  exit 3
fi

required_proof_markers=(
  "DOCKER_PROOF cli=ok"
  "DOCKER_PROOF non_root=ok"
  "DOCKER_PROOF vapoursynth_import=ok version=R81 api=4.3"
  "DOCKER_PROOF plugin_dir="
  "DOCKER_PROOF extra_plugin_path=/opt/vapoursynth-extra-plugins"
  "DOCKER_PROOF core_plugins="
  "DOCKER_PROOF lsmash_works=ok release=1310.0.0.0"
  "DOCKER_PROOF ffms2=ok release=5.0"
  "DOCKER_PROOF vs_placebo=ok version=2.0.4"
  "DOCKER_PROOF debian_ffmpeg="
  "DOCKER_PROOF ffmpeg_version="
  "DOCKER_PROOF ffprobe_version="
  "DOCKER_PROOF software_vulkan=ok"
  "DOCKER_PROOF native_shared_libraries=ok"
  "DOCKER_PROOF obuparse=ok linkage=shared soname=libobuparse.so.2 provenance=verified"
  "DOCKER_PROOF source_provenance=ok strategy=git-commit-tracked-tree-sha256"
  "DOCKER_PROOF doctor_json=ok"
  "DOCKER_PROOF generated_fixture_matrix=ok fixtures=h264_limited"
  "DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,ffms2,placebo"
)

for proof_marker in "${required_proof_markers[@]}"; do
  if ! grep -Fq "$proof_marker" "$tmp_log"; then
    echo "ERROR: docker runtime proof marker missing: $proof_marker" >&2
    exit 4
  fi
done

# Prove the default generated-data bind mount survives container removal.  The
# unique host directory is created under the same generated root used by the
# default Compose services, then removed by the EXIT trap after all assertions.
# The container runs the real CLI against two tiny FFmpeg-generated clips; no
# handcrafted report, screenshot, or run-record files are accepted as proof.
proof_dir="$(mktemp -d generated/.docker-integration-proof.XXXXXX)"
if ! host_uid="$(id -u)" || ! host_gid="$(id -g)"; then
  echo "ERROR: unable to determine the invoking user's UID/GID for the Docker proof" >&2
  exit 2
fi
readonly host_uid host_gid
proof_name="$(basename "$proof_dir")"
container_proof_cmd=$(cat <<'EOF'
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
export PATH="/home/framecompare/.local/bin:${PATH}"
if command -v uv >/dev/null 2>&1 || command -v uvx >/dev/null 2>&1; then
  echo "ERROR: uv build tooling leaked into the production image" >&2
  exit 6
fi
if python -c 'import pytest' >/dev/null 2>&1; then
  echo "ERROR: pytest test tooling leaked into the production image" >&2
  exit 6
fi
echo "DOCKER_PROOF production_tooling_absent=ok"
icd="/usr/share/vulkan/icd.d/lvp_icd.json"
if [[ -f "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
generated_root="/workspace/generated/PROOF_NAME"
workspace_dir="$(mktemp -d /tmp/frame-compare-docker-proof.XXXXXX)"
cleanup_workspace() {
  rm -rf -- "$workspace_dir"
}
trap cleanup_workspace EXIT

media_dir="$workspace_dir/comparison_videos"
config_dir="$workspace_dir/config"
mkdir -p "$media_dir" "$config_dir"
cat > "$config_dir/config.toml" <<CONFIG
[paths]
input_dir = "comparison_videos"
generated_dir = "$generated_root"
config_dir = "config"

[sources]
reference = "reference.mp4"

[analysis]
user_frames = []
random_frame_count = 0
dark_frame_count = 1
bright_frame_count = 0
motion_frame_count = 0
min_window_seconds = 0.0

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[color]
enable_tonemap = false

[slowpics]
auto_upload = false

[tmdb]
enabled = false

[report]
enable = true
auto_open = false
CONFIG

ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=32x32:rate=2:duration=2 \
  -frames:v 4 -c:v mpeg4 -pix_fmt yuv420p -y "$media_dir/reference.mp4"
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=32x32:rate=2:duration=2 \
  -vf hue=h=20 -frames:v 4 -c:v mpeg4 -pix_fmt yuv420p -y "$media_dir/comparison.mp4"

frame-compare run \
  --root "$workspace_dir" \
  --config "$config_dir/config.toml" \
  --input "$media_dir" \
  --skip-metadata \
  --no-upload \
  --quiet

# The application must not leave core output artifacts beside the ephemeral
# fixture workspace. Any match here means generated_dir containment failed.
unexpected_outputs="$(find "$workspace_dir" -type f \( \
  -name 'report.html' -o -name 'run_info.toml' -o -name 'run_result.toml' -o -name '*.png' \
\) -print)"
if [[ -n "$unexpected_outputs" ]]; then
  echo "ERROR: Frame Compare emitted core artifacts outside /workspace/generated:" >&2
  printf '%s\n' "$unexpected_outputs" >&2
  exit 7
fi

run_dirs=()
while IFS= read -r -d '' run_dir; do
  run_dirs+=("$run_dir")
done < <(find "$generated_root" -mindepth 1 -maxdepth 1 -type d ! -name cache -print0)
if [[ "${#run_dirs[@]}" != "1" ]]; then
  echo "ERROR: expected one application-created run folder under $generated_root" >&2
  exit 8
fi
run_root="${run_dirs[0]}"
require_nonempty_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" || ! -s "$path" ]]; then
    echo "ERROR: missing or empty $label: $path" >&2
    exit 9
  fi
}

require_nonempty_file "$run_root/report.html" "HTML report"
require_nonempty_file "$run_root/run_info.toml" "run_info.toml"
require_nonempty_file "$run_root/run_result.toml" "run_result.toml"
require_nonempty_file "$generated_root/clip_probe.toml" "shared probe cache"
require_nonempty_file "$run_root/generated/clip_probe.toml" "run-local probe state"

if ! screenshot_path="$(
  find "$run_root/screenshots" -type f -name '*.png' -size +0c -print -quit 2>/dev/null
)" || [[ -z "$screenshot_path" ]]; then
  echo "ERROR: no non-empty PNG screenshots found under $run_root/screenshots" >&2
  exit 9
fi
if ! analysis_cache_path="$(
  find "$generated_root/cache/analysis" -type f -name '*.compframes' -size +0c -print -quit 2>/dev/null
)" || [[ -z "$analysis_cache_path" ]]; then
  echo "ERROR: no non-empty shared analysis cache found under $generated_root/cache/analysis" >&2
  exit 9
fi
echo "DOCKER_PROOF application_run=ok"
EOF
)
container_proof_cmd="${container_proof_cmd//PROOF_NAME/$proof_name}"

if ! env \
  FRAME_COMPARE_HOST_UID="$host_uid" \
  FRAME_COMPARE_HOST_GID="$host_gid" \
  docker compose run --rm --entrypoint /bin/bash frame-compare-run -lc "$container_proof_cmd" \
    | tee "$production_log"; then
  echo "ERROR: generated-data bind-mount proof failed" >&2
  exit 5
fi
if ! grep -Fq "DOCKER_PROOF production_tooling_absent=ok" "$production_log"; then
  echo "ERROR: production-image tooling proof marker missing" >&2
  exit 6
fi

host_python=""
if command -v python3 >/dev/null 2>&1; then
  host_python="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  host_python="$(command -v python)"
fi
if [[ -z "$host_python" ]]; then
  echo "ERROR: host Python is required to parse Docker-generated TOML and PNG proof files" >&2
  exit 127
fi

export PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}"
if ! "$host_python" - "$proof_dir" <<'PY'
from __future__ import annotations

import struct
import sys
import tomllib
from pathlib import Path

from frame_compare.vs.runtime_contract import media_runtime_fingerprint


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


proof_dir = Path(sys.argv[1]).resolve()
run_dirs = sorted(
    path
    for path in proof_dir.iterdir()
    if path.is_dir() and not path.is_symlink() and path.name != "cache"
)
if len(run_dirs) != 1:
    fail(f"expected one host run folder after container removal under {proof_dir}, found {run_dirs}")
run_dir = run_dirs[0]
generated_root = proof_dir


def require_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        fail(f"generated-data bind-mount artifact missing after container removal: {label}: {path}")
    return path


report_path = require_file(run_dir / "report.html", "report.html")
if "<html" not in report_path.read_text(encoding="utf-8").lower():
    fail(f"application report is not HTML: {report_path}")

run_info_path = require_file(run_dir / "run_info.toml", "run_info.toml")
with run_info_path.open("rb") as handle:
    run_info = tomllib.load(handle)
if run_info.get("version") != 2:
    fail(f"run_info.toml is not a parseable V2 record: {run_info_path}")
media_runtime = run_info.get("media_runtime")
if not isinstance(media_runtime, dict):
    fail(f"run_info.toml has no media_runtime table: {run_info_path}")
fingerprints = media_runtime.get("fingerprints")
if not isinstance(fingerprints, dict):
    fail(f"run_info.toml has no media runtime fingerprints: {run_info_path}")
if fingerprints.get("full") != media_runtime_fingerprint("full", profile="debian-trixie"):
    fail(f"run_info.toml media runtime fingerprint mismatch: {run_info_path}")

run_result_path = require_file(run_dir / "run_result.toml", "run_result.toml")
with run_result_path.open("rb") as handle:
    run_result = tomllib.load(handle)
if run_result.get("version") != 1 or run_result.get("status") not in {
    "completed",
    "completed_with_warnings",
}:
    fail(f"run_result.toml is not a completed parseable V1 record: {run_result_path}")
if run_result.get("report_path") != "report.html":
    fail(f"run_result.toml report_path is not canonical: {run_result_path}")
if run_result.get("screenshot_dir") != "screenshots":
    fail(f"run_result.toml screenshot_dir is not canonical: {run_result_path}")

screenshot_dir = run_dir / "screenshots"
screenshots = sorted(screenshot_dir.glob("*.png"))
if not screenshots:
    fail(f"application produced no PNG screenshots: {screenshot_dir}")
for screenshot in screenshots:
    payload = require_file(screenshot, "screenshots/*.png").read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"application screenshot is not a PNG: {screenshot}")
    if len(payload) < 24 or payload[12:16] != b"IHDR":
        fail(f"application screenshot has no PNG IHDR: {screenshot}")
    width, height = struct.unpack(">II", payload[16:24])
    if width == 0 or height == 0:
        fail(f"application screenshot has invalid dimensions: {screenshot}")

root_probe_path = require_file(generated_root / "clip_probe.toml", "shared probe cache")
with root_probe_path.open("rb") as handle:
    root_probe = tomllib.load(handle)
if root_probe.get("version") != "1":
    fail(f"shared probe cache is not parseable: {root_probe_path}")

run_probe_path = require_file(run_dir / "generated" / "clip_probe.toml", "run-local probe state")
with run_probe_path.open("rb") as handle:
    run_probe = tomllib.load(handle)
if run_probe.get("version") != "1":
    fail(f"run-local probe state is not parseable: {run_probe_path}")

analysis_cache_dir = generated_root / "cache" / "analysis"
analysis_caches = sorted(analysis_cache_dir.glob("*.compframes"))
if not analysis_caches:
    fail(f"application produced no shared analysis cache: {analysis_cache_dir}")
for cache_path in analysis_caches:
    require_file(cache_path, "shared analysis cache")

print(
    "DOCKER_PROOF generated_mount=ok "
    "artifacts=report,screenshots,run_info,run_result,run_generated,analysis_cache,probe_cache"
)
PY
then
  exit 6
fi

echo "OK: docker runtime proof and integration tests passed with zero skips"

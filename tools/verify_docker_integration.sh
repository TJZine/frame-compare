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

# Ensure the host bind-mount source exists before Compose creates any container.
# This keeps the generated-data proof writable by the invoking host user on
# Linux daemons that otherwise create a missing bind source as root.
mkdir -p generated

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
proof_dir=""
cleanup() {
  rm -f "$tmp_log"
  if [[ "$proof_dir" == generated/.docker-integration-proof.* && -d "$proof_dir" ]]; then
    rm -rf -- "$proof_dir"
  fi
}
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

# Prove the default generated-data bind mount survives container removal.  The
# unique host directory is created under the same generated root used by the
# default Compose services, then removed by the EXIT trap after all assertions.
# The container runs the real CLI against two tiny FFmpeg-generated clips; no
# handcrafted report, screenshot, or run-record files are accepted as proof.
proof_dir="$(mktemp -d generated/.docker-integration-proof.XXXXXX)"
# mktemp creates an owner-only directory, while the production-like service
# intentionally runs as the image's non-root user. The directory is unique,
# contains only generated proof fixtures, and is removed by the EXIT trap, so
# grant that container identity access without changing the persistent root.
chmod 0777 "$proof_dir"
proof_name="$(basename "$proof_dir")"
container_proof_cmd=$(cat <<'EOF'
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
export PATH="/home/framecompare/.local/bin:${PATH}"
icd="$(ls /usr/share/vulkan/icd.d/lvp_icd.*.json 2>/dev/null | head -n 1 || true)"
if [[ -n "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
generated_root="/workspace/generated/PROOF_NAME"
workspace_dir="$(mktemp -d /tmp/frame-compare-docker-proof.XXXXXX)"
cleanup_workspace() {
  # The host validates and removes these container-owned artifacts after this
  # container exits. Restore host write access on descendants without changing
  # the persistent generated root or relying on matching host/container UIDs.
  if [[ -d "$generated_root" ]]; then
    find "$generated_root" -mindepth 1 -exec chmod a+rwX {} +
  fi
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
[[ -s "$run_root/report.html" ]]
[[ -s "$run_root/run_info.toml" ]]
[[ -s "$run_root/run_result.toml" ]]
[[ -n "$(find "$run_root/screenshots" -type f -name '*.png' -size +0c -print -quit)" ]]
[[ -s "$generated_root/clip_probe.toml" ]]
[[ -s "$run_root/generated/clip_probe.toml" ]]
[[ -n "$(find "$generated_root/cache/analysis" -type f -name '*.compframes' -size +0c -print -quit)" ]]
# The tiny deterministic fixture disables audio alignment, so supplement only
# that non-natural shared-cache path; core run artifacts above remain real CLI
# output and are never replaced by sentinels.
mkdir -p "$generated_root/cache/alignment"
printf '%s\n' 'supplemental docker proof alignment cache' > \
  "$generated_root/cache/alignment/.docker-proof-supplemental-alignment"
echo "DOCKER_PROOF application_run=ok"
EOF
)
container_proof_cmd="${container_proof_cmd//PROOF_NAME/$proof_name}"

if ! docker compose run --rm --entrypoint /bin/bash frame-compare-run -lc "$container_proof_cmd"; then
  echo "ERROR: generated-data bind-mount proof failed" >&2
  exit 5
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

if ! "$host_python" - "$proof_dir" <<'PY'
from __future__ import annotations

import struct
import sys
import tomllib
from pathlib import Path


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
if run_info.get("version") != 1:
    fail(f"run_info.toml is not a parseable V1 record: {run_info_path}")

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

alignment_supplement = require_file(
    generated_root / "cache" / "alignment" / ".docker-proof-supplemental-alignment",
    "supplemental shared alignment cache",
)
if alignment_supplement.read_text(encoding="utf-8").strip() != "supplemental docker proof alignment cache":
    fail(f"supplemental alignment cache marker is invalid: {alignment_supplement}")

print(
    "DOCKER_PROOF generated_mount=ok "
    "artifacts=report,screenshots,run_info,run_result,run_generated,analysis_cache,alignment_cache,probe_cache"
)
PY
then
  exit 6
fi

echo "OK: docker runtime proof and integration tests passed with zero skips"

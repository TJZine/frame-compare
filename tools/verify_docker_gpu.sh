#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_gpu.sh [--service NAME] [--no-build] [--no-cache]

Runs the optional NVIDIA Docker GPU proof inside the Docker image.

Defaults:
  --service frame-compare-test

Notes:
  - Requires a Linux host with a working NVIDIA driver and NVIDIA Container Toolkit.
  - Requires Docker Compose 2.30.0 or later for the gpu-nvidia Compose override.
  - If Compose is older, the script prints a docker run --gpus all fallback command.
EOF
}

readonly MIN_COMPOSE_GPUS_VERSION="2.30.0"
readonly DEFAULT_SERVICE="frame-compare-test"
if ! REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; then
  echo "ERROR: unable to determine repository root" >&2
  exit 2
fi
readonly REPO_ROOT
readonly DEFAULT_IMAGE="frame-compare:dev"
readonly CONTAINER_WORKDIR="/home/framecompare/frame-compare"
readonly DEFAULT_DRIVER_CAPABILITIES="compute,utility,graphics"

service="$DEFAULT_SERVICE"
run_build="1"
no_cache="0"
inside_container="0"

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
    --inside-container)
      inside_container="1"
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

compose_version() {
  local version
  version="$(docker compose version --short 2>/dev/null || true)"
  if [[ -n "$version" ]]; then
    printf '%s\n' "$version" | sed -nE 's/^v?([0-9]+(\.[0-9]+){1,2}).*/\1/p'
    return 0
  fi

  version="$(
    docker compose version 2>/dev/null \
      | sed -nE 's/.*v([0-9]+(\.[0-9]+){1,2}).*/\1/p' \
      | head -n 1
  )"
  if [[ -z "$version" ]]; then
    return 1
  fi
  printf '%s\n' "$version"
}

version_ge() {
  local left="$1"
  local right="$2"
  local IFS='.'
  local -a left_parts=()
  local -a right_parts=()
  local index=0
  local max_len=0
  local left_part=0
  local right_part=0

  read -r -a left_parts <<<"$left"
  read -r -a right_parts <<<"$right"

  if (( ${#left_parts[@]} > ${#right_parts[@]} )); then
    max_len="${#left_parts[@]}"
  else
    max_len="${#right_parts[@]}"
  fi

  for (( index=0; index<max_len; index+=1 )); do
    left_part="${left_parts[index]:-0}"
    right_part="${right_parts[index]:-0}"
    if (( 10#${left_part} > 10#${right_part} )); then
      return 0
    fi
    if (( 10#${left_part} < 10#${right_part} )); then
      return 1
    fi
  done

  return 0
}

fallback_command() {
  printf '%s\n' \
    "docker run --rm --gpus all \\" \
    "  -e NVIDIA_VISIBLE_DEVICES=all \\" \
    "  -e NVIDIA_DRIVER_CAPABILITIES=${DEFAULT_DRIVER_CAPABILITIES} \\" \
    "  -e VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins \\" \
    "  -e LIBGL_ALWAYS_SOFTWARE=0 \\" \
    "  -v \"${REPO_ROOT}:${CONTAINER_WORKDIR}\" \\" \
    "  -w ${CONTAINER_WORKDIR} \\" \
    "  --entrypoint /bin/bash ${DEFAULT_IMAGE} \\" \
    "  -lc 'bash tools/verify_docker_gpu.sh --inside-container'"
}

find_nvidia_icd() {
  local search_dirs=()
  local search_dir
  local candidate

  if [[ -n "${FRAME_COMPARE_GPU_ICD_SEARCH_DIRS:-}" ]]; then
    IFS=':' read -r -a search_dirs <<<"${FRAME_COMPARE_GPU_ICD_SEARCH_DIRS}"
  else
    search_dirs=(/usr/share/vulkan/icd.d /etc/vulkan/icd.d)
  fi

  for search_dir in "${search_dirs[@]}"; do
    [[ -d "$search_dir" ]] || continue
    while IFS= read -r -d '' candidate; do
      printf '%s\n' "$candidate"
      return 0
    done < <(find "$search_dir" -maxdepth 1 -type f \( -iname '*nvidia*.json' -o -iname 'nvidia_icd*.json' \) -print0 | sort -z)
  done

  return 1
}

run_placebo_proof() {
  if [[ -n "${FRAME_COMPARE_GPU_PLACEBO_PROOF_CMD:-}" ]]; then
    bash -lc "${FRAME_COMPARE_GPU_PLACEBO_PROOF_CMD}"
    return
  fi

  python - <<'PY'
from __future__ import annotations

import vapoursynth as vs


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


core = vs.core
assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
assert_true(hasattr(core.placebo, "Tonemap"), "core.placebo.Tonemap missing")

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
frame = tonemap_out.get_frame(0)
assert_true(frame.width == 16 and frame.height == 16, "placebo frame render failed")
print("DOCKER_GPU_PROOF placebo_tonemap=ok")
PY
}

run_container_proof() {
  unset LIBGL_ALWAYS_SOFTWARE
  local nvidia_icd=""

  if [[ "${VK_ICD_FILENAMES:-}" =~ [Ll][Aa][Vv][Aa][Pp][Ii][Pp][Ee]|lvp_icd ]]; then
    echo "ERROR: VK_ICD_FILENAMES points at a lavapipe ICD; refusing software Vulkan proof" >&2
    exit 20
  fi

  if [[ -n "${FRAME_COMPARE_GPU_FORCE_NO_NVIDIA_ICD:-}" ]]; then
    nvidia_icd=""
  elif nvidia_icd="$(find_nvidia_icd 2>/dev/null)"; then
    export VK_ICD_FILENAMES="$nvidia_icd"
  fi

  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "ERROR: nvidia-smi is unavailable inside the container; NVIDIA container support is not active" >&2
    exit 21
  fi

  local nvidia_log
  nvidia_log="$(mktemp)"
  local vulkan_summary
  vulkan_summary="$(mktemp)"
  trap 'rm -f "$nvidia_log" "$vulkan_summary"' RETURN

  if ! nvidia-smi -L >"$nvidia_log" 2>&1; then
    echo "ERROR: nvidia-smi failed; NVIDIA container support is not active" >&2
    cat "$nvidia_log" >&2
    exit 22
  fi

  if ! grep -Eiq 'GPU [0-9]+:|NVIDIA' "$nvidia_log"; then
    echo "ERROR: nvidia-smi did not report an NVIDIA GPU" >&2
    cat "$nvidia_log" >&2
    exit 23
  fi

  echo "DOCKER_GPU_PROOF nvidia_visible=ok"

  if [[ -z "$nvidia_icd" ]]; then
    echo "ERROR: unable to locate an NVIDIA Vulkan ICD; refusing GPU proof without an explicit NVIDIA ICD pin" >&2
    exit 24
  fi

  if ! command -v vulkaninfo >/dev/null 2>&1; then
    echo "ERROR: vulkaninfo is unavailable in the Docker image; install vulkan-tools before GPU proofing" >&2
    exit 25
  fi

  if ! vulkaninfo --summary >"$vulkan_summary" 2>&1; then
    echo "ERROR: vulkaninfo --summary failed under the active NVIDIA environment" >&2
    cat "$vulkan_summary" >&2
    exit 26
  fi

  python - "$vulkan_summary" "${VK_ICD_FILENAMES:-auto}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
icd_value = sys.argv[2]
text = summary_path.read_text(encoding="utf-8")
device_patterns = (
    re.compile(r"^\s*GPU\d+\s*:\s*(.+?)\s*$", re.MULTILINE),
    re.compile(r"^\s*GPU id\s*=\s*\d+\s*\((.+?)\)\s*$", re.MULTILINE),
    re.compile(r"^\s*deviceName\s*=\s*(.+?)\s*$", re.MULTILINE),
)

devices: list[str] = []
for pattern in device_patterns:
    for match in pattern.finditer(text):
        device = re.sub(r"\s+", " ", match.group(1).strip())
        if device and device not in devices:
            devices.append(device)

if not devices:
    raise SystemExit("ERROR: vulkaninfo --summary did not expose any Vulkan devices")

selected = devices[0]
banned_patterns = (
    "lavapipe",
    "llvmpipe",
    "software",
    "mesa x.org",
    "cpu",
)

print(f"DOCKER_GPU_PROOF vulkan_icd={icd_value}")
print(f"DOCKER_GPU_PROOF vulkan_device={selected}")

selected_lower = selected.casefold()
if any(pattern in selected_lower for pattern in banned_patterns):
    raise SystemExit(
        f"ERROR: selected Vulkan device is software-backed ({selected}); refusing placebo proof"
    )

if "nvidia" not in selected_lower:
    raise SystemExit(
        f"ERROR: selected Vulkan device is not NVIDIA hardware ({selected}); refusing placebo proof"
    )

print("DOCKER_GPU_PROOF vulkan_hardware=ok")
PY

  run_placebo_proof
}

run_host_proof() {
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

  local build_args=()
  if [[ "$no_cache" == "1" ]]; then
    build_args+=(--no-cache)
  fi

  if [[ "$run_build" == "1" ]]; then
    if [[ "${#build_args[@]}" -gt 0 ]]; then
      docker compose build "${build_args[@]}" "$service"
    else
      docker compose build "$service"
    fi
  fi

  local current_compose_version
  current_compose_version="$(compose_version || true)"
  if [[ -z "$current_compose_version" ]]; then
    echo "ERROR: unable to determine docker compose version" >&2
    exit 26
  fi

  if ! version_ge "$current_compose_version" "$MIN_COMPOSE_GPUS_VERSION"; then
    echo "ERROR: Docker Compose ${MIN_COMPOSE_GPUS_VERSION} or later is required for the gpu-nvidia Compose gpus override; found ${current_compose_version}" >&2
    echo "DOCKER_GPU_FALLBACK command_begin"
    fallback_command
    echo "DOCKER_GPU_FALLBACK command_end"
    exit 27
  fi

  docker compose \
    -f docker-compose.yml \
    -f docker-compose.gpu-nvidia.yml \
    --profile gpu-nvidia \
    run --rm "$service" \
    -lc 'bash tools/verify_docker_gpu.sh --inside-container'
}

if [[ "$inside_container" == "1" ]]; then
  run_container_proof
else
  run_host_proof
fi

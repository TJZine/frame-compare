#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_gui.sh [--service NAME] [--no-build] [--no-cache]

Runs the optional Linux X11/VSPreview Docker proof without launching a real UI.

Defaults:
  --service frame-compare-test

Host contract:
  - Linux host with an active X11 DISPLAY
  - /tmp/.X11-unix available on the host
  - Optional XAUTHORITY cookie file, exported via FRAME_COMPARE_XAUTHORITY_PATH
  - Container runs as the host UID/GID so narrow local-user X11 permissions apply

Manual UI launch remains separate from this proof.
EOF
}

readonly DEFAULT_SERVICE="frame-compare-test"
readonly COMPOSE_BASE=(-f docker-compose.yml -f docker-compose.gui-linux.yml)

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

print_manual_ui_instructions() {
  local host_user="$1"

  cat <<EOF
Manual X11 permission command (run on the host only if your X server denies access):
  xhost +si:localuser:${host_user}

Cleanup command:
  xhost -si:localuser:${host_user}

Manual GUI launch example:
  docker compose -f docker-compose.yml -f docker-compose.gui-linux.yml run --rm frame-compare-run \\
    run --root /workspace --input /workspace/comparison_videos
EOF
}

run_container_proof() {
  mkdir -p "${HOME:-/tmp/framecompare-home}" "${XDG_RUNTIME_DIR:-/tmp/framecompare-runtime}"

  python -m vspreview --help >/tmp/framecompare-vspreview-help.txt
  echo "DOCKER_GUI_PROOF vspreview_help=ok"

  local doctor_json
  doctor_json="$(mktemp)"
  local script_path_file
  script_path_file="$(mktemp)"
  trap 'rm -f "$doctor_json" "$script_path_file" /tmp/framecompare-vspreview-help.txt' RETURN

  frame-compare doctor --json >"$doctor_json"
  python - "$doctor_json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

doctor_report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
checks = doctor_report.get("doctor", {}).get("checks", [])
vspreview_entry = next((entry for entry in checks if entry.get("id") == "vspreview"), None)
if vspreview_entry is None:
    raise SystemExit("doctor JSON did not include a vspreview check entry")
if vspreview_entry.get("status") != "pass":
    raise SystemExit(f"unexpected vspreview status: {vspreview_entry.get('status')!r}")
if vspreview_entry.get("message") != "VSPreview is available for interactive alignment":
    raise SystemExit(f"unexpected vspreview message: {vspreview_entry.get('message')!r}")
print("DOCKER_GUI_PROOF doctor_vspreview=ok")
PY

  python - <<'PY'
from __future__ import annotations

from frame_compare.vspreview.adapter import check_vspreview_availability

availability = check_vspreview_availability()
if availability.is_available is not True:
    raise SystemExit(f"expected VSPreview availability, got: {availability!r}")
print("DOCKER_GUI_PROOF availability=ok")
PY

  python - "$script_path_file" <<'PY'
from __future__ import annotations

from pathlib import Path

from frame_compare.vspreview.adapter import (
    VSPreviewConfig,
    VSPreviewSessionRequest,
    launch_alignment_verification_session,
)

cache_dir = Path("/tmp/framecompare-gui-proof")
cache_dir.mkdir(parents=True, exist_ok=True)
script_path = launch_alignment_verification_session(
    VSPreviewSessionRequest(
        reference=Path("/workspace/comparison_videos/reference.mkv"),
        comparisons=[Path("/workspace/comparison_videos/comparison.mkv")],
        suggested_offsets_by_key={"comparison": 0},
        cache_dir=cache_dir,
    ),
    VSPreviewConfig(enabled=False),
)
compiled = compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec")
assert compiled is not None
Path(__import__("sys").argv[1]).write_text(str(script_path), encoding="utf-8")
print("DOCKER_GUI_PROOF session_script=ok")
PY

  printf 'DOCKER_GUI_PROOF session_script_path=%s\n' "$(cat "$script_path_file")"
}

if [[ "$inside_container" == "1" ]]; then
  run_container_proof
  exit 0
fi

host_os="$(uname -s)"
if [[ "$host_os" != "Linux" ]]; then
  echo "ERROR: GUI Docker proof is Linux/X11-only; mark this surface documented-only/unverified on ${host_os}" >&2
  exit 21
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "ERROR: DISPLAY is not set; GUI Docker proof requires an active X11 session" >&2
  exit 22
fi

if [[ ! -d /tmp/.X11-unix ]]; then
  echo "ERROR: /tmp/.X11-unix is unavailable; GUI Docker proof requires the host X11 socket directory" >&2
  exit 23
fi

if [[ -z "${FRAME_COMPARE_XAUTHORITY_PATH:-}" ]]; then
  if [[ -n "${XAUTHORITY:-}" && -f "${XAUTHORITY}" ]]; then
    export FRAME_COMPARE_XAUTHORITY_PATH="${XAUTHORITY}"
  elif [[ -f "${HOME}/.Xauthority" ]]; then
    export FRAME_COMPARE_XAUTHORITY_PATH="${HOME}/.Xauthority"
  fi
fi

if ! host_uid="$(id -u)"; then
  echo "ERROR: unable to determine host UID for GUI Docker proof" >&2
  exit 24
fi
readonly host_uid
if ! host_gid="$(id -g)"; then
  echo "ERROR: unable to determine host GID for GUI Docker proof" >&2
  exit 24
fi
readonly host_gid
export FRAME_COMPARE_HOST_UID="$host_uid"
export FRAME_COMPARE_HOST_GID="$host_gid"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required to run the GUI proof" >&2
  exit 20
fi

docker info >/dev/null

compose_cmd=(docker compose "${COMPOSE_BASE[@]}")
if [[ "$run_build" == "1" ]]; then
  build_args=()
  if [[ "$no_cache" == "1" ]]; then
    build_args+=(--no-cache)
  fi
  "${compose_cmd[@]}" build "${build_args[@]}" "$service"
fi

if ! host_user_name="$(id -un)"; then
  echo "ERROR: unable to determine host username for GUI Docker proof" >&2
  exit 24
fi
readonly host_user_name
print_manual_ui_instructions "$host_user_name"

"${compose_cmd[@]}" run --rm --entrypoint /bin/bash "$service" -lc \
  'bash tools/verify_docker_gui.sh --inside-container'

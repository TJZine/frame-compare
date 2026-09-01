#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_gui.sh [--service NAME] [--no-build] [--no-cache]

Runs the optional Linux X11/VSView Docker proof without launching a real UI.

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

  if command -v uv >/dev/null 2>&1 || command -v uvx >/dev/null 2>&1; then
    echo "ERROR: uv build tooling leaked into the GUI production image" >&2
    return 6
  fi
  if python -c 'import pytest' >/dev/null 2>&1; then
    echo "ERROR: pytest test tooling leaked into the GUI production image" >&2
    return 6
  fi
  echo "DOCKER_GUI_PROOF production_tooling_absent=ok"

  python -m vsview --help >/tmp/framecompare-vsview-help.txt
  echo "DOCKER_GUI_PROOF vsview_help=ok"

  python - <<'PY'
from PySide6.QtWidgets import QApplication
import vapoursynth as vs

app = QApplication([])
if not hasattr(vs.core, "bs"):
    raise SystemExit("BestSource is unavailable in the VSView runtime")
app.quit()
print("DOCKER_GUI_PROOF pyside6_application=ok")
print("DOCKER_GUI_PROOF bestsource=ok")
PY

  local doctor_json
  doctor_json="$(mktemp)"
  local script_path_file
  script_path_file="$(mktemp)"
  local proof_dir
  proof_dir="$(mktemp -d)"
  trap 'rm -rf -- "$proof_dir"; rm -f "$doctor_json" "$script_path_file" /tmp/framecompare-vsview-help.txt' RETURN

  frame-compare doctor --json >"$doctor_json"
  python - "$doctor_json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

doctor_report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
checks = doctor_report.get("doctor", {}).get("checks", [])
vsview_entry = next((entry for entry in checks if entry.get("id") == "vsview"), None)
if vsview_entry is None:
    raise SystemExit("doctor JSON did not include a vsview check entry")
if vsview_entry.get("status") != "pass":
    raise SystemExit(f"unexpected vsview status: {vsview_entry.get('status')!r}")
if vsview_entry.get("message") != "VSView and the Frame Compare alignment panel are available":
    raise SystemExit(f"unexpected vsview message: {vsview_entry.get('message')!r}")
print("DOCKER_GUI_PROOF doctor_vsview=ok")
PY

  python - <<'PY'
from __future__ import annotations

from frame_compare.vsview.adapter import check_vsview_availability

availability = check_vsview_availability()
if availability.is_available is not True:
    raise SystemExit(f"expected VSView availability, got: {availability!r}")
print("DOCKER_GUI_PROOF availability=ok")
PY

  ffmpeg -hide_banner -loglevel error \
    -f lavfi -i "color=c=black:size=64x48:rate=1:duration=3" \
    -frames:v 3 -c:v libx264 -pix_fmt yuv420p -y "$proof_dir/reference.mkv"
  ffmpeg -hide_banner -loglevel error \
    -f lavfi -i "color=c=white:size=64x48:rate=1:duration=3" \
    -frames:v 3 -c:v libx264 -pix_fmt yuv420p -y "$proof_dir/comparison.mkv"
  ffmpeg -hide_banner -loglevel error \
    -f lavfi -i "color=c=gray:size=64x48:rate=1:duration=3" \
    -frames:v 3 -c:v libx264 -pix_fmt yuv420p -y "$proof_dir/comparison_2.mkv"
  echo "DOCKER_GUI_PROOF real_media=ok"

  python - "$proof_dir" "$script_path_file" <<'PY'
from __future__ import annotations

import importlib.metadata
import os
import sys
import types
from pathlib import Path

import vapoursynth as vs
from PySide6.QtWidgets import QApplication, QWidget

from frame_compare.vs.source import source_index_path
from frame_compare.vsview.adapter import (
    VSViewConfig,
    VSViewSessionRequest,
    launch_alignment_verification_session,
)
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewContractError,
    AlignmentReviewExpectedComparison,
    AlignmentReviewOutputCandidate,
    parse_alignment_review_workspace_metadata,
    read_alignment_review_result,
)
from frame_compare.vsview.alignment_review_panel import AlignmentReviewPanel
from vsview.api.output import get_outputs

proof_dir = Path(sys.argv[1])
reference = proof_dir / "reference.mkv"
comparison = proof_dir / "comparison.mkv"
comparison_2 = proof_dir / "comparison_2.mkv"
unspecified_color_props = {"_Matrix": 2, "_Transfer": 2, "_Primaries": 2}
session = launch_alignment_verification_session(
    VSViewSessionRequest(
        reference=reference,
        comparisons=[comparison, comparison_2],
        suggested_offsets_by_key={
            "reference:comparison": 0,
            "reference:comparison_2": 0,
        },
        cache_dir=proof_dir / "cache",
        frame_props_by_stem={
            reference.stem: unspecified_color_props,
            comparison.stem: unspecified_color_props,
            comparison_2.stem: unspecified_color_props,
        },
    ),
    VSViewConfig(enabled=False),
)
script_path = session.script_path
script_text = script_path.read_text(encoding="utf-8")
compiled = compile(script_text, str(script_path), "exec")
assert "from vsview import set_output" in script_text

script_module = types.ModuleType("__vsview__")
script_module.__file__ = str(script_path)
sys.modules["__vsview__"] = script_module
exec(compiled, script_module.__dict__)

metadata = get_outputs()
expected_names = {0: "Reference", 1: "Comparison 1", 2: "Comparison 2"}
actual_names = {index: item.name for index, item in metadata.items()}
if actual_names != expected_names:
    raise SystemExit(f"unexpected VSView output metadata: {actual_names!r}")
print("DOCKER_GUI_PROOF named_outputs=ok")

entry_points = tuple(
    entry_point
    for entry_point in importlib.metadata.entry_points(group="vsview")
    if entry_point.name == "frame-compare-alignment-review"
    and entry_point.value == "frame_compare.vsview.alignment_review_panel"
)
if len(entry_points) != 1:
    raise SystemExit(f"unexpected Frame Compare VSView entry points: {entry_points!r}")
if getattr(entry_points[0].load(), "AlignmentReviewPanel", None) is not AlignmentReviewPanel:
    raise SystemExit("Frame Compare VSView entry point did not load the native alignment panel")
print("DOCKER_GUI_PROOF vsview_entry_point=ok")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
app = QApplication.instance() or QApplication([])
panel_parent = QWidget()
panel = AlignmentReviewPanel(panel_parent, types.SimpleNamespace(file_path=None))
if "Inactive" not in panel.progress_label.text():
    raise SystemExit("native alignment panel was not inert outside a generated session")
panel.setParent(None)
panel_parent.deleteLater()
app.processEvents()
print("DOCKER_GUI_PROOF panel_offscreen=ok")

outputs = vs.get_outputs()
if set(outputs) != set(expected_names):
    raise SystemExit(f"unexpected VapourSynth output indexes: {sorted(outputs)!r}")
for index in sorted(outputs):
    outputs[index].clip.get_frame(0)
print("DOCKER_GUI_PROOF frame_zero=ok")

index_paths = [
    source_index_path(reference),
    source_index_path(comparison),
    source_index_path(comparison_2),
]
if not all(path.is_file() and path.stat().st_size > 0 for path in index_paths):
    raise SystemExit(f"missing L-SMASH indexes: {index_paths!r}")
print("DOCKER_GUI_PROOF lsmash_indexes=ok")

candidates = tuple(
    AlignmentReviewOutputCandidate(
        output_id=index,
        source_frame_count=output.clip.num_frames,
        metadata=metadata[index].kwargs,
    )
    for index, output in sorted(outputs.items())
)
workspace = parse_alignment_review_workspace_metadata(candidates)
if workspace.session_id != session.session_id:
    raise SystemExit("generated VSView metadata/session identity mismatch")
expected = tuple(
    AlignmentReviewExpectedComparison(
        pair.comparison_key,
        workspace.reference.source_frame_count,
        pair.source_frame_count,
    )
    for pair in workspace.comparisons
)

class Timeline:
    def clear_notches(self, *_args, **_kwargs):
        return None

    def add_notch(self, *_args, **_kwargs):
        return None


voutputs = [
    types.SimpleNamespace(
        vs_index=index,
        vs_output=output,
        kwargs=metadata[index].kwargs,
    )
    for index, output in sorted(outputs.items())
]
panel_api = types.SimpleNamespace(
    file_path=script_path,
    voutputs=voutputs,
    current_voutput=voutputs[0],
    current_frame=1,
    timeline=Timeline(),
)
from vsengine.loops import get_loop, set_loop
from vsview.vsenv import QtEventLoop

previous_loop = get_loop()
set_loop(QtEventLoop(app))
try:
    active_parent = QWidget()
    active_panel = AlignmentReviewPanel(active_parent, panel_api)
    active_panel.on_workspace_loaded()
    app.processEvents()
    if active_panel.progress_label.text() != "0 / 3 sources ready":
        raise SystemExit("alignment panel did not start with an empty three-source lineup")
    for output_index, frame in enumerate((1, 0, 2)):
        panel_api.current_voutput = voutputs[output_index]
        panel_api.current_frame = frame
        active_panel.on_current_voutput_changed(voutputs[output_index], output_index)
        app.processEvents()
    if active_panel.progress_label.text() != "3 / 3 sources ready":
        raise SystemExit("alignment panel did not record every source position")
    if active_panel.use_positions_button.text() != "Use these aligned positions":
        raise SystemExit("alignment panel primary action label changed")
    if active_panel.keep_button.text() != "Keep audio-derived alignment":
        raise SystemExit("alignment panel keep action label changed")
    if not active_panel.use_positions_button.isEnabled():
        raise SystemExit("alignment positions action did not become ready for the whole set")
    active_panel.use_positions_button.click()
    app.processEvents()
    observed_result = read_alignment_review_result(session, expected)
    if [decision.action for decision in observed_result.decisions] != ["confirmed", "confirmed"]:
        raise SystemExit("alignment positions action did not write complete confirmed decisions")
    print("DOCKER_GUI_PROOF alignment_positions=ok")

    session.result_path.unlink()
    keep_parent = QWidget()
    keep_panel = AlignmentReviewPanel(keep_parent, panel_api)
    keep_panel.on_workspace_loaded()
    app.processEvents()
    keep_panel.keep_button.click()
    app.processEvents()
    observed_result = read_alignment_review_result(session, expected)
    if [decision.action for decision in observed_result.decisions] != ["keep_current", "keep_current"]:
        raise SystemExit("keep-audio action did not write one decision per comparison")
    print("DOCKER_GUI_PROOF alignment_keep_current=ok")
finally:
    set_loop(previous_loop)

print("DOCKER_GUI_PROOF alignment_metadata=ok topology=one_reference_ordered_comparisons")
print("DOCKER_GUI_PROOF alignment_result_roundtrip=ok")
session.result_path.write_text("{}\n", encoding="utf-8")
try:
    read_alignment_review_result(session, expected)
except AlignmentReviewContractError:
    pass
else:
    raise SystemExit("malformed alignment result was accepted")
print("DOCKER_GUI_PROOF alignment_result_validation=ok malformed=rejected")
session.result_path.unlink(missing_ok=True)

Path(sys.argv[2]).write_text(str(script_path), encoding="utf-8")
print("DOCKER_GUI_PROOF session_script=ok")
PY

  printf 'DOCKER_GUI_PROOF session_script_path=%s\n' "$(cat "$script_path_file")"
  rm -rf -- "$proof_dir"
  test ! -e "$proof_dir"
  echo "DOCKER_GUI_PROOF temp_cleanup=ok"
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

"${compose_cmd[@]}" run --rm --entrypoint /bin/bash "$service" -c \
  'bash tools/verify_docker_gui.sh --inside-container'

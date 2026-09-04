from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail

from ._helpers import SCRIPT_SUBPROCESS_TIMEOUT_SECONDS
from ._helpers import bash_executable_or_skip as _bash_executable_or_skip
from ._helpers import with_bash_env as _with_bash_env
from ._helpers import write_bash_env as _write_bash_env


def _assert_adjacent_statements(source: str, first: str, second: str) -> None:
    assert re.search(rf"{re.escape(first)}\s+{re.escape(second)}", source) is not None


def test_dockerfile_gui_target_uses_lock_derived_vsview_install(repo_root: Path) -> None:
    dockerfile = _read_text_or_fail(repo_root / "Dockerfile")
    stage_names = re.findall(r"^FROM .* AS (\S+)$", dockerfile, re.MULTILINE)

    assert "FROM runtime AS gui-linux" in dockerfile
    assert stage_names[-1] == "default-runtime"
    assert (
        "uv export --frozen --no-dev --extra vsview --no-emit-project --format requirements.txt"
        in dockerfile
    )
    assert "--output-file /tmp/requirements.vsview.lock.txt" in dockerfile
    assert (
        "python -m pip install --no-cache-dir --user --require-hashes \\\n"
        "        -r /tmp/requirements.vsview.lock.txt"
    ) in dockerfile
    assert "pip install vsview" not in dockerfile
    assert "--extra recommended" not in dockerfile
    assert "--extra full" not in dockerfile


def test_gui_override_uses_optional_gui_linux_profile_and_minimal_x11_contract(
    repo_root: Path,
) -> None:
    base_compose = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.yml"))
    gui_override = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.gui-linux.yml"))

    base_services = base_compose["services"]
    override_services = gui_override["services"]

    assert set(override_services) == {"frame-compare", "frame-compare-test", "frame-compare-run"}

    for service_name, service in override_services.items():
        assert "profiles" not in base_services[service_name]
        assert service["profiles"] == ["gui-linux"]
        assert service["build"]["target"] == "gui-linux"
        assert service["image"] == "frame-compare:gui-linux"
        assert service["user"] == "${FRAME_COMPARE_HOST_UID:-1000}:${FRAME_COMPARE_HOST_GID:-1000}"

        environment = service["environment"]
        assert "DISPLAY=${DISPLAY:?Set DISPLAY for X11 forwarding}" in environment
        assert "XAUTHORITY=/tmp/framecompare.Xauthority" in environment
        assert "HOME=/tmp/framecompare-home" in environment
        assert "PYTHONUSERBASE=/home/framecompare/.local" in environment
        assert "XDG_RUNTIME_DIR=/tmp/framecompare-runtime" in environment

        volumes = service["volumes"]
        assert "/tmp/.X11-unix:/tmp/.X11-unix" in volumes
        assert (
            "${FRAME_COMPARE_XAUTHORITY_PATH:-/dev/null}:/tmp/framecompare.Xauthority:ro" in volumes
        )
        assert not any(volume == "/tmp:/tmp" for volume in volumes)
        assert not any("/:" in volume for volume in volumes)


def test_verify_docker_gui_script_documents_narrow_x11_permissions(repo_root: Path) -> None:
    script = _read_text_or_fail(repo_root / "tools" / "verify_docker_gui.sh")

    assert "docker-compose.gui-linux.yml" in script
    assert "python -m vsview --help" in script
    assert "from PySide6.QtWidgets import QApplication" in script
    assert 'hasattr(vs.core, "bs")' in script
    assert "frame-compare doctor --json" in script
    assert 'doctor_report.get("doctor", {}).get("checks", [])' in script
    assert 'entry.get("id") == "vsview"' in script
    assert 'entry.get("name") == "vsview"' not in script
    assert 'entry.get("available")' not in script
    assert "check_vsview_availability" in script
    assert "launch_alignment_verification_session" in script
    assert 'entry_point.name == "frame-compare-alignment-review"' in script
    assert 'entry_point.value == "frame_compare.vsview.alignment_review_panel"' in script
    assert "entry_points[0].load()" in script
    assert "AlignmentReviewPanel" in script
    assert "DOCKER_GUI_PROOF vsview_entry_point=ok" in script
    assert "DOCKER_GUI_PROOF panel_offscreen=ok" in script
    assert "DOCKER_GUI_PROOF alignment_positions=ok" in script
    assert "DOCKER_GUI_PROOF alignment_keep_current=ok" in script
    assert "DOCKER_GUI_PROOF alignment_metadata=ok" in script
    assert "DOCKER_GUI_PROOF alignment_result_roundtrip=ok" in script
    assert "DOCKER_GUI_PROOF alignment_result_validation=ok" in script
    assert "from vsview import set_output" in script
    assert "color=c=black:size=64x48:rate=1:duration=3" in script
    assert "color=c=white:size=64x48:rate=1:duration=3" in script
    assert "color=c=gray:size=64x48:rate=1:duration=3" in script
    assert 'types.ModuleType("__vsview__")' in script
    assert 'expected_names = {0: "Reference", 1: "Comparison 1", 2: "Comparison 2"}' in script
    assert "outputs[index].clip.get_frame(0)" in script
    assert "source_index_path(reference)" in script
    assert "source_index_path(comparison)" in script
    assert "source_index_path(comparison_2)" in script
    _assert_adjacent_statements(
        script,
        "active_panel.on_workspace_loaded()",
        "app.processEvents()",
    )
    _assert_adjacent_statements(
        script,
        "active_panel.on_current_voutput_changed(voutputs[output_index], output_index)",
        "app.processEvents()",
    )
    _assert_adjacent_statements(
        script,
        "active_panel.use_positions_button.click()",
        "app.processEvents()",
    )
    _assert_adjacent_statements(
        script,
        "keep_panel.keep_button.click()",
        "app.processEvents()",
    )
    assert '"3 / 3 sources ready"' in script
    assert '"Use these aligned positions"' in script
    assert '"Keep audio-derived alignment"' in script
    assert "pair.reference.source_frame_count" not in script
    assert "pair.comparison.source_frame_count" not in script
    assert 'rm -rf -- "$proof_dir"' in script
    assert "DOCKER_GUI_PROOF temp_cleanup=ok" in script
    assert "xhost +si:localuser:" in script
    assert "xhost -si:localuser:" in script
    assert "xhost +" not in script.replace("xhost +si:localuser:", "")
    assert "Manual GUI launch example:" in script
    assert "frame-compare-run" in script
    assert "--inside-container" in script
    assert '"$service" -c \\' in script
    assert '"$service" -lc \\' not in script


def test_verify_docker_gui_inside_container_proves_production_tooling_absence(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    bash_env = tmp_path / "gui-production-proof.env"
    _write_bash_env(
        bash_env,
        r"""
python() {
  if [[ "${1:-}" == "-c" ]]; then
    return 1
  fi
  if [[ "${1:-}" == "-" && "$#" -eq 2 ]]; then
    printf '/tmp/framecompare-fake-session.py\n' > "$2"
  fi
  return 0
}

frame-compare() {
  if [[ "${1:-}" == "doctor" ]]; then
  printf '{"doctor":{"checks":[{"id":"vsview","status":"pass","message":"VSView and the Frame Compare alignment panel are available"}]}}\n'
  fi
}

ffmpeg() {
  return 0
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gui.sh", "--inside-container"],
        cwd=repo_root,
        env=_with_bash_env(
            {
                "PATH": "/usr/bin:/bin",
                "HOME": str(tmp_path),
                "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
            },
            bash_env,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0
    assert "DOCKER_GUI_PROOF production_tooling_absent=ok" in combined
    assert "DOCKER_GUI_PROOF real_media=ok" in combined
    assert "DOCKER_GUI_PROOF temp_cleanup=ok" in combined


def test_verify_docker_gui_inside_container_rejects_uv_tooling(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_uv.chmod(0o755)

    bash_env = tmp_path / "gui-production-tooling.env"
    _write_bash_env(
        bash_env,
        """
python() {
  return 1
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gui.sh", "--inside-container"],
        cwd=repo_root,
        env=_with_bash_env(
            {
                "PATH": f"{fake_bin}:/usr/bin:/bin",
                "HOME": str(tmp_path),
                "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
            },
            bash_env,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 6
    assert "uv build tooling leaked into the GUI production image" in combined


def test_verify_docker_gui_script_requires_linux_x11_host(repo_root: Path, tmp_path: Path) -> None:
    bash = _bash_executable_or_skip()
    bash_env = tmp_path / "gui-host-os.env"
    _write_bash_env(
        bash_env,
        """
uname() {
  printf 'Darwin\\n'
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gui.sh", "--no-build"],
        cwd=repo_root,
        env=_with_bash_env({"DISPLAY": ""}, bash_env),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 21
    assert "Linux/X11-only" in combined
    assert "documented-only/unverified" in combined

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


def test_dockerfile_gui_target_uses_lock_derived_vspreview_install(repo_root: Path) -> None:
    dockerfile = _read_text_or_fail(repo_root / "Dockerfile")
    stage_names = re.findall(r"^FROM .* AS (\S+)$", dockerfile, re.MULTILINE)

    assert "FROM runtime AS gui-linux" in dockerfile
    assert stage_names[-1] == "default-runtime"
    assert (
        "uv export --frozen --no-dev --extra vspreview --no-emit-project --format requirements.txt"
        in dockerfile
    )
    assert "--output-file /tmp/requirements.vspreview.lock.txt" in dockerfile
    assert (
        "python -m pip install --no-cache-dir --user --require-hashes \\\n"
        "        -r /tmp/requirements.vspreview.lock.txt"
    ) in dockerfile
    assert "pip install vspreview" not in dockerfile
    assert "pip install PyQt6" not in dockerfile


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
    assert "python -m vspreview --help" in script
    assert "frame-compare doctor --json" in script
    assert 'doctor_report.get("doctor", {}).get("checks", [])' in script
    assert 'entry.get("id") == "vspreview"' in script
    assert 'entry.get("name") == "vspreview"' not in script
    assert 'entry.get("available")' not in script
    assert "check_vspreview_availability" in script
    assert "launch_alignment_verification_session" in script
    assert "xhost +si:localuser:" in script
    assert "xhost -si:localuser:" in script
    assert "xhost +" not in script.replace("xhost +si:localuser:", "")
    assert "Manual GUI launch example:" in script
    assert "frame-compare-run" in script
    assert "--inside-container" in script


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

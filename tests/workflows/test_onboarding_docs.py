from __future__ import annotations

from pathlib import Path

import yaml

from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail


def test_default_compose_separates_wizard_config_writes_from_normal_runs(
    repo_root: Path,
) -> None:
    compose = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.yml"))
    services = compose["services"]

    wizard = services["frame-compare-wizard"]
    assert wizard["profiles"] == ["setup"]
    assert wizard["command"] == ["wizard", "--root", "/workspace"]
    assert wizard["user"] == ("${FRAME_COMPARE_HOST_UID:-1000}:${FRAME_COMPARE_HOST_GID:-1000}")
    assert "HOME=/tmp/framecompare-home" in wizard["environment"]
    assert "PYTHONUSERBASE=/home/framecompare/.local" in wizard["environment"]
    assert "./comparison_videos:/workspace/comparison_videos:ro" in wizard["volumes"]
    assert "./config:/workspace/config" in wizard["volumes"]
    assert "./generated:/workspace/generated" in wizard["volumes"]
    assert "./config:/workspace/config:ro" not in wizard["volumes"]
    assert not any("/workspace/screenshots" in volume for volume in wizard["volumes"])
    assert wizard["stdin_open"] is True
    assert wizard["tty"] is True

    runtime = services["frame-compare-run"]
    assert runtime["user"] == ("${FRAME_COMPARE_HOST_UID:-1000}:${FRAME_COMPARE_HOST_GID:-1000}")
    assert "HOME=/tmp/framecompare-home" in runtime["environment"]
    assert "PYTHONUSERBASE=/home/framecompare/.local" in runtime["environment"]
    assert "./comparison_videos:/workspace/comparison_videos:ro" in runtime["volumes"]
    assert "./config:/workspace/config:ro" in runtime["volumes"]
    assert "./generated:/workspace/generated" in runtime["volumes"]
    assert not any("/workspace/screenshots" in volume for volume in runtime["volumes"])


def test_default_compose_uses_one_generated_output_mount(repo_root: Path) -> None:
    compose = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.yml"))
    services = compose["services"]

    for service_name in ("frame-compare", "frame-compare-test", "frame-compare-run"):
        volumes = services[service_name]["volumes"]
        assert "./generated:/workspace/generated" in volumes
        assert not any("/workspace/screenshots" in volume for volume in volumes)


def test_default_compose_keeps_test_runtime_image_separate(repo_root: Path) -> None:
    compose = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.yml"))

    assert compose["services"]["frame-compare-test"]["image"] == "frame-compare:test"


def test_docker_workflow_invokes_canonical_runtime_gate(repo_root: Path) -> None:
    workflow = yaml.safe_load(
        _read_text_or_fail(repo_root / ".github" / "workflows" / "docker-integration.yml")
    )

    steps = workflow["jobs"]["docker-integration"]["steps"]
    assert any(step.get("run") == "bash tools/verify_docker_integration.sh" for step in steps)

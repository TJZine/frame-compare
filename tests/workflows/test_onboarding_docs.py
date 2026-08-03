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


def test_docker_gate_proves_generated_artifacts_survive_container_removal(repo_root: Path) -> None:
    script = _read_text_or_fail(repo_root / "tools" / "verify_docker_integration.sh")

    assert "docker compose run --rm --entrypoint /bin/bash frame-compare-run" in script
    assert 'chmod 0777 "$proof_dir"' in script
    assert "frame-compare run" in script
    assert "ffmpeg -hide_banner -loglevel error" in script
    assert 'generated_dir = "$generated_root"' in script
    assert '--input "$media_dir"' in script
    assert "tomllib.load(handle)" in script
    assert "report_path" in script
    assert "screenshot_dir" in script
    assert 'payload[:8] != b"\\x89PNG' in script
    assert "outside /workspace/generated" in script
    assert "DOCKER_PROOF generated_mount=ok" in script
    assert "generated-data bind-mount artifact missing after container removal" in script
    assert ".docker-proof-supplemental-alignment" in script
    assert "supplemental docker proof alignment cache" in script
    assert "printf 'docker durable" not in script
    assert "sentinel.compframes" not in script

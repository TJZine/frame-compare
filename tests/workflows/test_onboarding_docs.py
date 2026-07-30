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
    assert "./config:/workspace/config:ro" not in wizard["volumes"]
    assert wizard["stdin_open"] is True
    assert wizard["tty"] is True

    runtime = services["frame-compare-run"]
    assert runtime["user"] == ("${FRAME_COMPARE_HOST_UID:-1000}:${FRAME_COMPARE_HOST_GID:-1000}")
    assert "HOME=/tmp/framecompare-home" in runtime["environment"]
    assert "PYTHONUSERBASE=/home/framecompare/.local" in runtime["environment"]
    assert "./comparison_videos:/workspace/comparison_videos:ro" in runtime["volumes"]
    assert "./config:/workspace/config:ro" in runtime["volumes"]
    assert "./screenshots:/workspace/screenshots" in runtime["volumes"]
    assert "./generated:/workspace/generated" in runtime["volumes"]

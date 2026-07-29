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


def test_readme_docker_quick_start_uses_one_persistent_compose_workspace(
    repo_root: Path,
) -> None:
    readme = _read_text_or_fail(repo_root / "README.md")

    expected_steps = (
        'export FRAME_COMPARE_HOST_UID="$(id -u)"',
        'export FRAME_COMPARE_HOST_GID="$(id -g)"',
        "mkdir -p config comparison_videos screenshots generated",
        "docker compose build frame-compare-run",
        "docker compose run --rm frame-compare-wizard",
        "docker compose run --rm frame-compare-run doctor",
        "docker compose run --rm frame-compare-run run --root /workspace --dry-run",
        "docker compose run --rm frame-compare-run run --root /workspace",
    )
    positions = [readme.index(step) for step in expected_steps]
    assert positions == sorted(positions)
    assert 'python tools/open_docker_host_target.py "<report_path_from_run_output>"' in readme
    assert "docker run --rm -it" not in readme
    assert "$PWD/output" not in readme


def test_docker_docs_describe_default_run_folder_output(repo_root: Path) -> None:
    docker_docs = _read_text_or_fail(repo_root / "docs/docker-environments.md")

    assert "`paths.use_run_folders = true`" in docker_docs
    assert "`/workspace/generated/<run>/`" in docker_docs
    assert (
        "`report.output_dir = null` places the report beneath `/workspace/screenshots`"
    ) in docker_docs


def test_readme_native_uv_quick_start_bootstraps_config_and_uses_managed_entrypoint(
    repo_root: Path,
) -> None:
    readme = _read_text_or_fail(repo_root / "README.md")

    expected_steps = (
        "uv sync --no-dev --extra vspreview --frozen",
        "uv run --no-sync frame-compare wizard",
        "uv run --no-sync frame-compare doctor",
        "uv run --no-sync frame-compare run --root . --dry-run",
        "uv run --no-sync frame-compare run --root .",
    )
    positions = [readme.index(step) for step in expected_steps]
    assert positions == sorted(positions)
    assert "VapourSynth is not optional\nfor the default renderer" in readme
    assert "Reproducible Docker Runtime" in readme
    assert "Zero-Config Docker" not in readme


def test_contributor_setup_uses_the_canonical_locked_environment(repo_root: Path) -> None:
    contributing = _read_text_or_fail(repo_root / "CONTRIBUTING.md")

    assert "uv sync --group dev --frozen" in contributing
    assert "pip-only editable install" in contributing
    assert "pip install pytest pytest-cov ruff pyright" not in contributing

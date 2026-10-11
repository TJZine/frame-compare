"""E2: typed CLI errors through the real console entry point."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from typing import Any

import pytest

from tests.e2e.harness import CommandResult, Workspace

ERROR_CASES = (
    pytest.param(
        "missing-input",
        {
            "config": None,
            "arguments": ["run", "--json", "--dry-run", "--skip-metadata", "--no-upload"],
        },
        4,
        "FC-3006",
        "DIRECTORY_NOT_FOUND",
        id="missing-input-directory",
    ),
    pytest.param(
        "invalid-config",
        {
            "config": {"analysis": {"random_frame_count": -1}},
            "arguments": ["run", "--json", "--dry-run", "--skip-metadata", "--no-upload"],
        },
        2,
        "FC-1003",
        "CONFIG_VALIDATION_ERROR",
        id="invalid-config-value",
    ),
    pytest.param(
        "mutual-cache-flags",
        {
            "config": None,
            "arguments": [
                "run",
                "--json",
                "--no-cache",
                "--from-cache-only",
                "--skip-metadata",
                "--no-upload",
            ],
        },
        2,
        "FC-1003",
        "CONFIG_VALIDATION_ERROR",
        id="mutually-exclusive-cache-flags",
    ),
    pytest.param(
        "dry-run-write-config",
        {
            "config": None,
            "arguments": [
                "run",
                "--json",
                "--dry-run",
                "--write-config",
                "--skip-metadata",
                "--no-upload",
            ],
        },
        2,
        "FC-1003",
        "CONFIG_VALIDATION_ERROR",
        id="dry-run-with-write-config",
    ),
    pytest.param(
        "missing-reference",
        {
            "config": {"sources": {"reference": "missing.mkv"}},
            "arguments": ["run", "--json", "--dry-run", "--skip-metadata", "--no-upload"],
        },
        4,
        "FC-3012",
        "SOURCE_SELECTION_ERROR",
        id="reference-selector-matches-no-file",
    ),
    pytest.param(
        "path-escape",
        {
            "config": {"paths": {"config_dir": "../outside"}},
            "arguments": ["run", "--json", "--dry-run", "--skip-metadata", "--no-upload"],
        },
        4,
        "FC-3009",
        "PATH_ESCAPES_ROOT",
        id="path-escapes-root",
    ),
)


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("scenario_id", "case", "expected_exit_code", "expected_code", "expected_name"),
    ERROR_CASES,
)
def test_cli_errors_are_typed_and_json_only(
    scenario_id: str,
    case: dict[str, Any],
    expected_exit_code: int,
    expected_code: str,
    expected_name: str,
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace(case["config"])
    if scenario_id == "missing-input":
        shutil.rmtree(root.input_dir)
    else:
        (root.input_dir / "reference.mkv").touch()
        (root.input_dir / "comparison.mkv").touch()
    arguments = [*case["arguments"], "--root", str(root.root)]
    result = run_cli(root.root, arguments)
    payload = json.loads(result.stdout)
    error = payload["error"]

    # Output modes contract, including JSON stream placement.
    summary = {
        "exit_code": result.exit_code,
        "success": payload["success"],
        "error_code": error["code"],
        "error_name": error["name"],
        "stream": "stdout" if result.stdout else "stderr",
        "other_stream_empty": not bool(result.stderr if result.stdout else result.stdout),
    }
    expected = {
        "exit_code": expected_exit_code,
        "success": False,
        "error_code": expected_code,
        "error_name": expected_name,
        "stream": "stdout",
        "other_stream_empty": True,
    }
    record(f"E2-{scenario_id}", root, [(arguments, result)], summary, expected)


@pytest.mark.e2e
@pytest.mark.parametrize("field_name", ["input_dir", "generated_dir", "config_dir"])
def test_cli_rejects_nul_paths_as_typed_config_errors(
    field_name: str,
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
) -> None:
    root = workspace()
    root.config_path.write_text(
        f'[paths]\n{field_name} = "\\u0000"\n',
        encoding="utf-8",
    )
    before = root.config_path.read_bytes()
    result = run_cli(
        root.root,
        [
            "run",
            "--json",
            "--dry-run",
            "--skip-metadata",
            "--no-upload",
            "--root",
            str(root.root),
        ],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["name"] == "CONFIG_VALIDATION_ERROR"
    assert result.stderr == ""
    assert root.config_path.read_bytes() == before


@pytest.mark.e2e
@pytest.mark.parametrize("json_output", [True, False], ids=["json", "human"])
def test_cli_rejects_invalid_utf8_config_without_traceback(
    json_output: bool,
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
) -> None:
    root = workspace()
    root.config_path.write_bytes(b"[analysis]\nrandom_frame_count = 10\n\xff")
    before = root.config_path.read_bytes()
    output_options = ["--json"] if json_output else []
    result = run_cli(
        root.root,
        [
            "run",
            *output_options,
            "--dry-run",
            "--skip-metadata",
            "--no-upload",
            "--root",
            str(root.root),
        ],
    )

    assert result.exit_code == 2
    assert root.config_path.read_bytes() == before
    assert "Traceback" not in result.stderr
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["error"]["code"] == "FC-1002"
        assert payload["error"]["name"] == "CONFIG_PARSE_ERROR"
        assert result.stderr == ""
    else:
        assert result.stdout == ""
        assert "[FC-1002]" in result.stderr
        assert "CONFIG_PARSE_ERROR" not in result.stderr


@pytest.mark.e2e
@pytest.mark.parametrize("field_name", ["ignore_lead_seconds", "ignore_trail_seconds"])
def test_cli_rejects_nonfinite_exclusions_as_typed_config_errors(
    field_name: str,
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
) -> None:
    root = workspace()
    root.config_path.write_text(
        f"[analysis]\n{field_name} = inf\n",
        encoding="utf-8",
    )
    before = root.config_path.read_bytes()
    result = run_cli(
        root.root,
        [
            "run",
            "--json",
            "--dry-run",
            "--skip-metadata",
            "--no-upload",
            "--root",
            str(root.root),
        ],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["name"] == "CONFIG_VALIDATION_ERROR"
    assert result.stderr == ""
    assert root.config_path.read_bytes() == before

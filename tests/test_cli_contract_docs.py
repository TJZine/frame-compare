from __future__ import annotations

import re
from pathlib import Path

from frame_compare.config.overrides import CLI_OVERRIDE_MAP


def test_current_cli_contract_is_wired_into_repo_authority_surfaces() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = repo_root / "docs" / "current-cli-contract.md"

    assert cli_contract.exists()

    runbook = (repo_root / "docs" / "ENGINEERING_RUNBOOK.md").read_text(encoding="utf-8")
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    coordinator = (repo_root / "src" / "frame_compare" / "orchestration" / "types.py").read_text(
        encoding="utf-8"
    )

    assert "docs/current-cli-contract.md" in runbook
    assert "docs/current-cli-contract.md" in agents
    assert "docs/current-cli-contract.md" in coordinator
    assert "cli-module.md" not in coordinator

    runbook_pos = agents.index("[docs/ENGINEERING_RUNBOOK.md]")
    architecture_pos = agents.index("[docs/current-architecture.md]")
    cli_contract_pos = agents.index("[docs/current-cli-contract.md]")
    importlinter_pos = agents.index("[importlinter.ini]")
    pyproject_pos = agents.index("[pyproject.toml]")
    assert runbook_pos < architecture_pos < cli_contract_pos < importlinter_pos < pyproject_pos


def test_current_cli_contract_keeps_command_families_and_live_override_map() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    for family in ("version", "run", "wizard", "doctor", "preset"):
        assert f"## `{family}` Command Contract" in cli_contract

    mapping_section = cli_contract.split("## CLI Flag To Config Mapping", maxsplit=1)[1].split(
        "## Config-Only Analysis Surface",
        maxsplit=1,
    )[0]
    row_pattern = re.compile(r"^\| `(?P<flag>--[^`]+)` \| `(?P<config_path>[^`]+)` \|")
    row_lines = [line for line in mapping_section.splitlines() if line.startswith("| `--")]
    documented_pairs: list[tuple[str, str]] = []
    for row in row_lines:
        match = row_pattern.match(row)
        assert match is not None, f"Malformed CLI mapping row: {row}"
        documented_pairs.append((match.group("flag"), match.group("config_path")))

    expected_pairs = {
        (f"--{cli_name.replace('_', '-')}", config_path)
        for cli_name, config_path in CLI_OVERRIDE_MAP.items()
    }
    assert len(documented_pairs) == len(CLI_OVERRIDE_MAP)
    assert set(documented_pairs) == expected_pairs


def test_current_cli_contract_names_primary_executable_contract_checks() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    authority_heading = "## Authority And Update Rules"
    command_surface_heading = "## Command Surface"
    assert authority_heading in cli_contract, f"Missing heading: {authority_heading}"
    assert command_surface_heading in cli_contract, f"Missing heading: {command_surface_heading}"

    authority_section = cli_contract.split(authority_heading, maxsplit=1)[1].split(
        command_surface_heading,
        maxsplit=1,
    )[0]

    expected_checks = (
        "`tests/cli/test_help_and_import.py` for command registration, help text, and",
        "`tests/cli/test_run_command.py`, `tests/cli/test_run_json_errors.py`, and",
        "`tests/cli/test_run_report_open.py` for command behavior, JSON errors, and",
        "`tests/config/test_overrides.py` for CLI override mapping semantics.",
        "`tests/e2e/test_cli_version.py` for the public `version` command contract.",
        "`tests/cli/test_exit_codes.py` for exit-code behavior.",
        "`tests/test_cli_contract_docs.py` for keeping this document aligned with the live",
    )

    for expected in expected_checks:
        assert expected in authority_section


def test_current_cli_contract_describes_generated_data_cutover() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    assert "`paths.generated_dir`" in cli_contract
    assert "`report.output_dir`" in cli_contract
    assert "`paths.screenshots_dir`" in cli_contract
    assert "`paths.use_run_folders`" in cli_contract
    assert "canonical run-root `report.html`" in cli_contract
    assert "`output` value is the resolved generated-data root" in cli_contract
    assert "The constant run-folder policy" in cli_contract
    assert "`FC-3018`" in cli_contract


def test_current_authorities_describe_run_relative_records_and_clean_history_cutover() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    assert "run-folder-relative output" in architecture
    assert "workspace-relative output" not in architecture
    assert "Folders without a supported `run_result.toml` are omitted" in cli_contract
    assert "`FC-3016`" in cli_contract
    assert "does not create the root" in cli_contract

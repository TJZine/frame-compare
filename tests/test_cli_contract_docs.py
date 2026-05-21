from __future__ import annotations

from pathlib import Path

from frame_compare.config.overrides import CLI_OVERRIDE_MAP


def test_current_cli_contract_is_wired_into_repo_authority_surfaces() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = repo_root / "docs" / "current-cli-contract.md"

    assert cli_contract.exists()

    runbook = (repo_root / "docs" / "ENGINEERING_RUNBOOK.md").read_text(encoding="utf-8")
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    coordinator = (
        repo_root / "src" / "frame_compare" / "orchestration" / "coordinator.py"
    ).read_text(encoding="utf-8")

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


def test_current_cli_contract_covers_all_public_command_families() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    assert "## `version` Command Contract" in cli_contract
    assert "## `run` Command Contract" in cli_contract
    assert "## `wizard` Command Contract" in cli_contract
    assert "## `doctor` Command Contract" in cli_contract
    assert "## `preset` Command Contract" in cli_contract


def test_current_cli_contract_matches_live_override_map() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        flag = f"--{cli_name.replace('_', '-')}"
        assert flag in cli_contract
        assert config_path in cli_contract


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
        "`tests/cli/test_cli_commands.py` for help text, JSON payloads, report auto-open",
        "`tests/config/test_overrides.py` for CLI override mapping semantics.",
        "`tests/e2e/test_cli_version.py` for the public `version` command contract.",
        "`tests/cli/test_exit_codes.py` for exit-code behavior.",
        "`tests/test_cli_contract_docs.py` for keeping this document aligned with the live",
    )

    for expected in expected_checks:
        assert expected in authority_section

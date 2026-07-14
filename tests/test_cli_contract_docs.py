from __future__ import annotations

from pathlib import Path


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


def test_current_cli_contract_covers_all_public_command_families() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    assert "## `version` Command Contract" in cli_contract
    assert "## `run` Command Contract" in cli_contract
    assert "## `wizard` Command Contract" in cli_contract
    assert "## `doctor` Command Contract" in cli_contract
    assert "## `preset` Command Contract" in cli_contract


def test_current_cli_contract_documents_secondary_command_streams() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    wizard_section = cli_contract.split("## `wizard` Command Contract", maxsplit=1)[1].split(
        "## `doctor` Command Contract",
        maxsplit=1,
    )[0]
    doctor_section = cli_contract.split("## `doctor` Command Contract", maxsplit=1)[1].split(
        "## `preset` Command Contract",
        maxsplit=1,
    )[0]
    preset_section = cli_contract.split("## `preset` Command Contract", maxsplit=1)[1]
    normalized_wizard = " ".join(wizard_section.split())
    normalized_doctor = " ".join(doctor_section.split())
    normalized_preset = " ".join(preset_section.split())

    assert "confirmation to stderr including the resolved config path" in normalized_wizard
    assert "honor the `NO_COLOR` environment variable" in normalized_wizard
    assert "do not suggest unsupported `--verbose` usage" in normalized_wizard
    assert "neutral status marker for optional unavailable checks" in normalized_doctor
    assert "This does not change `doctor --json` status values." in normalized_doctor
    assert "honor the `NO_COLOR` environment variable" in normalized_doctor
    assert "do not suggest unsupported `--verbose` usage" in normalized_doctor
    assert "Prints preset names one per line to stdout." in normalized_preset
    assert "Emits no success confirmation." in normalized_preset
    assert "confirmation to stderr including the preset name and resolved config path" in (
        normalized_preset
    )
    assert "confirmation to stderr including the preset name and saved preset path" in (
        normalized_preset
    )
    assert "honor the `NO_COLOR` environment variable" in normalized_preset
    assert "do not suggest unsupported `--verbose` usage" in normalized_preset


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


def test_current_cli_contract_matches_goal_oriented_wizard_scope() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    wizard_heading = "## `wizard` Command Contract"
    doctor_heading = "## `doctor` Command Contract"
    assert wizard_heading in cli_contract, f"Missing heading: {wizard_heading}"
    assert doctor_heading in cli_contract, f"Missing heading: {doctor_heading}"

    wizard_section = cli_contract.split(wizard_heading, maxsplit=1)[1].split(
        doctor_heading,
        maxsplit=1,
    )[0]

    for expected in (
        "Random spot check",
        "Dark, bright, and motion coverage",
        "Specific frame numbers",
        "Keep current frame selection",
        "Publishing visibility/deletion and TMDB-key setup",
    ):
        assert expected in wizard_section
    for removed_prompt in (
        "slow.pics visibility (`public` or `unlisted`)",
        "slow.pics delete-after-upload",
        "optional TMDB API key",
    ):
        assert removed_prompt not in wizard_section


def test_current_contract_docs_define_hybrid_workspace_path_policy() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    security = (repo_root / "SECURITY.md").read_text(encoding="utf-8")
    normalized_cli_contract = " ".join(cli_contract.split())

    for phrase in (
        "Media input is a read boundary, not a write boundary",
        "`PathEscapesRootError` / `FC-3009`",
        "beneath the contained resolved `paths.generated_dir`, never beneath `paths.input_dir`",
        "sole selected-config containment exception",
        "`run`, `wizard`, `preset apply`, `preset save`, and both `history` subcommands",
    ):
        assert phrase in normalized_cli_contract

    assert "permitting external media reads" in architecture
    assert "never beneath an external media input" in architecture
    assert "Media inputs may be read from outside the workspace" in security
    assert "%LOCALAPPDATA%/Programs/FrameCompare/state/config.toml" in security

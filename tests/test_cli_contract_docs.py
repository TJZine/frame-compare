from __future__ import annotations

from pathlib import Path

from frame_compare.config.overrides import CLI_OVERRIDE_MAP
from frame_compare.config.schema import Visibility


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


def test_current_cli_contract_matches_live_override_map() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        flag = f"--{cli_name.replace('_', '-')}"
        assert flag in cli_contract
        assert config_path in cli_contract


def test_current_cli_contract_documents_screenshot_config_only_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    screenshot_heading = "## Config-Only Screenshot Surface"
    persistence_heading = "## Persistence Rules"
    assert screenshot_heading in cli_contract, f"Missing heading: {screenshot_heading}"
    assert persistence_heading in cli_contract, f"Missing heading: {persistence_heading}"

    screenshot_section = cli_contract.split(screenshot_heading, maxsplit=1)[1].split(
        persistence_heading,
        maxsplit=1,
    )[0]

    for expected in (
        '`geometry_mode = "native" | "aligned"`',
        '`vs_writer = "auto" | "pillow" | "fpng"`',
        "`png_compression` remains an integer from `0` through `9`",
        "config-only public surfaces",
        "dedicated `run` flags",
        "preserves current behavior until a writer-specific",
        "explicit `fpng` requires successful VapourSynth loading and does not silently fall",
        "Fpng maps `0..3` to `0`, `4..6` to `1`, and `7..9` to `2`",
        "unsupported values fail config validation rather than being silently clamped",
    ):
        assert expected in screenshot_section

    command_heading = "## Command Surface"
    screenshot_heading = "## Config-Only Screenshot Surface"
    command_override_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        screenshot_heading,
        maxsplit=1,
    )[0]

    for unsupported_flag in ("--geometry-mode", "--vs-writer", "--png-compression"):
        assert unsupported_flag not in command_override_surface


def test_current_cli_contract_documents_audio_alignment_config_only_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    audio_heading = "## Config-Only Audio Alignment Surface"
    persistence_heading = "## Persistence Rules"
    assert audio_heading in cli_contract, f"Missing heading: {audio_heading}"

    audio_section = cli_contract.split(audio_heading, maxsplit=1)[1].split(
        persistence_heading,
        maxsplit=1,
    )[0]

    for expected in (
        '`correlation_mode = "raw_fft" | "gcc_phat"`',
        '`preprocessing_mode = "none" | "standard"`',
        '`channel_strategy = "mono_downmix" | "best_channel"`',
        "`confidence_threshold` remains a float from `0.0` through `1.0`",
        "`ambiguity_peak_ratio` remains a float greater than or equal to `1.0`",
        "`window_length_seconds` and `window_stride_seconds` remain floats",
        "`minimum_valid_windows` remains an integer greater than or equal to `1`",
        "`consensus_minimum_ratio` remains a float from `0.0` through `1.0`",
        '`refinement_mode = "disabled" | "local"`',
        "`refinement_sample_rate` is either `null` or an integer from `4000` through",
        "`reference_stream` is either `null` or a non-negative audio stream ordinal",
        "`comparison_streams` is a mapping from comparison filename stem",
        "config-only public surfaces",
    ):
        assert expected in audio_section

    normalized_audio_section = " ".join(audio_section.split())
    for expected in (
        "correlation algorithm",
        "preprocessing",
        "audio channel handling",
        "It gates whether computed offsets are applied",
        "It gates ambiguous correlation peaks",
        "consensus window",
        "It gates whether enough windows produced valid estimates",
        "It gates whether enough windows agree",
        "consensus",
        "refinement",
        "selects the reference clip audio stream",
        "select the comparison clip audio stream",
    ):
        assert expected in normalized_audio_section

    audio_section_lower = normalized_audio_section.lower()
    for stale_phrase in (
        "future correlation",
        "future preprocessing",
        "future channel",
        "future refinement",
        "future-only",
        "inert",
        "accepts and forwards",
    ):
        assert stale_phrase not in audio_section_lower

    command_heading = "## Command Surface"
    screenshot_heading = "## Config-Only Screenshot Surface"
    command_override_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        screenshot_heading,
        maxsplit=1,
    )[0]

    for unsupported_flag in (
        "--correlation-mode",
        "--preprocessing-mode",
        "--channel-strategy",
        "--confidence-threshold",
        "--ambiguity-peak-ratio",
        "--window-length-seconds",
        "--window-stride-seconds",
        "--minimum-valid-windows",
        "--consensus-minimum-ratio",
        "--refinement-mode",
        "--refinement-sample-rate",
        "--reference-stream",
        "--comparison-streams",
    ):
        assert unsupported_flag not in command_override_surface


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


def test_current_cli_contract_matches_wizard_visibility_choices() -> None:
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

    for visibility in Visibility:
        assert visibility.value in wizard_section
    for unsupported_token in (
        "--visibility private",
        "--visibility=private",
        "visibility: private",
    ):
        assert unsupported_token not in wizard_section

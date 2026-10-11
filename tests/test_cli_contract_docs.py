from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from frame_compare.config.overrides import CLI_OVERRIDE_MAP
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig


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
    assert "resolved generated-data root may be outside the workspace" in cli_contract


def test_current_authorities_describe_run_relative_records_and_clean_history_cutover() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    assert "run-folder-relative output" in architecture
    assert "workspace-relative output" not in architecture
    assert "Folders without a supported `run_result.toml` are omitted" in cli_contract
    assert "`FC-3016`" in cli_contract
    assert "does not create the root" in cli_contract


def test_configuration_reference_lists_every_config_key() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    reference = (repo_root / "docs" / "reference" / "configuration.md").read_text(encoding="utf-8")
    documented = set(
        re.findall(r"^\| `([a-z_]+(?:\.[a-z_<>]+)+)` \|", reference, flags=re.MULTILINE)
    )

    expected: set[str] = set()
    for section, field in ConfigSchema.model_fields.items():
        model = field.annotation
        assert isinstance(model, type) and issubclass(model, BaseModel)
        expected.update(f"{section}.{key}" for key in model.model_fields)
    expected.update(
        f"sources.overrides.<selector>.{key}" for key in SourceOverrideConfig.model_fields
    )

    assert documented == expected

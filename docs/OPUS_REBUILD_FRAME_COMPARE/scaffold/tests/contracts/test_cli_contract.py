"""Contract tests for CLI flags.

Verifies that CLI_FLAGS dict in _generated.py matches contracts/cli_flags.yaml.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to contracts (relative to test file location)
# scaffold/tests/contracts/ -> scaffold/../contracts/ -> docs/OPUS_REBUILD_FRAME_COMPARE/contracts/
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent / "contracts"


def load_yaml_safe(path: Path) -> dict:
    """Load YAML file using PyYAML."""
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.tier_a
class TestCLIFlagsContract:
    """Tests that CLI_FLAGS matches canonical cli_flags.yaml."""

    def test_cli_flags_count_matches(self) -> None:
        """Number of flags in _generated.py matches yaml."""
        from frame_compare.cli._generated import CLI_FLAGS

        data = load_yaml_safe(CONTRACTS_DIR / "cli_flags.yaml")

        assert len(CLI_FLAGS) == len(data["flags"]), (
            f"CLI_FLAGS has {len(CLI_FLAGS)} flags, "
            f"yaml has {len(data['flags'])} flags"
        )

    def test_all_yaml_flags_present(self) -> None:
        """All flags from yaml are present in CLI_FLAGS."""
        from frame_compare.cli._generated import CLI_FLAGS

        data = load_yaml_safe(CONTRACTS_DIR / "cli_flags.yaml")

        for flag in data["flags"]:
            flag_id = flag["id"]
            assert flag_id in CLI_FLAGS, f"Missing flag: {flag_id}"

    def test_flag_long_form_matches(self) -> None:
        """Long form of each flag matches yaml."""
        from frame_compare.cli._generated import CLI_FLAGS

        data = load_yaml_safe(CONTRACTS_DIR / "cli_flags.yaml")

        for flag in data["flags"]:
            flag_id = flag["id"]
            expected_long = flag["long"]
            actual_long = CLI_FLAGS[flag_id]["long"]

            assert actual_long == expected_long, (
                f"{flag_id}: expected long={expected_long!r}, got {actual_long!r}"
            )

    def test_flag_type_matches(self) -> None:
        """Type of each flag matches yaml."""
        from frame_compare.cli._generated import CLI_FLAGS

        data = load_yaml_safe(CONTRACTS_DIR / "cli_flags.yaml")

        for flag in data["flags"]:
            flag_id = flag["id"]
            expected_type = flag["type"]
            actual_type = CLI_FLAGS[flag_id]["type"]

            assert actual_type == expected_type, (
                f"{flag_id}: expected type={expected_type!r}, got {actual_type!r}"
            )

    def test_flag_has_help_text(self) -> None:
        """All flags must have help text."""
        from frame_compare.cli._generated import CLI_FLAGS

        for flag_id, flag_data in CLI_FLAGS.items():
            assert flag_data.get("help"), f"{flag_id} missing help text"

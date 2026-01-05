"""Contract tests for error codes.

Verifies that ERROR_REGISTRY in errors.py matches contracts/error_codes.yaml.
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
class TestErrorCodesContract:
    """Tests that ERROR_REGISTRY matches canonical error_codes.yaml."""

    def test_registered_errors_in_yaml(self) -> None:
        """All registered errors must be defined in yaml."""
        from frame_compare.errors import ERROR_REGISTRY

        data = load_yaml_safe(CONTRACTS_DIR / "error_codes.yaml")
        yaml_codes = set(data["errors"].keys())

        for code in ERROR_REGISTRY:
            assert code in yaml_codes, f"Registered error {code} not in yaml"

    def test_registered_error_names_match(self) -> None:
        """Error NAME classvars match yaml."""
        from frame_compare.errors import ERROR_REGISTRY

        data = load_yaml_safe(CONTRACTS_DIR / "error_codes.yaml")

        for code, error_cls in ERROR_REGISTRY.items():
            if code not in data["errors"]:
                continue  # Covered by test_registered_errors_in_yaml

            expected_name = data["errors"][code]["name"]
            actual_name = error_cls.NAME

            assert (
                actual_name == expected_name
            ), f"{code}: expected NAME={expected_name!r}, got {actual_name!r}"

    def test_registered_error_exit_codes_match(self) -> None:
        """Error EXIT_CODE classvars match yaml."""
        from frame_compare.errors import ERROR_REGISTRY

        data = load_yaml_safe(CONTRACTS_DIR / "error_codes.yaml")

        for code, error_cls in ERROR_REGISTRY.items():
            if code not in data["errors"]:
                continue

            expected_exit = data["errors"][code]["exit_code"]
            actual_exit = error_cls.EXIT_CODE

            assert (
                actual_exit == expected_exit
            ), f"{code}: expected EXIT_CODE={expected_exit}, got {actual_exit}"

    def test_security_errors_registered(self) -> None:
        """FC-5010 and FC-5011 are registered (v11 requirement)."""
        from frame_compare.errors import ERROR_REGISTRY

        assert "FC-5010" in ERROR_REGISTRY, "FC-5010 (HTTPS_REQUIRED) not registered"
        assert "FC-5011" in ERROR_REGISTRY, "FC-5011 (HOST_NOT_ALLOWED) not registered"

"""Tests for phase ordering contract validation.

Verifies that contracts/phase_ordering.yaml exists and has valid structure.
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.tier_a

# Paths relative to scaffold root
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent / "contracts"
PHASE_ORDERING_PATH = CONTRACTS_DIR / "phase_ordering.yaml"


class TestPhaseOrderingContract:
    """Validate phase_ordering.yaml contract structure."""

    def test_contract_file_exists(self) -> None:
        """phase_ordering.yaml must exist in contracts directory."""
        assert PHASE_ORDERING_PATH.exists(), f"Missing contract file: {PHASE_ORDERING_PATH}"

    def test_contract_is_valid_yaml(self) -> None:
        """Contract file must be valid YAML."""
        content = PHASE_ORDERING_PATH.read_text()
        data = yaml.safe_load(content)
        assert data is not None
        assert isinstance(data, dict)

    def test_contract_has_required_fields(self) -> None:
        """Contract must have version and phases fields."""
        data = yaml.safe_load(PHASE_ORDERING_PATH.read_text())

        assert "version" in data
        assert "phases" in data
        assert isinstance(data["phases"], list)
        assert len(data["phases"]) >= 9, "Expected 9 phases"

    def test_each_phase_has_required_fields(self) -> None:
        """Each phase must have name, order, skip_condition, and failure_mode."""
        data = yaml.safe_load(PHASE_ORDERING_PATH.read_text())

        required_fields = {"name", "order", "skip_condition", "failure_mode"}

        for phase in data["phases"]:
            missing = required_fields - set(phase.keys())
            assert not missing, f"Phase {phase.get('name', '?')} missing: {missing}"

    def test_phase_order_is_sequential(self) -> None:
        """Phase order values must be sequential starting from 1."""
        data = yaml.safe_load(PHASE_ORDERING_PATH.read_text())

        orders = [p["order"] for p in data["phases"]]
        expected = list(range(1, len(orders) + 1))

        assert orders == expected, f"Non-sequential order: {orders}"

    def test_expected_phases_present(self) -> None:
        """Contract must include all 9 canonical phases."""
        data = yaml.safe_load(PHASE_ORDERING_PATH.read_text())

        expected_phases = {
            "preflight",
            "load_sources",
            "frame_plan",
            "analyze",
            "render",
            "metadata",
            "dovi",
            "publish",
            "report",
        }
        actual_phases = {p["name"] for p in data["phases"]}

        missing = expected_phases - actual_phases
        assert not missing, f"Missing phases: {missing}"

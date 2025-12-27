"""Contract tests for config schema.

Verifies that config_schema.json is structurally valid.
Avoids brittle assertions (field counts, specific defaults) per contract evolution policy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Path to contracts (relative to test file location)
# scaffold/tests/contracts/ -> scaffold/../contracts/ -> docs/OPUS_REBUILD_FRAME_COMPARE/contracts/
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent / "contracts"


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_all_fields_from_schema(schema: dict, prefix: str = "") -> set[str]:
    """Extract all field paths from JSON schema."""
    fields = set()

    properties = schema.get("properties", {})
    for name, prop in properties.items():
        field_path = f"{prefix}.{name}" if prefix else name

        if prop.get("type") == "object" and "properties" in prop:
            # Nested object - recurse
            fields.update(get_all_fields_from_schema(prop, field_path))
        else:
            # Leaf field
            fields.add(field_path)

    return fields


# Invariant section names that must always exist (stable IDs)
REQUIRED_SECTIONS = frozenset({
    "paths",
    "analysis",
    "color",
    "slowpics",
    "logging",
})


@pytest.mark.tier_a
class TestConfigSchemaContract:
    """Tests that config schema is valid and complete."""

    def test_schema_is_valid_json_schema(self) -> None:
        """config_schema.json is valid JSON Schema."""
        schema = load_json(CONTRACTS_DIR / "config_schema.json")

        assert "$schema" in schema, "Missing $schema declaration"
        assert "properties" in schema, "Missing properties definition"
        assert schema.get("type") == "object", "Root type should be 'object'"

    def test_required_sections_present(self) -> None:
        """Core config sections that must always exist."""
        schema = load_json(CONTRACTS_DIR / "config_schema.json")

        actual_sections = set(schema.get("properties", {}).keys())

        missing = REQUIRED_SECTIONS - actual_sections
        assert not missing, f"Missing required config sections: {missing}"

    def test_sections_are_objects(self) -> None:
        """Each config section is an object with properties."""
        schema = load_json(CONTRACTS_DIR / "config_schema.json")

        for section_name in REQUIRED_SECTIONS:
            section = schema["properties"].get(section_name, {})
            assert section.get("type") == "object", (
                f"Section '{section_name}' should be type 'object'"
            )
            assert "properties" in section, (
                f"Section '{section_name}' should have 'properties'"
            )

    def test_schema_has_meaningful_content(self) -> None:
        """Schema has non-trivial field inventory (>10 fields minimum)."""
        schema = load_json(CONTRACTS_DIR / "config_schema.json")
        fields = get_all_fields_from_schema(schema)

        # Very loose bound - just ensures schema isn't empty
        # Exact counts are enforced by canonical contract + generator freshness
        assert len(fields) >= 10, f"Schema seems too minimal: {len(fields)} fields"

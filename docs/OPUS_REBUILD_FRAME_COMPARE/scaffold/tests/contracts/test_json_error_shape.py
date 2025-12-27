"""Contract tests for JSON error output shape.

Verifies that ErrorContext.to_dict() conforms to error_output_schema.json.
Uses jsonschema for validation per Codex feedback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Path to contracts
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent / "contracts"


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.tier_a
class TestJsonErrorShape:
    """Tests that error output matches JSON schema."""

    def test_error_context_to_dict_has_required_fields(self) -> None:
        """ErrorContext.to_dict() includes all required fields."""
        from frame_compare.errors import ErrorContext

        ctx = ErrorContext(
            code="FC-1001",
            name="CONFIG_NOT_FOUND",
            message="Config not found",
        )

        result = ctx.to_dict()

        assert "code" in result
        assert "name" in result
        assert "message" in result

    def test_error_context_code_format(self) -> None:
        """Error codes match FC-XXXX pattern."""
        import re

        from frame_compare.errors import ErrorContext

        ctx = ErrorContext(
            code="FC-1001",
            name="CONFIG_NOT_FOUND",
            message="Config not found",
        )

        pattern = r"^FC-[0-9]{4}$"
        assert re.match(pattern, ctx.to_dict()["code"]), (
            f"Code does not match FC-XXXX pattern: {ctx.code}"
        )

    def test_error_context_name_format(self) -> None:
        """Error names are SCREAMING_SNAKE_CASE."""
        import re

        from frame_compare.errors import ErrorContext

        ctx = ErrorContext(
            code="FC-1001",
            name="CONFIG_NOT_FOUND",
            message="Config not found",
        )

        pattern = r"^[A-Z][A-Z0-9_]*$"
        assert re.match(pattern, ctx.to_dict()["name"]), (
            f"Name not SCREAMING_SNAKE_CASE: {ctx.name}"
        )

    def test_error_context_optional_fields(self) -> None:
        """Optional fields only present when set."""
        from frame_compare.errors import ErrorContext

        # Without optional fields
        ctx1 = ErrorContext(code="FC-9001", name="TEST", message="test")
        result1 = ctx1.to_dict()
        assert "hint" not in result1
        assert "details" not in result1

        # With optional fields
        ctx2 = ErrorContext(
            code="FC-9001",
            name="TEST",
            message="test",
            hint="Try this",
            details={"key": "value"},
        )
        result2 = ctx2.to_dict()
        assert result2["hint"] == "Try this"
        assert result2["details"] == {"key": "value"}

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_error_output_validates_against_schema(self) -> None:
        """Full error envelope validates against error_output_schema.json."""
        from frame_compare.errors import ErrorContext

        schema = load_json(CONTRACTS_DIR / "error_output_schema.json")

        ctx = ErrorContext(
            code="FC-3001",
            name="NO_VIDEOS_FOUND",
            message="No video files found in path",
            hint="Place *.mkv files in the input directory",
            details={"path": "/workspace/videos"},
        )

        # Build complete envelope matching schema
        output = {
            "success": False,
            "error": ctx.to_dict(),
        }

        # Validate against schema - raises if invalid
        jsonschema.validate(output, schema)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_minimal_error_validates_against_schema(self) -> None:
        """Minimal error (no optional fields) still validates."""
        from frame_compare.errors import ErrorContext

        schema = load_json(CONTRACTS_DIR / "error_output_schema.json")

        ctx = ErrorContext(
            code="FC-9001",
            name="INTERNAL_ERROR",
            message="Something went wrong",
        )

        output = {
            "success": False,
            "error": ctx.to_dict(),
        }

        # Should not raise
        jsonschema.validate(output, schema)

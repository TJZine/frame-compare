"""Unit tests for VSPreview integration module.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
All external dependencies are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from frame_compare.vspreview.overrides import (
    load_manual_overrides,
)


class TestLoadManualOverrides:
    """Tests for load_manual_overrides() function."""

    def test_load_manual_overrides_parses_valid_toml(self, tmp_path: Path) -> None:
        """Valid TOML is parsed correctly."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        overrides_file = cache_dir / "manual_overrides.toml"
        overrides_file.write_text(
            """\
version = "1"

["reference:comparison_a"]
reference_clip = "reference"
comparison_clip = "comparison_a"
frame_offset = 42
timestamp = "2026-01-03T12:00:00Z"
confirmed = true

["reference:comparison_b"]
reference_clip = "reference"
comparison_clip = "comparison_b"
frame_offset = -10
timestamp = "2026-01-03T12:05:00Z"
confirmed = false
""",
            encoding="utf-8",
        )

        result = load_manual_overrides(cache_dir)

        assert len(result) == 2
        assert "reference:comparison_a" in result
        assert "reference:comparison_b" in result

        override_a = result["reference:comparison_a"]
        assert override_a.reference_clip == "reference"
        assert override_a.comparison_clip == "comparison_a"
        assert override_a.frame_offset == 42
        assert override_a.timestamp == "2026-01-03T12:00:00Z"
        assert override_a.confirmed is True

        override_b = result["reference:comparison_b"]
        assert override_b.frame_offset == -10
        assert override_b.confirmed is False

    def test_load_manual_overrides_returns_empty_dict_on_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns empty dict without error."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        result = load_manual_overrides(cache_dir)

        assert result == {}

    def test_load_manual_overrides_returns_empty_dict_on_parse_error(self, tmp_path: Path) -> None:
        """Corrupt TOML returns empty dict with warning."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        overrides_file = cache_dir / "manual_overrides.toml"
        overrides_file.write_text("this is not valid TOML [[[", encoding="utf-8")

        result = load_manual_overrides(cache_dir)

        assert result == {}

    def test_load_manual_overrides_returns_empty_dict_on_read_os_error(
        self, tmp_path: Path
    ) -> None:
        """Plain filesystem read failures degrade like invalid generated state."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        overrides_file = cache_dir / "manual_overrides.toml"
        overrides_file.write_text('version = "1"', encoding="utf-8")

        with (
            patch("pathlib.Path.open", side_effect=OSError("permission denied")),
            patch("frame_compare.vspreview.overrides.log.warning") as warning,
        ):
            result = load_manual_overrides(cache_dir)

        assert result == {}
        warning.assert_called_once()
        assert warning.call_args.args[0] == "manual_overrides_read_error"

    def test_load_manual_overrides_returns_empty_dict_on_version_mismatch(
        self, tmp_path: Path
    ) -> None:
        """Version mismatch returns empty dict with warning."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        overrides_file = cache_dir / "manual_overrides.toml"
        overrides_file.write_text(
            """\
version = "999"

["reference:comparison"]
reference_clip = "reference"
comparison_clip = "comparison"
frame_offset = 42
timestamp = "2026-01-03T12:00:00Z"
""",
            encoding="utf-8",
        )

        result = load_manual_overrides(cache_dir)

        assert result == {}

    def test_load_manual_overrides_skips_invalid_types(self, tmp_path: Path) -> None:
        """Skip entries with invalid field types."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        overrides_file = cache_dir / "manual_overrides.toml"
        overrides_file.write_text(
            """\
version = "1"

["ref:invalid_frame_offset_type"]
reference_clip = "reference"
comparison_clip = "comparison"
frame_offset = "not-an-int"
timestamp = "2026-01-03T12:00:00Z"
confirmed = true

["ref:invalid_frame_offset_bool"]
reference_clip = "reference"
comparison_clip = "comparison"
frame_offset = true
timestamp = "2026-01-03T12:00:00Z"
confirmed = true

["ref:missing_required_field"]
reference_clip = "reference"
comparison_clip = "comparison"
frame_offset = 42
confirmed = true

["ref:valid_entry"]
reference_clip = "reference"
comparison_clip = "comparison"
frame_offset = 42
timestamp = "2026-01-03T12:00:00Z"
confirmed = true
""",
            encoding="utf-8",
        )

        result = load_manual_overrides(cache_dir)
        assert len(result) == 1
        assert "ref:valid_entry" in result

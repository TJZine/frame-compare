"""Unit tests for VSPreview integration module.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
All external dependencies are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from frame_compare.vspreview.adapter import is_vspreview_available
from frame_compare.vspreview.overrides import (
    ManualOverride,
    load_manual_overrides,
    save_manual_override,
)


class TestIsVspreviewAvailable:
    """Tests for is_vspreview_available() function."""

    def test_is_vspreview_available_returns_true_when_executable_in_path(self) -> None:
        """Availability check returns True when vspreview executable exists."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/vspreview"

            result = is_vspreview_available()

            assert result is True
            mock_which.assert_called_once_with("vspreview")

    def test_is_vspreview_available_returns_true_when_importable(self) -> None:
        """Availability check returns True when vspreview module + Qt backend importable."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None  # No executable
            # Mock find_spec to return non-None for vspreview and PySide6
            mock_find_spec.side_effect = (
                lambda name: MagicMock() if name in ("vspreview", "PySide6") else None
            )

            result = is_vspreview_available()

            assert result is True

    def test_is_vspreview_available_returns_true_with_pyqt5_backend(self) -> None:
        """Availability check returns True with PyQt5 as Qt backend."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None

            # vspreview importable, PySide6 missing, PyQt5 available
            def find_spec_side_effect(name: str) -> MagicMock | None:
                if name == "vspreview":
                    return MagicMock()
                if name == "PyQt5":
                    return MagicMock()
                return None

            mock_find_spec.side_effect = find_spec_side_effect

            result = is_vspreview_available()

            assert result is True

    def test_is_vspreview_available_returns_false_when_missing(self) -> None:
        """Availability check returns False when vspreview not found."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None
            mock_find_spec.return_value = None  # Nothing importable

            result = is_vspreview_available()

            assert result is False

    def test_is_vspreview_available_returns_false_when_no_qt_backend(self) -> None:
        """Availability check returns False when vspreview importable but no Qt."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None

            # vspreview is importable, but no Qt backends
            def find_spec_side_effect(name: str) -> MagicMock | None:
                if name == "vspreview":
                    return MagicMock()
                return None

            mock_find_spec.side_effect = find_spec_side_effect

            result = is_vspreview_available()

            assert result is False


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


class TestSaveManualOverride:
    """Tests for save_manual_override() function."""

    def test_save_manual_override_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Creates file if not exists."""
        cache_dir = tmp_path / "cache"
        # Note: cache_dir doesn't exist yet

        override = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp",
            frame_offset=10,
            timestamp="2026-01-03T12:00:00Z",
            confirmed=True,
        )

        save_manual_override(cache_dir, override)

        overrides_file = cache_dir / "manual_overrides.toml"
        assert overrides_file.exists()

        # Verify contents
        result = load_manual_overrides(cache_dir)
        assert "ref:comp" in result
        assert result["ref:comp"].frame_offset == 10

    def test_save_manual_override_merges_with_existing(self, tmp_path: Path) -> None:
        """Merge semantics preserve existing keys."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Save first override
        override1 = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp_a",
            frame_offset=10,
            timestamp="2026-01-03T12:00:00Z",
        )
        save_manual_override(cache_dir, override1)

        # Save second override
        override2 = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp_b",
            frame_offset=20,
            timestamp="2026-01-03T12:05:00Z",
        )
        save_manual_override(cache_dir, override2)

        # Verify both are present
        result = load_manual_overrides(cache_dir)
        assert len(result) == 2
        assert "ref:comp_a" in result
        assert "ref:comp_b" in result
        assert result["ref:comp_a"].frame_offset == 10
        assert result["ref:comp_b"].frame_offset == 20

    def test_save_manual_override_overwrites_same_key(self, tmp_path: Path) -> None:
        """Update semantics overwrite same clip pair."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Save initial override
        override1 = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp",
            frame_offset=10,
            timestamp="2026-01-03T12:00:00Z",
        )
        save_manual_override(cache_dir, override1)

        # Save updated override for same key
        override2 = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp",
            frame_offset=99,
            timestamp="2026-01-03T12:30:00Z",
            confirmed=False,
        )
        save_manual_override(cache_dir, override2)

        # Verify updated value
        result = load_manual_overrides(cache_dir)
        assert len(result) == 1
        assert result["ref:comp"].frame_offset == 99
        assert result["ref:comp"].confirmed is False

    def test_save_manual_override_logs_and_continues_on_existing_read_os_error(
        self, tmp_path: Path
    ) -> None:
        """Existing manual override read failures do not block saving a new override."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        overrides_file = cache_dir / "manual_overrides.toml"
        overrides_file.write_text(
            """\
version = "1"

["old:entry"]
reference_clip = "old"
comparison_clip = "entry"
frame_offset = 1
timestamp = "2026-01-03T12:00:00Z"
""",
            encoding="utf-8",
        )
        override = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp",
            frame_offset=99,
            timestamp="2026-01-03T12:30:00Z",
            confirmed=False,
        )
        original_open = Path.open

        def open_with_read_failure(path: Path, mode: str = "r", *args, **kwargs):
            if path == overrides_file and "r" in mode:
                raise OSError("stale handle")
            return original_open(path, mode, *args, **kwargs)

        with (
            patch("pathlib.Path.open", open_with_read_failure),
            patch("frame_compare.vspreview.overrides.log.warning") as warning,
        ):
            save_manual_override(cache_dir, override)

        assert warning.call_args.args[0] == "manual_overrides_read_existing_error"
        result = load_manual_overrides(cache_dir)
        assert result == {"ref:comp": override}

    def test_save_manual_override_logs_and_continues_on_write_os_error(
        self, tmp_path: Path
    ) -> None:
        """Manual override writes are best-effort generated-state acceleration."""
        cache_dir = tmp_path / "cache"
        override = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp",
            frame_offset=10,
            timestamp="2026-01-03T12:00:00Z",
        )

        with (
            patch("pathlib.Path.open", side_effect=OSError("disk full")),
            patch("frame_compare.vspreview.overrides.log.warning") as warning,
        ):
            save_manual_override(cache_dir, override)

        warning.assert_called_once()
        assert warning.call_args.args[0] == "manual_overrides_write_error"


class TestManualOverridePrecedence:
    """Tests for manual override precedence over computed/cached results."""

    def test_manual_override_takes_precedence_over_computed(self, tmp_path: Path) -> None:
        """Manual overrides take precedence and skip FFmpeg extraction."""
        from fractions import Fraction

        # Prepare test directories and files
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create stub video files (content doesn't matter since we're mocking)
        reference = input_dir / "reference.mkv"
        comparison = input_dir / "comparison.mkv"
        reference.write_bytes(b"stub")
        comparison.write_bytes(b"stub")

        # Save a manual override
        override = ManualOverride(
            reference_clip="reference",
            comparison_clip="comparison",
            frame_offset=42,
            timestamp="2026-01-03T12:00:00Z",
            confirmed=True,
        )
        save_manual_override(cache_dir, override)

        # Prepare mocks
        with (
            patch("frame_compare.services.alignment._probe_fps") as mock_probe_fps,
            patch("frame_compare.services.alignment._extract_audio") as mock_extract_audio,
            patch("frame_compare.services.alignment.load_cached_offsets") as mock_load_cached,
        ):
            mock_probe_fps.return_value = Fraction(24, 1)
            mock_extract_audio.side_effect = AssertionError(
                "FFmpeg should NOT be called for overridden entries"
            )
            mock_load_cached.return_value = None  # No cache

            # Import and call align_clips
            from frame_compare.services.alignment import align_clips
            from frame_compare.services.types import AlignmentConfig

            config = AlignmentConfig(
                enable=True,
                sample_rate=8000,
                cache_results=False,  # Disable cache to focus on override test
            )

            results = align_clips(
                reference=reference,
                comparisons=[comparison],
                config=config,
                cache_dir=cache_dir,
            )

            # Verify result
            assert len(results) == 1
            result = results[0]
            assert result.source == "manual"
            assert result.algorithm is None
            assert result.frame_offset == 42
            assert result.correlation_score == 1.0
            assert result.reference_clip == "reference.mkv"
            assert result.comparison_clip == "comparison.mkv"

            # Verify FFmpeg was NOT called
            mock_extract_audio.assert_not_called()

            # FPS probe should have been called once (for time_offset_seconds)
            mock_probe_fps.assert_called_once()

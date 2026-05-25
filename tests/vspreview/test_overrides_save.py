"""Unit tests for VSPreview integration module.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
All external dependencies are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from frame_compare.vspreview.overrides import (
    ManualOverride,
    load_manual_overrides,
    save_manual_override,
)


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
            patch(
                "frame_compare.vspreview.overrides.write_bytes_atomic",
                side_effect=OSError("disk full"),
            ),
            patch("frame_compare.vspreview.overrides.log.warning") as warning,
        ):
            save_manual_override(cache_dir, override)

        warning.assert_called_once()
        assert warning.call_args.args[0] == "manual_overrides_write_error"

    def test_save_manual_override_uses_atomic_bytes_write(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        override = ManualOverride(
            reference_clip="ref",
            comparison_clip="comp",
            frame_offset=10,
            timestamp="2026-01-03T12:00:00Z",
        )
        calls: list[tuple[Path, bytes]] = []

        def _fake_write(path: Path, content: bytes) -> None:
            calls.append((path, content))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        with patch("frame_compare.vspreview.overrides.write_bytes_atomic", _fake_write):
            save_manual_override(cache_dir, override)

        assert [path for path, _ in calls] == [cache_dir / "manual_overrides.toml"]
        assert load_manual_overrides(cache_dir) == {"ref:comp": override}

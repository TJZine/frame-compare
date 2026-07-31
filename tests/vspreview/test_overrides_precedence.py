"""Unit tests for VSPreview integration module.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
All external dependencies are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from frame_compare.vspreview.overrides import (
    ManualOverride,
    save_manual_override,
)


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
        ):
            mock_probe_fps.return_value = Fraction(24, 1)
            mock_extract_audio.side_effect = AssertionError(
                "FFmpeg should NOT be called for overridden entries"
            )

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

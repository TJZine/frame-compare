"""Math and trim coverage kept with code that still exists (U3-R M6)."""

# pyright: reportPrivateUsage=false

import pytest

from frame_compare.services.alignment_math import calculate_alignment_trims
from frame_compare.services.types import AlignmentConfig


def test_alignment_config_defaults() -> None:
    """AlignmentConfig keeps its current whole-track defaults."""
    cfg = AlignmentConfig()
    assert cfg.enable is True
    assert cfg.max_offset_seconds == 30.0
    assert cfg.use_vsview is False
    assert cfg.force_interactive is False
    assert cfg.cache_results is True
    assert cfg.previous_offsets == "disabled"
    assert cfg.channel_strategy == "mono_downmix"
    assert cfg.reference_stream is None
    assert cfg.comparison_streams == {}
    assert cfg.no_color is False


def test_calculate_alignment_trims_rejects_mismatched_lengths_when_offsets_are_unknown() -> None:
    """Default trim path preserves the same length invariant as aligned offsets."""
    with pytest.raises(ValueError, match=r"comp_offsets and comp_num_frames.*1 != 2"):
        calculate_alignment_trims(
            ref_num_frames=100,
            comp_offsets=[None],
            comp_num_frames=[100, 100],
        )

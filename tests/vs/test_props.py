"""Unit tests for frame property extraction."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock vapoursynth BEFORE importing module under test (VS missing in CI)
if "vapoursynth" not in sys.modules:
    sys.modules["vapoursynth"] = MagicMock()

from frame_compare.vs.props import get_color_props, is_hdr


def test_get_color_props_returns_colorprops_with_defaults():
    """Verify defaults (2, 2, 2, 1) when props missing."""
    clip = MagicMock()
    # Mock frame 0 props as empty dict
    clip.get_frame.return_value.props = {}

    props = get_color_props(clip)
    assert props.primaries == 2
    assert props.transfer == 2
    assert props.matrix == 2
    assert props.color_range == 1


def test_get_color_props_extracts_all_fields():
    """Verify all fields extracted when present."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Primaries": 1,
        "_Transfer": 1,
        "_Matrix": 1,
        "_ColorRange": 1,
    }

    props = get_color_props(clip)
    assert props.primaries == 1
    assert props.transfer == 1
    assert props.matrix == 1
    assert props.color_range == 1


def test_get_color_props_partial_props_uses_defaults():
    """Verify partial props missing uses defaults."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Primaries": 9,
        "_Transfer": 16,
    }

    props = get_color_props(clip)
    assert props.primaries == 9
    assert props.transfer == 16
    assert props.matrix == 2
    assert props.color_range == 1


def test_is_hdr_pq_bt2020_returns_true():
    """PQ (16) + BT.2020 (9) is HDR."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Transfer": 16,
        "_Primaries": 9,
    }
    assert is_hdr(clip) is True


def test_is_hdr_hlg_bt2020_returns_true():
    """HLG (18) + BT.2020 (9) is HDR."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Transfer": 18,
        "_Primaries": 9,
    }
    assert is_hdr(clip) is True


def test_is_hdr_sdr_returns_false():
    """BT.709 (1) + BT.709 (1) is SDR."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Transfer": 1,
        "_Primaries": 1,
    }
    assert is_hdr(clip) is False


def test_is_hdr_pq_without_bt2020_returns_false():
    """PQ (16) without BT.2020 (e.g. BT.709=1) is False by rule."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Transfer": 16,
        "_Primaries": 1,
    }
    assert is_hdr(clip) is False


def test_is_hdr_bt2020_without_pq_hlg_returns_false():
    """BT.2020 (9) with BT.709 transfer (1) is False."""
    clip = MagicMock()
    clip.get_frame.return_value.props = {
        "_Transfer": 1,
        "_Primaries": 9,
    }
    assert is_hdr(clip) is False

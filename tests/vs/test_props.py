"""Unit tests for frame property extraction."""

from __future__ import annotations

from frame_compare.vs.props import (
    detect_hdr,
    get_int_prop,
    get_optional_int_prop,
    get_optional_range_prop,
    get_str_prop,
    props_indicate_limited_range,
    range_label_from_props,
)


def test_get_int_prop():
    """Verify get_int_prop behaves correctly with different types."""
    props = {
        "int_val": 42,
        "float_val": 42.6,
        "str_val": "100",
        "bytes_val": b"200",
        "invalid_str": "not_an_int",
    }

    assert get_int_prop(props, "int_val", 0) == 42
    assert get_int_prop(props, "float_val", 0) == 42
    assert get_int_prop(props, "str_val", 0) == 100
    assert get_int_prop(props, "bytes_val", 0) == 200
    assert get_int_prop(props, "invalid_str", 5) == 5
    assert get_int_prop(props, "missing", 10) == 10


def test_get_optional_int_prop():
    """Verify get_optional_int_prop behaves correctly with different types."""
    props = {
        "int_val": 42,
        "float_val": 42.6,
        "str_val": "100",
        "bytes_val": b"200",
        "invalid_str": "not_an_int",
    }

    assert get_optional_int_prop(props, "int_val") == 42
    assert get_optional_int_prop(props, "float_val") == 42
    assert get_optional_int_prop(props, "str_val") == 100
    assert get_optional_int_prop(props, "bytes_val") == 200
    assert get_optional_int_prop(props, "invalid_str") is None
    assert get_optional_int_prop(props, "missing") is None


def test_get_str_prop():
    """Verify get_str_prop behaves correctly with different types."""
    props = {
        "str_val": "hello",
        "bytes_val": b"world",
        "int_val": 123,
    }

    assert get_str_prop(props, "str_val") == "hello"
    assert get_str_prop(props, "bytes_val") == "world"
    assert get_str_prop(props, "int_val") == "123"
    assert get_str_prop(props, "missing") is None


def test_get_optional_range_prop_prefers_modern_range_key():
    props = {
        "_ColorRange": 1,
        "_Range": 0,
    }

    assert get_optional_range_prop(props) == 0


def test_range_helpers_follow_current_vapoursynth_semantics():
    limited_props = {"_Range": 0}
    full_props = {"_ColorRange": 1}

    assert props_indicate_limited_range(limited_props) is True
    assert range_label_from_props(limited_props) == "limited"
    assert props_indicate_limited_range(full_props) is False
    assert range_label_from_props(full_props) == "full"


def test_detect_hdr_pq_bt2020():
    """PQ (16) + BT.2020 (9) is HDR."""
    props = {
        "_Transfer": 16,
        "_Primaries": 9,
        "_Matrix": 9,
        "MasteringDisplayPrimaries": b"G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)",
        "ContentLightLevelMax": 1000,
        "ContentLightLevelAverage": 400,
    }
    is_hdr_detected, metadata = detect_hdr(props)

    assert is_hdr_detected is True
    assert metadata is not None
    assert metadata.transfer == 16
    assert metadata.color_primaries == 9
    assert metadata.matrix == 9
    assert (
        metadata.mastering_display
        == "G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)"
    )
    assert metadata.max_cll == 1000
    assert metadata.max_fall == 400


def test_detect_hdr_hlg_bt2020():
    """HLG (18) + BT.2020 (9) is HDR."""
    props = {
        "_Transfer": 18,
        "_Primaries": 9,
    }
    is_hdr_detected, metadata = detect_hdr(props)

    assert is_hdr_detected is True
    assert metadata is not None
    assert metadata.transfer == 18
    assert metadata.color_primaries == 9
    assert metadata.matrix == 2  # Default unspecified
    assert metadata.mastering_display is None
    assert metadata.max_cll is None
    assert metadata.max_fall is None


def test_detect_hdr_sdr():
    """BT.709 (1) + BT.709 (1) is SDR."""
    props = {
        "_Transfer": 1,
        "_Primaries": 1,
    }
    is_hdr_detected, metadata = detect_hdr(props)

    assert is_hdr_detected is False
    assert metadata is None


def test_detect_hdr_pq_without_bt2020():
    """PQ (16) without BT.2020 (e.g. BT.709=1) is False by rule."""
    props = {
        "_Transfer": 16,
        "_Primaries": 1,
    }
    is_hdr_detected, metadata = detect_hdr(props)

    assert is_hdr_detected is False
    assert metadata is None

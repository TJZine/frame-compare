"""Unit tests for frame property extraction."""

from __future__ import annotations

from enum import Enum

import pytest

from frame_compare.vs.props import (
    detect_hdr,
    get_optional_int_prop,
    get_optional_range_prop,
    get_str_prop,
    merge_hdr_metadata,
    props_indicate_limited_range,
    range_label_from_props,
)
from frame_compare.vs.types import HDRMetadata


class _ExampleEnum(Enum):
    VALUE = 9


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
    assert get_optional_int_prop({"enum_val": _ExampleEnum.VALUE}, "enum_val") == 9


def test_get_optional_int_prop_treats_non_finite_numbers_as_unavailable() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        assert get_optional_int_prop({"value": value}, "value") is None


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


def test_range_helpers_follow_current_range_semantics():
    assert props_indicate_limited_range({"_Range": 0}) is True
    assert range_label_from_props({"_Range": 0}) == "limited"
    assert props_indicate_limited_range({"_Range": 1}) is False
    assert range_label_from_props({"_Range": 1}) == "full"


def test_range_helpers_normalize_deprecated_color_range_semantics():
    assert get_optional_range_prop({"_ColorRange": 1}) == 0
    assert props_indicate_limited_range({"_ColorRange": 1}) is True
    assert range_label_from_props({"_ColorRange": 1}) == "limited"

    assert get_optional_range_prop({"_ColorRange": 0}) == 1
    assert props_indicate_limited_range({"_ColorRange": 0}) is False
    assert range_label_from_props({"_ColorRange": 0}) == "full"


def test_range_helpers_ignore_unrecognized_range_values():
    assert get_optional_range_prop({"_Range": 2, "_ColorRange": 2}) is None
    assert props_indicate_limited_range({"_Range": 2, "_ColorRange": 2}) is None
    assert range_label_from_props({"_Range": 2, "_ColorRange": 2}) is None


@pytest.mark.parametrize(
    "props, expected_hdr, expected_metadata",
    [
        pytest.param(
            {
                "_Transfer": 16,
                "_Primaries": 9,
                "_Matrix": 9,
                "MasteringDisplayPrimaries": b"G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)",
                "ContentLightLevelMax": 1000,
                "ContentLightLevelAverage": 400,
            },
            True,
            HDRMetadata(
                "G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)",
                1000,
                400,
                9,
                16,
                9,
            ),
            id="pq_bt2020",
        ),
        pytest.param(
            {"_Transfer": 18, "_Primaries": 9},
            True,
            HDRMetadata(None, None, None, 9, 18, 2),
            id="hlg_bt2020",
        ),
        pytest.param({"_Transfer": 1, "_Primaries": 1}, False, None, id="sdr"),
        pytest.param({"_Transfer": 16, "_Primaries": 1}, False, None, id="pq_bt709"),
    ],
)
def test_detect_hdr_signal_cases(
    props: dict[str, object], expected_hdr: bool, expected_metadata: HDRMetadata | None
) -> None:
    is_hdr, metadata = detect_hdr(props)
    assert is_hdr is expected_hdr
    assert metadata == expected_metadata


@pytest.mark.parametrize(
    "props, fallback, expected",
    [
        pytest.param(
            {
                "_Transfer": b"16",
                "_Primaries": 2,
                "_Matrix": _ExampleEnum.VALUE,
                "MasteringDisplayPrimaries": "frame mastering",
                "ContentLightLevelMax": "1000",
                "ContentLightLevelAverage": b"400",
            },
            HDRMetadata("probe mastering", 900, 350, 9, 1, 1),
            HDRMetadata("frame mastering", 1000, 400, 9, 16, 9),
            id="usable_frame",
        ),
        pytest.param(
            {"_Transfer": "malformed", "_Primaries": "1", "_Matrix": b"malformed"},
            HDRMetadata(None, None, None, 9, 18, 9),
            HDRMetadata(None, None, None, 1, 18, 9),
            id="backfill_unusable",
        ),
        pytest.param(
            {"_Transfer": object(), "_Primaries": b"bad", "_Matrix": "bad"},
            HDRMetadata(None, None, None, 2, 2, 2),
            HDRMetadata(None, None, None, 2, 2, 2),
            id="both_unusable",
        ),
    ],
)
def test_merge_hdr_metadata_cases(
    props: dict[str, object], fallback: HDRMetadata, expected: HDRMetadata
) -> None:
    assert merge_hdr_metadata(props, fallback) == expected

"""Frame property extraction functions."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import cast

from frame_compare.vs.types import HDRMetadata

_RANGE_LIMITED = 0
_RANGE_FULL = 1
_COLOR_RANGE_FULL = 0
_COLOR_RANGE_LIMITED = 1


def get_int_prop(props: Mapping[str, object], key: str, default: int) -> int:
    """Safely extract an integer property from frame properties with fallback."""
    value = get_optional_int_prop(props, key)
    return default if value is None else value


def get_optional_int_prop(props: Mapping[str, object], key: str) -> int | None:
    """Safely extract an optional integer property from frame properties."""
    val = props.get(key)
    if val is None:
        return None
    if isinstance(val, Enum):
        val = cast(object, val.value)
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, (bytes, str)):
        try:
            return int(val)
        except ValueError:
            return None
    return None


def get_str_prop(props: Mapping[str, object], key: str) -> str | None:
    """Safely extract a string property from frame properties."""
    val = props.get(key)
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def get_optional_range_prop(props: Mapping[str, object]) -> int | None:
    """Return range normalized to modern `_Range` numbering.

    VapourSynth R74 introduced `_Range` with H.273 numbering where
    0=limited and 1=full. Deprecated `_ColorRange` uses the opposite legacy
    numbering, so normalize it before callers make limited/full decisions.
    """
    for key in ("_Range", "Range"):
        value = get_optional_int_prop(props, key)
        if value in {_RANGE_LIMITED, _RANGE_FULL}:
            return value
    for key in ("_ColorRange", "ColorRange"):
        value = get_optional_int_prop(props, key)
        if value == _COLOR_RANGE_FULL:
            return _RANGE_FULL
        if value == _COLOR_RANGE_LIMITED:
            return _RANGE_LIMITED
    return None


def props_indicate_limited_range(props: Mapping[str, object]) -> bool | None:
    """Return whether frame props indicate limited range under current VapourSynth semantics."""
    range_value = get_optional_range_prop(props)
    if range_value is None:
        return None
    if range_value == _RANGE_LIMITED:
        return True
    if range_value == _RANGE_FULL:
        return False
    return None


def range_label_from_props(props: Mapping[str, object]) -> str | None:
    """Return `limited` or `full` when frame props expose a recognized range value."""
    limited = props_indicate_limited_range(props)
    if limited is None:
        return None
    return "limited" if limited else "full"


def detect_hdr(frame_props: Mapping[str, object]) -> tuple[bool, HDRMetadata | None]:
    """Detect HDR from frame properties.

    HDR Detection:
        is_hdr = _Transfer in (16, 18) AND _Primaries == 9

    Where:
        - _Transfer == 16: PQ (Perceptual Quantizer)
        - _Transfer == 18: HLG (Hybrid Log-Gamma)
        - _Primaries == 9: BT.2020

    Args:
        frame_props: Mapping of frame property keys to values

    Returns:
        A tuple of (is_hdr, HDRMetadata)
    """
    transfer = get_int_prop(frame_props, "_Transfer", 2)
    primaries = get_int_prop(frame_props, "_Primaries", 2)

    is_hdr = transfer in (16, 18) and primaries == 9

    if not is_hdr:
        return (False, None)

    return (
        True,
        HDRMetadata(
            mastering_display=get_str_prop(frame_props, "MasteringDisplayPrimaries"),
            max_cll=get_optional_int_prop(frame_props, "ContentLightLevelMax"),
            max_fall=get_optional_int_prop(frame_props, "ContentLightLevelAverage"),
            color_primaries=primaries,
            transfer=transfer,
            matrix=get_int_prop(frame_props, "_Matrix", 2),
        ),
    )


def hdr_signal_is_unspecified(frame_props: Mapping[str, object]) -> bool:
    """Return whether frame props lack a usable transfer or primaries signal."""
    transfer = get_int_prop(frame_props, "_Transfer", 2)
    primaries = get_int_prop(frame_props, "_Primaries", 2)
    return transfer == 2 or primaries == 2

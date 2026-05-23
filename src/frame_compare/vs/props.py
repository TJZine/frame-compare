"""Frame property extraction functions."""

from __future__ import annotations

from collections.abc import Mapping

from frame_compare.vs.types import HDRMetadata


def get_int_prop(props: Mapping[str, object], key: str, default: int) -> int:
    """Safely extract an integer property from frame properties with fallback."""
    val = props.get(key)
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, (bytes, str)):
        try:
            return int(val)
        except ValueError:
            return default
    return default


def get_optional_int_prop(props: Mapping[str, object], key: str) -> int | None:
    """Safely extract an optional integer property from frame properties."""
    val = props.get(key)
    if val is None:
        return None
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

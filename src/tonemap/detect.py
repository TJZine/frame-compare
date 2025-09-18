"""HDR detection helpers."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from .exceptions import HDRDetectError

logger = logging.getLogger(__name__)

_HDR_TRANSFER_CODES = {16, 18}
_HDR_TRANSFER_NAMES = {"st2084", "pq", "smpte2084", "hlg", "arib-b67"}
_HDR_PRIMARIES_CODES = {9}
_HDR_PRIMARIES_NAMES = {"bt2020", "bt.2020", "2020"}
_HDR_METADATA_KEYS = {
    "_MasteringDisplayPrimaries",
    "_MasteringDisplayPeakLuminance",
    "_MasteringDisplayMinLuminance",
    "_MasteringDisplayMaxLuminance",
    "_ContentLightLevelMax",
    "_ContentLightLevelAverage",
    "_MaxCLL",
    "_MaxFALL",
}


def _normalise(value: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return value.strip().lower()
    return value


def is_hdr(props: Mapping[str, Any]) -> bool:
    """Return ``True`` when *props* describe an HDR source clip."""

    if props is None:
        raise HDRDetectError("frame_props", "frame properties are unavailable")

    transfer = _normalise(props.get("_Transfer") or props.get("Transfer"))
    primaries = _normalise(props.get("_Primaries") or props.get("Primaries"))
    matrix = _normalise(props.get("_Matrix") or props.get("Matrix"))
    color_range = _normalise(props.get("_ColorRange") or props.get("ColorRange"))

    transfer_hdr = False
    if isinstance(transfer, int):
        transfer_hdr = transfer in _HDR_TRANSFER_CODES
    elif isinstance(transfer, str):
        transfer_hdr = transfer in _HDR_TRANSFER_NAMES

    primaries_hdr = False
    if isinstance(primaries, int):
        primaries_hdr = primaries in _HDR_PRIMARIES_CODES
    elif isinstance(primaries, str):
        primaries_hdr = primaries in _HDR_PRIMARIES_NAMES

    metadata_present = any(key in props for key in _HDR_METADATA_KEYS)

    logger.debug(
        "hdr.detect props transfer=%r primaries=%r matrix=%r range=%r maxcll=%r maxfall=%r metadata=%s",
        transfer,
        primaries,
        matrix,
        color_range,
        props.get("_MaxCLL"),
        props.get("_MaxFALL"),
        metadata_present,
    )

    if transfer_hdr:
        return True
    if metadata_present and (transfer_hdr or primaries_hdr):
        return True
    if primaries_hdr and transfer_hdr:
        return True
    if metadata_present and transfer is None:
        return True
    return False

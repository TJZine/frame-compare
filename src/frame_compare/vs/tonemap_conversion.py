"""Shared conversion and post-processing helpers for HDR tonemapping."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from frame_compare.vs.errors import TonemapError
from frame_compare.vs.props import detect_hdr, get_optional_int_prop, get_optional_range_prop
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

_FRAME_PROP_MATRIX = "_Matrix"
_FRAME_PROP_TRANSFER = "_Transfer"
_FRAME_PROP_PRIMARIES = "_Primaries"
_UNSPECIFIED_COLOR_PROP = 2


@dataclass(frozen=True, slots=True)
class HdrTonemapInputs:
    hdr_metadata: HDRMetadata | None
    transfer: int | None
    primaries: int | None
    props: dict[str, object] | None
    detected_is_hdr: bool | None


def deduce_src_csp_hint(transfer: int | None, primaries: int | None) -> int | None:
    """Return vs-placebo `src_csp` hint based on HDR signaling.

    This mirrors the legacy behavior documented in `docs/archive/legacy_tonemap_info.md`.
    """
    if transfer == 16 and primaries == 9:
        return 1  # PQ + BT.2020 -> HDR10
    if transfer == 18 and primaries == 9:
        return 2  # HLG + BT.2020 -> HLG
    return None


def normalize_rgb_props(
    clip: vs.VideoNode, *, transfer: int | None, primaries: int | None
) -> vs.VideoNode:
    """Normalize RGB clip props before libplacebo tonemapping.

    Sets:
        _Matrix=0 (RGB), _ColorRange=0 (full)
    Preserves (when provided):
        _Transfer, _Primaries
    """
    kwargs: dict[str, int] = {"_Matrix": 0, "_ColorRange": 0}
    if transfer is not None:
        kwargs["_Transfer"] = int(transfer)
    if primaries is not None:
        kwargs["_Primaries"] = int(primaries)
    return clip.std.SetFrameProps(**kwargs)


def validate_target_nits(settings: TonemapSettings) -> int:
    """Validate and return target nits used by tonemap operations."""
    target_nits = settings.target_nits
    if target_nits <= 0:
        raise TonemapError(
            reason=f"Invalid target_nits: {target_nits}. target_nits must be > 0",
            hint="Set color.target_nits to a positive value",
        )
    return target_nits


def _specified_int_prop(props: Mapping[str, object], key: str) -> int | None:
    value = get_optional_int_prop(props, key)
    if value is None or value == _UNSPECIFIED_COLOR_PROP:
        return None
    return value


def _resolve_matrix_in(
    props: Mapping[str, object],
    *,
    detected_is_hdr: bool | None,
) -> int:
    import vapoursynth as vs

    matrix = _specified_int_prop(props, _FRAME_PROP_MATRIX)
    if matrix is not None:
        return matrix

    if detected_is_hdr is None:
        detected_is_hdr, _ = detect_hdr(props)
    if detected_is_hdr:
        return int(getattr(vs, "MATRIX_BT2020_NCL", 9))
    return int(getattr(vs, "MATRIX_BT709", 1))


def _resolve_range_in(props: Mapping[str, object]) -> int:
    import vapoursynth as vs

    range_limited = int(getattr(vs, "RANGE_LIMITED", 0))
    normalized_range = get_optional_range_prop(props)
    return range_limited if normalized_range is None else normalized_range


def _conversion_kwargs(
    *,
    target_format: int,
    props: Mapping[str, object],
    detected_is_hdr: bool | None,
) -> dict[str, int]:
    kwargs = {
        "format": target_format,
        "matrix_in": _resolve_matrix_in(props, detected_is_hdr=detected_is_hdr),
        "range_in": _resolve_range_in(props),
    }
    transfer = _specified_int_prop(props, _FRAME_PROP_TRANSFER)
    if transfer is not None:
        kwargs["transfer_in"] = transfer
    primaries = _specified_int_prop(props, _FRAME_PROP_PRIMARIES)
    if primaries is not None:
        kwargs["primaries_in"] = primaries
    return kwargs


def convert_non_rgb_with_matrix_hint(
    clip: vs.VideoNode,
    *,
    target_format: int,
    props: dict[str, object] | None = None,
    detected_is_hdr: bool | None = None,
) -> vs.VideoNode:
    """Convert non-RGB clips to RGB target format with validated source metadata."""
    if props is None:
        props = dict(clip.get_frame(0).props)

    kwargs = _conversion_kwargs(
        target_format=target_format,
        props=props,
        detected_is_hdr=detected_is_hdr,
    )
    return clip.resize.Bicubic(**kwargs)  # type: ignore[attr-defined]


def to_rgbs(clip: vs.VideoNode) -> vs.VideoNode:
    """Convert clip to RGBS if needed."""
    import vapoursynth as vs

    try:
        if clip.format.id != vs.RGBS:
            if clip.format.color_family == vs.RGB:
                return clip.resize.Bicubic(format=vs.RGBS)
            rgbs_format = vs.RGBS
            return convert_non_rgb_with_matrix_hint(clip, target_format=rgbs_format)
        return clip
    except Exception as e:
        raise TonemapError(
            reason=f"Failed to convert to RGBS: {e}",
            hint="Check input clip format compatibility",
        ) from e


def apply_post_processing(clip: vs.VideoNode, settings: TonemapSettings) -> vs.VideoNode:
    """Apply unified post-processing (contrast recovery and gamma lift)."""
    try:
        if settings.gamma_lift:
            clip = clip.std.Levels(gamma=0.9)

        return clip
    except Exception as e:
        raise TonemapError(
            reason=f"Post-processing failed: {e}",
            hint="Check post-processing parameters",
        ) from e


def resolve_hdr_tonemap_inputs(
    clip: vs.VideoNode,
    hdr_metadata: HDRMetadata | None,
) -> HdrTonemapInputs:
    props: dict[str, object] | None = None
    detected_is_hdr: bool | None = None
    if hdr_metadata is None:
        props = dict(clip.get_frame(0).props)
        detected_is_hdr, hdr_metadata = detect_hdr(props)

    transfer_raw: object | None = (
        getattr(hdr_metadata, "transfer", None) if hdr_metadata is not None else None
    )
    primaries_raw: object | None = (
        getattr(hdr_metadata, "color_primaries", None) if hdr_metadata is not None else None
    )
    return HdrTonemapInputs(
        hdr_metadata=hdr_metadata,
        transfer=transfer_raw if isinstance(transfer_raw, int) else None,
        primaries=primaries_raw if isinstance(primaries_raw, int) else None,
        props=props,
        detected_is_hdr=detected_is_hdr,
    )

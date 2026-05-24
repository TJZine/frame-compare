"""Shared conversion and post-processing helpers for HDR tonemapping."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from frame_compare.vs.errors import TonemapError
from frame_compare.vs.props import detect_hdr, get_optional_int_prop
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

_FRAME_PROP_MATRIX = "_Matrix"
_UNSPECIFIED_MATRIX = 2


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


def _matrix_prop_is_specified(props: Mapping[str, object]) -> bool:
    """Return whether frame props carry a usable VapourSynth matrix prop."""
    matrix = get_optional_int_prop(props, _FRAME_PROP_MATRIX)
    if matrix is not None:
        return matrix != _UNSPECIFIED_MATRIX
    return _FRAME_PROP_MATRIX in props


def convert_non_rgb_with_matrix_hint(
    clip: vs.VideoNode,
    *,
    target_format: int,
    props: dict[str, object] | None = None,
    detected_is_hdr: bool | None = None,
) -> vs.VideoNode:
    """Convert non-RGB clips to RGB target format with deterministic matrix fallback."""
    if props is None:
        props = dict(clip.get_frame(0).props)

    matrix_in_s: str | None = None
    if not _matrix_prop_is_specified(props):
        if detected_is_hdr is None:
            detected_is_hdr, _ = detect_hdr(props)
        matrix_in_s = "2020ncl" if detected_is_hdr else "709"

    if matrix_in_s is None:
        return clip.resize.Bicubic(format=target_format)  # type: ignore[attr-defined]
    return clip.resize.Bicubic(format=target_format, matrix_in_s=matrix_in_s)  # type: ignore[attr-defined]


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
        if settings.contrast_recovery > 0.0:
            factor = 1 + settings.contrast_recovery
            expr = f"x 0.5 - {factor} * 0.5 + 0 max 1 min"
            clip = clip.std.Expr(expr=[expr, expr, expr])

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

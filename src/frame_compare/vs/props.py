"""Frame property extraction functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frame_compare.vs.types import ColorProps

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore


def get_color_props(clip: vs.VideoNode) -> ColorProps:
    """
    Extract color space properties from frame 0.

    Args:
        clip: VapourSynth clip to extract properties from

    Returns:
        ColorProps with primaries, transfer, matrix, color_range

    Note:
        Always reads frame 0 for consistency with load_source().
        Missing properties default per ColorProps Field Mapping table.
    """
    frame = clip.get_frame(0)  # type: ignore
    props = frame.props  # type: ignore

    return ColorProps(
        primaries=int(props.get("_Primaries", 2)),  # type: ignore
        transfer=int(props.get("_Transfer", 2)),  # type: ignore
        matrix=int(props.get("_Matrix", 2)),  # type: ignore
        color_range=int(props.get("_ColorRange", 1)),  # type: ignore
    )


def is_hdr(clip: vs.VideoNode) -> bool:
    """
    Determine if clip is HDR based on frame 0 properties.

    HDR Detection Rule:
        is_hdr = _Transfer in (16, 18) AND _Primaries == 9

    Where:
        - _Transfer == 16: PQ (Perceptual Quantizer)
        - _Transfer == 18: HLG (Hybrid Log-Gamma)
        - _Primaries == 9: BT.2020

    Args:
        clip: VapourSynth clip to check

    Returns:
        True if clip is HDR (PQ or HLG with BT.2020 primaries)

    Note:
        Uses frame 0 properties. Consistent with _detect_hdr() in source.py.
    """
    frame = clip.get_frame(0)  # type: ignore
    props = frame.props  # type: ignore

    transfer = int(props.get("_Transfer", 2))  # type: ignore
    primaries = int(props.get("_Primaries", 2))  # type: ignore

    return transfer in (16, 18) and primaries == 9

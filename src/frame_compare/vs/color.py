"""Color space operations for VapourSynth clips."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frame_compare.vs.types import ColorProps

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore


def infer_color_props(clip: vs.VideoNode, props: ColorProps) -> ColorProps:
    """
    Resolve missing/unspecified color properties for downstream conversions.

    Unspecified handling:
        - For matrix/transfer/primaries: treat value 2 as missing ("unspecified").
        - For color_range: treat value 2 as missing; missing defaults to limited (1).

    Inference rules (deterministic):
        1) HDR signal backfill:
           - If props.transfer in (16, 18):
             - If primaries missing/unspecified, set primaries=9 (BT.2020).
             - If matrix missing/unspecified, set matrix to 9 (BT.2020nc).
           - If props.primaries == 9:
             - If matrix missing/unspecified, set matrix to 9 (BT.2020nc).
        2) SDR backfill by height:
           - If clip.height <= 576: set matrix/transfer/primaries to 6 (SMPTE170M) when missing.
           - If clip.height >= 577 (or height is unavailable):
             set matrix/transfer/primaries to 1 (BT.709) when missing.
        3) color_range is preserved (0 full / 1 limited).

    Returns:
        Resolved ColorProps suitable for resize matrix_in/transfer_in/primaries_in/range_in.
    """
    primaries = props.primaries
    transfer = props.transfer
    matrix = props.matrix
    color_range = props.color_range

    # Normalize range 2 -> 1
    if color_range == 2:
        color_range = 1

    # 1) HDR signal backfill
    if transfer in (16, 18) or primaries == 9:
        if transfer in (16, 18) and primaries == 2:
            primaries = 9

        if matrix == 2:
            # Prefer MATRIX_BT2020_CL, then MATRIX_BT2020_NCL, then 9
            import vapoursynth as vs

            matrix = getattr(vs, "MATRIX_BT2020_CL", getattr(vs, "MATRIX_BT2020_NCL", 9))  # type: ignore

    # 2) SDR backfill by height (if still unspecified)
    if primaries == 2 or transfer == 2 or matrix == 2:
        # Default to BT.709 (1) unless SD (<= 576)
        is_sd = clip.height > 0 and clip.height <= 576
        default_val = 6 if is_sd else 1

        if primaries == 2:
            primaries = default_val
        if transfer == 2:
            transfer = default_val
        if matrix == 2:
            matrix = default_val

    return ColorProps(
        primaries=primaries,
        transfer=transfer,
        matrix=matrix,
        color_range=color_range,
    )


def apply_color_props(clip: vs.VideoNode, props: ColorProps) -> vs.VideoNode:
    """
    Apply color properties to all frames via std.SetFrameProps.

    Sets:
        _Matrix, _Transfer, _Primaries, _ColorRange
    """
    return clip.std.SetFrameProps(
        _Matrix=props.matrix,
        _Transfer=props.transfer,
        _Primaries=props.primaries,
        _ColorRange=props.color_range,
    )


def expand_limited_rgb_to_full(clip: vs.VideoNode) -> vs.VideoNode:
    """
    Expand limited-range integer RGB to full range.

    For integer RGB:
        min_in=16*(2**(bits-8)), max_in=235*(2**(bits-8))
        min_out=0, max_out=(2**bits)-1
        planes=[0, 1, 2]

    For float RGB:
        No-op.
    """
    fmt = clip.format
    if fmt.color_family != 0:  # RGB is 0 in VS
        return clip

    if fmt.sample_type == 1:  # Float
        return clip

    bits = fmt.bits_per_sample
    shift = bits - 8
    min_in = 16 << shift
    max_in = 235 << shift
    max_out = (1 << bits) - 1

    return clip.resize.Point(
        range_in=1,  # Limited
        range=0,  # Full
        min_in=float(min_in),
        max_in=float(max_in),
        min_out=0.0,
        max_out=float(max_out),
        planes=[0, 1, 2],
    )


def to_rgb24(
    clip: vs.VideoNode,
    *,
    props: ColorProps,
    output_range: int = 0,
    expand_to_full: bool = True,
    dither_type: str = "error_diffusion",
) -> vs.VideoNode:
    """
    Convert clip to RGB24 for screenshot rendering.

    Conversion:
        Uses clip.resize.Point with:
        - format=vs.RGB24
        - range=output_range
        - dither_type=dither_type
        - matrix_in/transfer_in/primaries_in from inferred props
        - range_in from inferred props (always passed; 0 full / 1 limited)

    Range expansion:
        If expand_to_full is True AND output_range == 0 AND inferred input range == 1,
        expand via expand_limited_rgb_to_full().

    Output props:
        After conversion (and optional expansion), apply:
        - _Matrix=0 (RGB)
        - _ColorRange=output_range
        - _Transfer and _Primaries set from inferred props
    """
    from vapoursynth import RGB24

    inferred = infer_color_props(clip, props)

    # Convert to RGB24
    rgb = clip.resize.Point(
        format=RGB24,
        matrix_in=inferred.matrix,
        transfer_in=inferred.transfer,
        primaries_in=inferred.primaries,
        range_in=inferred.color_range,
        range=output_range,
        dither_type=dither_type,
    )

    # Optional expansion
    if expand_to_full and output_range == 0 and inferred.color_range == 1:
        rgb = expand_limited_rgb_to_full(rgb)

    # Apply output props
    return rgb.std.SetFrameProps(
        _Matrix=0,
        _Transfer=inferred.transfer,
        _Primaries=inferred.primaries,
        _ColorRange=output_range,
    )

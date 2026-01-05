"""Video source loading and metadata extraction."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from frame_compare.errors import SourceLoadError
from frame_compare.vs.env import ensure_vs_environment, require_plugin
from frame_compare.vs.types import HDRMetadata, SourceInfo

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    import vapoursynth as vs  # type: ignore


def load_source(path: Path, core: vs.Core | None = None) -> SourceInfo:
    """Load video source with automatic format detection.

    Raises:
        PluginNotFoundError: If lsmas plugin is not available (FC-2003, propagates)
        SourceLoadError: If file cannot be opened or is corrupt (FC-4015)
    """
    if core is None:
        core = ensure_vs_environment()

    # Propagates PluginNotFoundError (FC-2003) if lsmas missing
    require_plugin(core, "lsmas")

    # Loader selection per SSOT 1.4 Plugin Detection:
    # Check for LWLibavSource on the namespace, not just namespace existence
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        loader = core.lsmas
    else:
        # require_plugin passed, so core.lw.LWLibavSource must exist
        loader = core.lw

    try:
        clip = loader.LWLibavSource(str(path))
    except Exception as e:
        raise SourceLoadError(path, str(e)) from e

    # Extract properties
    frame = clip.get_frame(0)
    fps = Fraction(clip.fps.numerator, clip.fps.denominator)
    is_hdr, hdr_metadata = _detect_hdr(dict(frame.props))

    return SourceInfo(
        clip=clip,
        width=clip.width,
        height=clip.height,
        num_frames=clip.num_frames,
        fps=fps,
        format=clip.format,
        frame_props=dict(frame.props),
        is_hdr=is_hdr,
        hdr_metadata=hdr_metadata,
    )


def apply_trim(source: SourceInfo, start: int, end: int | None = None) -> vs.VideoNode:
    """Apply frame trim to clip.

    Args:
        start: First frame to include (0-indexed, inclusive)
        end: Last frame to include (0-indexed, inclusive).
             If None, trims to end of clip.

    Returns:
        Trimmed clip with frames [start, end] inclusive.
    """
    if end is None:
        return source.clip[start:]
    return source.clip[start : end + 1]  # end+1 because VS slice is exclusive on right


def _detect_hdr(frame_props: Mapping[str, object]) -> tuple[bool, HDRMetadata | None]:
    """Detect HDR from frame properties per SSOT 5.1 mapping.

    HDR Detection: is_hdr = _Transfer in (16, 18) AND _Primaries == 9
    """
    # Defaults to 2 (unspecified) if missing
    transfer = int(frame_props.get("_Transfer", 2))  # type: ignore
    primaries = int(frame_props.get("_Primaries", 2))  # type: ignore

    is_hdr = transfer in (16, 18) and primaries == 9

    if not is_hdr:
        return (False, None)

    return (
        True,
        HDRMetadata(
            mastering_display=str(frame_props["MasteringDisplayPrimaries"])
            if "MasteringDisplayPrimaries" in frame_props
            else None,
            max_cll=int(frame_props["ContentLightLevelMax"])  # type: ignore
            if "ContentLightLevelMax" in frame_props
            else None,
            max_fall=int(frame_props["ContentLightLevelAverage"])  # type: ignore
            if "ContentLightLevelAverage" in frame_props
            else None,
            color_primaries=primaries,
            transfer=transfer,
            matrix=int(frame_props.get("_Matrix", 2)),  # type: ignore
        ),
    )

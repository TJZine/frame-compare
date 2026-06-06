"""Video source loading and metadata extraction."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from frame_compare.utils.runtime_stderr import suppress_known_lsmash_api3_stderr
from frame_compare.vs.env import ensure_vs_environment, require_plugin
from frame_compare.vs.errors import SourceLoadError
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    from pathlib import Path

    import vapoursynth as vs


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

    # Loader selection:
    # Check for LWLibavSource on the namespace, not just namespace existence
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        loader = core.lsmas
    else:
        # require_plugin passed, so core.lw.LWLibavSource must exist
        loader = core.lw

    try:
        with suppress_known_lsmash_api3_stderr():
            clip = loader.LWLibavSource(str(path))
        frame = clip.get_frame(0)
        fps = Fraction(clip.fps.numerator, clip.fps.denominator)
        is_hdr, hdr_metadata = detect_hdr(dict(frame.props))
    except Exception as e:
        raise SourceLoadError(path, str(e)) from e

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
        source: Loaded source metadata whose clip will be trimmed.
        start: First frame to include (0-indexed, inclusive)
        end: Last frame to include (0-indexed, inclusive).
             If None, trims to end of clip.

    Returns:
        Trimmed clip with frames [start, end] inclusive.
    """
    if end is None:
        return source.clip[start:]
    return source.clip[start : end + 1]  # end+1 because VS slice is exclusive on right

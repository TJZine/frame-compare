"""Video source loading and metadata extraction."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from frame_compare.vs.env import ensure_vs_environment, require_plugin
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs

_INDEX_CONSTRUCTION_FAILURE_MARKER = "failed to construct index"


@dataclass(frozen=True, slots=True)
class LWLibavSourceOptions:
    """Explicit optional decoder settings forwarded to LWLibavSource."""

    threads: int | None = None
    ff_options: str | None = None
    prefer_hw: Literal[1] | None = None


def load_source(
    path: Path,
    core: vs.Core | None = None,
    *,
    decoder_options: LWLibavSourceOptions | None = None,
) -> SourceInfo:
    """Load video source with automatic format detection.

    Raises:
        PluginNotFoundError: If lsmas plugin is not available (FC-2003, propagates)
        SourceLoadError: If file cannot be opened or is corrupt (FC-4015)
    """
    if decoder_options is not None and (
        decoder_options.threads is not None and decoder_options.threads < 0
    ):
        raise ValueError("LWLibavSource thread count must be non-negative")
    if decoder_options is not None and decoder_options.prefer_hw is not None:
        prefer_hw = decoder_options.prefer_hw
        if type(prefer_hw) is not int or prefer_hw != 1:
            raise ValueError("LWLibavSource prefer_hw must be the integer 1 (NVIDIA CUVID) or None")

    if core is None:
        core = ensure_vs_environment()

    try:
        # Propagates PluginNotFoundError (FC-2003) if lsmas missing
        require_plugin(core, "lsmas")

        # Loader selection:
        # Check for LWLibavSource on the namespace, not just namespace existence
        if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
            loader = core.lsmas
        else:
            # require_plugin passed, so core.lw.LWLibavSource must exist
            loader = core.lw

        loader_kwargs: dict[str, int | str] = {}
        if decoder_options is not None:
            if decoder_options.threads is not None:
                loader_kwargs["threads"] = decoder_options.threads
            if decoder_options.ff_options is not None:
                loader_kwargs["ff_options"] = decoder_options.ff_options
            if decoder_options.prefer_hw is not None:
                loader_kwargs["prefer_hw"] = decoder_options.prefer_hw
        adjacent_index_path = Path(f"{path}.lwi")
        try:
            clip = loader.LWLibavSource(str(path), **loader_kwargs)
        except Exception as original_error:
            # L-SMASH may leave or encounter an unusable adjacent index and then
            # fail while trying to rebuild it in place. Retry without writing a
            # cache so callers do not have to delete generated index files.
            if not _is_adjacent_index_construction_failure(
                original_error,
                index_path=adjacent_index_path,
            ):
                raise
            try:
                clip = loader.LWLibavSource(str(path), cache=0, **loader_kwargs)
            except Exception as retry_error:
                raise original_error from retry_error
        frame = clip.get_frame(0)
        fps = Fraction(clip.fps.numerator, clip.fps.denominator)
        is_hdr, hdr_metadata = detect_hdr(dict(frame.props))
    except PluginNotFoundError:
        raise
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


def _is_adjacent_index_construction_failure(
    error: Exception,
    *,
    index_path: Path,
) -> bool:
    """Return whether an L-SMASH construction failure can use cache-free recovery."""
    return index_path.is_file() and _INDEX_CONSTRUCTION_FAILURE_MARKER in str(error).casefold()


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

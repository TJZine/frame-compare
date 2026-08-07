"""Video source loading and metadata extraction."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

from frame_compare.vs.env import ensure_vs_environment, require_plugin
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.runtime_contract import index_cache_token
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


class _LWLibavSourcePlugin(Protocol):
    def LWLibavSource(
        self,
        path: str,
        **kwargs: int | str,
    ) -> vs.VideoNode: ...


_INDEX_CONSTRUCTION_FAILURE_MARKER = "failed to construct index"


@dataclass(frozen=True, slots=True)
class LWLibavSourceOptions:
    """Explicit optional decoder settings forwarded to LWLibavSource.

    Raises:
        ValueError: If ``threads`` is not a non-negative integer, or if
            ``prefer_hw`` is not the integer 1 or ``None``.
    """

    threads: int | None = None
    ff_options: str | None = None
    prefer_hw: Literal[1] | None = None

    def __post_init__(self) -> None:
        """Reject invalid decoder settings before they reach the runtime boundary."""
        if self.threads is not None and (type(self.threads) is not int or self.threads < 0):
            raise ValueError("LWLibavSource thread count must be a non-negative integer or None")

        if self.prefer_hw is not None and (type(self.prefer_hw) is not int or self.prefer_hw != 1):
            raise ValueError("LWLibavSource prefer_hw must be the integer 1 (NVIDIA CUVID) or None")


def load_source(
    path: Path,
    core: vs.Core | None = None,
    *,
    decoder_options: LWLibavSourceOptions | None = None,
) -> SourceInfo:
    """Load video source with automatic format detection.

    Raises:
        PluginNotFoundError: If the L-SMASH Works plugin is unavailable (FC-2003).
        SourceLoadError: If the source cannot be loaded or inspected (FC-4015).
    """
    if core is None:
        core = ensure_vs_environment()

    try:
        # Propagates PluginNotFoundError (FC-2003) if lsmas missing
        require_plugin(core, "lsmas")

        # Loader selection:
        # Check for LWLibavSource on the namespace, not just namespace existence
        if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
            loader = cast(_LWLibavSourcePlugin, core.lsmas)
        else:
            # require_plugin passed, so core.lw.LWLibavSource must exist
            loader = cast(_LWLibavSourcePlugin, core.lw)

        loader_kwargs: dict[str, int | str] = {}
        if decoder_options is not None:
            if decoder_options.threads is not None:
                loader_kwargs["threads"] = decoder_options.threads
            if decoder_options.ff_options is not None:
                loader_kwargs["ff_options"] = decoder_options.ff_options
            if decoder_options.prefer_hw is not None:
                loader_kwargs["prefer_hw"] = decoder_options.prefer_hw
        clip = _load_lwlibav_source(
            loader,
            path=Path(path),
            loader_kwargs=loader_kwargs,
        )
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


def source_index_path(path: Path) -> Path:
    """Return the Frame Compare-owned L-SMASH-Works index path for ``path``."""
    return Path(f"{path}.frame-compare-{index_cache_token()}.lwi")


def _load_lwlibav_source(
    loader: _LWLibavSourcePlugin,
    *,
    path: Path,
    loader_kwargs: dict[str, int | str],
) -> vs.VideoNode:
    index_path = source_index_path(path)
    indexed_kwargs: dict[str, int | str] = {
        "cachefile": str(index_path),
        **loader_kwargs,
    }
    try:
        return loader.LWLibavSource(str(path), **indexed_kwargs)
    except Exception as original_error:
        if not _is_index_construction_failure(original_error):
            raise

        if index_path.is_file():
            try:
                index_path.unlink()
            except OSError:
                pass
            else:
                try:
                    return loader.LWLibavSource(str(path), **indexed_kwargs)
                except Exception:
                    # A cache-free retry remains the last recovery path for an
                    # unwritable or runtime-rejected index location.
                    pass

        try:
            return loader.LWLibavSource(str(path), cache=0, **loader_kwargs)
        except Exception as retry_error:
            raise original_error from retry_error


def _is_index_construction_failure(error: Exception) -> bool:
    """Return whether L-SMASH-Works reported an index-construction failure."""
    return _INDEX_CONSTRUCTION_FAILURE_MARKER in str(error).casefold()


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

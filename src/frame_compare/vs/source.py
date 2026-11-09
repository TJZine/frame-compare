"""Video source loading and metadata extraction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.canvas import validate_canvas_size
from frame_compare.vs.env import ensure_vs_environment, require_plugin
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.hdr_probe import probe_hdr_metadata
from frame_compare.vs.props import detect_hdr, hdr_signal_is_unspecified
from frame_compare.vs.source_admission import SourceAdmission, admit_source, bounded_decoder_options
from frame_compare.vs.source_index_cache import ManagedSourceIndexCache, private_index_directory
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


class _LWLibavSourcePlugin(Protocol):
    def LWLibavSource(
        self,
        path: str,
        **kwargs: int | str,
    ) -> vs.VideoNode: ...


class _VideoNodeWithFps(Protocol):
    fps: Fraction


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
    index_cache: ManagedSourceIndexCache | None = None,
    abort_check: Callable[[], None] = raise_if_cancelling,
) -> SourceInfo:
    """Load video source with automatic format detection.

    Raises:
        PluginNotFoundError: If the L-SMASH Works plugin is unavailable (FC-2003).
        SourceLoadError: If the source cannot be loaded or inspected (FC-4015).
    """
    path = Path(path)
    if path.suffix.lower() == ".lwi":
        raise SourceLoadError(path, "an L-SMASH index cannot be used as source media")
    if core is None:
        raise_if_cancelling()
        core = ensure_vs_environment()

    try:
        abort_check()
        admission = admit_source(path, abort_check=abort_check)

        # Propagates PluginNotFoundError (FC-2003) if lsmas missing
        require_plugin(core, "lsmas")

        loader = _resolve_lwlibav_loader(core)

        loader_kwargs: dict[str, int | str] = {
            "ff_options": bounded_decoder_options(
                decoder_options.ff_options if decoder_options is not None else None
            )
        }
        if decoder_options is not None:
            if decoder_options.threads is not None:
                loader_kwargs["threads"] = decoder_options.threads
            if decoder_options.prefer_hw is not None:
                loader_kwargs["prefer_hw"] = decoder_options.prefer_hw
        clip = _load_lwlibav_source(
            loader,
            path=path,
            loader_kwargs=loader_kwargs,
            admission=admission,
            index_cache=index_cache,
            abort_check=abort_check,
        )
        abort_check()
        validate_canvas_size(clip.width, clip.height, label="Source video")
        frame = clip.get_frame(0)
        clip_fps = cast(_VideoNodeWithFps, clip).fps
        fps = Fraction(clip_fps.numerator, clip_fps.denominator)
        frame_props = dict(frame.props)
        abort_check()
        probed_metadata = None
        if hdr_signal_is_unspecified(frame_props):
            probed_metadata = probe_hdr_metadata(path, streams=(admission.video_stream,))
        is_hdr, hdr_metadata = detect_hdr(frame_props, probed_metadata)
    except (PluginNotFoundError, SourceLoadError):
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
        frame_props=frame_props,
        is_hdr=is_hdr,
        hdr_metadata=hdr_metadata,
    )


def _resolve_lwlibav_loader(core: vs.Core) -> _LWLibavSourcePlugin:
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        return cast(_LWLibavSourcePlugin, core.lsmas)
    raise PluginNotFoundError("lsmas")


def _load_lwlibav_source(
    loader: _LWLibavSourcePlugin,
    *,
    path: Path,
    loader_kwargs: dict[str, int | str],
    admission: SourceAdmission,
    index_cache: ManagedSourceIndexCache | None,
    abort_check: Callable[[], None],
) -> vs.VideoNode:
    def open_source(source: Path, cache: int, index: Path) -> vs.VideoNode:
        # L-SMASH interprets a .lwi source argument as an index, overriding cachefile.
        if source.suffix.lower() == ".lwi":
            raise SourceLoadError(path, "an L-SMASH index cannot be used as source media")
        admission.verify(source)
        clip = loader.LWLibavSource(str(source), cache=cache, cachefile=str(index), **loader_kwargs)
        admission.verify(source)
        return clip

    if index_cache is not None:
        clip = index_cache.try_load(path, open_source, admission=admission, abort_check=abort_check)
        if clip is not None:
            return clip
    abort_check()
    admission.scan(path, abort_check=abort_check)
    with private_index_directory() as directory:
        return open_source(path, 0, directory / "disabled.lwi")


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

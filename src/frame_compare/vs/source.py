"""Video source loading and metadata extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from fractions import Fraction
from hashlib import file_digest
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

from frame_compare.vs.env import ensure_vs_environment, require_plugin
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.hdr_probe import probe_hdr_metadata
from frame_compare.vs.props import detect_hdr, hdr_signal_is_unspecified
from frame_compare.vs.runtime_contract import index_cache_token
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


log = logging.getLogger(__name__)


class _LWLibavSourcePlugin(Protocol):
    def LWLibavSource(
        self,
        path: str,
        **kwargs: int | str,
    ) -> vs.VideoNode: ...


class _VideoNodeWithFps(Protocol):
    fps: Fraction


INDEX_CONSTRUCTION_FAILURE_MARKER = "failed to construct index"


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

        loader = _resolve_lwlibav_loader(core)

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
        clip_fps = cast(_VideoNodeWithFps, clip).fps
        fps = Fraction(clip_fps.numerator, clip_fps.denominator)
        frame_props = dict(frame.props)
        probed_metadata = None
        if hdr_signal_is_unspecified(frame_props):
            probed_metadata = probe_hdr_metadata(Path(path))
        is_hdr, hdr_metadata = detect_hdr(frame_props, probed_metadata)
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
        frame_props=frame_props,
        is_hdr=is_hdr,
        hdr_metadata=hdr_metadata,
    )


def source_index_path(path: Path) -> Path:
    """Return the Frame Compare-owned L-SMASH-Works index path for ``path``."""
    return Path(f"{path}.frame-compare-{index_cache_token()}.lwi")


def validate_source_index(path: Path, core: vs.Core | None = None) -> None:
    """Fail unless the existing owned index opens the source without being rebuilt."""
    source_path = Path(path)
    index_path = source_index_path(source_path)
    try:
        before = _file_sha256(index_path)
    except OSError as error:
        raise SourceLoadError(source_path, f"Warm source index is unavailable: {error}") from error

    if core is None:
        core = ensure_vs_environment()

    try:
        require_plugin(core, "lsmas")
        loader = _resolve_lwlibav_loader(core)
        clip = loader.LWLibavSource(str(source_path), cachefile=str(index_path))
        clip.get_frame(0)
        after = _file_sha256(index_path)
    except PluginNotFoundError:
        raise
    except Exception as error:
        raise SourceLoadError(
            source_path, f"Warm source index validation failed: {error}"
        ) from error

    if after != before:
        raise SourceLoadError(
            source_path,
            "Warm source index changed during validation; regenerate it before benchmarking",
        )


def _resolve_lwlibav_loader(core: vs.Core) -> _LWLibavSourcePlugin:
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        return cast(_LWLibavSourcePlugin, core.lsmas)
    return cast(_LWLibavSourcePlugin, core.lw)


def _file_sha256(path: Path) -> str:
    with path.open("rb") as file:
        return file_digest(file, "sha256").hexdigest()


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
            except OSError as error:
                log.warning(
                    "Could not remove rejected L-SMASH index %s; retrying without an index cache: %s",
                    index_path,
                    error,
                )
            else:
                try:
                    return loader.LWLibavSource(str(path), **indexed_kwargs)
                except Exception as retry_error:
                    # A cache-free retry remains the last recovery path for an
                    # unwritable or runtime-rejected index location.
                    log.warning(
                        "L-SMASH index rebuild failed for %s; retrying without an index cache: %s",
                        path,
                        retry_error,
                    )

        log.warning(
            "Loading %s without an L-SMASH index cache after index construction failed",
            path,
        )

        try:
            return loader.LWLibavSource(str(path), cache=0, **loader_kwargs)
        except Exception as retry_error:
            raise original_error from retry_error


def _is_index_construction_failure(error: Exception) -> bool:
    """Return whether L-SMASH-Works reported an index-construction failure."""
    return INDEX_CONSTRUCTION_FAILURE_MARKER in str(error).casefold()


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

from __future__ import annotations

"""VapourSynth integration helpers used by the frame comparison tool."""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

try:  # Optional dependency during testing.
    import vapoursynth as vs  # type: ignore
except Exception:  # pragma: no cover - tested via injected cores.
    vs = None  # type: ignore


class ClipInitError(RuntimeError):
    """Raised when a clip cannot be created via VapourSynth."""


class ClipProcessError(RuntimeError):
    """Raised when screenshot preparation fails."""


_HDR_PRIMARIES_NAMES = {"bt2020", "bt.2020", "2020"}
_HDR_PRIMARIES_CODES = {9}
_HDR_TRANSFER_NAMES = {"st2084", "pq", "smpte2084", "hlg", "arib-b67"}
_HDR_TRANSFER_CODES = {16, 18}

_SDR_PROPS = {
    "_Matrix": "bt709",
    "_Primaries": "bt709",
    "_Transfer": "bt1886",
    "_ColorRange": "limited",
}


@dataclass(frozen=True)
class _TonemapDefaults:
    tone_mapping: str = "bt2390"
    target_nits: int = 100
    dest_primaries: str = "bt709"
    dest_transfer: str = "bt1886"
    dest_matrix: str = "bt709"
    dest_range: str = "limited"


_TONEMAP_DEFAULTS = _TonemapDefaults()


def _resolve_core(core: Optional[Any]) -> Any:
    if core is not None:
        return core
    if vs is None:
        raise ClipInitError("VapourSynth is not available in this environment")
    return vs.core


def _resolve_source(core: Any) -> Any:
    lsmas = getattr(core, "lsmas", None)
    if lsmas is None:
        raise ClipInitError("VapourSynth core is missing the lsmas plugin")
    source = getattr(lsmas, "LWLibavSource", None)
    if not callable(source):
        raise ClipInitError("lsmas.LWLibavSource is not callable")
    return source


def _ensure_std_namespace(clip: Any, error: RuntimeError) -> Any:
    std = getattr(clip, "std", None)
    if std is None:
        raise error
    return std


def _apply_trim(clip: Any, trims: Tuple[int, int]) -> Any:
    std = _ensure_std_namespace(clip, ClipInitError("Clip is missing std namespace for Trim"))
    first, last = trims
    try:
        return std.Trim(first=first, last=last)
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError("Failed to apply trim to clip") from exc


def _apply_fps_map(clip: Any, fps_map: Tuple[int, int]) -> Any:
    std = _ensure_std_namespace(clip, ClipInitError("Clip is missing std namespace for AssumeFPS"))
    num, den = fps_map
    if den <= 0:
        raise ClipInitError("fps_map denominator must be positive")
    try:
        return std.AssumeFPS(num=num, den=den)
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError("Failed to apply FPS mapping to clip") from exc


def init_clip(
    path: str,
    *,
    trims: Tuple[int, int] | None = None,
    fps_map: Tuple[int, int] | None = None,
    core: Optional[Any] = None,
) -> Any:
    """Initialise a VapourSynth clip for subsequent processing."""

    resolved_core = _resolve_core(core)
    source = _resolve_source(resolved_core)
    try:
        clip = source(path)
    except Exception as exc:  # pragma: no cover - exercised via mocks
        raise ClipInitError(f"Failed to open clip '{path}': {exc}") from exc

    if trims is not None:
        clip = _apply_trim(clip, trims)
    if fps_map is not None:
        clip = _apply_fps_map(clip, fps_map)
    return clip


def _normalise_property_value(value: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _value_matches(value: Any, names: set[str], codes: set[int]) -> bool:
    if isinstance(value, int):
        return value in codes
    value = _normalise_property_value(value)
    if isinstance(value, str):
        return value in names
    return False


def _extract_frame_props(clip: Any) -> Mapping[str, Any]:
    getter = getattr(clip, "get_frame_props", None)
    if callable(getter):
        props = getter()
        if isinstance(props, Mapping):
            return props
    frame_props = getattr(clip, "frame_props", None)
    if isinstance(frame_props, Mapping):
        return frame_props
    return {}


def _props_signal_hdr(props: Mapping[str, Any]) -> bool:
    primaries = props.get("_Primaries") or props.get("Primaries")
    transfer = props.get("_Transfer") or props.get("Transfer")
    if not _value_matches(primaries, _HDR_PRIMARIES_NAMES, _HDR_PRIMARIES_CODES):
        return False
    return _value_matches(transfer, _HDR_TRANSFER_NAMES, _HDR_TRANSFER_CODES)


def _tonemap_defaults(cfg: Any) -> _TonemapDefaults:
    base = _TONEMAP_DEFAULTS
    return _TonemapDefaults(
        tone_mapping=getattr(cfg, "tone_mapping", base.tone_mapping),
        target_nits=getattr(cfg, "target_nits", base.target_nits),
        dest_primaries=getattr(cfg, "dest_primaries", base.dest_primaries),
        dest_transfer=getattr(cfg, "dest_transfer", base.dest_transfer),
        dest_matrix=getattr(cfg, "dest_matrix", base.dest_matrix),
        dest_range=getattr(cfg, "dest_range", base.dest_range),
    )


def _set_sdr_props(clip: Any) -> Any:
    std = _ensure_std_namespace(clip, ClipProcessError("clip.std.SetFrameProps is unavailable"))
    setter = getattr(std, "SetFrameProps", None)
    if not callable(setter):  # pragma: no cover - defensive
        raise ClipProcessError("clip.std.SetFrameProps is unavailable")
    return setter(**_SDR_PROPS)


def process_clip_for_screenshot(clip: Any, file_name: str, cfg: Any) -> Any:
    """Apply HDR→SDR processing to *clip* when necessary."""

    props = _extract_frame_props(clip)
    if not _props_signal_hdr(props):
        return clip

    core = getattr(clip, "core", None)
    if core is None:
        raise ClipProcessError("Clip has no associated VapourSynth core")

    libplacebo = getattr(core, "libplacebo", None)
    tonemap = getattr(libplacebo, "Tonemap", None) if libplacebo is not None else None
    if not callable(tonemap):
        raise ClipProcessError("libplacebo.Tonemap is unavailable")

    defaults = _tonemap_defaults(cfg)
    try:
        tonemapped = tonemap(
            clip,
            tone_mapping=defaults.tone_mapping,
            target_nits=defaults.target_nits,
            dest_primaries=defaults.dest_primaries,
            dest_transfer=defaults.dest_transfer,
            dest_matrix=defaults.dest_matrix,
            dest_range=defaults.dest_range,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipProcessError(f"libplacebo tonemapping failed: {exc}") from exc

    return _set_sdr_props(tonemapped)

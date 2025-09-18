"""Configuration helpers for the tonemapping subsystem."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, replace
import hashlib
from typing import Any, Mapping, MutableMapping

from .exceptions import TonemapConfigError

_VALID_PRESETS = {"reference", "contrast", "filmic", "custom"}
_VALID_METRICS = {"abs", "ssim", "psnr", "deltae"}
_VALID_FUNCS = {"bt2390", "mobius", "hable"}
_ALIAS_FUNCS = {"bt.2390": "bt2390", "bt-2390": "bt2390", "pq": "bt2390"}
ALIAS_KEYS = {
    "tone_mapping": "func",
    "target_nits": "dst_max",
    "dest_primaries": "dst_primaries",
    "dest_transfer": "dst_transfer",
    "dest_matrix": "dst_matrix",
    "dest_range": "dst_range",
}

_PRESET_DEFAULTS: dict[str, dict[str, Any]] = {
    "reference": {
        "func": "bt2390",
        "dpd": False,
        "dst_max": 100.0,
        "dst_min": 0.0,
        "gamut_mapping": "clip",
        "smoothing_period": 3,
        "scene_threshold_low": 0.12,
        "scene_threshold_high": 0.32,
    },
    "contrast": {
        "func": "mobius",
        "dpd": True,
        "dst_max": 120.0,
        "dst_min": 0.005,
        "gamut_mapping": "saturate",
        "smoothing_period": 2,
        "scene_threshold_low": 0.05,
        "scene_threshold_high": 0.18,
    },
    "filmic": {
        "func": "hable",
        "dpd": True,
        "dst_max": 110.0,
        "dst_min": 0.001,
        "gamut_mapping": "desaturate",
        "smoothing_period": 5,
        "scene_threshold_low": 0.08,
        "scene_threshold_high": 0.26,
    },
}


def _normalise_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _normalise_func(name: str) -> str:
    lowered = name.strip().lower()
    return _ALIAS_FUNCS.get(lowered, lowered)


@dataclass(slots=True)
class TMConfig:
    """Tonemap configuration resolved from TOML/CLI inputs."""

    preset: str = "reference"
    func: str = "bt2390"
    dpd: bool = False
    dst_max: float = 100.0
    dst_min: float = 0.0
    gamut_mapping: str = "clip"
    smoothing_period: int = 3
    scene_threshold_low: float = 0.12
    scene_threshold_high: float = 0.32
    overlay: bool = False
    verify: bool = False
    verify_metric: str = "abs"
    verify_frame: int | None = None
    verify_auto_search: bool = True
    verify_search_max: int = 180
    verify_search_step: int = 12
    verify_start_frame: int = 0
    verify_luma_thresh: float = 0.45
    use_dovi: bool = True
    always_try_placebo: bool = False
    dst_primaries: str = "bt709"
    dst_transfer: str = "bt1886"
    dst_matrix: str = "bt709"
    dst_range: str = "limited"

    _explicit_fields: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self.preset = _normalise_key(self.preset) or "reference"
        self.func = _normalise_func(self.func or "bt2390")
        self.verify_metric = _normalise_key(self.verify_metric or "abs")
        self.gamut_mapping = _normalise_key(self.gamut_mapping or "clip")
        self.dst_primaries = _normalise_key(self.dst_primaries or "bt709")
        self.dst_transfer = _normalise_key(self.dst_transfer or "bt1886")
        self.dst_matrix = _normalise_key(self.dst_matrix or "bt709")
        self.dst_range = _normalise_key(self.dst_range or "limited")

        self._seed_explicit_defaults()

    def _seed_explicit_defaults(self) -> None:
        for field_def in self.__dataclass_fields__.values():
            if not field_def.init or field_def.name.startswith("_"):
                continue
            default = field_def.default
            if default is MISSING and field_def.default_factory is not MISSING:
                default = field_def.default_factory()
            if default is MISSING:
                continue
            if getattr(self, field_def.name) != default:
                self._explicit_fields.add(field_def.name)

    @property
    def tone_mapping(self) -> str:
        """Compatibility accessor for legacy callers."""

        return self.func

    @property
    def target_nits(self) -> float:
        """Compatibility accessor for legacy callers."""

        return self.dst_max

    def resolved(self) -> TMConfig:
        """Return a validated copy with preset defaults applied."""

        clone = replace(self)
        clone._explicit_fields = set(self._explicit_fields)
        clone._apply_preset_defaults()
        clone._validate()
        return clone

    def mark_explicit(self, *fields: str) -> None:
        for field_name in fields:
            self._explicit_fields.add(field_name)

    def _apply_preset_defaults(self) -> None:
        if self.preset not in _VALID_PRESETS:
            raise TonemapConfigError("preset", f"must be one of: {sorted(_VALID_PRESETS)}")
        if self.preset == "custom":
            return
        defaults = _PRESET_DEFAULTS.get(self.preset, {})
        for key, value in defaults.items():
            if key not in self._explicit_fields:
                setattr(self, key, value)

    def _validate(self) -> None:
        if self.func not in _VALID_FUNCS:
            raise TonemapConfigError("func", f"must be one of: {sorted(_VALID_FUNCS)}")
        if self.dst_max <= 0:
            raise TonemapConfigError("dst_max", "must be greater than zero")
        if self.dst_min < 0:
            raise TonemapConfigError("dst_min", "must be >= 0")
        if self.dst_min > self.dst_max:
            raise TonemapConfigError("dst_min", "must be <= dst_max")
        if self.smoothing_period < 0:
            raise TonemapConfigError("smoothing_period", "must be >= 0")
        if self.scene_threshold_low < 0 or self.scene_threshold_high < 0:
            raise TonemapConfigError("scene_threshold", "thresholds must be >= 0")
        if self.scene_threshold_low > self.scene_threshold_high:
            raise TonemapConfigError("scene_threshold_low", "must be <= scene_threshold_high")
        if self.verify_metric not in _VALID_METRICS:
            raise TonemapConfigError("verify_metric", f"must be one of: {sorted(_VALID_METRICS)}")
        if self.verify_frame is not None and self.verify_frame < 0:
            raise TonemapConfigError("verify_frame", "must be >= 0 when set")
        if self.verify_search_max <= 0:
            raise TonemapConfigError("verify_search_max", "must be > 0")
        if self.verify_search_step <= 0:
            raise TonemapConfigError("verify_search_step", "must be > 0")
        if self.verify_luma_thresh < 0 or self.verify_luma_thresh > 1:
            raise TonemapConfigError("verify_luma_thresh", "must be between 0 and 1")

    def to_libplacebo_kwargs(self) -> dict[str, Any]:
        return {
            "tone_mapping": self.func,
            "dynamic_peak_detection": int(bool(self.dpd)),
            "dst_max": float(self.dst_max),
            "dst_min": float(self.dst_min),
            "gamut_mapping": self.gamut_mapping,
            "smoothing_period": int(self.smoothing_period),
            "scene_threshold_low": float(self.scene_threshold_low),
            "scene_threshold_high": float(self.scene_threshold_high),
            "dst_csp": self.dst_matrix,
            "dst_prim": self.dst_primaries,
            "dst_tf": self.dst_transfer,
        }

    def fingerprint(self) -> str:
        """Return a short hash for overlay/debug tracing."""

        payload = repr(
            (
                self.preset,
                self.func,
                self.dpd,
                self.dst_max,
                self.dst_min,
                self.gamut_mapping,
                self.smoothing_period,
                self.scene_threshold_low,
                self.scene_threshold_high,
                self.use_dovi,
                self.always_try_placebo,
            )
        ).encode("utf-8")
        return hashlib.sha1(payload).hexdigest()[:8]

    def merged(self, **overrides: Any) -> TMConfig:
        clone = replace(self)
        for key, value in overrides.items():
            key_norm = _normalise_key(key)
            alias = ALIAS_KEYS.get(key_norm, key_norm)
            if not hasattr(clone, alias):
                raise TonemapConfigError(alias, "unknown field in overrides")
            setattr(clone, alias, value)
            clone.mark_explicit(alias)
        return clone

    def as_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "func": self.func,
            "dpd": self.dpd,
            "dst_max": self.dst_max,
            "dst_min": self.dst_min,
            "gamut_mapping": self.gamut_mapping,
            "smoothing_period": self.smoothing_period,
            "scene_threshold_low": self.scene_threshold_low,
            "scene_threshold_high": self.scene_threshold_high,
            "overlay": self.overlay,
            "verify": self.verify,
            "verify_metric": self.verify_metric,
            "verify_frame": self.verify_frame,
            "verify_auto_search": self.verify_auto_search,
            "verify_search_max": self.verify_search_max,
            "verify_search_step": self.verify_search_step,
            "verify_start_frame": self.verify_start_frame,
            "verify_luma_thresh": self.verify_luma_thresh,
            "use_dovi": self.use_dovi,
            "always_try_placebo": self.always_try_placebo,
            "dst_primaries": self.dst_primaries,
            "dst_transfer": self.dst_transfer,
            "dst_matrix": self.dst_matrix,
            "dst_range": self.dst_range,
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> TMConfig:
        prepared: MutableMapping[str, Any] = {}
        explicit: set[str] = set()
        for raw_key, value in mapping.items():
            key_norm = _normalise_key(raw_key)
            alias = ALIAS_KEYS.get(key_norm, key_norm)
            if alias not in cls.__dataclass_fields__:
                raise TonemapConfigError(alias, "unknown field in tonemap section")
            prepared[alias] = value
            explicit.add(alias)
        cfg = cls(**prepared)
        cfg._explicit_fields = explicit
        return cfg


DEFAULT_TM_CONFIG = TMConfig().resolved()

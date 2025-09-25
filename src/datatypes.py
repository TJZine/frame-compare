"""Configuration dataclasses for frame comparison tool."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


@dataclass
class AnalysisConfig:
    """Options controlling frame analysis, selection, and data caching."""

    frame_count_dark: int = 20
    frame_count_bright: int = 10
    frame_count_motion: int = 15
    user_frames: List[int] = field(default_factory=list)
    random_frames: int = 15
    save_frames_data: bool = True
    downscale_height: int = 480
    step: int = 2
    analyze_in_sdr: bool = True
    use_quantiles: bool = True
    dark_quantile: float = 0.20
    bright_quantile: float = 0.80
    motion_use_absdiff: bool = False
    motion_scenecut_quantile: float = 0.0
    screen_separation_sec: int = 6
    motion_diff_radius: int = 4
    analyze_clip: str = ""
    random_seed: int = 20202020
    frame_data_filename: str = "generated.compframes"
    skip_head_seconds: float = 0.0
    skip_tail_seconds: float = 0.0
    ignore_lead_seconds: float = 0.0
    ignore_trail_seconds: float = 0.0
    min_window_seconds: float = 5.0


@dataclass
class ScreenshotConfig:
    """Screenshot export behavior, renderer selection, and geometry tweaks."""

    directory_name: str = "screens"
    add_frame_info: bool = True
    use_ffmpeg: bool = False
    compression_level: int = 1
    upscale: bool = True
    single_res: int = 0
    mod_crop: int = 2
    letterbox_pillarbox_aware: bool = True


@dataclass
class ColorConfig:
    """HDR tonemapping, overlay, and verification controls."""

    enable_tonemap: bool = True
    preset: str = "reference"
    tone_curve: str = "bt.2390"
    dynamic_peak_detection: bool = True
    target_nits: float = 100.0
    dst_min_nits: float = 0.1
    overlay_enabled: bool = True
    overlay_text_template: str = "TM:{tone_curve} dpd={dynamic_peak_detection} dst={target_nits}nits"
    verify_enabled: bool = True
    verify_frame: Optional[int] = None
    verify_auto: bool = True
    verify_start_seconds: float = 10.0
    verify_step_seconds: float = 10.0
    verify_max_seconds: float = 90.0
    verify_luma_threshold: float = 0.10
    strict: bool = False


@dataclass
class SlowpicsConfig:
    """slow.pics upload automation flags and metadata."""

    auto_upload: bool = False
    collection_name: str = ""
    is_hentai: bool = False
    is_public: bool = True
    tmdb_id: str = ""
    remove_after_days: int = 0
    webhook_url: str = ""
    open_in_browser: bool = True
    create_url_shortcut: bool = True
    delete_screen_dir_after_upload: bool = True


@dataclass
class NamingConfig:
    """Filename parsing and display preferences."""

    always_full_filename: bool = True
    prefer_guessit: bool = True


@dataclass
class PathsConfig:
    """Filesystem paths configured by the user."""

    input_dir: str = "."


@dataclass
class RuntimeConfig:
    """Runtime safeguards such as memory limits."""

    ram_limit_mb: int = 8000
    vapoursynth_python_paths: List[str] = field(default_factory=list)


@dataclass
class OverridesConfig:
    """Clip-specific overrides for trimming and frame rate adjustments."""

    trim: Dict[str, int] = field(default_factory=dict)
    trim_end: Dict[str, int] = field(default_factory=dict)
    change_fps: Dict[str, Union[List[int], str]] = field(default_factory=dict)


@dataclass
class AppConfig:
    """Aggregated configuration loaded from the user-provided TOML file."""

    analysis: AnalysisConfig
    screenshots: ScreenshotConfig
    slowpics: SlowpicsConfig
    naming: NamingConfig
    paths: PathsConfig
    runtime: RuntimeConfig
    overrides: OverridesConfig
    color: ColorConfig

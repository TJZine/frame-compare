from dataclasses import dataclass, field
from typing import Dict, List, Union

@dataclass
class AnalysisConfig:
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

@dataclass
class ScreenshotConfig:
    directory_name: str = "screens"
    add_frame_info: bool = True
    use_ffmpeg: bool = False
    compression_level: int = 1
    upscale: bool = True
    single_res: int = 0
    mod_crop: int = 2
    letterbox_pillarbox_aware: bool = True

@dataclass
class SlowpicsConfig:
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
    always_full_filename: bool = True
    prefer_guessit: bool = True

@dataclass
class PathsConfig:
    input_dir: str = "."

@dataclass
class RuntimeConfig:
    ram_limit_mb: int = 8000

@dataclass
class OverridesConfig:
    trim: Dict[str, int] = field(default_factory=dict)
    trim_end: Dict[str, int] = field(default_factory=dict)
    change_fps: Dict[str, Union[List[int], str]] = field(default_factory=dict)

@dataclass
class AppConfig:
    analysis: AnalysisConfig
    screenshots: ScreenshotConfig
    slowpics: SlowpicsConfig
    naming: NamingConfig
    paths: PathsConfig
    runtime: RuntimeConfig
    overrides: OverridesConfig

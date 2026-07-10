"""Default configuration template for Frame Compare."""

DEFAULT_CONFIG_TOML = """\
# Frame Compare Configuration
# See docs for full options

[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[sources]
# reference = "auto"
# analysis_source = "reference"  # reference, fastest, or a source selector
# match_fps = "majority"  # opt-in; timing metadata only, no frame resampling
# Add per-source overrides with tables such as:
# [sources.overrides."encode-a.mkv"]
# trim_start_frames = 0
# trim_end_frames = 0
# effective_fps = "24000/1001"

[analysis]
user_frames = []
random_frame_count = 10
dark_frame_count = 0
bright_frame_count = 0
motion_frame_count = 0
random_seed = 42
performance_mode = "quality"
ignore_lead_seconds = 0.0
ignore_trail_seconds = 0.0
min_window_seconds = 5.0
dark_quantile = 0.05
bright_quantile = 0.95

[audio_alignment]
enable = true
sample_rate = 8000
max_offset_seconds = 30.0
use_vspreview = false
force_interactive = false
cache_results = true
previous_offsets = "disabled"
correlation_mode = "raw_fft"
preprocessing_mode = "none"
channel_strategy = "mono_downmix"
confidence_threshold = 0.0
ambiguity_peak_ratio = 1.0
window_length_seconds = 0.0
window_stride_seconds = 0.0
minimum_valid_windows = 1
consensus_minimum_ratio = 1.0
refinement_mode = "disabled"
# refinement_sample_rate = null
# reference_stream = null
comparison_streams = {}

[screenshots]
use_ffmpeg = false
overlay_mode = "standard"
include_frame_number = true
png_compression = 6
ffmpeg_timeout_seconds = 30.0
geometry_mode = "native"
active_rect_detection = "aspect_ratio"
aligned_scale_policy = "largest_active"
# aligned_target_width = 3840
# aligned_target_height = 2160
vs_writer = "auto"

[color]
enable_tonemap = true
preset = "reference"
target_nits = 100
tone_curve = "bt2390"
gamma_lift = false
contrast_recovery = 0.3

[slowpics]
auto_upload = false
confirm_upload_after_report = false
visibility = "unlisted"
delete_after_upload = false
timeout_seconds = 60.0
max_retries = 3
copy_url_to_clipboard = true
open_in_browser = true
create_url_shortcut = true
# webhook_url = null

[tmdb]
# api_key = "your-api-key"
enabled = true
unattended = false
timeout_seconds = 10.0
year_tolerance = 2
# category_preference = "movie"  # optional: "movie" or "tv"

[report]
enable = true
# output_dir = null  # defaults to screenshots_dir
default_mode = "slider"
include_filmstrip = true
embed_images = false
auto_open = true

[diagnostics]
per_frame_nits = false

[logging]
level = "INFO"
format = "console"
"""

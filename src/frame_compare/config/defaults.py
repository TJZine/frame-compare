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

[analysis]
frame_count = 10
random_seed = 42
save_frames_data = true
selection_mode = "mixed"
dark_quantile = 0.05
bright_quantile = 0.95

[audio_alignment]
enable = true
sample_rate = 8000
max_offset_seconds = 30.0
use_vspreview = false
force_interactive = false
cache_results = true

[screenshots]
use_ffmpeg = false
directory_name = "screenshots"
overlay_mode = "standard"
include_frame_number = true
png_compression = 6
ffmpeg_timeout_seconds = 30.0

[color]
enable_tonemap = true
preset = "reference"
target_nits = 203
tone_curve = "bt2390"
gamma_lift = false
contrast_recovery = 0.0

[slowpics]
auto_upload = false
visibility = "unlisted"
delete_after_upload = false
timeout_seconds = 60.0
max_retries = 3

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

[dovi]
enable = true
# dovi_tool_path = null  # auto-detect from PATH
cache_results = true

[diagnostics]
per_frame_nits = false
show_hdr_info = false
frame_timing = false

[logging]
level = "INFO"
format = "console"
# file = null
"""

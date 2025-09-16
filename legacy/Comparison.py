r"""
This script was originally written for VS R53 and Python 3.9, and has been tested on VS R65 and Python 3.11.

You'll need:
- VapourSynth (https://github.com/vapoursynth/vapoursynth/releases)
- "pip install anitopy guessit pyperclip requests requests_toolbelt natsort vstools rich colorama" in terminal (without quotes)
- "vsrepo install fpng lsmas sub" in terminal (without quotes) or the following installed to your usual VapourSynth plugins folder:
    - https://github.com/Mikewando/vsfpng
    - https://github.com/AkarinVS/L-SMASH-Works/releases/latest
    - https://github.com/vapoursynth/subtext/releases/latest
    - Note: plugins folder is typically found in "%AppData%\Roaming\VapourSynth\plugins64" or "C:\Program Files\VapourSynth\plugins"
- Optional: If using FFmpeg, it must be installed and in PATH.

How to use:
- Drop comp.py into a folder with the video files you want to compare.
- (Recommended) Rename your files to have the typical [Group] Show - Ep.mkv naming, since the script will try to parse the group and show name.
  e.g. [JPBD] Youjo Senki - 01.m2ts; [Vodes] Youjo Senki - 01.mkv.
- Change variables below.
- Run comp.py.
"""

# Ram limit (in MB)
ram_limit = 8000

# Number of dark, bright, and high motion frames to algorithmically select.
frame_count_dark = 20
frame_count_bright = 10
frame_count_motion = 15
# Choose your own frames to export. Does not decrease the number of algorithmically selected frames.
user_frames = []
# Number of frames to choose randomly. Completely separate from frame_count_bright, frame_count_dark, and save_frames. Will change every time you run the script.
random_frames = 15

# Save the brightness data in a text file so it doesn't have to be reanalysed next time the script is run. Frames will be reanalysed if show/movie name or episode numbers change.
# Does not save user_frames or random_frames.
save_frames = True

# Print frame info on screenshots.
frame_info = True
# Upscale videos to make the clips match the highest found res.
upscale = True
# Scale all videos to one vertical resolution. Set to 0 to disable, otherwise input the desired vertical res.
single_res = 0
# Use FFmpeg as the image renderer. If false, fpng is used instead
ffmpeg = False
# Compression level. For FFmpeg, range is 0-100. For fpng, 0 is fast, 1 is slow, 2 is uncompressed.
compression = 1
# Naming behavior for labels and slow.pics image names.
# When True (default), use the full filename for display/overlay and slow.pics image names.
# When False, prefer release group naming and shortened-difference display as in prior behavior.
always_full_filename = True
# Prefer GuessIt over Anitopy for filename parsing (movies/TV). Falls back automatically if GuessIt is unavailable.
prefer_guessit = True
# Analysis controls (off by default to preserve behavior)
# Downscale analysis clip to this height (0 disables). Speeds up stats and motion analysis.
analysis_downscale_h = 480
# Sample every Nth frame when measuring brightness/motion (1 = every frame).
analysis_step = 2
# Convert HDR sources to SDR for luma analysis (detects PQ/HLG+BT.2020). Slightly slower.
analyze_in_sdr = True
# Use percentile thresholds for dark/bright selection instead of fixed bands.
analysis_use_quantiles = True
# Dark/Bright quantiles if enabled (0..1). Example: 0.2 = darkest 20%, 0.8 = brightest 20%.
dark_quantile = 0.20
bright_quantile = 0.80
# Prefer absolute difference for motion metric instead of Prewitt edge magnitude.
motion_use_absdiff = False
# Exclude likely scene cuts in motion selection by filtering frames with diff above this quantile (0 disables).
motion_scenecut_quantile = 0.0
# --- Cropping/Geometry Settings ---
# Align *both* edges to this modulus. Use 2 for 4:2:0 sources; 4 or 8 if you require stricter alignment.
mod_crop = 2
letterbox_pillarbox_aware = True


# Automatically upload to slow.pics.
slowpics = False
# Flags to toggle for slowpics settings.
hentai_flag = False
public_flag = True
# TMDB ID of show or movie being comped. Should be in the format "TV_XXXXXX" or "MOVIE_XXXXXX".
tmdbID = ""
# Remove the comparison after this many days. Set to 0 to disable.
remove_after = 0
# Output slow.pics link to discord webhook. Disabled if empty.
webhook_url = r""
# Automatically open slow.pics url in default browser
browser_open = True
# Create a URL shortcut for each comparison uploaded.
url_shortcut = True
# Automatically delete the screenshot directory after uploading to slow.pics.
delete_screen_dir = True

"""
Used to trim clips, or add blank frames to the beginning of a clip.
Clips are taken in alphabetical order of the filenames.
First input can be the filename, group name, or index of the file. Second input must be an integer.

Example:
trim_dict = {0: 1000, "Vodes": 1046, 3:-50}
trim_dict_end = {"Youjo Senki - 01.mkv": 9251, 4: -12}
First clip will start at frame 1000.
Clip with group name "Vodes" will start at frame 1046.
Clip with filename "Youjo Senki - 01.mkv" will end at frame 9251.
Fourth clip will have 50 blank frames appended to its start.
Fifth clip will end 12 frames early.

Note:
If multiple files have the same group name, the trim will be applied to all of them.
"""
trim_dict = {}
trim_dict_end = {}

"""
Actively adjusts a clip's fps to a target. Useful for sources which incorrectly convert 23.976fps to 24fps.
First input can be the filename, group name, or index of the file. 
Second input must be a fraction split into a list. Numerator comes first, denominator comes second.
Second input can also be the string "set". This will make all other files, if unspecified fps, use the set file's fps.

Example:
change_fps = {0: [24, 1], 1: [24000, 1001]}
First clip will have its fps adjusted to 24
Second clip will have its fps adjusted to 23.976

Example 2:
change_fps = {0: [24, 1], "MTBB": "set"}
First clip will have its fps adjusted to 24
Every other clip will have its fps adjusted to match MTBB's

Note:
If multiple files have the same group name, the specified fps will be applied to all of them.
"""
change_fps = {}

"""
Specify which clip will be analyzed for frame selection algorithm.
Input can be the filename, group name, or index of the file.
By default will select the file which can be accessed the fastest.
"""
analyze_clip = ""

##### Advanced Settings #####

# Random seed to use in frame selection algorithm. May change selected frames. Recommended to leave as default
random_seed = 20202020
# Filename of the text file in which the brightness data will be stored. Recommended to leave as default.
frame_filename = "generated.compframes"
# Directory in which the screenshots will be kept
screen_dirname = "screens"
# Minimum time between dark, light, and random frames, in seconds. Motion frames use a quarter of this value
screen_separation = 6
# Number of frames in each direction over which the motion data will be averaged out. So a radius of 4 would take the average of 9 frames, the frame in the middle, and 4 in each direction.
# Higher value will make it less likely scene changes get picked up as motion, but may lead to less precise results.
motion_diff_radius = 4

### Not recommended to change stuff below
import os, sys, time, textwrap, re, uuid, random, pathlib, requests, vstools, webbrowser, colorama, shutil, fractions, subprocess, math
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from natsort import os_sorted
import anitopy as ani
try:
    from guessit import guessit as _guessit
    GUESSIT_AVAILABLE = True
except Exception:
    _guessit = None
    GUESSIT_AVAILABLE = False
import pyperclip as pc
import vapoursynth as vs
# --- Unified print wrapper (defined early so it's available everywhere) ---
def printwrap(text: str, width: int=os.get_terminal_size().columns, end: str="\n", *args, **kwargs) -> None:
    """
    Prints text with smart wrapping using textwrap.fill().

    :param text:  Text to wrap and display.
    :param width: Width of wrapping area, default to terminal width.
    :param end:   Passed to print().
    """
    try:
        print(textwrap.fill(str(text), width, *args, **kwargs), end=end)
    except Exception:
        # Last resort: plain print
        try:
            print(str(text), end=end)
        except Exception:
            print(repr(text), end=end)

# --- In-file tonemap configuration ---
from dataclasses import dataclass

@dataclass
class TMConfig:
    func: str = "bt.2390"   # "bt.2390", "mobius", "hable"
    dpd: int = 1            # 1=on, 0=off (dynamic peak detection)
    dst_max: float = 100.0  # SDR target nits (80-120 common)
    overlay: bool = False   # stamp settings on screenshots
    verify: bool = False    # print Δ vs naive SDR on a chosen frame

# Presets: "reference" (bt.2390/100nits/dpd=1), "contrast" (mobius/120nits/dpd=0), "filmic" (hable/100nits/dpd=1), or "custom"
TM_PRESET = "custom"  # change to "custom" to set exact values below

def _preset_config(name: str) -> TMConfig:
    n = (name or "").lower()
    if n == "contrast":
        return TMConfig(func="mobius", dpd=0, dst_max=120.0, overlay=False, verify=False)
    if n == "filmic":
        return TMConfig(func="hable", dpd=1, dst_max=100.0, overlay=False, verify=False)
    return TMConfig(func="bt.2390", dpd=1, dst_max=100.0, overlay=False, verify=False)

# If you pick "custom", set your values here:
CONFIG = _preset_config(TM_PRESET) if TM_PRESET != "custom" else TMConfig(
    func="bt.2390",
    dpd=0,
    dst_max=120.0,
    overlay=True,
    verify=True,
)

TM_FUNC = CONFIG.func
TM_DPD = CONFIG.dpd
DST_MAX = CONFIG.dst_max
OVERLAY = CONFIG.overlay
VERIFY = CONFIG.verify

# Verification frame selection (for better signal than frame 0)
# - Set VERIFY_FRAME to an integer to force a specific frame index (e.g., 41105)
# - Otherwise, AUTO: search for the first "bright enough" frame in the early part of the clip.
VERIFY_FRAME: int | None = None
VERIFY_AUTO_SEARCH: bool = True
VERIFY_SEARCH_MAX: int = 2000   # scan up to this many frames (or clip length), cheap step
VERIFY_SEARCH_STEP: int = 240   # sample every 240 frames (~10s @ 23.976fps)
VERIFY_START_FRAME: int = 240  # skip the first ~10s to avoid black/credits
VERIFY_LUMA_THRESH: float = 0.10  # stricter avg-luma threshold (0..1) so we avoid frame 0


printwrap(f" Tonemap preset={TM_PRESET} func={TM_FUNC} dpd={TM_DPD} dst_max={DST_MAX} overlay={OVERLAY} verify={VERIFY}")

# --- Helper: ensure RGB clip has props libplacebo expects ---
def _normalize_props_for_placebo_rgb16(rgb16, transfer_in, primaries_in):
    c = rgb16
    c = c.std.SetFrameProp(prop="_Matrix", intval=0)
    if transfer_in is not None:
        c = c.std.SetFrameProp(prop="_Transfer", intval=int(transfer_in))
    if primaries_in is not None:
        c = c.std.SetFrameProp(prop="_Primaries", intval=int(primaries_in))
    c = c.std.SetFrameProp(prop="_ColorRange", intval=0)
    return c

# --- Helper: deduce src_csp from props (common HDR cases) ---
def _deduce_src_csp_from_props(transfer_in, primaries_in):
    # PQ(16)+BT.2020(9) -> 1 ; HLG(18)+BT.2020(9) -> 2 ; else None (let placebo infer)
    if transfer_in == 16 and primaries_in == 9:
        return 1
    if transfer_in == 18 and primaries_in == 9:
        return 2
    return None



def _pick_verify_frame(clip: vs.VideoNode) -> int:
    """
    Choose a frame index for VERIFY:
      - explicit VERIFY_FRAME wins
      - otherwise skip first ~10s, sample every VERIFY_SEARCH_STEP up to VERIFY_SEARCH_MAX
      - pick first frame with avg luma >= VERIFY_LUMA_THRESH
      - else pick the brightest sampled, else middle of clip
    Never returns 0 unless you force VERIFY_FRAME=0.
    """
    try:
        # 0) Explicit override
        if isinstance(VERIFY_FRAME, int):
            idx = max(0, min(clip.num_frames - 1, VERIFY_FRAME))
            printwrap(f"[VERIFY] using configured frame {idx}")
            return idx

        nf = getattr(clip, "num_frames", 0)
        if nf <= 0:
            printwrap("[VERIFY] clip has no frames; using 0")
            return 0

        # 1) Auto disabled → middle
        if not VERIFY_AUTO_SEARCH:
            mid = max(0, min(nf // 2, nf - 1))
            printwrap(f"[VERIFY] auto-search disabled; using middle frame {mid}")
            return mid

        # 2) Scan (skip early titles/black)
        max_idx = min(nf - 1, VERIFY_SEARCH_MAX)
        start   = min(max(VERIFY_START_FRAME, 1), max_idx)  # avoid 0
        step    = max(1, min(VERIFY_SEARCH_STEP, max_idx or 1))

        stats_clip = vs.core.std.PlaneStats(clip)
        best_idx, best_avg = None, -1.0

        for idx in range(start, max_idx + 1, step):
            avg = float(stats_clip.get_frame(idx).props.get("PlaneStatsAverage", 0.0))
            if avg >= VERIFY_LUMA_THRESH:
                printwrap(f"[VERIFY] auto-picked bright-ish frame {idx} (avg={avg:.4f}); start={start}, step={step}")
                return idx
            if avg > best_avg:
                best_idx, best_avg = idx, avg

        # 3) Brightest sampled or middle fallback
        if best_idx is not None:
            printwrap(f"[VERIFY] no frame met threshold {VERIFY_LUMA_THRESH:.2f}; using brightest sampled frame {best_idx} (avg={best_avg:.4f})")
            return best_idx

        mid = max(0, min(nf // 2, nf - 1))
        printwrap(f"[VERIFY] search failed; using middle frame {mid}")
        return mid

    except Exception as e:
        # Final safety net: choose middle (never explode the pipeline)
        nf = getattr(clip, "num_frames", 0)
        mid = max(0, min(nf // 2, nf - 1)) if nf > 0 else 0
        printwrap(f"[VERIFY] frame-pick failed ({e}); using middle frame {mid}")
        return mid

# --- Helper: call Tonemap with retries ---
def _tonemap_with_retries(core, rgb16, src_csp_hint, file_name_for_log):
    kwargs = dict(
        dst_csp=0,           # BT.709 + BT.1886
        dst_prim=1,          # BT.709 primaries
        dst_max=DST_MAX,
        dst_min=0.1,
        dynamic_peak_detection=TM_DPD,
        smoothing_period=2.0,
        scene_threshold_low=0.15,
        scene_threshold_high=0.30,
        gamut_mapping=1,     # perceptual compression
        tone_mapping_function_s=TM_FUNC,
        use_dovi=True,
        log_level=2,
    )
    # Try with hint
    if src_csp_hint is not None:
        try:
            return core.placebo.Tonemap(rgb16, src_csp=src_csp_hint, **kwargs)
        except Exception as e:
            printwrap(f"[Tonemap attempt A failed] src_csp={src_csp_hint}: {e}")
    # Try inference
    try:
        return core.placebo.Tonemap(rgb16, **kwargs)
    except Exception as e:
        printwrap(f"[Tonemap attempt B failed] infer-from-props: {e}")
    # Last resort: assume PQ/2020
    return core.placebo.Tonemap(rgb16, src_csp=1, **kwargs)
# =============================================================================



# --- FFmpeg FPS helper ---
def compute_ffmpeg_fps(node):
    """Return a sensible float FPS for FFmpeg -framerate."""
    num = getattr(node, 'fps_num', None)
    den = getattr(node, 'fps_den', None)
    try:
        if isinstance(num, int) and isinstance(den, int) and den:
            return num / den
    except Exception:
        pass
    return 24000/1001
from requests import Session
from functools import partial
from requests_toolbelt import MultipartEncoder
from typing import Any, Dict, List, Optional, BinaryIO, Union, Callable, TypeVar, Sequence, cast, Tuple
RenderCallback = Callable[[int, vs.VideoFrame], None]
VideoProp = Union[int, Sequence[int],float, Sequence[float],str, Sequence[str],vs.VideoNode, Sequence[vs.VideoNode],vs.VideoFrame, Sequence[vs.VideoFrame],Callable[..., Any], Sequence[Callable[..., Any]]]
T = TypeVar("T", bound=VideoProp)
vs.core.max_cache_size = ram_limit
colorama.init()

# --- Unified filename metadata parser (GuessIt + Anitopy) ---
def _extract_release_group_brackets(file_name: str) -> str | None:
    m = re.match(r"^\[(?P<grp>[^\]]+)\]", file_name)
    return m.group("grp") if m else None

def _normalize_episode_number(val) -> str:
    try:
        if val is None:
            return ""
        if isinstance(val, (list, tuple)):
            return "-".join(str(x) for x in val)
        return str(val)
    except Exception:
        return ""

def parse_filename_metadata(file_name: str, prefer_guessit: bool = True) -> dict:
    """
    Return a dict with keys: anime_title, episode_number, episode_title, release_group, file_name
    Prefers GuessIt if available (for movies/TV), falls back to Anitopy.
    """
    # Try GuessIt first if configured and available
    if prefer_guessit and GUESSIT_AVAILABLE and _guessit is not None:
        try:
            g = _guessit(file_name)
            anime_title = g.get('title') or ""
            episode_number = _normalize_episode_number(g.get('episode'))
            episode_title = g.get('episode_title') or ""
            release_group = g.get('release_group') or _extract_release_group_brackets(file_name)
            return {
                'anime_title': anime_title,
                'episode_number': episode_number,
                'episode_title': episode_title,
                'release_group': release_group,
                'file_name': file_name,
            }
        except Exception:
            # fall through to Anitopy
            pass

    # Fallback to Anitopy
    try:
        a = ani.parse(file_name)
    except Exception:
        a = {}
    anime_title = a.get('anime_title') or a.get('title') or ""
    episode_number = _normalize_episode_number(a.get('episode_number'))
    episode_title = a.get('episode_title') or ""
    release_group = a.get('release_group') or _extract_release_group_brackets(file_name)
    return {
        'anime_title': anime_title,
        'episode_number': episode_number,
        'episode_title': episode_title,
        'release_group': release_group,
        'file_name': file_name,
    }

# --- Small helpers for analysis ---
def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    q = min(max(q, 0.0), 1.0)
    xs = sorted(values)
    if q <= 0:
        return xs[0]
    if q >= 1:
        return xs[-1]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac

def FrameInfo(clip: vs.VideoNode,
              title: str,
              style: str = "sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,""0,0,0,0,100,100,0,0,1,2,0,7,10,10,10,1",
              newlines: int = 3,
              pad_info: bool = False) -> vs.VideoNode:
    """
    FrameInfo function stolen from awsmfunc, implemented by LibreSneed
    Prints the frame number, frame type and a title on the clip
    """

    def FrameProps(n: int, f: vs.VideoFrame, clip: vs.VideoNode, padding: Optional[str]) -> vs.VideoNode:
        if "_PictType" in f.props:
            info = f"Frame {n} of {clip.num_frames}\nPicture type: {f.props['_PictType'].decode()}"
        else:
            info = f"Frame {n} of {clip.num_frames}\nPicture type: N/A"

        if pad_info and padding:
            info_text = [padding + info]
        else:
            info_text = [info]

        clip = vs.core.sub.Subtitle(clip, text=info_text, style=style)

        return clip

    padding_info: Optional[str] = None

    if pad_info:
        padding_info = " " + "".join(['\n'] * newlines)
        padding_title = " " + "".join(['\n'] * (newlines + 4))
    else:
        padding_title = " " + "".join(['\n'] * newlines)

    clip = vs.core.std.FrameEval(clip, partial(FrameProps, clip=clip, padding=padding_info), prop_src=clip)
    clip = vs.core.sub.Subtitle(clip, text=[padding_title + title], style=style)

    return clip

def process_clip_for_screenshot(clip_to_process: vs.VideoNode, original_props: vs.FrameProps, file_name_for_log: str) -> vs.VideoNode:

    """
    Processes a clip for screenshotting, applying HDR tone mapping if needed
    using libplacebo when available, and converting to RGB24 for output.
    Geometry (crop/resize) is preserved as handled elsewhere in the script.
    """
    # Extract original colorimetry from props
    transfer_in = original_props.get("_Transfer")
    primaries_in = original_props.get("_Primaries")
    matrix_in = original_props.get("_Matrix")
    color_range_in = original_props.get("_ColorRange")  # 0=Full, 1=Limited

    # Heuristic HDR detection
    source_is_hdr = (transfer_in in (16, 18)) and (primaries_in == 9)

    target_format = vs.RGB24
    target_range = vs.RANGE_FULL

    try:
        has_placebo = hasattr(vs.core, "placebo") and callable(getattr(vs.core.placebo, "Tonemap", None))

        if source_is_hdr and has_placebo:
            printwrap(f"[libplacebo] HDR->SDR for '{file_name_for_log}' (Transfer={transfer_in}, Primaries={primaries_in}, Matrix={matrix_in}, Range={color_range_in})")
            try:
                f0 = clip_to_process.get_frame(0)
                printwrap(f"[DEBUG props before RGB] _Matrix={f0.props.get('_Matrix')} _Transfer={f0.props.get('_Transfer')} _Primaries={f0.props.get('_Primaries')} _ColorRange={f0.props.get('_ColorRange')}")
            except Exception:
                pass

            # YUV -> RGB48 via zimg; preserve input props for accurate linearization
            rgb16 = clip_to_process.resize.Spline36(
                format=vs.RGB48,
                matrix_in=matrix_in,
                transfer_in=transfer_in,
                primaries_in=primaries_in,
                range_in=color_range_in if color_range_in is not None else vs.RANGE_LIMITED,
                dither_type="error_diffusion",
            )
            # Normalize props for RGB so placebo accepts it
            rgb16 = _normalize_props_for_placebo_rgb16(rgb16, transfer_in, primaries_in)

            # libplacebo tonemap with adaptive src_csp and retries
            src_hint = _deduce_src_csp_from_props(transfer_in, primaries_in)
            tonemapped = _tonemap_with_retries(vs.core, rgb16, src_hint, file_name_for_log)

            # Optional verification vs naive SDR on first frame
            if VERIFY:
                vf = _pick_verify_frame(clip_to_process)
                printwrap(f"[VERIFY] enabled — computing Δ vs naive SDR on frame {vf} (this may take a moment)...")
                naive = clip_to_process.resize.Spline36(
                    format=vs.RGB24,
                    matrix_in=matrix_in,
                    transfer_in=transfer_in,
                    primaries_in=primaries_in,
                    range_in=color_range_in if color_range_in is not None else vs.RANGE_LIMITED,
                    transfer=1, primaries=1, range=vs.RANGE_FULL,
                    dither_type="error_diffusion",
                )
                tm_rgb24 = tonemapped.resize.Point(format=vs.RGB24, range=vs.RANGE_FULL, dither_type="error_diffusion")
                diff = vs.core.std.Expr([tm_rgb24, naive], 'x y - abs')
                stats = vs.core.std.PlaneStats(diff)
                try:
                    p = stats.get_frame(vf).props
                    mae = p.get("PlaneStatsAverage", 0.0)
                    mx  = p.get("PlaneStatsMax", 0.0)
                    printwrap(f"[VERIFY] diff avg={mae:.4f}, max={mx:.4f} (RGB, frame {vf}) vs naive SDR (non-zero indicates tone-mapping).")
                except Exception as _:
                    pass

            # Mark frames and optional overlay
            tonemapped = tonemapped.std.SetFrameProp(prop="_Tonemapped", data=f"placebo:{TM_FUNC},dpd={TM_DPD},dst_max={DST_MAX}")
            if OVERLAY:
                try:
                    txt = f"TM:{TM_FUNC} dpd={TM_DPD} dst_max={DST_MAX} + BT.709/BT.1886"
                    tonemapped = vs.core.text.Text(tonemapped, txt, alignment=9)
                    printwrap("[OVERLAY] stamp applied")
                except Exception as e:
                    printwrap(f"[OVERLAY] failed: {e}")

            # Dither to RGB24 for screenshot output
            return tonemapped.resize.Point(format=target_format, range=target_range, dither_type="error_diffusion")

        # Non-HDR or no placebo: standard RGB24 conversion (keep matrix/range sane)
        effective_matrix_in = matrix_in
        if clip_to_process.format.color_family != vs.RGB and (effective_matrix_in is None or effective_matrix_in in (0, 2)):
            effective_matrix_in = 1  # assume BT.709 for SDR YUV
        printwrap(f"[SDR] '{file_name_for_log}' Matrix={matrix_in} (eff={effective_matrix_in}) Range={color_range_in} -> RGB24")
        return clip_to_process.resize.Spline36(
            format=target_format,
            matrix_in=effective_matrix_in,
            range_in=color_range_in if color_range_in is not None else vs.RANGE_LIMITED,
            range=target_range,
            dither_type="error_diffusion",
        )

    except Exception as e:
        printwrap(f"[ERROR] Color processing failed for '{file_name_for_log}': {e}. Falling back to simple RGB24 conversion.")
        fallback_matrix = matrix_in
        if clip_to_process.format.color_family != vs.RGB and (fallback_matrix is None or fallback_matrix in (0, 2)):
            fallback_matrix = 1
        return clip_to_process.resize.Spline36(format=target_format, matrix_in=fallback_matrix, dither_type="error_diffusion")

def dedupe(clip: vs.VideoNode, framelist: list, framecount: int, diff_thr: int, selected_frames: list = [], seed: int = None, motion: bool = False):
    """
    Selects frames from a list as long as they aren't too close together.
    
    :param framelist:     Detailed list of frames that has to be cut down.
    :param framecount:    Number of frames to select.
    :param seed:          Seed for `random.sample()`.
    :param diff_thr:      Minimum distance between each frame (in seconds).
    :param motion:        If enabled, the frames will be put in an ordered list, not selected randomly.

    :return:              Deduped framelist
    """

    random.seed(seed)
    thr = round(clip.fps_num / clip.fps_den * diff_thr)
    initial_length = len(selected_frames)

    while (len(selected_frames) - initial_length) < framecount and len(framelist) > 0:
        dupe = False

        #get random frame from framelist with removal. if motion, get first frame     
        if motion:
            rand = framelist.pop(0)
        else:
            rand = framelist.pop(random.randint(0, len(framelist) - 1))

        #check if it's too close to an already selected frame
        for selected_frame in selected_frames:
            if abs(selected_frame - rand) < thr:
                dupe = True
                break

        if not dupe:
            selected_frames.append(rand)

    selected_frames.sort()
    
    return selected_frames

def lazylist(clip: vs.VideoNode, dark_frames: int = 25, light_frames: int = 15, motion_frames: int = 0, selected_frames: list = [], seed: int = random_seed,
             diff_thr: int = screen_separation, diff_radius: int = motion_diff_radius, dark_list: list = None, light_list: list = None, motion_list: list = None, 
             save_frames: bool = False, file: str = None, files: list = None, files_info: list = None):
    """
    Generates a list of frames for comparison purposes.

    :param clip:             Input clip.
    :param dark_frames:      Number of dark frames.
    :param light_frames:     Number of light frames.
    :param motion_frames:    Number of frames with high level of motion.
    :param seed:             Seed for `random.sample()`.
    :param diff_thr:         Minimum distance between each frame (in seconds).
    :param diff_radius:      Number of frames on each side for motion smoothing (window = 2*diff_radius+1 frames).
    :param dark_list:        Pre-existing detailed list of dark frames that needs to be sorted.
    :param light_list:       Pre-existing detailed list of light frames that needs to be sorted.
    :param motion_list:      Pre-existing detailed list of high motion frames that needs to be sorted.
    :param save_frames:      If true, returns detailed lists with every type of frame.
    :param file:             File being analyzed.
    :param files:            List of files in directory.
    :param files_info:       Information for each file in directory.

    :return:                 List of dark, light, and high motion frames.
    """

    #if no frames were requested, return empty list before running algorithm
    if dark_frames + light_frames + motion_frames == 0:
        return [], dark_list, light_list, motion_list
    
    findex = files.index(file)

    dark = []
    light = []
    diff = []
    motion = []

    if dark_list is None or light_list is None or motion_list is None:

        # Build analysis clip (optional SDR, optional downscale), then gray + stats
        base_clip = clip
        try:
            if analyze_in_sdr:
                # Light conversion to SDR RGB for perceptual averaging
                # Try to preserve input transfer/primaries/range when available
                f0 = base_clip.get_frame(0)
                matrix_in = f0.props.get('_Matrix', None)
                transfer_in = f0.props.get('_Transfer', None)
                primaries_in = f0.props.get('_Primaries', None)
                color_range_in = f0.props.get('_ColorRange', None)
                base_clip = base_clip.resize.Spline36(
                    format=vs.RGB24,
                    matrix_in=matrix_in if matrix_in is not None else None,
                    transfer_in=transfer_in if transfer_in is not None else None,
                    primaries_in=primaries_in if primaries_in is not None else None,
                    range_in=color_range_in if color_range_in is not None else vs.RANGE_LIMITED,
                    transfer=1, primaries=1, range=vs.RANGE_FULL,
                    dither_type="error_diffusion",
                )
        except Exception:
            # Fall back to original clip if conversion fails
            base_clip = clip

        # Optional downscale to speed up stats
        try:
            if isinstance(analysis_downscale_h, int) and analysis_downscale_h > 0 and base_clip.height > analysis_downscale_h:
                new_h = max(2, int(analysis_downscale_h))
                new_w = max(2, (base_clip.width * new_h) // max(1, base_clip.height))
                # keep even dimensions
                new_w = (new_w + 1) // 2 * 2
                new_h = (new_h + 1) // 2 * 2
                base_clip = base_clip.resize.Spline36(width=new_w, height=new_h)
        except Exception:
            pass

        # Build a grayscale analysis clip regardless of color family
        try:
            if base_clip.format.color_family == vs.RGB:
                # From RGB to GRAY requires a matrix; use BT.709 coefficients
                try:
                    gray = base_clip.resize.Spline36(format=vs.GRAY8, matrix=1, range=vs.RANGE_FULL, dither_type="error_diffusion")
                except Exception:
                    # Fallback path: convert to YUV444 with matrix, then extract Y
                    yuv = base_clip.resize.Spline36(format=vs.YUV444P8, matrix=1, range=vs.RANGE_FULL, dither_type="error_diffusion")
                    gray = vs.core.std.ShufflePlanes(yuv, 0, vs.GRAY)
            else:
                gray = vstools.get_y(base_clip)
        except Exception:
            # Last resort: attempt GRAY with matrix specified
            gray = base_clip.resize.Spline36(format=vs.GRAY8, matrix=1, dither_type="error_diffusion")

        # Luma statistics clip
        luma_stats = gray.std.PlaneStats()

        # Motion metric: absolute difference or legacy Prewitt on diff
        diff_metric = None
        if motion_frames > 0:
            if motion_use_absdiff:
                prev = vs.core.std.BlankClip(gray)[0] + gray
                absdiff = vs.core.std.Expr([prev, gray], 'x y - abs')
                diff_metric = absdiff.std.PlaneStats()
            else:
                prev = vs.core.std.BlankClip(gray)[0] + gray
                diffclip = vs.core.std.MakeDiff(prev, gray)
                diffclip = vs.core.std.Prewitt(diffclip)
                diff_metric = diffclip.std.PlaneStats()

        step = max(1, int(analysis_step))
        # Use full-length stats as prop_src; apply sampling inside the callback
        luma_sel = luma_stats
        diff_sel = diff_metric

        luma_vals: list[tuple[int, float]] = []
        diff_vals: list[tuple[int, float]] = []

        def checkclip(n, f, _clip):
            try:
                avg = float(f.props.get("PlaneStatsAverage", 0.0))
            except Exception:
                avg = 0.0
            # Apply analysis stepping here to avoid SelectEvery length issues
            if step > 1 and (n % step) != 0:
                return _clip
            orig_idx = n
            luma_vals.append((orig_idx, avg))

            if motion_frames > 0 and diff_sel is not None:
                try:
                    d = float(diff_sel.get_frame(n).props.get("PlaneStatsAverage", 0.0))
                except Exception:
                    d = 0.0
                diff_vals.append((orig_idx, d))
            return _clip

        # Progress label
        if file is not None and files is not None and files_info is not None:
            suffix = files_info[findex].get('suffix')
            if files_info[findex].get("suffix_color") == "yellow":
                message = f'Analyzing video: [yellow]{suffix.strip()}'
            elif files_info[findex].get("suffix_color") == "cyan":
                message = f"Analyzing video: [cyan]{suffix.strip()}"
            else:
                message = "Analyzing video"
        else:
            message = "Analyzing video"

        eval_frames = vs.core.std.FrameEval(clip, partial(checkclip, _clip=clip), prop_src=luma_sel)
        vstools.clip_async_render(eval_frames, progress=message)

    else:
        dark = dark_list
        light = light_list
        diff_vals = list(enumerate(motion_list)) if isinstance(motion_list, list) else []
        # We keep 'diff' variable later as the raw diff series (values only)

    #remove frames that are within diff_thr seconds of other frames. for dark and light, select random frames as well
    if dark_list is None or light_list is None or motion_list is None:
        # Build dark/light candidates from measured luma
        if analysis_use_quantiles:
            lum_vals_only = [v for (_, v) in luma_vals]
            qd = _quantile(lum_vals_only, dark_quantile)
            qb = _quantile(lum_vals_only, bright_quantile)
            dark = [idx for (idx, v) in luma_vals if v <= qd]
            light = [idx for (idx, v) in luma_vals if v >= qb]
        else:
            # Legacy fixed bands
            dark = [idx for (idx, v) in luma_vals if 0.062746 <= v <= 0.380000]
            light = [idx for (idx, v) in luma_vals if 0.450000 <= v <= 0.800000]

    selected_frames = dedupe(clip, dark, dark_frames, diff_thr, selected_frames, seed)
    selected_frames = dedupe(clip, light, light_frames, diff_thr, selected_frames, seed)

    #find frames with most motion
    if motion_frames > 0:
        # Use measured diff values if newly computed, else reconstruct from saved motion_list
        if dark_list is None or light_list is None or motion_list is None:
            diff = [v for (_, v) in diff_vals]
        else:
            diff = list(motion_list)

        # Smooth over +/- diff_radius samples (original domain; step handled during collection)
        avg_diff: list[tuple[int, float]] = []
        total = len(diff)
        if total > 0:
            for i in range(total):
                if i >= diff_radius and i < (total - diff_radius):
                    surr = diff[i - diff_radius : i + diff_radius + 1]
                    mean = float(sum(surr)) / float(len(surr))
                    # Index already in original domain
                    idx = i
                    avg_diff.append((idx, mean))

        # Optional scene cut suppression based on raw diff distribution
        if motion_scenecut_quantile and motion_scenecut_quantile > 0.0 and motion_scenecut_quantile < 1.0:
            raw_thr = _quantile(diff, motion_scenecut_quantile) if diff else float('inf')
            avg_diff = [t for t in avg_diff if t[1] < raw_thr]

        # Sort by motion magnitude desc
        sorted_avg_diff = sorted(avg_diff, key=lambda x: x[1], reverse=True)
        motion = [idx for (idx, _) in sorted_avg_diff]

        #remove frames that are too close to other frames. uses lower diff_thr because high motion frames will be different from one another
        selected_frames = dedupe(clip, motion, motion_frames, round(diff_thr/4), selected_frames, seed, motion=True)

    print()

    if save_frames:
        dark_list = dark
        light_list = light
        # Save the raw diff series for reuse; if not computed earlier, save empty list
        motion_list = diff

        return selected_frames, dark_list, light_list, motion_list
    else:
        return selected_frames

def _get_slowpics_header(content_length: str, content_type: str, sess: Session) -> Dict[str, str]:
    """
    Stolen from vardefunc, fixed by Jimbo.
    """

    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Access-Control-Allow-Origin": "*",
        "Content-Length": content_length,
        "Content-Type": content_type,
        "Origin": "https://slow.pics/",
        "Referer": "https://slow.pics/comparison",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "X-XSRF-TOKEN": sess.cookies.get_dict()["XSRF-TOKEN"]
    }

def get_highest_res(files: List[str]) -> Tuple[int, int, int]:
    """
    Finds the video source with the highest resolution from a list of files.

    :param files:    The list of files in question.

    :return:         (width, height, index) of the highest resolution video.
    """

    height = 0
    width = 0
    filenum = -1
    for f in files:
        filenum+=1
        video = vs.core.lsmas.LWLibavSource(f)
        if height < video.height:
            height = video.height
            width = video.width
            max_res_file = filenum

    return width, height, max_res_file

def estimate_analysis_time(file, read_len: int=15):
    """
    Estimates the time it would take to analyze a video source.

    :param read_len:    How many frames to read from the video.
    """

    clip = vs.core.lsmas.LWLibavSource(file)

    #safeguard for if there arent enough frames in clip
    while clip.num_frames / 3 + 1 < read_len:
        read_len -= 1

    clip1 = clip[int(clip.num_frames / 3) : int(clip.num_frames / 3) + read_len]
    clip2 = clip[int(clip.num_frames * 2 / 3) : int(clip.num_frames * 2 / 3) + read_len]

    def checkclip(n, f, clip):
        avg = f.props["PlaneStatsAverage"]
        return clip

    start_time = time.time()
    vstools.clip_async_render(vs.core.std.FrameEval(clip1, partial(checkclip, clip=clip1.std.PlaneStats()), prop_src=clip1.std.PlaneStats()))
    elapsed_time = time.time() - start_time

    start_time = time.time()
    vstools.clip_async_render(vs.core.std.FrameEval(clip2, partial(checkclip, clip=clip2.std.PlaneStats()), prop_src=clip2.std.PlaneStats()))
    elapsed_time = (elapsed_time + time.time() - start_time)/2

    return elapsed_time

def evaluate_analyze_clip(analyze_clip, files, files_info):
    """
    Determines which file should be analyzed by lazylist.
    """

    file_analysis_default = False

    #check if analyze_clip is an int or string with just an int in it
    if (isinstance(analyze_clip, int) and analyze_clip >= 0) or (isinstance(analyze_clip, str) and analyze_clip.isdigit() and int(analyze_clip) >= 0):
        first_file = files[int(analyze_clip)]

    #check if analyze_clip is a group or file name
    elif isinstance(analyze_clip, str) and analyze_clip != "":
        matches = 0
        for dict_item in files_info: # Renamed dict to dict_item to avoid conflict
            if analyze_clip == dict_item.get("release_group") or analyze_clip == dict_item.get("file_name") or analyze_clip in dict_item.get("file_name"):
                matches+=1
                first_file = files[files_info.index(dict_item)]

        #if no matches found, use default
        if matches == 0:
            printwrap('No file matching the "analyze_clip" parameter has been found. Using default.')
            file_analysis_default = True
        if matches > 1:
            printwrap('Too many files match the "analyze_clip" parameter. Using default.')

    #if no clip specified, use default
    else:
        file_analysis_default = True

    #default: pick file with smallest read time
    if file_analysis_default:
        printwrap("Determining which file to analyze...\n")
        estimated_times = [estimate_analysis_time(file) for file in files]
        first_file = files[estimated_times.index(min(estimated_times))]
    
    return first_file

def init_clip(file: str, files: list, trim_dict: dict, trim_dict_end: dict, change_fps: dict = {}, 
              analyze_clip: str = None, files_info: list = None, return_file: bool = False):
    """
    Gets trimmed and fps modified clip from video file.
    """
    # Ensure first_file is accessible if it's meant to be a global modified elsewhere
    # or manage its state more explicitly if it's determined within this scope.
    # For now, assuming 'first_file' might be set globally or passed if needed.
    # If 'file' is None, it means we need to determine the file to analyze.
    if file is None: # This implies analyze_clip should be used if provided
        if analyze_clip is not None: # Check if analyze_clip parameter has a value
             file = evaluate_analyze_clip(analyze_clip, files, files_info)
        else:
            # Fallback if analyze_clip is also not provided, though evaluate_analyze_clip has its own default.
            # This case might indicate a logic path to review if 'file' can be None without 'analyze_clip'.
            # For safety, let evaluate_analyze_clip pick its default if 'analyze_clip' was empty string.
            file = evaluate_analyze_clip("", files, files_info)


    findex = files.index(file)
    try:
        clip = vs.core.lsmas.LWLibavSource(file)
    except Exception as e:
        printwrap(f"Error loading source '{file}': {e}")
        # Decide how to handle this: re-raise, return None, or exit
        sys.exit(f"Failed to load video file: {file}")


    if trim_dict.get(findex) is not None:

        if trim_dict.get(findex) > 0:
            clip = clip[trim_dict.get(findex):]

        elif trim_dict.get(findex) < 0:
            #append blank clip to beginning of source to "extend" it
            clip = vs.core.std.BlankClip(clip)[:(trim_dict.get(findex) * -1)] + clip
            #keep count of how many blank frames were appended
            # extended = trim_dict.get(findex) * -1 # 'extended' variable was not used

    if trim_dict_end.get(findex) is not None:
            clip = clip[:trim_dict_end.get(findex)]

    if change_fps.get(findex) is not None:
        clip = vstools.change_fps(clip, fractions.Fraction(numerator=change_fps.get(findex)[0], denominator=change_fps.get(findex)[1]))

    if return_file:
        return clip, file
    else:
        return clip

def get_suffixes(files_info: list, first_display: bool = False):
    """
    Gets display name ('suffix') and its color for every file based on its release group and filename.

    :param files_info:       List of dictionaries generated by anitopy for every file.
    :param first_display:    Whether or not the suffixes are being generated for the program's initial display of found files.

    :return:                 List of dictionaries for every file with 'suffix' and 'suffix_color' updated.
    """

    # By default, prefer full filenames for display/overlay and image names.
    if always_full_filename:
        for i in range(0, len(files_info)):
            files_info[i]['suffix'] = files_info[i].get('file_name')
            files_info[i]['suffix_color'] = "yellow"
    else:
        # Prior behavior: if group name exists use it, otherwise use file name
        for i in range(0, len(files_info)):
            if files_info[i].get('release_group') is not None:
                files_info[i]['suffix'] = str(files_info[i].get('release_group'))
                files_info[i]['suffix_color'] = "cyan"
            else:
                files_info[i]['suffix'] = files_info[i].get('file_name')
                files_info[i]['suffix_color'] = "yellow"

    #check for duplicates (only relevant when not using full filenames)
    if not always_full_filename:
        for i in range(0, len(files_info)):
            matches = [i]

            for f in range(i + 1, len(files_info)):
                if files_info[i].get('suffix') == files_info[f].get('suffix'):
                    matches.append(f)

            #if duplicates found, check whether they have version number in file name and put it in suffix
            if len(matches) > 1:
                for f_idx in (matches): # Renamed f to f_idx

                    for pos, letter in enumerate(files_info[f_idx].get('file_name')):
                        x = 0

                        if letter.lower() == "v":
                            while files_info[f_idx].get('file_name')[pos+1:pos+x+2].isdigit() and pos+x+2 <= len(files_info[f_idx].get('file_name')):
                                x += 1

                            #if they do, add " vXX" to suffix
                            #also check that the match for "vXX" not in the file extension
                            if x > 0 and files_info[f_idx].get('file_name')[pos+1:pos+x+2] not in os.path.splitext(files_info[f_idx].get('file_name'))[1]:
                                files_info[f_idx]['suffix'] = files_info[f_idx].get('suffix') + " " + files_info[f_idx].get('file_name')[pos:pos+x+1]
                                files_info[f_idx]['suffix_color'] = "cyan"
                                break

    #check for duplicates again and just set filename this time (only when not using full filenames)
    if not always_full_filename:
        for i in range(0, len(files_info)):
            matches = [i]

            for f in range(i + 1, len(files_info)):
                if files_info[i].get('suffix') == files_info[f].get('suffix'):
                    matches.append(f)

            if len(matches) > 1:
                for f_idx in (matches): # Renamed f to f_idx
                    files_info[f_idx]['suffix'] = files_info[f_idx].get('file_name')
                    files_info[f_idx]['suffix_color'] = "yellow"

    # If not the first display and we're not forcing full filenames,
    # only show enough of the filename to disambiguate against others.
    if not first_display and not always_full_filename:
        for i in range(0, len(files_info)):
            highest = 0
            highest_file = 0
            filename = files_info[i].get('file_name')

            if files_info[i].get('suffix') == filename:
                for f in range(0, len(files_info)):
                    pos = 0

                    if i == f:
                        continue
                    
                    # Ensure comparison doesn't go out of bounds
                    min_len = min(len(files_info[i].get('file_name')), len(files_info[f].get('file_name')))
                    while pos < min_len and files_info[i].get('file_name')[pos] == files_info[f].get('file_name')[pos]:
                        pos += 1


                    if pos > highest:
                        highest = pos
                        highest_file = f
                
                if highest_file >= len(files_info): # bounds check for highest_file
                    continue


                #progress bar should take up about half the screen, at least 2/5 of that will be used, max all of it
                #original: l_bound = 20, h_bound = 45
                consolesize = os.get_terminal_size().columns
                progress_bar_width = min(round(consolesize / 2), 68) # Renamed progress to progress_bar_width
                l_bound = round((consolesize - progress_bar_width) * 2/5)
                h_bound = consolesize - progress_bar_width

                #show whole filename if it fits within limit
                if len(filename) < (h_bound):
                    pass

                #put "..." at the end if the different part appears within limit
                elif highest < h_bound-3:
                    files_info[i]['suffix'] = filename[:h_bound-3].strip() + "..."

                #if section thats different starts less than "l_bound" chars away from end, put "..." in middle of name, with diff following it
                elif len(filename[highest+1:]) <= l_bound:
                    files_info[i]['suffix'] = filename[:h_bound-3-len(filename[highest+1:])].strip() + "..." + filename[highest+1:].strip()

                #if section thats different starts more than "l_bound" chars away from end, put "..." then diff in parentheses
                else:
                    last_diff_pos = highest # Initialize last_diff_pos
                    # Iterate up to the minimum length of the two filenames being compared
                    min_comp_len = min(len(filename), len(files_info[highest_file].get('file_name')))
                    for pos_comp, letter_comp in enumerate(filename[:min_comp_len]): # Renamed pos, letter
                        if letter_comp != files_info[highest_file].get('file_name')[pos_comp]:
                            last_diff_pos = pos_comp
                            break # Found the first difference
                    else: # If loop completed without break, means one is a prefix of the other up to min_comp_len
                        if len(filename) > len(files_info[highest_file].get('file_name')):
                           last_diff_pos = len(files_info[highest_file].get('file_name')) -1


                    if last_diff_pos + 1 >= len(filename): # Check bounds for filename
                        diff_text = filename[highest:]
                    elif highest > last_diff_pos +1 : # if highest is somehow after last_diff_pos
                         diff_text = filename[last_diff_pos:]
                    else:
                        diff_text = filename[highest:last_diff_pos+1]


                    #if all of the diff fits
                    if len(diff_text) < (h_bound-l_bound-6):
                        files_info[i]['suffix'] = filename[:l_bound].strip() + "... (" + diff_text.strip() + ")"

                    #if only some of the diff fits
                    else:
                        files_info[i]['suffix'] = filename[:l_bound].strip() + "... (" + diff_text[:h_bound-l_bound-6].strip() + ")"

    return files_info

def str_to_number(string: str):
    """
    Converts a string to a float or int if possible.
    """

    try:
        float(string)
        try:
            int(string)
            return int(string)
        except ValueError: # More specific exception
            return float(string)
    except ValueError: # More specific exception
        return string
    
def extend_clip(clip: vs.VideoNode, frames: list):
    """
    If a clip is shorter than the largest frame that needs to be rendered, extend it.
    """
    if not frames: # Handle empty frames list
        return clip
    if clip.num_frames < frames[-1] + 1: # frames are 0-indexed, num_frames is 1-indexed count
        clip = clip + (vs.core.std.BlankClip(clip)[0] * (frames[-1] - clip.num_frames + 1))

    return clip

def _snap_pair_to_mod(left: int, right: int, total: int, mod: int) -> tuple[int, int]:
    """
    Adjust (left, right) so both are multiples of `mod` and sum close to `total` without going negative.
    """
    if total < 0:
        return 0, 0
    # Round left up to multiple of mod
    if left % mod != 0:
        left += (mod - (left % mod))
    left = min(left, total)
    right = total - left
    rem = right % mod
    if rem != 0:
        shift = rem
        if left - shift >= 0:
            left -= shift
            right += shift
        else:
            right += (mod - rem)
    # Final clamp to ensure mod alignment
    left = max(0, left - (left % mod))
    right = max(0, right - (right % mod))
    # Keep total close
    while left + right > total:
        if left >= mod:
            left -= mod
        elif right >= mod:
            right -= mod
        else:
            break
    return left, right

def plan_mod_crop(clips: List[vs.VideoNode], mod: int = 2, letterbox_pillarbox: bool = True) -> List[Tuple[int,int,int,int]]:
    """
    Compute per-clip crop plans so every clip ends at the common min width/height,
    with all edges aligned to `mod`. If `letterbox_pillarbox` is True, crop only the
    mismatched axis when widths or heights already match across all clips.
    """
    if not clips:
        return []
    valid = [c for c in clips if c.width > 0 and c.height > 0]
    if not valid:
        return [(0,0,0,0) for _ in clips]

    # Determine target dimensions
    target_w = min(c.width for c in valid)
    target_h = min(c.height for c in valid)

    # Letterbox/pillarbox heuristics based on *consistency* across all valid clips
    same_w = all(c.width == valid[0].width for c in valid)
    same_h = all(c.height == valid[0].height for c in valid)

    plans: List[Tuple[int,int,int,int]] = []
    for c in clips:
        if c.width <= 0 or c.height <= 0:
            plans.append((0,0,0,0)); continue

        wdiff = max(0, c.width  - target_w)
        hdiff = max(0, c.height - target_h)

        # Axis-aware: only crop the dimension that varies (if all valid clips share same W or H)
        if letterbox_pillarbox and same_w and not same_h:
            # Letterbox: widths identical, crop only vertical
            l = r = 0
            t = hdiff // 2
            b = hdiff - t
            t, b = _snap_pair_to_mod(t, b, hdiff, mod)
        elif letterbox_pillarbox and same_h and not same_w:
            # Pillarbox: heights identical, crop only horizontal
            t = b = 0
            l = wdiff // 2
            r = wdiff - l
            l, r = _snap_pair_to_mod(l, r, wdiff, mod)
        else:
            # General: center-crop both axes to min dimensions
            l = wdiff // 2
            r = wdiff - l
            t = hdiff // 2
            b = hdiff - t
            l, r = _snap_pair_to_mod(l, r, wdiff, mod)
            t, b = _snap_pair_to_mod(t, b, hdiff, mod)

        plans.append((l, r, t, b))
    return plans

def run_comparison():
    #START_TIME = time.time()

    global first_file # Declaring intent to modify global; ensure it's handled carefully
    first_file = None # Initialize to ensure it's None before any potential assignment
    #first file is only determined by analyze_clip if it is called 

    supported_extensions = ('.mkv', '.m2ts', '.mp4', '.webm', '.ogm', '.mpg', '.vob', '.iso', '.ts', '.mts', '.mov', '.qv', '.yuv',
                            '.flv', '.avi', '.rm', '.rmvb', '.m2v', '.m4v', '.mp2', '.mpeg', '.mpe', '.mpv', '.wmv', '.avc', '.hevc',
                            '.264', '.265', '.av1')

    #find video files in the current directory, and exit if there are fewer than two
    files = [f for f in os.listdir('.') if f.lower().endswith(supported_extensions)] # Renamed file to f
    files = os_sorted(files)
    file_count = len(files)
    if file_count < 2:
        sys.exit("Error: Fewer than 2 video files found in directory.")

    # Parse filenames to collect show/movie metadata (GuessIt preferred, fallback to Anitopy)
    files_info = []
    for f_name in files: # Renamed file to f_name
        files_info.append(parse_filename_metadata(f_name, prefer_guessit=prefer_guessit))

    anime_title = ""
    anime_episode_number = ""
    anime_episode_title = ""

    #get anime title, episode number, and episode title
    for dict_item in files_info: # Renamed dict to dict_item
        if dict_item.get('anime_title') is not None and anime_title == "":
            anime_title = dict_item.get('anime_title')

        if dict_item.get('episode_number') is not None and anime_episode_number == "":
            anime_episode_number = dict_item.get('episode_number')

        if dict_item.get('episode_title') is not None and anime_episode_title == "":
            anime_episode_title = dict_item.get('episode_title')

    #what to name slow.pics collection
    if anime_title != "" and anime_episode_number != "":
        collection_name = anime_title.strip() + " - " + anime_episode_number.strip()
    elif anime_title != "":
        collection_name = anime_title.strip()
    elif anime_episode_title != "":
        collection_name = anime_episode_title.strip()
    else:
        collection_name = files_info[0].get('file_name')
        # Remove leading group tags [..], (...) and {...}, and strip file extension
        collection_name = re.sub(r"\[.*?\]|\(.*?\)|\{.*?\}|\.[^.]+$", "", collection_name).strip()
    
    #if anime title still isn't found, give it collection name
    if anime_title == "":
        anime_title = collection_name

    #replace group or file names in trim_dict with file index
    for d in [trim_dict, trim_dict_end, change_fps]:
        for i_key in list(d): # Renamed i to i_key
            if isinstance(i_key, str):
                found = False

                for dict_item in files_info: # Renamed dict to dict_item
                    if i_key == dict_item.get("release_group") or i_key == dict_item.get("file_name"): # or i_key in dict_item.get("file_name")
                        d[files_info.index(dict_item)] = d[i_key]
                        found = True

                if found:
                    d.pop(i_key)

    #detects and sets up change_fps "set" feature
    if (list(change_fps.values())).count("set") > 0:
        if (list(change_fps.values())).count("set") > 1:
            sys.exit('Error: More than one change_fps file using "set".')
        
        #if "set" is found, get the index of its file, get its fps, and set every other unspecified file to that fps
        findex_set = list(change_fps.keys())[list(change_fps.values()).index("set")] # Renamed findex to findex_set
        del change_fps[findex_set]
        file_set = files[findex_set] # Renamed file to file_set
        temp_clip_set = vs.core.lsmas.LWLibavSource(file_set) # Renamed temp_clip to temp_clip_set
        fps_set = [temp_clip_set.fps_num, temp_clip_set.fps_den] # Renamed fps to fps_set

        for i in range(0, len(files)):
            if i not in change_fps:
                change_fps[i] = fps_set

    #if file is already set to certain fps, remove it from change_fps
    for findex, file_path in enumerate(files): # Renamed file to file_path
        temp_clip = init_clip(file_path, files, trim_dict, trim_dict_end)
        if change_fps.get(findex) is not None:
            if not isinstance(change_fps.get(findex), list):
                sys.exit("Error: change_fps parameter only accepts lists as input")
            if temp_clip.fps_num / temp_clip.fps_den == change_fps.get(findex)[0] / change_fps.get(findex)[1]:
                del change_fps[findex]

    #get display version of suffixes
    get_suffixes(files_info, first_display=True)

    #print list of files
    print('\nFiles found: ')
    for findex, file_path in enumerate(files): # Renamed file to file_path

        groupname = files_info[findex].get("suffix")
        filename_display = files_info[findex].get("file_name") # Default to full filename

        if files_info[findex].get("release_group") != None:
            #if group name is found, highlight
            if groupname == files_info[findex].get("release_group"):
                parts = files_info[findex].get("file_name").split(groupname, 1)
                if len(parts) == 2:
                    filename_display = parts[0] + colorama.Fore.CYAN + groupname + colorama.Fore.YELLOW + parts[1]
                else: # groupname not found as expected, or at start/end
                    filename_display = files_info[findex].get("file_name").replace(groupname, colorama.Fore.CYAN + groupname + colorama.Fore.YELLOW)


            #if group name with version number is found, highlight both group and version
            elif (files_info[findex].get("release_group") + " v") in groupname:
                v_pos = groupname.rindex("v") # Renamed v to v_pos
                base_group = groupname[:v_pos - 1].strip() # Renamed groupname to base_group
                version_part = groupname[v_pos:].strip() # Renamed groupname to version_part

                filename_display = files_info[findex].get("file_name")
                # Highlight base group
                filename_display = filename_display.replace(base_group, colorama.Fore.CYAN + base_group + colorama.Fore.YELLOW)
                # Highlight version part (this might need more robust splitting if version_part is not unique)
                filename_display = filename_display.replace(version_part, colorama.Fore.CYAN + version_part + colorama.Fore.YELLOW)

            
            #if suffix is filename but group name found, still highlight
            elif files_info[findex].get("release_group") in groupname: # groupname is filename here
                release_group_str = files_info[findex].get("release_group")
                parts = files_info[findex].get("file_name").split(release_group_str, 1)
                if len(parts) == 2:
                     filename_display = parts[0] + colorama.Fore.CYAN + release_group_str + colorama.Fore.YELLOW + parts[1]
                else:
                     filename_display = files_info[findex].get("file_name").replace(release_group_str, colorama.Fore.CYAN + release_group_str + colorama.Fore.YELLOW)


        #if no group name is found, dont highlight (filename_display is already file_name)
        else:
            filename_display = groupname # groupname is file_name here

        #output filenames
        printwrap(colorama.Fore.YELLOW + " - " + filename_display + colorama.Style.RESET_ALL, subsequent_indent="   ")

        #output which files will be trimmed
        if trim_dict.get(findex) is not None:
            if trim_dict.get(findex) >= 0:
                printwrap(f"     - Trimmed to start at frame {trim_dict.get(findex)}", subsequent_indent="       ")
            elif trim_dict.get(findex) < 0:
                printwrap(f"     - {(trim_dict.get(findex) * -1)} frame(s) appended at start", subsequent_indent="       ")
        if trim_dict_end.get(findex) is not None:
            if trim_dict_end.get(findex) >= 0:
                printwrap(f"     - Trimmed to end at frame {trim_dict_end.get(findex)}", subsequent_indent="       ")
            elif trim_dict_end.get(findex) < 0:
                printwrap(f"     - Trimmed to end {trim_dict_end.get(findex) * -1} frame(s) early", subsequent_indent="       ")
            
        if change_fps.get(findex) is not None:
            printwrap(f"     - FPS changed to {change_fps.get(findex)[0]}/{change_fps.get(findex)[1]}", subsequent_indent="       ")
            
    print()

    #get version of suffixes that will be used in the rest of the file
    get_suffixes(files_info, first_display=False)

    #check if conflicting options are enabled
    if (upscale and single_res > 0):
        sys.exit("Error: Can't use 'upscale' and 'single_res' functions at the same time.")

    
    
    frames = []

    #add user specified frames to list
    frames.extend(user_frames)

    #if save_frames is enabled, store generated brightness data in a text file, so they don't have to be analyzed again
    if save_frames and (frame_count_dark + frame_count_bright + frame_count_motion) > 0:
        mismatch = False
        #if frame file exists, read from it
        if os.path.exists(frame_filename) and os.stat(frame_filename).st_size > 0:

            printwrap(f'Reading data from "{frame_filename}"...')
            with open(frame_filename) as frame_file_obj: # Renamed frame_file to frame_file_obj
                generated_frames = frame_file_obj.readlines()

            #turn numbers into floats or ints, and get rid of newlines
            for i, v_val in enumerate(generated_frames): # Renamed v to v_val
                v_val = v_val.strip()
                generated_frames[i] = str_to_number(v_val)
            
            dark_list = generated_frames[generated_frames.index("dark:")+1:generated_frames.index("bright:")]
            light_list = generated_frames[generated_frames.index("bright:")+1:generated_frames.index("motion:")]
            motion_list = generated_frames[generated_frames.index("motion:")+1:]

            analyzed_file = generated_frames[generated_frames.index("analyzed_file:") + 1]
            analyzed_group = None
            if isinstance(analyzed_file, str):
                try:
                    analyzed_group = parse_filename_metadata(analyzed_file, prefer_guessit=prefer_guessit).get("release_group")
                except Exception:
                    try:
                        analyzed_group = ani.parse(analyzed_file).get("release_group")
                    except Exception:
                        analyzed_group = None
            file_trim = generated_frames[generated_frames.index("analyzed_file_trim:") + 1]
            file_trim_end = generated_frames[generated_frames.index("analyzed_file_trim:") + 2]
            file_fps_num = generated_frames[generated_frames.index("analyzed_file_fps:") + 1]
            file_fps_den = generated_frames[generated_frames.index("analyzed_file_fps:") + 2]

            #check if a file with the same group name as the analyzed file is present in our current directory
            group_found = False
            group_file_index = -1 # Initialize
            if analyzed_group: # Ensure analyzed_group is not None
                for i, dict_item in enumerate(files_info): # Renamed dict to dict_item
                    if dict_item.get("release_group") is not None:
                        if dict_item.get("release_group").lower() == analyzed_group.lower():
                            group_found = True
                            group_file_index = files.index(dict_item.get("file_name")) # Use files_info[i]
                            break # Found the group, no need to continue
            
            #if file wasn't found but group name was, set file with the same group name
            if analyzed_file not in files and group_found is True and group_file_index != -1:
                analyzed_file = files[group_file_index]

            #check if show name, episode number, or the release which was analyzed has changed
            # Ensure anime_episode_number is comparable (e.g. string to string or int to int)
            current_ep_num_str = str(anime_episode_number) if anime_episode_number is not None else ""
            saved_ep_num_str = str(generated_frames[generated_frames.index("episode_num:") + 1]) if "episode_num:" in generated_frames else ""


            if (generated_frames[generated_frames.index("show_name:") + 1] != anime_title
                or saved_ep_num_str != current_ep_num_str # Compare as strings
                or analyzed_file not in files):

                mismatch = True

            #check if trim for analyzed file has changed
            if mismatch == False and analyzed_file in files: # Ensure analyzed_file is valid
                found_trim = 0
                found_trim_end = 0
                analyzed_file_idx = files.index(analyzed_file)
                if analyzed_file_idx in trim_dict:
                    found_trim = trim_dict.get(analyzed_file_idx)
                if analyzed_file_idx in trim_dict_end:
                    found_trim_end = trim_dict_end.get(analyzed_file_idx)


                if (file_trim != found_trim
                    or file_trim_end != found_trim_end):
                    mismatch = True

            #check if fps of analyzed file has changed
            if mismatch == False and analyzed_file in files: # Ensure analyzed_file is valid
                temp_clip = init_clip(analyzed_file, files, trim_dict, trim_dict_end, change_fps)
                if file_fps_num / file_fps_den != temp_clip.fps_num / temp_clip.fps_den:
                    mismatch = True


            #if mismatch is detected, re-analyze frames
            if mismatch:
                printwrap("\nParameters have changed. Will re-analyze brightness data.\n")
                if os.path.exists(frame_filename): # Check again before removing
                    os.remove(frame_filename)


            #only spend time processing lazylist if we need to
            elif (frame_count_dark + frame_count_bright + frame_count_motion) > 0:
                # Determine which clip to use for lazylist if not re-analyzing
                # This should be the 'analyzed_file' from the saved data if valid
                clip_for_lazylist_path = analyzed_file if analyzed_file in files else files[0]
                clip_for_lazylist = init_clip(clip_for_lazylist_path, files, trim_dict, trim_dict_end, change_fps, analyze_clip, files_info)

                frames.extend(lazylist(clip_for_lazylist, frame_count_dark, frame_count_bright, frame_count_motion, frames, dark_list=dark_list, light_list=light_list, motion_list=motion_list, file=clip_for_lazylist_path, files=files, files_info=files_info))


        #if frame file does not exist or has less frames than specified, write to it
        if not os.path.exists(frame_filename) or os.stat(frame_filename).st_size == 0 or mismatch:
            # If first_file is None here, it means evaluate_analyze_clip hasn't been called yet for this path
            # or its result wasn't stored in the global 'first_file'.
            # init_clip will call evaluate_analyze_clip if its 'file' param is None and 'analyze_clip' is set.
            # To ensure 'first_file' (the path string) is correctly determined and used:
            if first_file is None: # Ensure first_file (path) is determined
                 # This will set the global first_file if analyze_clip is used by init_clip
                 # and init_clip is modified to update it, or we get it from evaluate_analyze_clip directly.
                 # For now, rely on init_clip's internal call to evaluate_analyze_clip.
                 # The 'return_file=True' ensures 'first_file_path' gets the string.
                 clip_to_analyze, first_file_path = init_clip(None, files, trim_dict, trim_dict_end, change_fps, analyze_clip, files_info, return_file=True)
                 first_file = first_file_path # Update global first_file with the path string
            else: # first_file path is already known
                 clip_to_analyze = init_clip(first_file, files, trim_dict, trim_dict_end, change_fps, analyze_clip, files_info, return_file=False)


            #get the trim
            first_trim = 0
            first_trim_end = 0
            if first_file in files: # Check if first_file is a valid path in files list
                first_file_idx = files.index(first_file)
                if first_file_idx in trim_dict:
                    first_trim = trim_dict[first_file_idx]
                if first_file_idx in trim_dict_end:
                    first_trim_end = trim_dict_end[first_file_idx]


            frames_temp, dark_list, light_list, motion_list = lazylist(clip_to_analyze, frame_count_dark, frame_count_bright, frame_count_motion, frames, save_frames=True, file=first_file, files=files, files_info=files_info)
            frames.extend(frames_temp)
            
            with open(frame_filename, 'w') as frame_file_obj: # Renamed frame_file

                frame_file_obj.write(f"show_name:\n{anime_title}\nepisode_num:\n{anime_episode_number}\nanalyzed_file:\n{first_file}\nanalyzed_file_trim:\n{first_trim}\n{first_trim_end}\nanalyzed_file_fps:\n{clip_to_analyze.fps_num}\n{clip_to_analyze.fps_den}\ndark:\n")
                for val in dark_list:
                    frame_file_obj.write(f"{val}\n")

                frame_file_obj.write("bright:\n")
                for val in light_list:
                    frame_file_obj.write(f"{val}\n")

                frame_file_obj.write("motion:\n")
                for val in motion_list:
                    frame_file_obj.write(f"{val}\n")

    #if save_frames isn't enabled, run lazylist
    elif (frame_count_dark + frame_count_bright + frame_count_motion) > 0:
        # Similar to above, ensure first_file (path) is determined correctly
        if first_file is None:
            clip_to_analyze, first_file_path = init_clip(None, files, trim_dict, trim_dict_end, change_fps, analyze_clip, files_info, return_file=True)
            first_file = first_file_path # Update global
        else:
            clip_to_analyze = init_clip(first_file, files, trim_dict, trim_dict_end, change_fps, analyze_clip, files_info, return_file=False)
        
        frames.extend(lazylist(clip_to_analyze, frame_count_dark, frame_count_bright, frame_count_motion, frames, file=first_file, files=files, files_info=files_info))


    if random_frames > 0:

        print("Getting random frames...\n")
        
        # Determine the clip for random frame selection (e.g., the first file or the analyzed one)
        # Using files[0] as a default if first_file isn't set, or use first_file if available.
        clip_for_random_path = first_file if first_file and first_file in files else files[0]
        clip_for_random = init_clip(clip_for_random_path, files, trim_dict, trim_dict_end, change_fps)


        #get list of all frames in clip
        frame_ranges = list(range(0, clip_for_random.num_frames))


        #randomly selects frames at least screen_separation seconds apart
        # The dedupe function modifies selected_frames in place and also returns it.
        # We want to extend the global 'frames' list, not just get a new list.
        # So, pass 'frames' to dedupe.
        dedupe(clip_for_random, frame_ranges, random_frames, screen_separation, frames)
        # frames.extend(frame_ranges) # This would add the *remaining* frame_ranges, not the selected ones.
                                     # dedupe already appends to 'frames'.

    #remove dupes and sort
    frames = [*set(frames)]
    frames.sort()

    #if no frames selected, terminate program
    if len(frames) == 0:
        sys.exit("Error: No frames have been selected, unable to proceed.")

    #print comma separated list of which frames have been selected
    print(f"Selected {len(frames)} frames:")
    first_print = True # Renamed first to first_print
    message = ""
    for f_num in frames: # Renamed f to f_num
        if not first_print:
            message+=", "
        first_print = False
        message+=str(f_num)

    printwrap(message, end="\n\n")



    if upscale: # This is global upscale, distinct from compc.py logic
        max_width, max_height, max_res_file_idx = get_highest_res(files) # Renamed max_res_file to max_res_file_idx

    #create screenshot directory, if one already exists delete it first
    screen_dir = pathlib.Path("./" + screen_dirname + "/")
    if os.path.isdir(screen_dir):
        shutil.rmtree(screen_dir)
    os.mkdir(screen_dir)

    #check if ffmpeg is available. if not, run script with ffmpeg disabled
    global ffmpeg # Accessing global ffmpeg
    if ffmpeg:
        try:
            subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError: # More specific exception
            ffmpeg = False
            printwrap("FFmpeg was not found. Continuing to generate screens without it (using fpng).")
        except subprocess.CalledProcessError: # FFmpeg found but error running version
            ffmpeg = False
            printwrap("FFmpeg found but '-version' command failed. Continuing with fpng.")

    printwrap("Calculating crop/resize parameters...")

    # Get initial clips to determine dimensions
    try:
        # temp_clips are used for dimension calculation and then as base for each iteration's processing
        temp_clips = [init_clip(file_path, files, trim_dict, trim_dict_end, change_fps) for file_path in files] # Renamed file to file_path
    except Exception as e:
        printwrap(f"Error initializing clips for dimension calculation: {e}")
        sys.exit(1)

    # --- Calculate source_index ---
    # Filter out clips with invalid dimensions first before finding max
    valid_clips = [c for c in temp_clips if c.width > 0 and c.height > 0]
    if not valid_clips:
        printwrap("Error: No valid clips found to determine source dimensions.")
        sys.exit(1)
    try:
        # Find the clip with max dimensions among valid ones
        source_clip_obj = max(valid_clips, key=lambda c: c.width * c.height)
        # Get its index from the original temp_clips list
        source_index = temp_clips.index(source_clip_obj)
    except ValueError:
        printwrap("Error: Could not find the calculated source clip in the initial list.")
        sys.exit(1)
    printwrap(f"Identified source clip (largest dimensions) index: {source_index} (File: {files[source_index]})")


    # --- Determine resize values for the source clip ---
    # This resizes the source_clip if it's significantly different from the first clip (encode)
    resized_width, resized_height = (0, 0)  # Initialize to no resizing
    if len(temp_clips) > 0 and temp_clips[0].width > 0 and temp_clips[0].height > 0: # Need at least one valid clip to compare against
        if source_index != 0 : # Check if source is not the first clip (compc.py logic)
            # Use dimensions from temp_clips directly
            src_width_compc = temp_clips[source_index].width
            enc_width_compc = temp_clips[0].width  # Use the first clip as the reference encode

            if abs(src_width_compc - enc_width_compc) > 600 and enc_width_compc > 0:  # Check for significant difference & valid enc_width
                if src_width_compc // enc_width_compc == 2:
                    resized_width, resized_height = (1920, 1080)  # Target 1080p
                elif src_width_compc // enc_width_compc == 3 or src_width_compc // enc_width_compc == 1:
                    # This ratio logic from compc might need review, but replicating exactly:
                    resized_width, resized_height = (1280, 720)  # Target 720p
        # Ensure resize dimensions are mod 2 if calculated
        if resized_width > 0: resized_width = (resized_width + 1) // 2 * 2
        if resized_height > 0: resized_height = (resized_height + 1) // 2 * 2
    printwrap(f"Calculated resize for source (Clip {source_index}): {resized_width}x{resized_height}")


    # --- Calculate crop values based on smallest clip ---
    # New per-clip crop planning (mod-safe on *both* edges; letterbox/pillarbox aware)
    valid_clips = [c for c in temp_clips if c.width > 0 and c.height > 0]
    if not valid_clips:
        printwrap("Error: No valid clips found to compute crop plans."); sys.exit(1)

    smallest_width = min(c.width for c in valid_clips)
    smallest_height = min(c.height for c in valid_clips)
    printwrap(f"Smallest valid dimensions found across all clips: {smallest_width}x{smallest_height}")

    # Compute per-clip plans; indices align with temp_clips
    crop_plans = plan_mod_crop(temp_clips, mod=mod_crop, letterbox_pillarbox=letterbox_pillarbox_aware)

    # For transparency, print the source clip's plan (and any non-zero plans)
    for idx, (L,R,T,B) in enumerate(crop_plans):
        if any([L,R,T,B]):
            printwrap(f"Crop plan for clip {idx}: L={L} R={R} T={T} B={B}")

    print("Generating screenshots:")
    with Progress(TextColumn("{task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"), TextColumn("{task.percentage:>3.02f}%"), TimeRemainingColumn()) as progress:

        total_gen_progress = progress.add_task("[green]Total", total=len(frames) * len(files))
        file_gen_progress = progress.add_task("", total=len(frames), visible=0)

        for i, file_path in enumerate(files): # Renamed file to file_path
            findex = files.index(file_path)

            # Use the pre-calculated 'safe_suffix' for filenames
            # The user's script did not have 'safe_suffix'. It used 'display_suffix' from 'get_suffixes'.
            display_suffix = files_info[findex].get('suffix', f"file_{findex}") # Fallback

            # Setup progress bar message
            if files_info[findex].get("suffix_color") == "yellow":
                message = f'[yellow]{display_suffix.strip()}'
            elif files_info[findex].get("suffix_color") == "cyan":
                message = f'[cyan]{display_suffix.strip()}'
            else:
                message = display_suffix.strip()
            progress.reset(file_gen_progress, description=message, visible=1)

            original_clip_from_temp = temp_clips[i]
            processed_geometry_clip = original_clip_from_temp # Start with this for geometry changes

            current_resized_width, current_resized_height = 0, 0
            current_crop_values = (0,0,0,0)

            # Apply compc.py derived geometry changes (resizing then cropping) to the source_index clip
            if True:  # Apply geometry to all clips (per-clip crop plan)
                # Apply compc.py-style resize (e.g. 4K -> 1080p if encode is 1080p)
                if resized_width > 0 and resized_height > 0:
                    if processed_geometry_clip.width != resized_width or processed_geometry_clip.height != resized_height:
                        processed_geometry_clip = vs.core.resize.Spline36(processed_geometry_clip, resized_width, resized_height)
                    current_resized_width, current_resized_height = resized_width, resized_height
                
                                # Apply per-clip crop plan (L,R,T,B)
                _L, _R, _T, _B = crop_plans[i] if 'crop_plans' in locals() else (0,0,0,0)
                if any(cv > 0 for cv in (_L,_R,_T,_B)):
                    if processed_geometry_clip.width - _L - _R > 0 and processed_geometry_clip.height - _T - _B > 0:
                        processed_geometry_clip = vs.core.std.Crop(processed_geometry_clip, left=_L, right=_R, top=_T, bottom=_B)
                        current_crop_values = (_L,_R,_T,_B)
                    else:
                        printwrap(f"Warning: crop for clip {i} skipped (target dimensions non-positive).")

                # Print dimensions and compc operations for the current clip
                printwrap(f"Processing {file_path}: Initial Dims: {original_clip_from_temp.width}x{original_clip_from_temp.height}")
                if True:  # Apply geometry to all clips (per-clip crop plan)
                    if current_resized_width > 0:
                        printwrap(f" Resize to: {current_resized_width}x{current_resized_height}")
                    if any(cv > 0 for cv in current_crop_values):
                        printwrap(f" Crop by: L={current_crop_values[0]} R={current_crop_values[1]} T={current_crop_values[2]} B={current_crop_values[3]}")
                printwrap(f"  Dims after geometry processing: {processed_geometry_clip.width}x{processed_geometry_clip.height}\n")


            # Extend clip if a frame is out of range (operates on geometrically processed clip)
            processed_geometry_clip = extend_clip(processed_geometry_clip, frames)
                
            # --- Color Processing (HDR Tone Mapping / SDR Conversion) ---
            # Get original properties from the clip *before* geometric alterations for accurate color decisions.
            actual_video_start_frame = 0
            # Check if negative trim was applied by init_clip (which is reflected in original_clip_from_temp)
            # trim_dict uses findex, which is 'i' here.
            if trim_dict.get(i) is not None and trim_dict.get(i) < 0:
                 actual_video_start_frame = abs(trim_dict.get(i))
            
            if actual_video_start_frame >= original_clip_from_temp.num_frames: # Safety for very short clips
                actual_video_start_frame = 0 
            
            original_frame_props = original_clip_from_temp.get_frame(actual_video_start_frame).props
            
            # Apply color processing to the (potentially) geometrically altered clip
            final_render_clip = process_clip_for_screenshot(processed_geometry_clip, original_frame_props, file_path)


            #if frame_info option selected, print frame info to screen
            if frame_info:
                # FIX: Convert to Limited Range for subtitle compatibility to avoid MaskedMerge errors.
                final_render_clip = final_render_clip.resize.Point(range=vs.RANGE_LIMITED, dither_type="none")
            final_render_clip = FrameInfo(final_render_clip, title=display_suffix)
            final_render_clip = final_render_clip.resize.Point(range=vs.RANGE_FULL, dither_type="none")
            
            #generate screens
            for frame_actual_index in frames: # Renamed loop variable

                # filename for screenshot uses display_suffix
                screenshot_filename = f"{screen_dir}/{frame_actual_index} - {display_suffix.strip()}.png" # Ensure suffix is stripped

                if ffmpeg:
                    # Ensure final_render_clip has valid dimensions for ffmpeg
                    if final_render_clip.width <= 0 or final_render_clip.height <= 0:
                        printwrap(f"Skipping FFmpeg for frame {frame_actual_index} of {file_path} due to invalid dimensions: {final_render_clip.width}x{final_render_clip.height}")
                        progress.update(total_gen_progress, advance=1) # Still advance progress
                        progress.update(file_gen_progress, advance=1)
                        continue
                    fps_for_ff = compute_ffmpeg_fps(final_render_clip)
                    ffmpeg_line = f"ffmpeg -y -hide_banner -loglevel error -f rawvideo -video_size {final_render_clip.width}x{final_render_clip.height} -pixel_format gbrp -framerate {fps_for_ff:g} -i pipe: -pred mixed -compression_level {compression} \"{screenshot_filename}\""
                    try:
                        with subprocess.Popen(ffmpeg_line, stdin=subprocess.PIPE, shell=True) as process: # shell=True from original
                            #ffmpeg needs these planes to be shuffled so they are in gbrp pixel_format (the p is important, rgb24 format doesnt work)
                            final_render_clip[frame_actual_index].std.ShufflePlanes([1, 2, 0], vs.RGB).output(cast(BinaryIO, process.stdin), y4m=False)
                    except Exception as e_ffmpeg:
                        printwrap(f"Error during FFmpeg processing for frame {frame_actual_index} of {file_path}: {e_ffmpeg}")
                        # Original script had 'None', which does nothing. Error is now printed.

                else: # fpng path
                    try:
                        # Original script: vs.core.fpng.Write(clip, filename, compression=compression, overwrite=True).get_frame(frame)
                        # Adapted: Use final_render_clip and frame_actual_index
                        vs.core.fpng.Write(final_render_clip, screenshot_filename, compression=compression, overwrite=True).get_frame(frame_actual_index)
                    except Exception as e_fpng:
                         printwrap(f"Error during fpng.Write for frame {frame_actual_index} of {file_path}: {e_fpng}")

                
                progress.update(total_gen_progress, advance=1)
                progress.update(file_gen_progress, advance=1)


    print()
    #print(time.time() - START_TIME)

    if slowpics:
        #time.sleep(0.5)

        browserId = str(uuid.uuid4())
        fields: Dict[str, Any] = {
            'collectionName': collection_name,
            'hentai': str(hentai_flag).lower(),
            'optimize-images': 'true',
            'browserId': browserId,
            'public': str(public_flag).lower()
        }

        if tmdbID != "":
            fields |= {'tmdbId': str(tmdbID)}
        if remove_after != "" and remove_after != 0: # remove_after is int
            fields |= {'removeAfter': str(remove_after)}

        all_image_files = os_sorted([f for f in os.listdir(screen_dir) if f.endswith('.png')])

        #check if all image files are present before uploading. if not, wait a bit and check again. if still not, exit program
        if len(all_image_files) < len(frames) * len(files):
            printwrap(f"Warning: Expected {len(frames) * len(files)} screenshots, found {len(all_image_files)}. Waiting briefly...")
            time.sleep(5)
            all_image_files = os_sorted([f for f in os.listdir(screen_dir) if f.endswith('.png')])

            if len(all_image_files) < len(frames) * len(files):
                sys.exit(f'Error: Number of screenshots in "{screen_dirname}" folder ({len(all_image_files)}) does not match expected value ({len(frames) * len(files)}).')
        
        for x_idx, frame_val in enumerate(frames): # Renamed x to x_idx, frames[x] to frame_val
            #current_comp is list of image files for this frame
            current_comp = [f for f in all_image_files if f.startswith(str(frame_val) + " - ")]

            #add field for comparison name. after every comparison name there needs to be as many image names as there are comped video files
            fields[f'comparisons[{x_idx}].name'] = str(frame_val)
            
            #iterate over the image files for this frame
            for i_img, imageName in enumerate(current_comp): # Renamed i to i_img
                image_path = screen_dir / imageName # Use pathlib for path construction
                # fields[f'comparisons[{x_idx}].imageNames[{i_img}]'] = os.path.basename(imageName).split(' - ', 1)[1].replace(".png", "")
                # More robust way to get display name part from filename "FRAME - DISPLAY_SUFFIX.png"
                # Assumes display_suffix does not contain " - "
                name_parts = os.path.basename(imageName).split(' - ', 1)
                if len(name_parts) > 1:
                    image_display_name = name_parts[1].removesuffix(".png")
                else: # Fallback if " - " not found
                    image_display_name = os.path.basename(imageName).removesuffix(".png")

                fields[f'comparisons[{x_idx}].imageNames[{i_img}]'] = image_display_name


                #this would upload the images all at once, but that wouldnt let us get progress
                #fields[f'comparisons[{x_idx}].images[{i_img}].file'] = (imageName, image_path.read_bytes(), 'image/png')


        with Session() as sess:
            # Initial request to get cookies like XSRF-TOKEN
            try:
                sess.get('https://slow.pics/comparison', timeout=10)
            except requests.exceptions.RequestException as e:
                sys.exit(f"Error connecting to slow.pics to get session cookies: {e}")

            if "XSRF-TOKEN" not in sess.cookies:
                 sys.exit("Error: Could not retrieve XSRF-TOKEN from slow.pics.")


            files_for_upload = MultipartEncoder(fields, str(uuid.uuid4())) # Renamed files to files_for_upload

            try:
                comp_req = sess.post(
                    'https://slow.pics/upload/comparison', data=files_for_upload.to_string(),
                    headers=_get_slowpics_header(str(files_for_upload.len), files_for_upload.content_type, sess),
                    timeout=30 
                )
                comp_req.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                comp_response = comp_req.json()
            except requests.exceptions.RequestException as e:
                sys.exit(f"Error creating comparison collection on slow.pics: {e}")
            except ValueError: # Includes JSONDecodeError
                sys.exit(f"Error decoding JSON response from slow.pics comparison creation. Response: {comp_req.text}")


            collection_uuid = comp_response.get("collectionUuid") # Renamed collection to collection_uuid
            key = comp_response.get("key")

            if not collection_uuid or not key:
                sys.exit(f"Error: Missing 'collectionUuid' or 'key' in slow.pics response: {comp_response}")


            with Progress(TextColumn("{task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"), TextColumn("{task.percentage:>3.02f}%"), TimeRemainingColumn()) as progress_upload: # Renamed progress
                upload_progress = progress_upload.add_task("[bright_magenta]Uploading to Slowpoke Pics", total=len(all_image_files))

                for index, image_section in enumerate(comp_response.get("images", [])):
                    base = index * file_count
                    for image_index, image_id in enumerate(image_section):
                        
                        current_image_filename = all_image_files[base + image_index]
                        current_image_path = screen_dir / current_image_filename

                        upload_info = {
                            "collectionUuid": collection_uuid,
                            "imageUuid": image_id,
                            "file": (current_image_filename, current_image_path.read_bytes(), 'image/png'),
                            'browserId': browserId,
                        }
                        upload_info_encoded = MultipartEncoder(upload_info, str(uuid.uuid4())) # Renamed upload_info
                        try:
                            upload_response = sess.post(
                                'https://slow.pics/upload/image', data=upload_info_encoded.to_string(),
                                headers=_get_slowpics_header(str(upload_info_encoded.len), upload_info_encoded.content_type, sess),
                                timeout=60 # Increased timeout for image upload
                            )
                            upload_response.raise_for_status()

                            progress_upload.update(upload_progress, advance=1)

                            assert upload_response.content.decode() == "OK", f"Content not OK: {upload_response.content.decode()}"
                        except requests.exceptions.RequestException as e:
                            printwrap(f"\nError uploading image {current_image_filename} to slow.pics: {e}")
                            # Decide whether to continue or exit
                        except AssertionError as e:
                            printwrap(f"\nAssertion failed for image {current_image_filename}: {e}")


        slowpics_url = f'https://slow.pics/c/{key}'
        print(f'\nSlowpoke Pics url: {slowpics_url}', end='')
        try:
            pc.copy(slowpics_url)
        except pc.PyperclipException as e:
            printwrap(f"\nCould not copy URL to clipboard: {e}")


        if browser_open:
            webbrowser.open(slowpics_url)

        if webhook_url:
            try:
                webhook_response = requests.post(webhook_url, json={"content": slowpics_url}, timeout=10) # Send as JSON
                if webhook_response.status_code < 300:
                    print('Posted to webhook.')
                else:
                    print(f'Failed to post on webhook! Status: {webhook_response.status_code}, Response: {webhook_response.text}')
            except requests.exceptions.RequestException as e:
                print(f'Error posting to webhook: {e}')


        if url_shortcut:
            #datetime.datetime.now().strftime("%Y.%m.%d") + " - " + 
            shortcut_dir = pathlib.Path("Comparisons") # Use pathlib
            shortcut_dir.mkdir(exist_ok=True) # Create dir if not exists
            
            # Sanitize collection_name for use in filename
            sane_collection_name = re.sub(r'[<>:"/\\|?*]', '_', collection_name) # Replace invalid chars
            sane_key = re.sub(r'[<>:"/\\|?*]', '_', key)
            shortcut_filename = f"{sane_collection_name} - {sane_key}.url"
            shortcut_path = shortcut_dir / shortcut_filename


            with open(shortcut_path, "w", encoding='utf-8') as shortcut:
                shortcut.write(f'[InternetShortcut]\nURL={slowpics_url}')

        if delete_screen_dir and screen_dir.is_dir(): # Check with pathlib
            shutil.rmtree(screen_dir)

        time.sleep(3)

if __name__ == "__main__":
    run_comparison()


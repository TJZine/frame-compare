"""CLI entry point and orchestration logic for frame comparison runs."""

from __future__ import annotations

import asyncio
import datetime as _dt  # noqa: F401  (re-exported via frame_compare)
import importlib.util  # noqa: F401  # Legacy tests monkeypatch core.importlib
import logging
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    List,
    Mapping,
    MutableMapping,
    NoReturn,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

import click
import httpx
from rich import print
from rich.console import Console  # noqa: F401
from rich.progress import Progress, ProgressColumn  # noqa: F401

from src import audio_alignment as _audio_alignment_module
from src.config_loader import load_config as _load_config
from src.datatypes import TMDBConfig

if TYPE_CHECKING:
    class _AsyncHTTPTransport(Protocol):
        def __init__(self, retries: int = ...) -> None: ...
        def close(self) -> None: ...

import src.frame_compare.alignment_preview as _alignment_preview_module
import src.frame_compare.alignment_runner as _alignment_runner_module
import src.frame_compare.doctor as _doctor_module
import src.frame_compare.metadata as _metadata_module
import src.frame_compare.planner as _planner_module
import src.frame_compare.preflight as _preflight_constants
import src.frame_compare.vspreview as _vspreview_module
import src.frame_compare.wizard as _wizard_module
import src.screenshot as _screenshot_module
from src import vs_core
from src.analysis import (
    export_selection_metadata,  # noqa: F401
    probe_cached_metrics,  # noqa: F401
    select_frames,  # noqa: F401
    selection_details_to_json,  # noqa: F401
    selection_hash_for_config,  # noqa: F401
    write_selection_cache_file,  # noqa: F401
)
from src.frame_compare.cli_runtime import (
    AudioAlignmentJSON,  # noqa: F401 - re-exported for compatibility
    CLIAppError,  # noqa: F401 - re-exported for compatibility
    ClipRecord,  # noqa: F401 - re-exported for compatibility
    JsonTail,  # noqa: F401 - re-exported for compatibility
    ReportJSON,  # noqa: F401 - re-exported for compatibility
    SlowpicsJSON,  # noqa: F401 - re-exported for compatibility
    SlowpicsTitleBlock,  # noqa: F401 - re-exported for compatibility
    SlowpicsTitleInputs,  # noqa: F401 - re-exported for compatibility
    TrimClipEntry,  # noqa: F401 - re-exported for compatibility
    TrimsJSON,  # noqa: F401 - re-exported for compatibility
    TrimSummary,  # noqa: F401 - re-exported for compatibility
    ViewerJSON,  # noqa: F401 - re-exported for compatibility
    _ClipPlan,  # noqa: F401 - re-exported for compatibility
    _coerce_str_mapping,
)
from src.frame_compare.preflight import (
    PACKAGED_TEMPLATE_PATH,  # noqa: F401 - compatibility re-export
    PROJECT_ROOT,  # noqa: F401 - compatibility re-export
    PreflightResult,
    collect_path_diagnostics,
    prepare_preflight,
)
from src.frame_compare.preflight import (
    _abort_if_site_packages as _preflight_abort_if_site_packages,
)
from src.slowpics import SlowpicsAPIError, build_shortcut_filename, upload_comparison  # noqa: F401
from src.tmdb import (
    TMDBAmbiguityError,  # noqa: F401
    TMDBCandidate,
    TMDBResolution,
    TMDBResolutionError,
    parse_manual_id,
    resolve_tmdb,  # noqa: F401
)
from src.vs_core import ClipInitError, ClipProcessError  # noqa: F401

logger = logging.getLogger(__name__)

CONFIG_ENV_VAR: Final[str] = _preflight_constants.CONFIG_ENV_VAR
NO_WIZARD_ENV_VAR: Final[str] = _preflight_constants.NO_WIZARD_ENV_VAR
ROOT_ENV_VAR: Final[str] = _preflight_constants.ROOT_ENV_VAR
ROOT_SENTINELS: Final[tuple[str, ...]] = _preflight_constants.ROOT_SENTINELS
resolve_workspace_root = _preflight_constants.resolve_workspace_root

ScreenshotError = _screenshot_module.ScreenshotError
generate_screenshots = _screenshot_module.generate_screenshots
_fresh_app_config = _preflight_constants._fresh_app_config
_PathPreflightResult = PreflightResult
_prepare_preflight = prepare_preflight
_collect_path_diagnostics = collect_path_diagnostics
_confirm_alignment_with_screenshots = _alignment_preview_module._confirm_alignment_with_screenshots
load_config = _load_config
build_plans = _planner_module.build_plans
_build_plans = _planner_module.build_plans

audio_alignment = _audio_alignment_module
_AudioAlignmentSummary = _alignment_runner_module._AudioAlignmentSummary
_AudioAlignmentDisplayData = _alignment_runner_module._AudioAlignmentDisplayData
_AudioMeasurementDetail = _alignment_runner_module._AudioMeasurementDetail
apply_audio_alignment = _alignment_runner_module.apply_audio_alignment
format_alignment_output = _alignment_runner_module.format_alignment_output
_maybe_apply_audio_alignment = _alignment_runner_module.apply_audio_alignment
_resolve_alignment_reference = _alignment_runner_module._resolve_alignment_reference
_prompt_vspreview_offsets = _vspreview_module.prompt_offsets
_apply_vspreview_manual_offsets = _vspreview_module.apply_manual_offsets
_write_vspreview_script = _vspreview_module.write_script
_launch_vspreview = _vspreview_module.launch
_format_vspreview_manual_command = _vspreview_module.format_manual_command
_VSPREVIEW_WINDOWS_INSTALL = _vspreview_module.VSPREVIEW_WINDOWS_INSTALL
_VSPREVIEW_POSIX_INSTALL = _vspreview_module.VSPREVIEW_POSIX_INSTALL

_DEFAULT_CONFIG_HELP: Final[str] = (
    "Optional explicit path to config.toml. When omitted, Frame Compare looks for "
    "ROOT/config/config.toml (see --root/FRAME_COMPARE_ROOT)."
)


DoctorStatus = _doctor_module.DoctorStatus
DoctorCheck = _doctor_module.DoctorCheck


def _resolve_wizard_paths(root_override: str | None, config_override: str | None) -> tuple[Path, Path]:
    """Backward-compatible shim that defers to the wizard module implementation."""

    return _wizard_module.resolve_wizard_paths(root_override, config_override)


def _abort_if_site_packages(path_map: Mapping[str, Path]) -> None:
    """Backward-compatible shim that defers to the preflight helper."""

    _preflight_abort_if_site_packages(path_map)




@dataclass
class TMDBLookupResult:
    """Outcome of the TMDB workflow (resolution, manual overrides, or failure)."""

    resolution: TMDBResolution | None
    manual_override: tuple[str, str] | None
    error_message: Optional[str]
    ambiguous: bool


def _should_retry_tmdb_error(message: str) -> bool:
    """Return True when *message* indicates a transient TMDB/HTTP failure."""

    lowered = message.lower()
    transient_markers = (
        "request failed",
        "timeout",
        "temporarily",
        "connection",
        "503",
        "502",
        "504",
        "429",
    )
    return any(marker in lowered for marker in transient_markers)


def _resolve_tmdb_blocking(
    *,
    file_name: str,
    tmdb_cfg: TMDBConfig,
    year_hint: Optional[int],
    imdb_id: Optional[str],
    tvdb_id: Optional[str],
    attempts: int = 3,
    transport_retries: int = 2,
) -> TMDBResolution | None:
    """Resolve TMDB metadata even when the caller already owns an event loop."""

    max_attempts = max(1, attempts)
    backoff = 0.75
    for attempt in range(max_attempts):
        transport_cls = getattr(httpx, "AsyncHTTPTransport", None)
        if transport_cls is None:
            raise RuntimeError("httpx.AsyncHTTPTransport is unavailable in this environment")
        transport = transport_cls(retries=max(0, transport_retries))

        async def _make_coro():
            return await resolve_tmdb(
                file_name,
                config=tmdb_cfg,
                year=year_hint,
                imdb_id=imdb_id,
                tvdb_id=tvdb_id,
                unattended=tmdb_cfg.unattended,
                category_preference=tmdb_cfg.category_preference,
                http_transport=transport,
            )

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(_make_coro())

            result_holder: list[TMDBResolution | None] = []
            error_holder: list[BaseException] = []

            def _worker() -> None:
                try:
                    result_holder.append(asyncio.run(_make_coro()))
                except BaseException as exc:  # pragma: no cover - bubbled up when joined
                    error_holder.append(exc)

            thread = threading.Thread(target=_worker, daemon=True)
            thread.start()
            thread.join()
            if error_holder:
                raise error_holder[0]
            return result_holder[0] if result_holder else None
        except TMDBResolutionError as exc:
            message = str(exc)
            if attempt + 1 >= max_attempts or not _should_retry_tmdb_error(message):
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
        finally:
            close_fn = getattr(transport, "close", None)
            if callable(close_fn):
                close_fn()
    return None


def resolve_tmdb_workflow(
    *,
    files: Sequence[Path],
    metadata: Sequence[Mapping[str, str]],
    tmdb_cfg: TMDBConfig,
    year_hint_raw: Optional[str] = None,
) -> TMDBLookupResult:
    """
    Resolve TMDB metadata for the current comparison set, prompting when needed.
    """

    if not files or not tmdb_cfg.api_key.strip():
        return TMDBLookupResult(
            resolution=None,
            manual_override=None,
            error_message=None,
            ambiguous=False,
        )

    base_file = files[0]
    imdb_hint_raw = _metadata_module.first_non_empty(metadata, "imdb_id")
    imdb_hint = imdb_hint_raw.lower() if imdb_hint_raw else None
    tvdb_hint = _metadata_module.first_non_empty(metadata, "tvdb_id") or None
    effective_year_hint = year_hint_raw or _metadata_module.first_non_empty(metadata, "year")
    year_hint = _metadata_module.parse_year_hint(effective_year_hint)

    resolution: TMDBResolution | None = None
    manual_tmdb: tuple[str, str] | None = None
    error_message: Optional[str] = None
    ambiguous = False

    try:
        resolution = _resolve_tmdb_blocking(
            file_name=base_file.name,
            tmdb_cfg=tmdb_cfg,
            year_hint=year_hint,
            imdb_id=imdb_hint,
            tvdb_id=tvdb_hint,
        )
    except TMDBAmbiguityError as exc:
        ambiguous = True
        if tmdb_cfg.unattended:
            error_message = (
                "TMDB returned multiple matches but unattended mode prevented prompts."
            )
        else:
            manual_tmdb = _prompt_manual_tmdb(exc.candidates)
    except TMDBResolutionError as exc:
        error_message = str(exc)
    else:
        if resolution is not None and tmdb_cfg.confirm_matches and not tmdb_cfg.unattended:
            accepted, override = _prompt_tmdb_confirmation(resolution)
            if override:
                manual_tmdb = override
                resolution = None
            elif not accepted:
                resolution = None

    return TMDBLookupResult(
        resolution=resolution,
        manual_override=manual_tmdb,
        error_message=error_message,
        ambiguous=ambiguous,
    )


def _prompt_manual_tmdb(candidates: Sequence[TMDBCandidate]) -> tuple[str, str] | None:
    """Prompt the user to choose a TMDB candidate when multiple matches exist."""
    print("[yellow]TMDB search returned multiple plausible matches:[/yellow]")
    for cand in candidates:
        year = cand.year or "????"
        print(
            f"  • [cyan]{cand.category.lower()}/{cand.tmdb_id}[/cyan] "
            f"{cand.title or '(unknown title)'} ({year}) score={cand.score:0.3f}"
        )
    while True:
        response = click.prompt(
            "Enter TMDB id (movie/##### or tv/#####) or leave blank to skip",
            default="",
            show_default=False,
        ).strip()
        if not response:
            return None
        try:
            return parse_manual_id(response)
        except TMDBResolutionError as exc:
            print(f"[red]Invalid TMDB identifier:[/red] {exc}")


def _prompt_tmdb_confirmation(
    resolution: TMDBResolution,
) -> tuple[bool, tuple[str, str] | None]:
    """Ask the user to confirm the TMDB result or supply a manual override."""
    title = resolution.title or resolution.original_title or "(unknown title)"
    year = resolution.year or "????"
    category = resolution.category.lower()
    link = f"https://www.themoviedb.org/{category}/{resolution.tmdb_id}"
    print(
        "[cyan]TMDB match found:[/cyan] "
        f"{title} ({year}) -> [underline]{link}[/underline]"
    )
    while True:
        response = click.prompt(
            "Confirm TMDB match? [Y/n or enter movie/#####]",
            default="y",
            show_default=False,
        ).strip()
        if not response or response.lower() in {"y", "yes"}:
            return True, None
        if response.lower() in {"n", "no"}:
            return False, None
        try:
            manual = parse_manual_id(response)
        except TMDBResolutionError as exc:
            print(f"[red]Invalid TMDB identifier:[/red] {exc}")
        else:
            return True, manual


def _render_collection_name(template_text: str, context: Mapping[str, str]) -> str:
    """Render the configured TMDB collection template with *context* values."""
    if "${" not in template_text:
        return template_text
    try:
        template = Template(template_text)
        return template.safe_substitute(context)
    except Exception:
        return template_text


def _estimate_analysis_time(file: Path, cache_dir: Path | None) -> float:
    """Estimate time to read two small windows of frames via VapourSynth.

    Mirrors the legacy heuristic: read ~15 frames around 1/3 and 2/3 into the clip,
    average the elapsed time. Returns +inf on failure so slower/unreadable clips are avoided.
    """
    try:
        clip = vs_core.init_clip(str(file), cache_dir=str(cache_dir) if cache_dir else None)
    except Exception:
        return float("inf")

    try:
        total = getattr(clip, "num_frames", 0)
        if not isinstance(total, int) or total <= 1:
            return float("inf")
        read_len = 15
        # safeguard when the clip is very short
        while (total // 3) + 1 < read_len and read_len > 1:
            read_len -= 1

        stats = clip.std.PlaneStats()

        def _read_window(base: int) -> float:
            start = max(0, min(base, max(0, total - 1)))
            t0 = time.perf_counter()
            for j in range(read_len):
                idx = min(start + j, max(0, total - 1))
                frame = stats.get_frame(idx)
                del frame
            return time.perf_counter() - t0

        t1 = _read_window(total // 3)
        t2 = _read_window((2 * total) // 3)
        return (t1 + t2) / 2.0
    except Exception:
        return float("inf")


def _pick_analyze_file(
    files: Sequence[Path],
    metadata: Sequence[Mapping[str, str]],
    target: str | None,
    *,
    cache_dir: Path | None = None,
) -> Path:
    """Resolve the clip to analyse, honouring user targets and heuristics."""
    if not files:
        raise ValueError("No files to analyze")
    target = (target or "").strip()
    if not target:
        # Legacy parity: default to the file with the smallest estimated read time.
        print("[cyan]Determining which file to analyze...[/cyan]")
        times = [(_estimate_analysis_time(file, cache_dir), idx) for idx, file in enumerate(files)]
        times.sort(key=lambda x: x[0])
        fastest_idx = times[0][1] if times else 0
        return files[fastest_idx]

    target_lower = target.lower()

    # Allow numeric index selection
    if target.isdigit():
        idx = int(target)
        if 0 <= idx < len(files):
            return files[idx]

    for idx, file in enumerate(files):
        if file.name.lower() == target_lower or file.stem.lower() == target_lower:
            return file
        meta = metadata[idx]
        for key in ("label", "release_group", "anime_title", "file_name"):
            value = str(meta.get(key) or "")
            if value and value.lower() == target_lower:
                return file
        if target_lower == str(idx):
            return file

    return files[0]


def _extract_clip_fps(clip: object) -> Tuple[int, int]:
    """Return (fps_num, fps_den) from *clip*, defaulting to 24000/1001 when missing."""
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return (num, den)
    return (24000, 1001)


def _format_seconds(value: float) -> str:
    """
    Format a time value in seconds as an HH:MM:SS.s string with one decimal place.

    Negative input is treated as zero. The seconds component is rounded to one decimal place and may carry into minutes (and similarly minutes into hours) when rounding produces overflow.

    Parameters:
        value (float): Time in seconds.

    Returns:
        str: Formatted time as "HH:MM:SS.s" with two-digit hours and minutes and one decimal place for seconds.
    """
    total = max(0.0, float(value))
    hours = int(total // 3600)
    minutes = int((total - hours * 3600) // 60)
    seconds = total - hours * 3600 - minutes * 60
    seconds = round(seconds, 1)
    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        hours += 1
    return f"{hours:02d}:{minutes:02d}:{seconds:04.1f}"


def _fps_to_float(value: Tuple[int, int] | None) -> float:
    """
    Convert an FPS expressed as a (numerator, denominator) tuple into a floating-point frames-per-second value.

    Parameters:
        value ((int, int) | None): A two-integer tuple representing FPS as (numerator, denominator). May be None.

    Returns:
        float: The FPS as a float. Returns 0.0 if `value` is None, the denominator is zero, or the tuple is invalid.
    """
    if not value:
        return 0.0
    num, den = value
    if not den:
        return 0.0
    return float(num) / float(den)


def _fold_sequence(
    values: Sequence[object],
    *,
    head: int,
    tail: int,
    joiner: str,
    enabled: bool,
) -> str:
    """
    Produce a compact string representation of a sequence by optionally folding the middle elements with an ellipsis.

    Parameters:
        values (Sequence[object]): Items to render; each item is stringified.
        head (int): Number of items to keep from the start when folding is enabled.
        tail (int): Number of items to keep from the end when folding is enabled.
        joiner (str): Separator used to join items.
        enabled (bool): If True and the sequence is longer than head + tail, replace the omitted middle with "…".

    Returns:
        str: The joined string containing all items when folding is disabled or not needed, or a string containing the head items, a single "…" token, and the tail items when folding is applied.
    """
    items = [str(item) for item in values]
    if not enabled or len(items) <= head + tail:
        return joiner.join(items)
    head_items = items[: max(0, head)]
    tail_items = items[-max(0, tail) :]
    if not head_items:
        return joiner.join(tail_items)
    if not tail_items:
        return joiner.join(head_items)
    return joiner.join([*head_items, "…", *tail_items])


def _evaluate_rule_condition(condition: Optional[str], *, flags: Mapping[str, Any]) -> bool:
    """
    Evaluate a simple rule condition string against a mapping of flags.

    The condition may be None/empty (treated as satisfied), a flag name (satisfied if the flag is truthy), or a negated flag name prefixed with `!`. Known tokens `verbose` and `upload_enabled` are supported like any other flag name.

    Parameters:
        condition (Optional[str]): The rule expression to evaluate (e.g. "verbose", "!upload_enabled") or None/empty to always satisfy.
        flags (Mapping[str, Any]): Mapping of flag names to values; values are interpreted by their truthiness.

    Returns:
        True if the condition is satisfied given `flags`, False otherwise.
    """
    if not condition:
        return True
    expr = condition.strip()
    if not expr:
        return True
    if expr == "!verbose":
        return not bool(flags.get("verbose"))
    if expr == "verbose":
        return bool(flags.get("verbose"))
    if expr == "upload_enabled":
        return bool(flags.get("upload_enabled"))
    if expr == "!upload_enabled":
        return not bool(flags.get("upload_enabled"))
    return bool(flags.get(expr))


def _build_legacy_summary_lines(values: Mapping[str, Any], *, emit_json_tail: bool) -> List[str]:
    """
    Generate legacy human-readable summary lines from the collected layout values.

    Parameters:
        values (Mapping[str, Any]): Mapping containing layout sections (for example:
            "clips", "window", "analysis", "audio_alignment", "render",
            "tonemap", "cache"). The function reads specific keys from those
            sections to synthesize compact summary lines.

    Returns:
        List[str]: A list of non-empty summary lines suitable for the legacy
        textual summary display.
    """

    def _maybe_number(value: Any) -> float | None:
        """Convert numeric-like input to float, returning ``None`` on failure."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_number(value: Any, fmt: str, fallback: str) -> str:
        """Format numeric values with ``fmt``; fall back to the provided string."""
        number = _maybe_number(value)
        if number is None:
            return fallback
        return format(number, fmt)

    def _string(value: Any, fallback: str = "n/a") -> str:
        """Return lowercase booleans, fallback for ``None``, else ``str(value)``."""
        if value is None:
            return fallback
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _bool_text(value: Any) -> str:
        """
        Format a value as lowercase boolean text.

        Returns:
            `'true'` if the value evaluates to True, `'false'` otherwise.
        """
        return "true" if bool(value) else "false"

    clips = _coerce_str_mapping(values.get("clips"))
    window = _coerce_str_mapping(values.get("window"))
    analysis = _coerce_str_mapping(values.get("analysis"))
    counts = _coerce_str_mapping(analysis.get("counts")) if analysis else {}
    audio = _coerce_str_mapping(values.get("audio_alignment"))
    render = _coerce_str_mapping(values.get("render"))
    tonemap = _coerce_str_mapping(values.get("tonemap"))
    cache = _coerce_str_mapping(values.get("cache"))

    lines: List[str] = []

    clip_count = _string(clips.get("count"), "0")
    lead_text = _format_number(window.get("ignore_lead_seconds"), ".2f", "0.00")
    trail_text = _format_number(window.get("ignore_trail_seconds"), ".2f", "0.00")
    step_text = _string(analysis.get("step"), "0")
    downscale_text = _string(analysis.get("downscale_height"), "0")
    lines.append(
        f"Clips: {clip_count}  Window: lead={lead_text}s trail={trail_text}s  step={step_text} downscale={downscale_text}px"
    )

    offsets_text = _format_number(audio.get("offsets_sec"), "+.3f", "+0.000")
    offsets_file = _string(audio.get("offsets_filename"), "n/a")
    lines.append(
        f"Align: audio={_bool_text(audio.get('enabled'))}  offsets={offsets_text}s  file={offsets_file}"
    )

    lines.append(
        "Plan: "
        f"Dark={_string(counts.get('dark'), '0')} "
        f"Bright={_string(counts.get('bright'), '0')} "
        f"Motion={_string(counts.get('motion'), '0')} "
        f"Random={_string(counts.get('random'), '0')} "
        f"User={_string(counts.get('user'), '0')}  "
        f"sep={_format_number(analysis.get('screen_separation_sec'), '.1f', '0.0')}s"
    )

    lines.append(
        "Canvas: "
        f"single_res={_string(render.get('single_res'), '0')} "
        f"upscale={_bool_text(render.get('upscale'))} "
        f"crop=mod{_string(render.get('mod_crop'), '0')} "
        f"pad={_bool_text(render.get('center_pad'))}"
    )

    tonemap_curve = _string(tonemap.get("tone_curve"), "n/a")
    tonemap_target = _format_number(tonemap.get("target_nits"), ".0f", "0")
    tonemap_dst_min = _format_number(tonemap.get("dst_min_nits"), ".2f", "0.00")
    tonemap_knee = _format_number(tonemap.get("knee_offset"), ".2f", "0.00")
    tonemap_preset_label = _string(tonemap.get("dpd_preset"), "n/a")
    tonemap_cutoff = _format_number(tonemap.get("dpd_black_cutoff"), ".3f", "0.000")
    tonemap_gamma = _format_number(tonemap.get("post_gamma"), ".2f", "1.00")
    gamma_flag = "*" if bool(tonemap.get("post_gamma_enabled")) else ""
    dpd_enabled = bool(
        tonemap.get("dpd")
        if "dpd" in tonemap
        else tonemap.get("dynamic_peak_detection")
    )
    preset_suffix = f" ({tonemap_preset_label})" if dpd_enabled and tonemap_preset_label.lower() != "n/a" else ""
    lines.append(
        "Tonemap: "
        f"{tonemap_curve}@{tonemap_target}nits "
        f"dst_min={tonemap_dst_min} knee={tonemap_knee} "
        f"dpd={_bool_text(dpd_enabled)}"
        f"{preset_suffix} black_cutoff={tonemap_cutoff}  "
        f"gamma={tonemap_gamma}{gamma_flag}  "
        f"verify≤{_format_number(tonemap.get('verify_luma_threshold'), '.2f', '0.00')}"
    )

    lines.append(
        f"Output: {_string(render.get('out_dir'), 'n/a')}  compression={_string(render.get('compression'), 'n/a')}"
    )

    lines.append(f"Cache: {_string(cache.get('file'), 'n/a')}  {_string(cache.get('status'), 'unknown')}")

    frame_count = _string(analysis.get("output_frame_count"), "0")
    preview = _string(analysis.get("output_frames_preview"), "")
    preview_display = f"[{preview}]" if preview else "[]"
    if emit_json_tail:
        lines.append(
            f"Output frames: {frame_count}  e.g., {preview_display}  (full list in JSON)"
        )
    else:
        full_list = _string(analysis.get("output_frames_full"), "[]")
        lines.append(f"Output frames ({frame_count}): {full_list}")

    return [line for line in lines if line]


def _format_clock(seconds: Optional[float]) -> str:
    """Format seconds as H:MM:SS (or MM:SS) with a placeholder for invalid input."""
    if seconds is None or not math.isfinite(seconds):
        return "--:--"
    total = max(0, int(seconds + 0.5))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _validate_tonemap_overrides(overrides: MutableMapping[str, Any]) -> None:
    """Validate CLI-provided tonemap overrides and raise ClickException on invalid values."""

    if not overrides:
        return

    def _bad(message: str) -> NoReturn:
        raise click.ClickException(message)

    parsed_floats: dict[str, float] = {}

    def _get_float(key: str, error_message: str) -> float:
        if key in parsed_floats:
            return parsed_floats[key]
        try:
            value = float(overrides[key])
        except (TypeError, ValueError):
            _bad(error_message)
        if not math.isfinite(value):
            _bad(error_message)
        parsed_floats[key] = value
        return value

    if "knee_offset" in overrides:
        knee_value = _get_float(
            "knee_offset",
            "--tm-knee must be a finite number in [0.0, 1.0]",
        )
        if knee_value < 0.0 or knee_value > 1.0:
            _bad("--tm-knee must be between 0.0 and 1.0")
    if "dst_min_nits" in overrides:
        dst_value = _get_float(
            "dst_min_nits",
            "--tm-dst-min must be a finite, non-negative number",
        )
        if dst_value < 0.0:
            _bad("--tm-dst-min must be >= 0.0")
    if "target_nits" in overrides:
        target_value = _get_float(
            "target_nits",
            "--tm-target must be a finite, positive number",
        )
        if target_value <= 0.0:
            _bad("--tm-target must be > 0")
    if "post_gamma" in overrides:
        gamma_value = _get_float(
            "post_gamma",
            "--tm-gamma must be a finite number between 0.9 and 1.1",
        )
        if gamma_value < 0.9 or gamma_value > 1.1:
            _bad("--tm-gamma must be between 0.9 and 1.1")
    if "dpd_preset" in overrides:
        dpd_value = str(overrides["dpd_preset"]).strip().lower()
        if dpd_value not in {"off", "fast", "balanced", "high_quality"}:
            _bad("--tm-dpd-preset must be one of: off, fast, balanced, high_quality")
    if "dpd_black_cutoff" in overrides:
        cutoff = _get_float(
            "dpd_black_cutoff",
            "--tm-dpd-black-cutoff must be a finite number in [0.0, 0.05]",
        )
        if cutoff < 0.0 or cutoff > 0.05:
            _bad("--tm-dpd-black-cutoff must be between 0.0 and 0.05")
    if "smoothing_period" in overrides:
        smoothing = _get_float(
            "smoothing_period",
            "--tm-smoothing must be a finite, non-negative number",
        )
        if smoothing < 0.0:
            _bad("--tm-smoothing must be >= 0")
    if "scene_threshold_low" in overrides:
        low_value = _get_float(
            "scene_threshold_low",
            "--tm-scene-low must be a finite, non-negative number",
        )
        if low_value < 0.0:
            _bad("--tm-scene-low must be >= 0")
    if "scene_threshold_high" in overrides:
        high_value = _get_float(
            "scene_threshold_high",
            "--tm-scene-high must be a finite, non-negative number",
        )
        if high_value < 0.0:
            _bad("--tm-scene-high must be >= 0")
    if "scene_threshold_low" in overrides and "scene_threshold_high" in overrides:
        high_value = parsed_floats["scene_threshold_high"]
        low_value = parsed_floats["scene_threshold_low"]
        if high_value < low_value:
            _bad("--tm-scene-high must be >= --tm-scene-low")
    if "percentile" in overrides:
        percentile = _get_float(
            "percentile",
            "--tm-percentile must be a finite number between 0 and 100",
        )
        if percentile < 0.0 or percentile > 100.0:
            _bad("--tm-percentile must be between 0 and 100")
    if "contrast_recovery" in overrides:
        contrast = _get_float(
            "contrast_recovery",
            "--tm-contrast must be a finite, non-negative number",
        )
        if contrast < 0.0:
            _bad("--tm-contrast must be >= 0")
    if "metadata" in overrides:
        meta_value = overrides["metadata"]
        if isinstance(meta_value, str):
            lowered = meta_value.strip().lower()
            if lowered in {"auto", ""}:
                overrides["metadata"] = "auto"
            elif lowered in {"none", "hdr10", "hdr10+", "hdr10plus", "luminance"}:
                overrides["metadata"] = lowered
            else:
                try:
                    meta_int = int(lowered)
                except ValueError:
                    _bad("--tm-metadata must be auto, none, hdr10, hdr10+, luminance, or 0-4")
                else:
                    if meta_int < 0 or meta_int > 4:
                        _bad("--tm-metadata integer must be between 0 and 4")
                    overrides["metadata"] = meta_int
        else:
            try:
                meta_int = int(meta_value)
            except (TypeError, ValueError):
                _bad("--tm-metadata must be auto, none, hdr10, hdr10+, luminance, or 0-4")
            else:
                if meta_int < 0 or meta_int > 4:
                    _bad("--tm-metadata integer must be between 0 and 4")
    if "use_dovi" in overrides:
        if overrides["use_dovi"] not in {None, True, False}:
            _bad("--tm-use-dovi/--tm-no-dovi must be specified without a value")
    for boolean_key in ("visualize_lut", "show_clipping"):
        if boolean_key in overrides and not isinstance(overrides[boolean_key], bool):
            _bad(f"--tm-{boolean_key.replace('_', '-')} must be used without a value")

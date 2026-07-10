from __future__ import annotations

from pathlib import Path

from click import Group
from typer.main import get_command

from frame_compare.cli.entry import app
from frame_compare.config.overrides import CLI_OVERRIDE_MAP
from frame_compare.config.schema import AnalysisConfig
from frame_compare.config.schema_enums import AnalysisPerformanceMode


def _declared_run_options() -> set[str]:
    command = get_command(app)
    assert isinstance(command, Group)
    run_command = command.commands["run"]
    return {
        opt
        for param in run_command.params
        for opt in (*getattr(param, "opts", ()), *getattr(param, "secondary_opts", ()))
    }


def test_current_cli_contract_matches_live_override_map() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    mapping_section = cli_contract.split("## CLI Flag To Config Mapping", maxsplit=1)[1].split(
        "## Config-Only Analysis Surface",
        maxsplit=1,
    )[0]

    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        flag = f"--{cli_name.replace('_', '-')}"
        expected_row = f"| `{flag}` | `{config_path}` |"
        assert expected_row in mapping_section


def test_current_cli_contract_documents_analysis_performance_mode_config_and_summary() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    analysis_heading = "## Config-Only Analysis Surface"
    slowpics_heading = "## Config-Only slow.pics Surface"
    assert analysis_heading in cli_contract, f"Missing heading: {analysis_heading}"

    analysis_section = cli_contract.split(analysis_heading, maxsplit=1)[1].split(
        slowpics_heading,
        maxsplit=1,
    )[0]
    run_section = cli_contract.split("## `run` Command Contract", maxsplit=1)[1].split(
        "## CLI Flag To Config Mapping",
        maxsplit=1,
    )[0]
    normalized_analysis_section = " ".join(analysis_section.split())
    declared_options = _declared_run_options()

    assert AnalysisConfig().performance_mode == AnalysisPerformanceMode.QUALITY
    assert 'performance_mode = "quality"' in analysis_section
    assert '`performance_mode = "quality" | "performance"`' in analysis_section
    assert "There is no dedicated `run` flag for analysis performance mode in v1." in (
        analysis_section
    )
    assert "--analysis-performance" not in declared_options
    assert "analysis.performance_mode" not in CLI_OVERRIDE_MAP.values()
    assert "cache-isolated from `quality`" in normalized_analysis_section
    assert "Both modes apply the prepared active picture rectangle" in (normalized_analysis_section)
    assert "trusted static metadata, configured dimension/aspect-ratio detection" in (
        normalized_analysis_section
    )
    assert "There are no new analysis performance modes or aliases for active-rect detection" in (
        normalized_analysis_section
    )
    assert "`quality` and `performance` consume the same prepared rectangle" in (
        normalized_analysis_section
    )
    assert "The `analysis mode` row reports the effective `analysis.performance_mode`:" in (
        run_section
    )
    assert "`quality` or `performance`." in run_section


def test_current_cli_contract_documents_screenshot_config_only_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    screenshot_heading = "## Config-Only Screenshot Surface"
    persistence_heading = "## Persistence Rules"
    assert screenshot_heading in cli_contract, f"Missing heading: {screenshot_heading}"
    assert persistence_heading in cli_contract, f"Missing heading: {persistence_heading}"

    screenshot_section = cli_contract.split(screenshot_heading, maxsplit=1)[1].split(
        persistence_heading,
        maxsplit=1,
    )[0]

    for expected in (
        '`geometry_mode = "native" | "aligned"`',
        '`vs_writer = "auto" | "pillow" | "fpng"`',
        "`png_compression` remains an integer from `0` through `9`",
        "config-only public surfaces",
        "dedicated `run` flags",
        "preserves current behavior until a writer-specific",
        "explicit `fpng` requires successful VapourSynth loading and does not silently fall",
        "Fpng maps `0..3` to `0`, `4..6` to `1`, and `7..9` to `2`",
        "unsupported values fail config validation rather than being silently clamped",
    ):
        assert expected in screenshot_section

    command_heading = "## Command Surface"
    screenshot_heading = "## Config-Only Screenshot Surface"
    command_override_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        screenshot_heading,
        maxsplit=1,
    )[0]

    for unsupported_flag in ("--geometry-mode", "--vs-writer", "--png-compression"):
        assert unsupported_flag not in command_override_surface


def test_current_cli_contract_documents_sources_config_only_surface() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    sources_heading = "## Config-Only Sources Surface"
    version_heading = "## `version` Command Contract"
    assert sources_heading in cli_contract, f"Missing heading: {sources_heading}"

    sources_section = cli_contract.split(sources_heading, maxsplit=1)[1].split(
        version_heading,
        maxsplit=1,
    )[0]
    normalized_sources_section = " ".join(sources_section.split())

    for expected in (
        "`reference`: optional source selector",
        'omitted or set to literal `"auto"`',
        "`analysis_source`: config-only string",
        '`"reference"` analyzes the selected reference clip',
        '`"fastest"` benchmarks discovered clips',
        "never changes the selected reference, comparison order, input order, or display order",
        "`match_fps`: FPS matching policy",
        "`assume_reference`",
        "`majority`",
        "falls back to the selected reference effective FPS",
        "`overrides`: mapping from source selector",
        "`trim_start_frames`",
        "`trim_end_frames`",
        "`active_rect = { x, y, width, height }`",
        '`effective_fps = "num/den"`',
        "input-dir-relative path, filename, then stem",
        "Backslashes are normalized to `/`",
        "Absolute paths, Windows drive paths, UNC paths, empty selectors",
        "Duplicate discovered source stems fail early",
        "Alignment trims compose on top of those base trims",
        "invalid explicit rectangles fail",
        "AssumeFPS-style timing override",
        "Mixed-FPS validation compares effective FPS values",
        "Explicit per-source `effective_fps` values take precedence",
        "`sources.analysis_source` is not resolved for metrics",
        "`fastest` is not benchmarked",
        "no analysis metrics cache is loaded, validated, written, or keyed by `analysis_source`",
        '`sources.analysis_source = "fastest"` is incompatible with `run --from-cache-only`',
        "before probe loading, metadata prefetch, run-folder reservation",
        "successful `run --json` schema is unchanged",
    ):
        assert expected in normalized_sources_section

    command_heading = "## Command Surface"
    sources_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        sources_heading,
        maxsplit=1,
    )[0]
    declared_options = _declared_run_options()
    override_flags = {f"--{cli_name.replace('_', '-')}" for cli_name in CLI_OVERRIDE_MAP}
    source_override_paths = {
        config_path
        for config_path in CLI_OVERRIDE_MAP.values()
        if config_path.startswith("sources.")
    }
    assert source_override_paths == set()
    for unsupported_flag in (
        "--source-reference",
        "--reference-source",
        "--source-override",
        "--analysis-source",
        "--match-fps",
    ):
        assert unsupported_flag not in sources_surface
        assert unsupported_flag not in declared_options
        assert unsupported_flag not in override_flags


def test_current_cli_contract_documents_audio_alignment_config_only_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    audio_heading = "## Config-Only Audio Alignment Surface"
    persistence_heading = "## Persistence Rules"
    assert audio_heading in cli_contract, f"Missing heading: {audio_heading}"

    audio_section = cli_contract.split(audio_heading, maxsplit=1)[1].split(
        persistence_heading,
        maxsplit=1,
    )[0]

    for expected in (
        '`previous_offsets = "disabled" | "prompt" | "always"`',
        "config-only, has no `run` flag",
        "`disabled` is the default",
        "Previous alignment offset reuse prompt unavailable; continuing without reuse.",
        "<resolved paths.generated_dir>/cache/alignment/",
        "`cache_results = true`",
        "Successful `run --json` output remains unchanged by previous-offset reuse",
        '`correlation_mode = "raw_fft" | "gcc_phat"`',
        '`preprocessing_mode = "none" | "standard"`',
        '`channel_strategy = "mono_downmix" | "best_channel"`',
        "`confidence_threshold` remains a float from `0.0` through `1.0`",
        "`ambiguity_peak_ratio` remains a float greater than or equal to `1.0`",
        "`window_length_seconds` and `window_stride_seconds` remain floats",
        "`minimum_valid_windows` remains an integer greater than or equal to `1`",
        "`consensus_minimum_ratio` remains a float from `0.0` through `1.0`",
        '`refinement_mode = "disabled" | "local"`',
        "`refinement_sample_rate` is either `null` or an integer from `4000` through",
        "`reference_stream` is either `null` or a non-negative audio stream ordinal",
        "`comparison_streams` is a mapping from comparison filename stem",
        "config-only public surfaces",
    ):
        assert expected in audio_section

    normalized_audio_section = " ".join(audio_section.split())
    for expected in (
        "correlation algorithm",
        "not present in the CLI override map",
        "Exact-match computed audio alignment offsets are deterministic cache hits",
        "`disabled` is the default and does not read or reuse shared VSPreview-confirmed offsets",
        "eligible current-run computed or VSPreview-confirmed results still write",
        "asks `Reuse previous preview-confirmed alignment offsets? [y/N]`",
        "declining the prompt reuses that computed result instead of rerunning audio alignment",
        "requires both stdin and stderr to be TTYs before",
        "persisted `accepted_at` timestamp",
        "workspace-level cache state even when `paths.use_run_folders = true`",
        '`previous_offsets = "prompt"` and `previous_offsets = "always"` require',
        '`force_interactive = true` is incompatible with `previous_offsets = "prompt"`',
        "preprocessing",
        "audio channel handling",
        "It gates whether computed offsets are applied",
        "It gates ambiguous correlation peaks",
        "consensus window",
        "It gates whether enough windows produced valid estimates",
        "It gates whether enough windows agree",
        "consensus",
        "refinement",
        "selects the reference clip audio stream",
        "select the comparison clip audio stream",
    ):
        assert expected in normalized_audio_section

    audio_section_lower = normalized_audio_section.lower()
    for stale_phrase in (
        "future correlation",
        "future preprocessing",
        "future channel",
        "future refinement",
        "future-only",
        "inert",
        "accepts and forwards",
    ):
        assert stale_phrase not in audio_section_lower

    command_heading = "## Command Surface"
    screenshot_heading = "## Config-Only Screenshot Surface"
    command_override_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        screenshot_heading,
        maxsplit=1,
    )[0]

    for unsupported_flag in (
        "--previous-offsets",
        "--correlation-mode",
        "--preprocessing-mode",
        "--channel-strategy",
        "--confidence-threshold",
        "--ambiguity-peak-ratio",
        "--window-length-seconds",
        "--window-stride-seconds",
        "--minimum-valid-windows",
        "--consensus-minimum-ratio",
        "--refinement-mode",
        "--refinement-sample-rate",
        "--reference-stream",
        "--comparison-streams",
    ):
        assert unsupported_flag not in command_override_surface
        assert unsupported_flag not in _declared_run_options()
    assert "audio_alignment.previous_offsets" not in CLI_OVERRIDE_MAP.values()


def test_current_cli_contract_documents_screenshot_geometry_config_surface() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    screenshot_heading = "## Config-Only Screenshot Surface"
    audio_heading = "## Config-Only Audio Alignment Surface"
    assert screenshot_heading in cli_contract, f"Missing heading: {screenshot_heading}"

    screenshot_section = cli_contract.split(screenshot_heading, maxsplit=1)[1].split(
        audio_heading,
        maxsplit=1,
    )[0]
    normalized_screenshot_section = " ".join(screenshot_section.split())

    for expected in (
        '`geometry_mode = "native" | "aligned"`',
        '`active_rect_detection = "provided" | "dimension" | "aspect_ratio" | "auto"`',
        '`aligned_scale_policy = "largest_active" | "smallest_active" |',
        "`aligned_target_width` and `aligned_target_height`",
        "Native mode ignores aligned-only geometry fields for behavior",
        "shared active-picture evidence used during preparation",
        "`auto` is opt-in",
        "samples luma frames",
        "returns full frame when uncertain",
        "is not ML, OCR, perceptual HDR analysis, or exhaustive scanning",
        "Metric analysis uses the resolved active picture",
        "Native screenshot render remains native/full-frame output",
        "includes the resolved active rectangle and provenance",
        "`content-derived` rectangles from `auto`",
        '[screenshots] active_rect_detection = "auto"',
        "fits active content inside the selected target width and height",
        "without exceeding either dimension",
        "Derived policy targets are normalized downward",
        "explicit-size targets preserve the exact configured canvas",
    ):
        assert expected in normalized_screenshot_section


def test_current_cli_contract_documents_config_strictness_logging_and_migration() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    validation_heading = "## Config Validation, Logging, And Migration"
    audio_heading = "## Config-Only Audio Alignment Surface"
    assert validation_heading in cli_contract, f"Missing heading: {validation_heading}"

    validation_section = cli_contract.split(validation_heading, maxsplit=1)[1].split(
        audio_heading,
        maxsplit=1,
    )[0]
    normalized_validation = " ".join(validation_section.split())

    for expected in (
        "Unknown keys at the root of the config remain ignored",
        "Every Frame Compare-owned nested config table rejects unknown keys",
        '`level = "INFO"`',
        "accepting `DEBUG`, `INFO`, `WARNING`, or `ERROR`",
        '`format = "console"`',
        "`--quiet` forces level `WARNING`",
        "`--verbose` forces `DEBUG`",
        "`--json` forces JSON-formatted logs on stderr",
        "Remove `analysis.save_frames_data`",
        "Replace `screenshots.directory_name` with `paths.screenshots_dir`",
        "Remove `logging.file`",
        "does not support config-driven file logging",
    ):
        assert expected in normalized_validation
    assert "CRITICAL" not in validation_section

    normalized_screenshot = " ".join(
        cli_contract.split("## Config-Only Screenshot Surface", maxsplit=1)[1]
        .split(validation_heading, maxsplit=1)[0]
        .split()
    )
    assert "`ffmpeg_timeout_seconds` defaults to `30.0` and must be at least `5.0`" in (
        normalized_screenshot
    )
    assert "controls only FFmpeg frame extraction" in normalized_screenshot
    assert "ffprobe HDR metadata probe keeps its fixed `15.0` second timeout" in (
        normalized_screenshot
    )

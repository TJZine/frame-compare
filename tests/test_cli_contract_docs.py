from __future__ import annotations

import json
from pathlib import Path

from click import Group
from typer.main import get_command

from frame_compare.cli.entry import app
from frame_compare.cli.run_command import handle_json_output
from frame_compare.config.overrides import CLI_OVERRIDE_MAP
from frame_compare.config.schema import AnalysisConfig, SlowpicsConfig, Visibility
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from frame_compare.orchestration.types import RunResult


def _declared_run_options() -> set[str]:
    command = get_command(app)
    assert isinstance(command, Group)
    run_command = command.commands["run"]
    return {
        opt
        for param in run_command.params
        for opt in (*getattr(param, "opts", ()), *getattr(param, "secondary_opts", ()))
    }


def test_current_cli_contract_is_wired_into_repo_authority_surfaces() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = repo_root / "docs" / "current-cli-contract.md"

    assert cli_contract.exists()

    runbook = (repo_root / "docs" / "ENGINEERING_RUNBOOK.md").read_text(encoding="utf-8")
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    coordinator = (repo_root / "src" / "frame_compare" / "orchestration" / "types.py").read_text(
        encoding="utf-8"
    )

    assert "docs/current-cli-contract.md" in runbook
    assert "docs/current-cli-contract.md" in agents
    assert "docs/current-cli-contract.md" in coordinator
    assert "cli-module.md" not in coordinator

    runbook_pos = agents.index("[docs/ENGINEERING_RUNBOOK.md]")
    architecture_pos = agents.index("[docs/current-architecture.md]")
    cli_contract_pos = agents.index("[docs/current-cli-contract.md]")
    importlinter_pos = agents.index("[importlinter.ini]")
    pyproject_pos = agents.index("[pyproject.toml]")
    assert runbook_pos < architecture_pos < cli_contract_pos < importlinter_pos < pyproject_pos


def test_current_cli_contract_covers_all_public_command_families() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    assert "## `version` Command Contract" in cli_contract
    assert "## `run` Command Contract" in cli_contract
    assert "## `wizard` Command Contract" in cli_contract
    assert "## `doctor` Command Contract" in cli_contract
    assert "## `preset` Command Contract" in cli_contract


def test_current_cli_contract_documents_secondary_command_streams() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    wizard_section = cli_contract.split("## `wizard` Command Contract", maxsplit=1)[1].split(
        "## `doctor` Command Contract",
        maxsplit=1,
    )[0]
    doctor_section = cli_contract.split("## `doctor` Command Contract", maxsplit=1)[1].split(
        "## `preset` Command Contract",
        maxsplit=1,
    )[0]
    preset_section = cli_contract.split("## `preset` Command Contract", maxsplit=1)[1]
    normalized_wizard = " ".join(wizard_section.split())
    normalized_doctor = " ".join(doctor_section.split())
    normalized_preset = " ".join(preset_section.split())

    assert "confirmation to stderr including the resolved config path" in normalized_wizard
    assert "honor the `NO_COLOR` environment variable" in normalized_wizard
    assert "do not suggest unsupported `--verbose` usage" in normalized_wizard
    assert "neutral status marker for optional unavailable checks" in normalized_doctor
    assert "This does not change `doctor --json` status values." in normalized_doctor
    assert "honor the `NO_COLOR` environment variable" in normalized_doctor
    assert "do not suggest unsupported `--verbose` usage" in normalized_doctor
    assert "Prints preset names one per line to stdout." in normalized_preset
    assert "Emits no success confirmation." in normalized_preset
    assert "confirmation to stderr including the preset name and resolved config path" in (
        normalized_preset
    )
    assert "confirmation to stderr including the preset name and saved preset path" in (
        normalized_preset
    )
    assert "honor the `NO_COLOR` environment variable" in normalized_preset
    assert "do not suggest unsupported `--verbose` usage" in normalized_preset


def test_current_cli_contract_matches_live_override_map() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")

    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        flag = f"--{cli_name.replace('_', '-')}"
        assert flag in cli_contract
        assert config_path in cli_contract


def test_current_cli_contract_documents_slowpics_config_surface_and_defaults() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    slowpics_heading = "## Config-Only slow.pics Surface"
    screenshot_heading = "## Config-Only Screenshot Surface"
    assert slowpics_heading in cli_contract, f"Missing heading: {slowpics_heading}"

    slowpics_section = cli_contract.split(slowpics_heading, maxsplit=1)[1].split(
        screenshot_heading,
        maxsplit=1,
    )[0]
    normalized_slowpics_section = " ".join(slowpics_section.split())

    assert list(SlowpicsConfig.model_fields) == [
        "auto_upload",
        "confirm_upload_after_report",
        "visibility",
        "delete_after_upload",
        "timeout_seconds",
        "max_retries",
        "copy_url_to_clipboard",
        "open_in_browser",
        "create_url_shortcut",
        "webhook_url",
    ]
    for expected in (
        "`auto_upload = false`",
        "`confirm_upload_after_report = false`",
        '`visibility = "unlisted"`',
        "`delete_after_upload = false`",
        "`timeout_seconds = 60.0`",
        "`max_retries = 3`",
        "`copy_url_to_clipboard = true`",
        "`open_in_browser = true`",
        "`create_url_shortcut = true`",
        "`webhook_url = null`",
        "`delete_after_upload` is local-only",
        "report-safe",
        "`removeAfter`",
        "`confirm_upload_after_report` is a config-only, interactive-only opt-in",
        "`copy_url_to_clipboard` and `open_in_browser` are interactive CLI-owned actions",
        "`create_url_shortcut` and `webhook_url` run after successful upload",
        "including `--json` and `--quiet`",
        "The JSON output schema remains unchanged by report-confirmed upload",
    ):
        assert expected in slowpics_section
    for expected in (
        "exact planned local screenshot files that were successfully uploaded",
        "Deletion is skipped for non-embedded reports",
        "warn-only report failures",
        "adds no `run` flag, no wizard prompt, and no `run --json` stdout field",
        "incompatible with `--json`, `--quiet`, non-TTY stdin, non-TTY stdout",
        "`report.enable = false`",
    ):
        assert expected in normalized_slowpics_section
    assert (
        "These ten fields are the full current public `[slowpics]` config surface"
        in normalized_slowpics_section
    )
    assert "parsed and defaulted only" not in normalized_slowpics_section
    assert "warning-only failures remain off JSON stdout" in normalized_slowpics_section

    for unsupported_field in (
        "collection_suffix",
        "collection_name",
        "image_format",
        "optimize_images",
        "tags",
        "hentai",
        "remove_after",
    ):
        assert unsupported_field not in SlowpicsConfig.model_fields


def test_current_cli_contract_documents_only_no_upload_slowpics_run_flag() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    mapping_heading = "## CLI Flag To Config Mapping"
    screenshot_heading = "## Config-Only slow.pics Surface"
    assert mapping_heading in cli_contract, f"Missing heading: {mapping_heading}"
    assert screenshot_heading in cli_contract, f"Missing heading: {screenshot_heading}"

    mapping_section = cli_contract.split(mapping_heading, maxsplit=1)[1].split(
        screenshot_heading,
        maxsplit=1,
    )[0]
    normalized_mapping_section = " ".join(mapping_section.split())

    declared_options = _declared_run_options()
    slowpics_related = {
        flag
        for flag in declared_options
        if (
            "slowpics" in flag
            or "slow-pics" in flag
            or "upload" in flag
            or "visibility" in flag
            or "remove" in flag
            or "delete" in flag
            or "webhook" in flag
        )
    }

    assert slowpics_related == {"--no-upload"}
    assert "--confirm-upload-after-report" not in declared_options
    assert "slowpics.confirm_upload_after_report" not in CLI_OVERRIDE_MAP.values()
    assert "`--no-upload` is the only slow.pics-specific `run` flag." in mapping_section
    assert "No runtime-only slow.pics `run` flags exist." in normalized_mapping_section


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


def test_current_cli_contract_documents_slowpics_json_shape(
    capsys,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    run_heading = "## `run` Command Contract"
    mapping_heading = "## CLI Flag To Config Mapping"
    assert run_heading in cli_contract, f"Missing heading: {run_heading}"

    run_section = cli_contract.split(run_heading, maxsplit=1)[1].split(
        mapping_heading,
        maxsplit=1,
    )[0]
    normalized_run_section = " ".join(run_section.split())

    assert "`slowpics_url`" in run_section
    assert "only machine-readable slow.pics result field" in normalized_run_section
    assert "No copy/open/shortcut/webhook result fields" in normalized_run_section
    assert "Report-confirmed upload confirmation status is also not emitted" in run_section
    assert "success schema remains unchanged" in normalized_run_section
    for forbidden_field in (
        "clipboard_result",
        "browser_result",
        "shortcut_path",
        "webhook_status",
    ):
        assert forbidden_field not in run_section

    handle_json_output(
        RunResult(
            success=True,
            slowpics_url=None,
            slowpics_upload_confirmation_status="declined",
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert "slowpics_url" in payload
    assert payload["slowpics_url"] is None
    assert "slowpics_upload_confirmation_status" not in payload


def test_current_cli_contract_documents_run_folder_identity_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_cli_contract = " ".join(cli_contract.split())
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "folder names are capped at 64 characters",
        "do not include exact timestamps",
        "collisions use compact numeric suffixes such as `_2` and `_3`",
        "`<run-folder>/run_info.toml`",
        "UTC `created_at` with a `Z` suffix",
        "`naming_source`",
        "`source_filenames`",
        "absent optional values omitted rather than serialized as null",
        "not a final outcome manifest",
        "If `run_info.toml` cannot be written, the run fails immediately",
    ):
        assert expected in normalized_cli_contract

    for expected in (
        "`<run-folder>/run_info.toml`: root-level run identity metadata",
        "Exact timestamps are not part of folder names",
        "The exact creation time lives in `<run-folder>/run_info.toml`",
        "written before probing, rendering, or other runtime-heavy work",
    ):
        assert expected in normalized_architecture


def test_current_cli_contract_documents_slowpics_post_upload_behavior() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    upload_heading = "### slow.pics Upload Behavior"
    shortcut_heading = "### slow.pics Shortcut Policy"
    webhook_heading = "### slow.pics Webhook Policy"
    mapping_heading = "## CLI Flag To Config Mapping"

    upload_section = cli_contract.split(upload_heading, maxsplit=1)[1].split(
        shortcut_heading,
        maxsplit=1,
    )[0]
    shortcut_section = cli_contract.split(shortcut_heading, maxsplit=1)[1].split(
        webhook_heading,
        maxsplit=1,
    )[0]
    webhook_section = cli_contract.split(webhook_heading, maxsplit=1)[1].split(
        mapping_heading,
        maxsplit=1,
    )[0]
    normalized_upload = " ".join(upload_section.split())
    normalized_shortcut = " ".join(shortcut_section.split())
    normalized_webhook = " ".join(webhook_section.split())

    for expected in (
        "`copy_url_to_clipboard` copies the slow.pics URL through the CLI",
        "`open_in_browser` opens the slow.pics URL through the CLI",
        "`create_url_shortcut` writes a deterministic `.url` shortcut",
        "`webhook_url` posts the slow.pics URL to the configured webhook",
        "including `--json` and `--quiet` runs",
        "no post-upload action fields are added to the JSON payload",
        "Disabled or skipped post-upload actions are not listed by default",
    ):
        assert expected in normalized_upload

    for expected in (
        "`frame_compare.services.slowpics_shortcut`",
        "Repeated writes overwrite the same deterministic shortcut path",
        "Shortcut files are not members of `slowpics.delete_after_upload` cleanup",
    ):
        assert expected in normalized_shortcut

    for expected in (
        "`frame_compare.services.slowpics_webhook`",
        'payload is exactly `{"content":"<slowpics_url>"}`',
        "strict external HTTPS endpoint",
        "prevalidated pinned IP address",
        "does not reuse slow.pics cookies, headers, client state",
        "fixed 10 second timeout, and 3 attempts",
        "redacted from warnings and logs",
        "Delivery failures are warning-only",
    ):
        assert expected in normalized_webhook


def test_current_cli_contract_documents_report_confirmed_slowpics_workflow() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    upload_heading = "### slow.pics Upload Behavior"
    shortcut_heading = "### slow.pics Shortcut Policy"

    upload_section = cli_contract.split(upload_heading, maxsplit=1)[1].split(
        shortcut_heading,
        maxsplit=1,
    )[0]
    normalized_upload = " ".join(upload_section.split())

    for expected in (
        "`slowpics.confirm_upload_after_report = true`",
        "inert unless effective `slowpics.auto_upload = true`",
        "There is no dedicated `run` flag for report-confirmed upload",
        "`--no-upload` remains the only slow.pics-specific `run` flag",
        "normal non-confirmed phase order remains",
        "`frame_plan -> analyze -> align -> render -> metadata -> publish -> report -> post_report_cleanup`",
        "Report-confirmed upload changes only the opted-in interactive path",
        "`frame_plan -> analyze -> align -> render -> metadata -> report -> confirm_slowpics_upload -> publish -> post_report_cleanup`",
        "`--json` was passed",
        "`--quiet` was passed",
        "stdin is not attached to a TTY",
        "stdout is not attached to a TTY",
        "`report.enable = false`",
        "not regenerated after upload",
        "`slowpics_url = null`",
        "slow.pics upload skipped because report confirmation was unavailable",
        "slow.pics upload skipped by confirmation",
        "`slowpics_url` remains `None`",
        "With `report.embed_images = false`, deletion is skipped",
        "If upload is declined or report confirmation is unavailable",
        "no slow.pics delete-after-upload cleanup runs",
    ):
        assert expected in normalized_upload


def test_current_cli_contract_documents_slowpics_browser_report_precedence() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    report_heading = "### Report Auto-Open Ownership"
    upload_heading = "### slow.pics Upload Behavior"

    report_section = cli_contract.split(report_heading, maxsplit=1)[1].split(
        upload_heading,
        maxsplit=1,
    )[0]
    normalized_report_section = " ".join(report_section.split())

    for expected in (
        "Clipboard copy and slow.pics browser opening are also CLI-owned",
        "If an enabled slow.pics browser open is attempted",
        "report auto-open is suppressed for that run",
        "If slow.pics browser open is not attempted",
        "existing report auto-open rules above still apply",
        "Report-confirmed slow.pics upload is the exception to that precedence rule",
        "CLI presents the local report before prompting for upload",
        "later confirmed upload will open the slow.pics URL in a browser",
        "If it is not opened, the CLI prints the report path before prompting",
    ):
        assert expected in normalized_report_section


def test_current_architecture_documents_slowpics_service_flow_and_upload_plan() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "browser-compatible slow.pics client flow",
        "`frame_compare.services.publishers`",
        "`frame_compare.services.slowpics_upload_plan`",
        "explicit upload-plan seam",
        "current render artifacts",
        "does not scan the screenshot directory",
        "`post_report_cleanup`",
        "exact uploaded planned local file paths",
        "report-safe local deletion policy",
        "typed post-upload action results plus warnings",
        "does not own clipboard, browser, shortcut, or webhook side-effect policy",
        "The `.url` shortcut is not cleanup membership",
    ):
        assert expected in normalized_architecture


def test_current_architecture_documents_report_confirmed_phase_order_and_owner_seams() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "`slowpics.confirm_upload_after_report`",
        "`frame_plan -> analyze -> align -> render -> metadata -> report -> confirm_slowpics_upload -> publish -> post_report_cleanup`",
        "The non-confirmed flow keeps the normal ordering above",
        "report-confirmed upload prompting",
        "Report-confirmed slow.pics upload uses a CLI-owned confirmation callback seam",
        "`RunDependencies.confirm_slowpics_upload`",
        "Orchestration owns the typed request, decision, confirmation-status state",
        "it does not import Typer, open browsers, read stdin, or print prompt text",
        "raises a typed config error before publish",
        "`report_unavailable`",
        "prevents slow.pics upload",
        "`publish` is skipped and `slowpics_url` stays `None`",
        "local report is generated before upload and is not regenerated after upload",
        "report payload therefore has no slow.pics URL",
        "CLI report presentation happens before the confirmation prompt",
        "before any later post-upload slow.pics browser opening",
        "existing non-confirmed rule remains",
        "It does not own slow.pics upload policy, prompting, or browser side effects",
    ):
        assert expected in normalized_architecture


def test_current_architecture_documents_slowpics_post_upload_owner_seams() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "`frame_compare.services.slowpics_shortcut` owns deterministic `.url` output",
        "safe common parent of the resolved screenshots/generated directories",
        "`frame_compare.services.slowpics_webhook` owns isolated outbound webhook",
        "prevalidated pinned address while preserving TLS verification",
        "does not reuse slow.pics client cookies, headers",
        "`frame_compare.cli.entry` and its run-command helper own interactive-only",
        "precedence rule between slow.pics browser opening and generated-report auto-open",
        "JSON stdout stays a single object",
    ):
        assert expected in normalized_architecture


def test_report_confirmed_slowpics_upload_starter_spec_is_absent() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    starter_spec = (
        repo_root / "docs" / "plans" / "2026-06-01-report-confirmed-slowpics-upload-starter-spec.md"
    )
    assert not starter_spec.exists()


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


def test_current_cli_contract_documents_analysis_ignore_window_and_cache_domain() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    analysis_heading = "## Config-Only Analysis Surface"
    slowpics_heading = "## Config-Only slow.pics Surface"
    assert analysis_heading in cli_contract, f"Missing heading: {analysis_heading}"

    analysis_section = cli_contract.split(analysis_heading, maxsplit=1)[1].split(
        slowpics_heading,
        maxsplit=1,
    )[0]
    normalized_analysis_section = " ".join(analysis_section.split())
    for expected in (
        "`user_frames = []`",
        "`random_frame_count = 10`",
        "`dark_frame_count = 0`",
        "`bright_frame_count = 0`",
        "`motion_frame_count = 0`",
        "`ignore_lead_seconds = 0.0`",
        "`ignore_trail_seconds = 0.0`",
        "`min_window_seconds = 5.0`",
        "original selected-reference source-frame numbers",
        "Removed stale analysis keys `selection_mode` and `frame_count` fail validation explicitly",
        "there are no dedicated `run` flags",
        "source-specific base trim domain",
        "do not physically trim sources",
        "reported source-frame numbers",
        "standard typed selection error",
    ):
        assert expected in normalized_analysis_section

    command_heading = "## Command Surface"
    command_override_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        analysis_heading,
        maxsplit=1,
    )[0]
    for unsupported_flag in (
        "--ignore-lead-seconds",
        "--ignore-trail-seconds",
        "--min-window-seconds",
    ):
        assert unsupported_flag not in command_override_surface

    cache_section = cli_contract.split("### Cache Mode Semantics", maxsplit=1)[1].split(
        "### Report Auto-Open Ownership",
        maxsplit=1,
    )[0]
    normalized_cache_section = " ".join(cache_section.split())
    for expected in (
        "stable all-source selection-domain token",
        "`analysis_source_path`",
        "`reference_path`",
        "Cache schema v6 stores `analysis_source_path`, `performance_mode`, `algorithm_id`",
        "`metric_active_rect`",
        "active-rect source, detection mode, and active-rect resolver algorithm ID",
        "performance modes, metric algorithm identities, or active-rect metric domains",
        "active-rect metric domains",
        "active-rect resolver policy",
        "each clip's resolved active rectangle",
        "produce coordinate-specific metric/cache identities",
        'When `sources.analysis_source = "reference"`',
        "source trims",
        "effective FPS values",
        "configured analysis ignore-window settings",
        "final shared selectable window",
        "probe cache is missing",
        "rather than validating a weaker fingerprint",
        "Previous alignment reuse is not part of analysis cache-only prevalidation",
        '`previous_offsets = "always"`',
        "missing previous alignment offsets do not fail `--from-cache-only`",
        "does not delete shared previous-offset reuse entries",
        "Alignment can compute current-run offsets",
        "<resolved paths.generated_dir>/cache/alignment/",
    ):
        assert expected in normalized_cache_section


def test_current_cli_contract_documents_previous_offsets_output_and_persistence() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    run_section = cli_contract.split("## `run` Command Contract", maxsplit=1)[1].split(
        "## CLI Flag To Config Mapping",
        maxsplit=1,
    )[0]
    persistence_section = cli_contract.split("## Persistence Rules", maxsplit=1)[1].split(
        "### Tonemap Preset And Target Resolution",
        maxsplit=1,
    )[0]
    normalized_run = " ".join(run_section.split())
    normalized_persistence = " ".join(persistence_section.split())

    for expected in (
        '`--json` is incompatible with `audio_alignment.previous_offsets = "prompt"`',
        '`previous_offsets = "always"` is compatible with `--json`',
        '`--quiet` is incompatible with `audio_alignment.previous_offsets = "prompt"`',
        "`previous offsets` row reports only the effective config mode",
        "`disabled`, `prompt`, or `always`",
        "disables ANSI styling for the previous-offset reuse table and prompt",
        "shared alignment reuse entries live below it at `cache/alignment`",
        "`--diagnose-paths` does not report the shared alignment cache path separately",
    ):
        assert expected in normalized_run

    for expected in (
        '`audio_alignment.previous_offsets = "prompt"` or `"always"`',
        "`audio_alignment.force_interactive = true`",
        "`audio_alignment.cache_results = false`",
        "The config is not written when either conflict is present",
    ):
        assert expected in normalized_persistence


def test_current_architecture_documents_shared_alignment_reuse_cache_seams() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "<resolved paths.generated_dir>/cache/alignment/alignment_reuse.toml",
        "`frame_compare.services.alignment_reuse_cache`",
        "shared previous alignment offset reuse cache",
        "`generated/manual_overrides.toml` or `<run-folder>/generated/manual_overrides.toml`",
        "stable generated area when run folders are disabled",
        "current run folder when run folders are enabled",
        "`WorkspacePaths.shared_alignment_cache_dir`",
        "shared workspace-level `<resolved paths.generated_dir>/cache/alignment` path",
        "`frame_compare.utils.types.AlignmentRequest`",
        "`frame_compare.orchestration.phase_tasks.run_align_phase()`",
        "typed orchestration-to-services request seam",
        "layer-neutral primitives or dependency-light shared utility types",
        "must not import orchestration-owned or analysis-owned identity types",
        "`frame_compare.services.alignment_reuse_prompt`",
        "`frame_compare.services.types.AlignmentProvenance`",
        "`computed_this_run`",
        "`vspreview_confirmed_this_run`",
        "`shared_computed_offsets`",
        "`shared_previous_offsets`",
        "`preexisting_manual_override`",
        "rather than inferring eligibility from the final flattened `AlignmentResult.source`",
    ):
        assert expected in normalized_architecture
    for stale in (
        "`generated/audio_offsets.toml`",
        "`<run-folder>/generated/audio_offsets.toml`",
        "run-scoped alignment cache",
        "run-scoped VSPreview-confirmed manual alignment overrides",
    ):
        assert stale not in normalized_architecture


def test_current_cli_contract_names_primary_executable_contract_checks() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    authority_heading = "## Authority And Update Rules"
    command_surface_heading = "## Command Surface"
    assert authority_heading in cli_contract, f"Missing heading: {authority_heading}"
    assert command_surface_heading in cli_contract, f"Missing heading: {command_surface_heading}"

    authority_section = cli_contract.split(authority_heading, maxsplit=1)[1].split(
        command_surface_heading,
        maxsplit=1,
    )[0]

    expected_checks = (
        "`tests/cli/test_cli_commands.py` for help text, JSON payloads, report auto-open",
        "`tests/config/test_overrides.py` for CLI override mapping semantics.",
        "`tests/e2e/test_cli_version.py` for the public `version` command contract.",
        "`tests/cli/test_exit_codes.py` for exit-code behavior.",
        "`tests/test_cli_contract_docs.py` for keeping this document aligned with the live",
    )

    for expected in expected_checks:
        assert expected in authority_section


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


def test_current_architecture_documents_shared_probe_cache_for_cache_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "shared clip probe cache used by `--from-cache-only` prevalidation",
        "before run-folder reservation",
        "current-run clip probe cache when run folders are enabled",
        "written to both the current run folder and the shared generated probe cache",
        "validate the exact all-source analysis selection domain",
    ):
        assert expected in normalized_architecture


def test_current_cli_contract_matches_wizard_visibility_choices() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    wizard_heading = "## `wizard` Command Contract"
    doctor_heading = "## `doctor` Command Contract"
    assert wizard_heading in cli_contract, f"Missing heading: {wizard_heading}"
    assert doctor_heading in cli_contract, f"Missing heading: {doctor_heading}"

    wizard_section = cli_contract.split(wizard_heading, maxsplit=1)[1].split(
        doctor_heading,
        maxsplit=1,
    )[0]

    for visibility in Visibility:
        assert visibility.value in wizard_section
    for unsupported_token in (
        "--visibility private",
        "--visibility=private",
        "visibility: private",
    ):
        assert unsupported_token not in wizard_section


def test_current_contract_docs_define_hybrid_workspace_path_policy() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    security = (repo_root / "SECURITY.md").read_text(encoding="utf-8")
    normalized_cli_contract = " ".join(cli_contract.split())

    for phrase in (
        "Media input is a read boundary, not a write boundary",
        "`PathEscapesRootError` / `FC-3009`",
        "beneath the contained resolved `paths.generated_dir`, never beneath `paths.input_dir`",
        "sole selected-config containment exception",
        "`run`, `wizard`, `preset apply`, and `preset save`",
    ):
        assert phrase in normalized_cli_contract

    assert "permitting external media reads" in architecture
    assert "never beneath an external media input" in architecture
    assert "Media inputs may be read from outside the workspace" in security
    assert "%LOCALAPPDATA%/Programs/FrameCompare/state/config.toml" in security

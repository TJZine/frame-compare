from __future__ import annotations

import json
from pathlib import Path

from click import Group
from typer.main import get_command

from frame_compare.cli.entry import app
from frame_compare.cli.run_command import handle_json_output
from frame_compare.config.overrides import CLI_OVERRIDE_MAP
from frame_compare.config.schema import SlowpicsConfig
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
        "title",
        "title_template",
        "title_suffix",
        "is_hentai",
        "tmdb_id",
        "tmdb_media_type",
        "remove_after_days",
        "image_upload_timeout_seconds",
        "copy_url_to_clipboard",
        "open_in_browser",
        "create_url_shortcut",
        "webhook_url",
    ]
    for expected in (
        "`auto_upload = false`",
        "`confirm_upload_after_report = false`",
        '`visibility = "public"`',
        "`delete_after_upload = false`",
        "`timeout_seconds = 60.0`",
        "`max_retries = 3`",
        '`title = ""`',
        '`title_template = ""`',
        '`title_suffix = ""`',
        "`is_hentai = false`",
        "`tmdb_id = null`",
        "`tmdb_media_type = null`",
        "`remove_after_days = 0`",
        "`image_upload_timeout_seconds = 180.0`",
        "`is_hentai` is a strict boolean",
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
        "These eighteen fields are the full current public `[slowpics]` config surface"
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

"""Validation policy for public ``run`` CLI mode combinations."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import JSONValue
from frame_compare.orchestration.analysis_policy import (
    validate_skip_analysis_frame_selection_contract as validate_skip_analysis_policy,
)

if TYPE_CHECKING:
    from frame_compare.cli.run_command import RunCliRawArgs, RunCommandDeps


class RunContractFailure(Enum):
    JSON_INTERACTIVE_ALIGNMENT = "json_interactive_alignment"
    PREVIOUS_OFFSETS = "previous_offsets"
    REPORT_CONFIRMED_SLOWPICS = "report_confirmed_slowpics"


def report_confirmed_slowpics_enabled(config: ConfigSchema) -> bool:
    return config.slowpics.auto_upload and config.slowpics.confirm_upload_after_report


def validate_dry_run_mode_contract(args: RunCliRawArgs) -> None:
    """Reject dry-run combinations with other early-exit modes."""
    if not args.dry_run:
        return
    validation_errors: list[dict[str, JSONValue]] = []
    if args.write_config:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "write_config"],
                "msg": "--dry-run cannot be combined with --write-config.",
                "input": True,
            }
        )
    if args.diagnose_paths:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "diagnose_paths"],
                "msg": "--dry-run cannot be combined with --diagnose-paths.",
                "input": True,
            }
        )
    if not validation_errors:
        return
    raise ConfigValidationError(
        validation_errors,
        message="--dry-run is incompatible with another early-exit mode",
        hint="Use --dry-run, --write-config, or --diagnose-paths separately",
    )


def validate_dry_run_cache_contract(args: RunCliRawArgs) -> None:
    """Validate cache flags without touching cache state."""
    if not args.no_cache or not args.from_cache_only:
        return
    raise ConfigValidationError(
        [
            {
                "type": "value_error",
                "loc": ["cli", "no_cache"],
                "msg": "--no-cache and --from-cache-only are mutually exclusive.",
                "input": True,
            },
            {
                "type": "value_error",
                "loc": ["cli", "from_cache_only"],
                "msg": "--no-cache and --from-cache-only are mutually exclusive.",
                "input": True,
            },
        ],
        message="Cache mode flags are mutually exclusive",
        hint="Use either --no-cache or --from-cache-only, not both",
    )


def validate_run_contracts(args: RunCliRawArgs, deps: RunCommandDeps, config: ConfigSchema) -> None:
    """Enforce public CLI mode combinations before entering the runtime pipeline."""
    validate_skip_analysis_frame_selection_contract(args, config)
    validation_errors: list[dict[str, JSONValue]] = []
    failures: set[RunContractFailure] = set()

    interactive_errors = json_interactive_alignment_contract_errors(args, config)
    if interactive_errors:
        failures.add(RunContractFailure.JSON_INTERACTIVE_ALIGNMENT)
        validation_errors.extend(interactive_errors)

    previous_offset_errors = previous_offset_reuse_contract_errors(args, config)
    if previous_offset_errors:
        failures.add(RunContractFailure.PREVIOUS_OFFSETS)
        validation_errors.extend(previous_offset_errors)

    report_confirmed_slowpics_errors = report_confirmed_slowpics_contract_errors(
        args,
        deps,
        config,
    )
    if report_confirmed_slowpics_errors:
        failures.add(RunContractFailure.REPORT_CONFIRMED_SLOWPICS)
        validation_errors.extend(report_confirmed_slowpics_errors)

    if not validation_errors:
        return

    raise ConfigValidationError(
        validation_errors,
        message=validation_error_message(frozenset(failures)),
        hint=validation_error_hint(frozenset(failures)),
    )


def validate_write_config_contracts(config: ConfigSchema) -> None:
    """Reject persisted effective configs that normal runs would not accept."""
    validation_errors = previous_offset_reuse_persisted_contract_errors(config)
    if not validation_errors:
        return
    raise ConfigValidationError(
        validation_errors,
        message="Previous offset reuse is not supported with this run configuration",
        hint=(
            "Set audio_alignment.previous_offsets to disabled, enable "
            "audio_alignment.cache_results, or disable force interactive alignment"
        ),
    )


def validate_skip_analysis_frame_selection_contract(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> None:
    validate_skip_analysis_policy(
        skip_analysis=args.skip_analysis,
        config=config.analysis,
    )


def json_interactive_alignment_contract_errors(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    if not args.json_output:
        return []

    interactive_fields: list[tuple[str, str]] = []
    if config.audio_alignment.use_vspreview:
        interactive_fields.append(("audio_alignment", "use_vspreview"))
    if config.audio_alignment.force_interactive:
        interactive_fields.append(("audio_alignment", "force_interactive"))
    if not interactive_fields:
        return []

    return [
        {
            "type": "value_error",
            "loc": list(loc),
            "msg": "Interactive alignment is not supported with --json.",
            "input": True,
        }
        for loc in interactive_fields
    ]


def previous_offset_reuse_contract_errors(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    previous_offsets = config.audio_alignment.previous_offsets
    if previous_offsets == "disabled":
        return []

    validation_errors: list[dict[str, JSONValue]] = []
    if args.json_output and previous_offsets == "prompt":
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["audio_alignment", "previous_offsets"],
                "msg": "Previous offset prompt mode is not supported with --json.",
                "input": previous_offsets,
            }
        )
    if args.quiet and previous_offsets == "prompt":
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "quiet"],
                "msg": "Previous offset prompt mode is not supported with --quiet.",
                "input": previous_offsets,
            }
        )
    validation_errors.extend(previous_offset_reuse_persisted_contract_errors(config))
    return validation_errors


def previous_offset_reuse_persisted_contract_errors(
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    previous_offsets = config.audio_alignment.previous_offsets
    if previous_offsets == "disabled":
        return []

    validation_errors: list[dict[str, JSONValue]] = []
    if config.audio_alignment.force_interactive:
        validation_errors.extend(
            [
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "force_interactive"],
                    "msg": "Previous offset reuse is not supported with force interactive alignment.",
                    "input": True,
                },
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "previous_offsets"],
                    "msg": "Previous offset reuse is not supported with force interactive alignment.",
                    "input": previous_offsets,
                },
            ]
        )
    if not config.audio_alignment.cache_results:
        validation_errors.extend(
            [
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "cache_results"],
                    "msg": "Previous offset reuse requires audio_alignment.cache_results = true.",
                    "input": False,
                },
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "previous_offsets"],
                    "msg": "Previous offset reuse requires audio_alignment.cache_results = true.",
                    "input": previous_offsets,
                },
            ]
        )
    return validation_errors


def report_confirmed_slowpics_contract_errors(
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    if not report_confirmed_slowpics_enabled(config):
        return []

    validation_errors: list[dict[str, JSONValue]] = []
    if args.json_output:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "json"],
                "msg": "Report-confirmed slow.pics upload is not supported with --json.",
                "input": True,
            }
        )
    if args.quiet:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "quiet"],
                "msg": "Report-confirmed slow.pics upload is not supported with --quiet.",
                "input": True,
            }
        )
    if not deps.stdin_is_tty:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["stdin"],
                "msg": "Report-confirmed slow.pics upload requires stdin to be attached to a TTY.",
                "input": False,
            }
        )
    if not deps.stdout_is_tty:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["stdout"],
                "msg": "Report-confirmed slow.pics upload requires stdout to be attached to a TTY.",
                "input": False,
            }
        )
    if not config.report.enable:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["report", "enable"],
                "msg": "Report-confirmed slow.pics upload requires report.enable = true.",
                "input": False,
            }
        )
    return validation_errors


def validation_error_message(failures: frozenset[RunContractFailure]) -> str:
    if RunContractFailure.JSON_INTERACTIVE_ALIGNMENT in failures:
        return "Interactive alignment is not supported with --json"
    if RunContractFailure.PREVIOUS_OFFSETS in failures:
        return "Previous offset reuse is not supported with this run configuration"
    if RunContractFailure.REPORT_CONFIRMED_SLOWPICS in failures:
        return "Report-confirmed slow.pics upload requires an interactive report-enabled run"
    return "Run configuration is invalid"


def validation_error_hint(failures: frozenset[RunContractFailure]) -> str:
    if RunContractFailure.JSON_INTERACTIVE_ALIGNMENT in failures:
        return (
            "Disable audio_alignment.use_vspreview and "
            "audio_alignment.force_interactive, or run without --json"
        )
    if RunContractFailure.PREVIOUS_OFFSETS in failures:
        return (
            "Set audio_alignment.previous_offsets to disabled, enable "
            "audio_alignment.cache_results, disable force interactive alignment, "
            "or run without --json/--quiet prompt mode"
        )
    if RunContractFailure.REPORT_CONFIRMED_SLOWPICS in failures:
        return (
            "Disable slowpics.confirm_upload_after_report, disable slowpics.auto_upload, "
            "enable reports, or run from an interactive terminal without --json/--quiet"
        )
    return "Review the validation errors and update the run configuration"

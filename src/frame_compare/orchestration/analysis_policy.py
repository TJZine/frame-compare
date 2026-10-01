"""Analysis phase policy helpers."""

from __future__ import annotations

from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema import AnalysisConfig
from frame_compare.errors import JSONValue


def needs_analysis(config: AnalysisConfig) -> bool:
    """Return whether requested frame selectors require metric analysis."""
    return (
        config.dark_frame_count > 0
        or config.bright_frame_count > 0
        or config.motion_frame_count > 0
    )


def validate_cache_mode_flags(*, no_cache: bool, from_cache_only: bool) -> None:
    """Reject mutually exclusive cache modes before runtime work."""
    if not no_cache or not from_cache_only:
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


def validate_skip_analysis_frame_selection_contract(
    *,
    skip_analysis: bool,
    config: AnalysisConfig,
) -> None:
    """Reject metric-based selectors when the caller explicitly skips analysis."""
    if not skip_analysis or not needs_analysis(config):
        return

    metric_counts = (
        ("dark_frame_count", config.dark_frame_count),
        ("bright_frame_count", config.bright_frame_count),
        ("motion_frame_count", config.motion_frame_count),
    )
    validation_errors: list[dict[str, JSONValue]] = []
    for field_name, count in metric_counts:
        if count > 0:
            validation_errors.append(
                {
                    "type": "value_error",
                    "loc": ["analysis", field_name],
                    "msg": f"{field_name} requires analysis and cannot be used with --skip-analysis.",
                    "input": count,
                }
            )
    if not validation_errors:
        return

    raise ConfigValidationError(
        validation_errors,
        message="Metric-based frame selection requires analysis",
        hint="Remove --skip-analysis or set dark/bright/motion frame counts to 0",
    )

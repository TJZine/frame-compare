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

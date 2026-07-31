"""Pure policy and typed state for the goal-oriented configuration wizard."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
from typing import Literal, cast

from frame_compare.config.loader import TomlPayload, TomlValue
from frame_compare.config.schema import ConfigSchema

type MetricScan = Literal["disabled", "quality", "performance"]


class WizardGoal(IntEnum):
    """Stable numbered goal choices from the approved wizard contract."""

    KEEP = 0
    RANDOM = 1
    COVERAGE = 2
    SPECIFIC = 3


@dataclass(frozen=True, slots=True)
class GoalChoice:
    """A validated goal choice and its exact partial analysis patch."""

    goal: WizardGoal
    analysis_patch: TomlPayload
    summary: str
    metric_scan: MetricScan


GOAL_MENU_LINES = (
    "1. Random spot check — Select 10 deterministic random frames using the configured seed. "
    "This does not run the luminance/motion metrics scan.",
    "2. Dark, bright, and motion coverage — Request 10 frames: 4 random, 2 dark, 2 bright, "
    "and 2 high-motion. This overrides performance mode, scans full-resolution luma for "
    "every eligible frame, can choose different frames than the 25%-sampled performance "
    "mode, and can take substantially longer.",
    "3. Specific frame numbers — Use only the listed zero-based frame numbers. This does not "
    "run the luminance/motion metrics scan.",
)


def random_goal() -> GoalChoice:
    return GoalChoice(
        goal=WizardGoal.RANDOM,
        analysis_patch={
            "user_frames": [],
            "random_frame_count": 10,
            "dark_frame_count": 0,
            "bright_frame_count": 0,
            "motion_frame_count": 0,
        },
        summary="10 deterministic random frames",
        metric_scan="disabled",
    )


def coverage_goal() -> GoalChoice:
    return GoalChoice(
        goal=WizardGoal.COVERAGE,
        analysis_patch={
            "user_frames": [],
            "random_frame_count": 4,
            "dark_frame_count": 2,
            "bright_frame_count": 2,
            "motion_frame_count": 2,
            "performance_mode": "quality",
        },
        summary="4 random + 2 dark + 2 bright + 2 motion",
        metric_scan="quality",
    )


def specific_goal(frames: list[int]) -> GoalChoice:
    frame_values: list[TomlValue] = list(frames)
    return GoalChoice(
        goal=WizardGoal.SPECIFIC,
        analysis_patch={
            "user_frames": frame_values,
            "random_frame_count": 0,
            "dark_frame_count": 0,
            "bright_frame_count": 0,
            "motion_frame_count": 0,
        },
        summary=f"frames {', '.join(str(frame) for frame in frames)}",
        metric_scan="disabled",
    )


def keep_goal(config: ConfigSchema) -> GoalChoice:
    return GoalChoice(
        goal=WizardGoal.KEEP,
        analysis_patch={},
        summary=summarize_frame_selection(config),
        metric_scan=metric_scan_for_config(config),
    )


def parse_specific_frames(raw: str) -> list[int]:
    """Parse the approved 1–100 item unsigned decimal frame-list grammar."""
    parts = raw.split(",")
    if not 1 <= len(parts) <= 100:
        raise ValueError("Enter between 1 and 100 frame numbers.")

    frames: list[int] = []
    for part in parts:
        token = part.strip()
        if not token:
            raise ValueError("Frame numbers cannot contain empty entries.")
        digits = token[1:] if token.startswith("+") else token
        if not digits or not digits.isascii() or not digits.isdecimal():
            raise ValueError("Frame numbers must be non-negative base-10 integers.")
        frames.append(int(digits, 10))

    if len(set(frames)) != len(frames):
        raise ValueError("Frame numbers must not contain duplicates.")
    return sorted(frames)


def copy_payload(payload: TomlPayload) -> TomlPayload:
    """Copy a narrowed TOML payload before applying in-memory patches."""
    return deepcopy(payload)


def set_table_values(payload: TomlPayload, table_name: str, patch: TomlPayload) -> None:
    current = payload.get(table_name)
    if current is None:
        table: TomlPayload = {}
        payload[table_name] = table
    else:
        table = cast("TomlPayload", current)
    table.update(patch)


def remove_table_key(payload: TomlPayload, table_name: str, key: str) -> None:
    current = payload.get(table_name)
    if isinstance(current, dict):
        cast("TomlPayload", current).pop(key, None)


def table_key(payload: TomlPayload, table_name: str, key: str) -> TomlValue | None:
    current = payload.get(table_name)
    if not isinstance(current, dict):
        return None
    return cast("TomlPayload", current).get(key)


def summarize_frame_selection(config: ConfigSchema) -> str:
    analysis = config.analysis
    if analysis.user_frames and not any(
        (
            analysis.random_frame_count,
            analysis.dark_frame_count,
            analysis.bright_frame_count,
            analysis.motion_frame_count,
        )
    ):
        return f"frames {', '.join(str(frame) for frame in analysis.user_frames)}"

    parts: list[str] = []
    if analysis.user_frames:
        parts.append(f"{len(analysis.user_frames)} specific")
    for count, label in (
        (analysis.random_frame_count, "random"),
        (analysis.dark_frame_count, "dark"),
        (analysis.bright_frame_count, "bright"),
        (analysis.motion_frame_count, "motion"),
    ):
        if count:
            parts.append(f"{count} {label}")
    return " + ".join(parts)


def metric_scan_for_config(config: ConfigSchema) -> MetricScan:
    analysis = config.analysis
    if not any(
        (analysis.dark_frame_count, analysis.bright_frame_count, analysis.motion_frame_count)
    ):
        return "disabled"
    return cast("MetricScan", analysis.performance_mode.value)

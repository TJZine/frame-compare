"""Shared doctor diagnostic data transfer objects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from frame_compare.errors import JSONValue


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of a diagnostic check."""

    passed: bool
    message: str
    available: bool | None = None
    hint: str | None = None
    details: dict[str, JSONValue] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """Single diagnostic check."""

    name: str
    category: str
    check_fn: Callable[[], CheckResult]


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Complete diagnostic report."""

    checks: list[tuple[DoctorCheck, CheckResult]]
    all_passed: bool
    critical_failures: list[str]


__all__ = ["CheckResult", "DoctorCheck", "DoctorReport"]

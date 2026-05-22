"""Orchestration public API.

Exports are resolved lazily to avoid importing VS-dependent modules when
consumers only need lightweight surfaces (for example `doctor` checks).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frame_compare.orchestration.coordinator import (
        RunDependencies,
        RunRequest,
        RunResult,
        execute_run,
    )
    from frame_compare.orchestration.doctor import (
        run_doctor,
    )

_EXPORTS: dict[str, tuple[str, str]] = {
    # Coordinator
    "RunDependencies": ("frame_compare.orchestration.coordinator", "RunDependencies"),
    "RunRequest": ("frame_compare.orchestration.coordinator", "RunRequest"),
    "RunResult": ("frame_compare.orchestration.coordinator", "RunResult"),
    "execute_run": ("frame_compare.orchestration.coordinator", "execute_run"),
    # Doctor
    "run_doctor": ("frame_compare.orchestration.doctor", "run_doctor"),
}

__all__ = (
    "RunDependencies",
    "RunRequest",
    "RunResult",
    "execute_run",
    "run_doctor",
)


def __getattr__(name: str) -> Any:
    export = _EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = export
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

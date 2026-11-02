"""Acquire run settings once; recheck filesystem facts at their use boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from frame_compare.config.loader import load_config
from frame_compare.config.overrides import CLIConfigOverrides, apply_cli_overrides
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError
from frame_compare.orchestration.preflight import resolve_paths, resolve_selected_config_path
from frame_compare.utils.types import WorkspacePaths

_NO_OVERRIDES = CLIConfigOverrides()

if TYPE_CHECKING:
    from frame_compare.orchestration.types import RunRequest


class LoadConfigFn(Protocol):
    def __call__(
        self, config_path: Path | None = None, overrides: dict[str, object] | None = None
    ) -> ConfigSchema: ...


@dataclass(frozen=True, slots=True)
class AcquiredRunConfig:
    """Admitted run settings, independent of later preference edits on disk."""

    root: Path
    config_path: Path
    config: ConfigSchema


def select_run_config_path(config_path: Path | None, root: Path | None) -> tuple[Path, Path]:
    resolved_root = (root or Path.cwd()).resolve()
    selected = config_path if config_path is not None else Path("config/config.toml")
    return resolved_root, resolve_selected_config_path(selected, resolved_root)


def acquire_run_config(
    *,
    root: Path | None,
    config_path: Path | None = None,
    overrides: CLIConfigOverrides = _NO_OVERRIDES,
    load_config_fn: LoadConfigFn = load_config,
) -> AcquiredRunConfig:
    resolved_root, selected = select_run_config_path(config_path, root)
    config = apply_cli_overrides(load_config_fn(selected), overrides)
    inputs = AcquiredRunConfig(resolved_root, selected, config)
    resolve_run_workspace(inputs)
    return inputs


def resolve_run_workspace(inputs: AcquiredRunConfig) -> WorkspacePaths:
    # Selection and managed paths may have been redirected since admission.
    selected = resolve_selected_config_path(
        inputs.config_path, inputs.root, expand_environment=False
    )
    return replace(resolve_paths(inputs.config, inputs.root), config_file=selected)


def build_run_request(
    *,
    root: Path | None,
    config_path: Path | None = None,
    overrides: CLIConfigOverrides = _NO_OVERRIDES,
    no_cache: bool = False,
    from_cache_only: bool = False,
    skip_analysis: bool = False,
    skip_metadata: bool = False,
    no_color: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False,
    load_config_fn: LoadConfigFn = load_config,
) -> RunRequest:
    from frame_compare.orchestration.types import RunRequest

    return RunRequest(
        inputs=acquire_run_config(
            root=root, config_path=config_path, overrides=overrides, load_config_fn=load_config_fn
        ),
        no_cache=no_cache,
        from_cache_only=from_cache_only,
        skip_analysis=skip_analysis,
        skip_metadata=skip_metadata,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        json_output=json_output,
    )


def refresh_report_auto_open_preference(
    inputs: AcquiredRunConfig, load_config_fn: LoadConfigFn = load_config
) -> bool | None:
    try:
        selected = resolve_selected_config_path(
            inputs.config_path, inputs.root, expand_environment=False
        )
        return load_config_fn(selected).report.auto_open
    except FrameCompareError:
        return None

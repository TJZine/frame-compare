"""Request builders for real workspaces and synthetic phase-only fixtures."""

from pathlib import Path

from frame_compare.config.loader import load_config
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.run_inputs import build_run_request
from frame_compare.orchestration.types import RunRequest


def make_run_request(
    *,
    root: Path,
    config: ConfigSchema | None = None,
    config_path: Path | None = None,
    overrides: CLIConfigOverrides | None = None,
    no_cache: bool = False,
    from_cache_only: bool = False,
    skip_analysis: bool = False,
    skip_metadata: bool = False,
    no_color: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False,
) -> RunRequest:
    def fixture_config(config_path: Path | None = None, overrides: dict[str, object] | None = None):
        return config if config is not None else load_config(config_path, overrides)

    return build_run_request(
        load_config_fn=fixture_config,
        root=root,
        config_path=config_path,
        overrides=overrides or CLIConfigOverrides(),
        no_cache=no_cache,
        from_cache_only=from_cache_only,
        skip_analysis=skip_analysis,
        skip_metadata=skip_metadata,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        json_output=json_output,
    )

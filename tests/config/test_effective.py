"""Acquisition applies CLI settings to one loader result without mutating it."""

from pathlib import Path

from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.orchestration.run_inputs import acquire_run_config


def test_acquisition_loads_selected_path_once_then_applies_overrides(tmp_path: Path) -> None:
    base = get_default_config()
    base.slowpics.auto_upload = True
    calls: list[Path | None] = []

    def load(config_path: Path | None = None, overrides: dict[str, object] | None = None):
        calls.append(config_path)
        assert overrides is None
        return base

    inputs = acquire_run_config(
        root=tmp_path,
        overrides=CLIConfigOverrides(
            input_dir=Path("incoming"), random_frame_count=7, no_upload=True
        ),
        load_config_fn=load,
    )
    assert calls == [tmp_path / "config/config.toml"]
    assert inputs.config.paths.input_dir == "incoming"
    assert inputs.config.analysis.random_frame_count == 7
    assert inputs.config.slowpics.auto_upload is False
    assert base.analysis.random_frame_count == 10
    assert base.slowpics.auto_upload is True

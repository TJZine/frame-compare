"""Legacy frame_compare shim coverage.

Phase 6.2 relocation map:
- CLI entry + runner orchestration: tests/runner/test_cli_entry.py (fixtures: cli_runner_env, runner, recording_output_manager, runner_vs_core_stub).
- Audio-alignment CLI flows: tests/runner/test_audio_alignment_cli.py (fixtures: cli_runner_env, recording_output_manager, json_tail_stub, runner_vs_core_stub).
- Slowpics/TMDB workflows: tests/runner/test_slowpics_workflow.py (fixtures: cli_runner_env, runner, runner_vs_core_stub).

Only shim delegation tests remain here until the compatibility layer is retired.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import frame_compare
import src.frame_compare.core as core_module
from src.frame_compare import runner as runner_module

pytestmark = pytest.mark.usefixtures("runner_vs_core_stub")  # type: ignore[attr-defined]


def test_run_cli_delegates_to_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure the frame_compare.run_cli shim forwards requests to runner.run."""

    cfg = core_module._fresh_app_config()
    dummy_result = frame_compare.RunResult(
        files=[],
        frames=[],
        out_dir=tmp_path,
        out_dir_created=False,
        out_dir_created_path=None,
        root=tmp_path,
        config=cfg,
        image_paths=[],
        slowpics_url=None,
        json_tail=None,
        report_path=None,
    )
    captured_request: runner_module.RunRequest | None = None
    captured_dependencies: runner_module.RunDependencies | None = None

    def _fake_run(
        request: runner_module.RunRequest,
        *,
        dependencies: runner_module.RunDependencies | None = None,
    ) -> frame_compare.RunResult:
        nonlocal captured_request, captured_dependencies
        captured_request = request
        captured_dependencies = dependencies
        return dummy_result

    monkeypatch.setattr(runner_module, "run", _fake_run)
    result = frame_compare.run_cli(
        "config-path",
        "input-dir",
        root_override=str(tmp_path),
        audio_track_overrides=("A=B",),
        quiet=True,
        verbose=True,
        no_color=True,
        report_enable_override=True,
        skip_wizard=True,
        debug_color=True,
        tonemap_overrides={"preset": "reference"},
    )

    assert result is dummy_result
    assert captured_request is not None
    request = captured_request
    assert request.config_path == "config-path"
    assert request.input_dir == "input-dir"
    assert request.root_override == str(tmp_path)
    assert request.audio_track_overrides == ("A=B",)
    assert request.quiet is True
    assert request.verbose is True
    assert request.no_color is True
    assert request.report_enable_override is True
    assert request.skip_wizard is True
    assert request.debug_color is True
    assert request.tonemap_overrides == {"preset": "reference"}
    assert captured_dependencies is None

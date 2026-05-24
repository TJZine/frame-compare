import json
import tomllib
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode
from frame_compare.config.schema import OverlayMode, ToneCurve, TonemapPreset
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult

from .cli_helpers import (
    MINIMAL_CONFIG,
    _invoke_run_with_minimal_workspace,
    runner,
)


def test_run_exits_processing_error_when_runner_returns_unsuccessful(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=False)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])
    assert result.exit_code == 5


def test_run_builds_run_request_from_cli_args(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        [
            "--tm-target",
            "203",
            "--overlay",
            "diagnostic",
            "--force-interactive-alignment",
        ]
    )
    assert result.exit_code == 0

    request = captured["request"]
    assert request.tm_target_nits == 203
    assert request.overlay_mode == OverlayMode.DIAGNOSTIC
    assert request.force_interactive_alignment is True


def test_run_builds_run_request_with_typed_choice_overrides(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        [
            "--tm-preset",
            "filmic",
            "--tm-curve",
            "spline",
            "--overlay",
            "diagnostic",
        ]
    )

    assert result.exit_code == 0
    request = captured["request"]
    assert request.tm_preset == TonemapPreset.FILMIC
    assert request.tm_curve == ToneCurve.SPLINE
    assert request.overlay_mode == OverlayMode.DIAGNOSTIC


def test_run_builds_run_request_with_input_dir(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--input", "custom_inputs"])
    assert result.exit_code == 0
    assert captured["request"].input_dir == Path("custom_inputs")


def test_run_write_config_respects_root_and_config_and_does_not_invoke_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --write-config")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            [
                "run",
                "--write-config",
                "--root",
                str(root),
                "--config",
                "configs/config.toml",
                "--frame-count",
                "17",
            ],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 17


def test_run_write_config_write_error_uses_cli_error_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    result = _invoke_run_with_minimal_workspace(["--write-config"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stdout == ""
    assert "FC-1007" in result.stderr
    assert "Failed to write configuration file" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_diagnose_paths_outputs_pinned_json_schema_and_does_not_invoke_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --diagnose-paths")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            [
                "run",
                "--diagnose-paths",
                "--root",
                str(root),
                "--config",
                "config/config.toml",
                "--input",
                "inputs",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {"cache", "config", "input", "output", "root"}
        assert payload["root"] == str(root.resolve())
        assert payload["config"] == str(config_path.resolve())
        assert payload["input"] == str((root / "inputs").resolve())
        assert payload["output"] == str((root / "screenshots").resolve())
        assert payload["cache"] == str((root / "generated").resolve())

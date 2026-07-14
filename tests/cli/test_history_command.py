from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from frame_compare.cli.entry import app
from frame_compare.services.run_result_record import (
    CompletedRunFacts,
    completed_record,
    write_run_result,
)
from frame_compare.utils.types import WorkspacePaths

runner = CliRunner()

CONFIG = """\
[paths]
input_dir = "inputs-that-no-longer-exist"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[report]
enable = true

[audio_alignment]
enable = false
"""


def _workspace(root: Path, run_dir: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=root,
        input_dir=root / "inputs-that-no-longer-exist",
        run_dir=run_dir,
        screenshots_dir=run_dir / "screenshots",
        generated_dir=run_dir / "generated",
        config_dir=root / "config",
        config_file=root / "config" / "config.toml",
        analysis_cache_dir=root / "generated" / "cache" / "analysis",
    )


def _setup(root: Path, name: str = "Exact Run") -> Path:
    config = root / "config" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(CONFIG, encoding="utf-8")
    run_dir = root / "generated" / name
    run_dir.mkdir(parents=True)
    report = run_dir / "report.html"
    report.write_text("report", encoding="utf-8")
    started = datetime(2026, 7, 14, 12, tzinfo=UTC)
    record = completed_record(
        workspace=_workspace(root, run_dir),
        facts=CompletedRunFacts(
            report_path=report,
            screenshot_dir=run_dir / "screenshots",
            clip_count=2,
            selected_frame_count=4,
            warnings=(),
            metrics_cache_status="miss",
            phase_timings={"render": 1.0},
            slowpics_url=None,
            slowpics_confirmation_status="not_applicable",
        ),
        started_at=started,
        completed_at=started + timedelta(seconds=5),
    )
    write_run_result(run_dir, record)
    return report


def _invoke(root: Path, args: list[str]):
    return runner.invoke(
        app,
        ["history", *args, "--root", str(root)],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )


def test_history_list_json_is_exact_allowlisted_object_without_inputs(tmp_path: Path) -> None:
    _setup(tmp_path)

    result = _invoke(tmp_path, ["list", "--json"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert set(payload) == {"runs"}
    assert len(payload["runs"]) == 1
    assert set(payload["runs"][0]) == {
        "name",
        "status",
        "started_at",
        "completed_at",
        "duration_seconds",
        "report_available",
    }
    assert payload["runs"][0] == {
        "name": "Exact Run",
        "status": "completed",
        "started_at": "2026-07-14T12:00:00Z",
        "completed_at": "2026-07-14T12:00:05Z",
        "duration_seconds": 5.0,
        "report_available": True,
    }


def test_history_list_malformed_warning_uses_stderr_and_keeps_json_clean(
    tmp_path: Path,
) -> None:
    _setup(tmp_path)
    broken = tmp_path / "generated" / "Broken"
    broken.mkdir()
    (broken / "run_result.toml").write_text("version = 99\n", encoding="utf-8")

    result = _invoke(tmp_path, ["list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [entry["status"] for entry in payload["runs"]] == ["completed", "unavailable"]
    assert "Broken" in result.stderr
    assert "unreadable or unsupported" in result.stderr
    assert "Warning" not in result.stdout


def test_history_list_human_exposes_concise_fields(tmp_path: Path) -> None:
    _setup(tmp_path)

    result = _invoke(tmp_path, ["list"])

    assert result.exit_code == 0
    assert result.stdout == "Exact Run\tcompleted\t2026-07-14T12:00:05Z\treport=yes\n"
    assert result.stderr == ""


def test_history_open_uses_exact_recorded_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _setup(tmp_path)
    opened: list[Path] = []
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda path: opened.append(path) is None or True,
    )

    result = _invoke(tmp_path, ["open", "Exact Run"])

    assert result.exit_code == 0
    assert opened == [report.resolve()]
    assert result.stdout == "Opened report for run 'Exact Run'.\n"


@pytest.mark.parametrize("outcome", [False, RuntimeError("browser secret")])
def test_history_open_browser_false_or_exception_is_typed_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: object
) -> None:
    _setup(tmp_path)

    def open_report(_path: Path) -> bool:
        if isinstance(outcome, Exception):
            raise outcome
        return False

    monkeypatch.setattr("frame_compare.cli.entry._maybe_open_report", open_report)
    result = _invoke(tmp_path, ["open", "Exact Run"])

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "[FC-4020]" in result.stderr
    assert "browser secret" not in result.stderr


def test_history_open_rejects_nonexact_name(tmp_path: Path) -> None:
    _setup(tmp_path)

    result = _invoke(tmp_path, ["open", "Exact"])

    assert result.exit_code == 4
    assert "Run was not found" in result.stderr


def test_history_help_does_not_import_vs_runtime() -> None:
    code = """
import sys
from typer.testing import CliRunner
from frame_compare.cli.entry import app
result = CliRunner().invoke(app, ['history', '--help'])
assert result.exit_code == 0, result.output
assert 'vapoursynth' not in sys.modules
assert 'frame_compare.vs.loader' not in sys.modules
"""
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.orchestration import coordinator
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.errors import NoVideosFoundError
from frame_compare.services.run_result_record import read_run_result

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    FakeVSLoader,
    create_config,
    create_video_files,
)


class FailingVSLoader:
    def __init__(self, error: RuntimeError) -> None:
        self.error = error

    def load(self, _path: Path) -> object:
        raise self.error

    def ensure_core(self) -> object:
        raise AssertionError("not reached")


def _request(root: Path) -> RunRequest:
    return RunRequest(
        root=root,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
        quiet=True,
    )


def test_success_writes_completed_result_after_run(tmp_path: Path) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")

    result = asyncio.run(
        execute_run(
            _request(tmp_path),
            deps=RunDependencies(
                vs_loader=FakeVSLoader(), ffmpeg_runner=cast(Any, FakeFFmpegRunner())
            ),
        )
    )

    assert result.screenshot_dir is not None
    record = read_run_result(result.screenshot_dir.parent / "run_result.toml")
    assert record.status == "completed"
    assert record.clip_count == 1
    assert record.selected_frame_count == result.frame_count
    assert record.report_path is None


def test_failure_after_reservation_during_prep_writes_failed_and_reraises_identical(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    original = RuntimeError("secret=/Users/private?token=abc")

    with pytest.raises(RuntimeError) as raised:
        asyncio.run(
            execute_run(
                _request(tmp_path),
                deps=RunDependencies(
                    vs_loader=FailingVSLoader(original),  # type: ignore[arg-type]
                    ffmpeg_runner=cast(Any, FakeFFmpegRunner()),
                ),
            )
        )

    assert raised.value is original
    run_dirs = [path for path in (tmp_path / "generated").iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    record = read_run_result(run_dirs[0] / "run_result.toml")
    assert record.status == "failed"
    assert record.clip_count == 1
    assert "preflight" in record.phase_timings
    assert record.failure is not None
    assert record.failure.code == "FC-0001"
    assert "secret" not in record.failure.message
    assert "/Users" not in record.failure.message


def test_failure_before_reservation_creates_no_result(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError):
        asyncio.run(execute_run(_request(tmp_path)))

    assert list(tmp_path.rglob("run_result.toml")) == []


def test_empty_input_failure_before_reservation_creates_no_result(tmp_path: Path) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    (tmp_path / "comparison_videos").mkdir()

    with pytest.raises(NoVideosFoundError):
        asyncio.run(execute_run(_request(tmp_path)))

    assert list(tmp_path.rglob("run_result.toml")) == []


def test_completed_result_write_failure_is_warning_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")

    def fail_write(_run_dir: Path, _record: object) -> None:
        raise PermissionError("secret-path")

    monkeypatch.setattr(
        "frame_compare.orchestration.run_result_lifecycle.write_run_result",
        fail_write,
    )
    result = asyncio.run(
        execute_run(
            _request(tmp_path),
            deps=RunDependencies(
                vs_loader=FakeVSLoader(), ffmpeg_runner=cast(Any, FakeFFmpegRunner())
            ),
        )
    )

    assert result.success is True
    assert result.warnings == ["history: run result could not be recorded"]
    assert list(tmp_path.rglob("run_result.toml")) == []


def test_completed_result_write_and_logger_failure_are_warning_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")

    def fail_write(_run_dir: Path, _record: object) -> None:
        raise PermissionError("recording")

    def fail_log(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("logger failure")

    monkeypatch.setattr(
        "frame_compare.orchestration.run_result_lifecycle.write_run_result",
        fail_write,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.run_result_lifecycle.log.warning",
        fail_log,
    )

    result = asyncio.run(
        execute_run(
            _request(tmp_path),
            deps=RunDependencies(
                vs_loader=FakeVSLoader(), ffmpeg_runner=cast(Any, FakeFFmpegRunner())
            ),
        )
    )

    assert result.success is True
    assert result.warnings == ["history: run result could not be recorded"]


@pytest.mark.parametrize("control_error", [KeyboardInterrupt(), SystemExit(2)])
def test_completed_result_process_control_write_failure_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    control_error: BaseException,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")

    def fail_write(_run_dir: Path, _record: object) -> None:
        raise control_error

    monkeypatch.setattr(
        "frame_compare.orchestration.run_result_lifecycle.write_run_result",
        fail_write,
    )

    with pytest.raises(type(control_error)) as raised:
        asyncio.run(
            execute_run(
                _request(tmp_path),
                deps=RunDependencies(
                    vs_loader=FakeVSLoader(), ffmpeg_runner=cast(Any, FakeFFmpegRunner())
                ),
            )
        )

    assert raised.value is control_error


def test_failed_result_write_failure_preserves_original_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    original = RuntimeError("original")

    def fail_write(_run_dir: Path, _record: object) -> None:
        raise PermissionError("recording")

    monkeypatch.setattr(
        "frame_compare.orchestration.run_result_lifecycle.write_run_result",
        fail_write,
    )
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(
            execute_run(
                _request(tmp_path),
                deps=RunDependencies(
                    vs_loader=FailingVSLoader(original),  # type: ignore[arg-type]
                    ffmpeg_runner=cast(Any, FakeFFmpegRunner()),
                ),
            )
        )

    assert raised.value is original


def test_failed_result_process_control_write_failure_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    original = RuntimeError("original")
    interrupt = KeyboardInterrupt()

    def interrupt_write(_run_dir: Path, _record: object) -> None:
        raise interrupt

    monkeypatch.setattr(
        "frame_compare.orchestration.run_result_lifecycle.write_run_result",
        interrupt_write,
    )

    with pytest.raises(KeyboardInterrupt) as raised:
        asyncio.run(
            execute_run(
                _request(tmp_path),
                deps=RunDependencies(
                    vs_loader=FailingVSLoader(original),  # type: ignore[arg-type]
                    ffmpeg_runner=cast(Any, FakeFFmpegRunner()),
                ),
            )
        )

    assert raised.value is interrupt


def test_failure_after_alignment_records_known_selected_frame_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    original = RuntimeError("post-alignment failure")

    def fail_after_alignment(**_kwargs: object) -> None:
        raise original

    monkeypatch.setattr(coordinator, "emit_final_selection_report", fail_after_alignment)
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(
            execute_run(
                _request(tmp_path),
                deps=RunDependencies(
                    vs_loader=FakeVSLoader(),
                    ffmpeg_runner=cast(Any, FakeFFmpegRunner()),
                ),
            )
        )

    assert raised.value is original
    run_dirs = [path for path in (tmp_path / "generated").iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    record = read_run_result(run_dirs[0] / "run_result.toml")
    assert record.status == "failed"
    assert record.selected_frame_count > 0

"""Phase integration tests covered by execute_run fixtures."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Never, cast
from unittest.mock import AsyncMock

import pytest

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode
from frame_compare.config.loader import load_config
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.orchestration import execution, phase_alignment, phase_post_render
from frame_compare.orchestration.coordinator import RunDependencies, execute_run
from frame_compare.orchestration.execution_types import (
    MetadataPrefetch,
    RunArtifacts,
)
from frame_compare.orchestration.types import (
    RunRequest,
    RunResult,
    SlowpicsUploadConfirmationDecision,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.render.errors import RenderError
from frame_compare.runner import run as real_run
from frame_compare.services import alignment, alignment_vsview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.run_result_record import read_run_result
from frame_compare.services.types import (
    AlignmentOperationOutcome,
    AlignmentResult,
    TmdbMetadata,
)
from tests.cli.cli_helpers import _normalize_cli_output, _write_minimal_config, runner
from tests.render_test_support import paths_by_label
from tests.run_request_support import make_run_request
from tests.services.alignment_request_test_support import vsview_session
from tests.services.alignment_resolution_test_support import configure_computed_alignment

from .execute_run_helpers import (
    FakeVSLoader,
    FakeVSNode,
    clip_state,
    create_video_files,
    execution_context,
    install_fake_frame_render,
)
from .phase_task_helpers import _render_artifacts, _workspace
from .preparation_test_support import create_config


def test_execute_run_align_applies_trim_first_frame_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = true

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_ref.mkv", "b_comp1.mkv", "c_comp2.mkv")

    async def _fake_align_clips_from_request(
        request,
        config,
        progress=None,
        frame_props_by_stem=None,
        verbose=False,
        quiet=False,
        json_output=False,
        vs_loader=None,
        on_reusable_cache_written=None,
        on_diagnostics_written=None,
    ):
        assert request.shared_alignment_cache_dir == tmp_path / "generated" / "cache" / "alignment"
        assert request.reference.identity.path == request.reference.path
        assert [comparison.identity.path for comparison in request.comparisons] == [
            comparison.path for comparison in request.comparisons
        ]
        assert json_output is False
        assert quiet is False
        assert verbose is False
        return AlignmentOperationOutcome(
            (
                AlignmentResult(
                    reference_clip=request.reference.path.name,
                    comparison_clip=request.comparisons[0].path.name,
                    frame_offset=1,
                    time_offset_seconds=0.041,
                    correlation_score=0.9,
                    algorithm="cross_correlation",
                    source="computed",
                ),
                AlignmentResult(
                    reference_clip=request.reference.path.name,
                    comparison_clip=request.comparisons[1].path.name,
                    frame_offset=-1,
                    time_offset_seconds=-0.041,
                    correlation_score=0.9,
                    algorithm="cross_correlation",
                    source="computed",
                ),
            )
        )

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    recorded = install_fake_frame_render(monkeypatch)
    deps = RunDependencies(vs_loader=FakeVSLoader())
    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(random_frame_count=3, no_upload=True),
    )

    result = asyncio.run(execute_run(request, deps=deps))
    assert result.success is True
    assert result.frame_count == 3

    by_video: dict[str, list[int]] = {}
    for render_request in recorded:
        source_name = cast(FakeVSNode, cast(Any, render_request.clip)).source_path.name
        by_video.setdefault(source_name, []).append(render_request.frame_number)

    assert by_video["a_ref.mkv"] == [32, 66, 83]
    assert by_video["b_comp1.mkv"] == [31, 65, 82]
    assert by_video["c_comp2.mkv"] == [33, 67, 84]


@pytest.fixture
def real_cli_runner(monkeypatch: pytest.MonkeyPatch) -> list[RunResult]:
    results: list[RunResult] = []
    install_fake_frame_render(monkeypatch)

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        result = real_run(
            request,
            replace(
                dependencies or RunDependencies(),
                vs_loader=FakeVSLoader(),
            ),
        )
        results.append(result)
        return result

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    return results


@pytest.mark.usefixtures("real_cli_runner")
@pytest.mark.parametrize(
    "mode", ["forced-failure", "warned-fallback", "plain-success", "write-failure"]
)
def test_cli_reports_alignment_diagnostics_from_the_actual_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    configure_computed_alignment(monkeypatch)
    forced = mode == "forced-failure"
    if forced:
        monkeypatch.setattr("frame_compare.cli.entry._sys_stream_isatty", lambda *_: True)
        monkeypatch.setattr(
            alignment_vsview,
            "launch_alignment_verification_session",
            lambda **_: (vsview_session(tmp_path), 0.0),
        )
    if mode == "write-failure":

        def fail_write(**_: object) -> Never:
            raise OSError("diagnostics write failed")

        monkeypatch.setattr(alignment, "write_alignment_diagnostic", fail_write)
    create_config(
        tmp_path,
        content=f"""
[audio_alignment]
enable = true
use_vsview = {str(forced).lower()}
force_interactive = {str(forced).lower()}
[report]
enable = false
[tmdb]
enabled = false
""",
    )
    create_video_files(tmp_path / "comparison_videos", "reference.mkv", "encode.mkv")
    result = runner.invoke(
        app,
        [
            "run",
            "--root",
            str(tmp_path),
            "--skip-analysis",
            "--skip-metadata",
            "--no-upload",
            "--frames",
            "0" if mode == "warned-fallback" else "30",
            "--random-frame-count",
            "0",
            "--no-color",
        ],
        env={"TERM": "dumb", "COLUMNS": "120"},
    )
    output = _normalize_cli_output(result.output)
    assert result.exit_code == (int(ExitCode.PROCESSING_ERROR) if forced else 0), output
    written = list(tmp_path.glob("generated/*/alignment_diagnostics/comparison-*.json"))
    if mode == "write-failure":
        assert not written and "diagnostics     generated/" not in output
        return
    (diagnostic,) = written
    display_path = str(diagnostic.parent.relative_to(tmp_path))
    assert output.count(display_path) == 1
    if forced:
        assert "Error [FC-4005]" in output
        assert output.index("did not return a valid VSView review result") < output.index(
            display_path
        )
        assert "Comparison complete" not in output
    else:
        assert output.index("Comparison complete") < output.index(display_path)
    if mode == "warned-fallback":
        assert "No selected frames remain after alignment." in output
    if mode == "plain-success":
        assert re.search(
            r"\[OK\] PLAN [^\n]+\n\nreference: \+3f · applied\n"
            r"  [^\n]+\n\n\[OK\] ALIGN",
            output,
        )


@pytest.mark.parametrize("answer", ["yes\n", "no\n", ""], ids=["accept", "decline", "eof"])
def test_cli_full_window_retry_preserves_precise_settings_and_block_spacing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    answer: str,
    real_cli_runner: list[RunResult],
) -> None:
    monkeypatch.setattr("frame_compare.cli.entry._sys_stream_isatty", lambda *_: True)
    create_config(
        tmp_path,
        content="""
[analysis]
min_window_seconds = 0
ignore_lead_seconds = 12.0
ignore_trail_seconds = 0.03
[audio_alignment]
enable = false
[report]
enable = false
[tmdb]
enabled = false
""",
    )
    create_video_files(tmp_path / "comparison_videos", "reference.mkv", "encode.mkv")
    result = runner.invoke(
        app,
        [
            "run",
            "--root",
            str(tmp_path),
            "--skip-metadata",
            "--no-upload",
            "--frames",
            "30",
            "--random-frame-count",
            "0",
            "--no-color",
        ],
        input=answer,
        env={"TERM": "dumb", "COLUMNS": "120"},
    )
    output = _normalize_cli_output(result.output)
    assert "Analyze the full shared clip for this run?" in output
    if answer == "yes\n":
        assert result.exit_code == 0, output
        warning_text = " ".join(line.removeprefix("│ ").strip() for line in output.splitlines())
        assert (
            "(configured lead=12.0 s, trail=0.03 s; effective lead=0.0 s, trail=0.0 s)"
            in warning_text
        )
        (run_result,) = real_cli_runner
        assert any(
            "(configured lead=12.0 s, trail=0.03 s; effective lead=0.0 s, trail=0.0 s)"
            in warning.text
            for warning in run_result.warnings
        )
    else:
        assert result.exit_code == int(ExitCode.PROCESSING_ERROR), output
        assert "╰─\n\n✗ Error [FC-4012]" in output
    assert output.count("first 12.0 s · last 0.03 s") == 2


@pytest.mark.usefixtures("real_cli_runner")
@pytest.mark.parametrize("transport", ["human", "json", "quiet"])
def test_render_failure_reports_written_alignment_diagnostics_once_in_human_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transport: str
) -> None:
    configure_computed_alignment(monkeypatch)

    def _fail_render(*_args: object, **_kwargs: object) -> Never:
        raise RenderError("test render failure")

    monkeypatch.setattr(execution, "run_render_phase", _fail_render)

    root = tmp_path / "workspace"
    config_path = _write_minimal_config(root)
    with config_path.open("a", encoding="utf-8") as stream:
        stream.write("\n[audio_alignment]\nenable = true\n[report]\nenable = false\n")
    create_video_files(root / "comparison_videos", "reference.mkv", "encode.mkv")
    command = [
        "run",
        "--root",
        str(root),
        "--skip-analysis",
        "--skip-metadata",
        "--no-upload",
        "--frames",
        "30",
        "--random-frame-count",
        "0",
    ]
    if transport != "human":
        command.append(f"--{transport}")
    result = runner.invoke(app, command)
    assert result.exit_code == int(ExitCode.PROCESSING_ERROR), result.output
    (path,) = (root / "generated").glob("*/alignment_diagnostics/comparison-1.json")
    display_path = str(path.parent.relative_to(root))
    if transport == "json":
        payload = json.loads(result.stdout)
        assert payload["error"]["code"] == "FC-4004"
        assert "alignment_diagnostics" not in result.stdout
        assert display_path not in result.stderr
    elif transport == "quiet":
        assert "test render failure" in result.stderr
        assert display_path not in result.stderr
    else:
        stderr = _normalize_cli_output(result.stderr)
        assert stderr.count(display_path) == 1
        assert stderr.index("test render failure") < stderr.index(display_path)
        assert "Comparison complete" not in result.stdout


def test_execute_run_forced_alignment_failure_stops_before_render_and_records_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = true
use_vsview = true
force_interactive = true

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    create_video_files(tmp_path / "comparison_videos", "a_ref.mkv", "b_comp.mkv")

    failure = AudioAlignmentError(
        "Interactive alignment did not return a valid VSView review result."
    )

    async def _fail_alignment(*_args: object, **_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fail_alignment)
    recorded = install_fake_frame_render(monkeypatch)

    with pytest.raises(AudioAlignmentError) as raised:
        asyncio.run(
            execute_run(
                make_run_request(
                    root=tmp_path,
                    skip_analysis=True,
                    skip_metadata=True,
                    overrides=CLIConfigOverrides(random_frame_count=1, no_upload=True),
                ),
                deps=RunDependencies(vs_loader=FakeVSLoader()),
            )
        )

    assert raised.value is failure
    assert recorded == []
    run_dirs = [path for path in (tmp_path / "generated").iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    record = read_run_result(run_dirs[0] / "run_result.toml")
    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.code == "FC-4005"


def test_execute_run_report_confirmed_decline_skips_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_frame_render(monkeypatch)
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[slowpics]
auto_upload = true
confirm_upload_after_report = true

[audio_alignment]
enable = false

[report]
enable = true
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_source.mkv", "b_encode.mkv")
    callback_calls: list[SlowpicsUploadConfirmationRequest] = []

    def _decline(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        callback_calls.append(request)
        return "declined"

    publish = AsyncMock()
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        publish,
    )

    result = asyncio.run(
        execute_run(
            make_run_request(
                root=tmp_path,
                skip_analysis=True,
                skip_metadata=True,
                overrides=CLIConfigOverrides(random_frame_count=1),
            ),
            deps=RunDependencies(
                vs_loader=FakeVSLoader(),
                confirm_slowpics_upload=_decline,
            ),
        )
    )

    assert result.success is True
    assert result.report_path is not None
    assert result.slowpics_upload_confirmation_status == "declined"
    assert result.slowpics_url is None
    publish.assert_not_awaited()
    assert not any(warning.text.startswith("publish:") for warning in result.warnings)


def test_run_metadata_phase_uses_prefetched_metadata_without_client(tmp_path: Path) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = execution_context(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[],
    )
    expected_metadata = TmdbMetadata(
        tmdb_id=789,
        title="Thief",
        original_title="Thief",
        year=1981,
        media_type="movie",
    )
    output = asyncio.run(
        phase_post_render.run_metadata_phase(
            ctx,
            client=None,
            metadata_prefetch=MetadataPrefetch(metadata=expected_metadata, was_attempted=True),
        )
    )

    assert output.resolved_metadata == expected_metadata


def test_run_publish_phase_without_client_clears_slowpics_url(tmp_path: Path) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = execution_context(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[],
    )
    artifacts = RunArtifacts(slowpics_url="https://slow.pics/c/example")

    output = asyncio.run(
        phase_post_render.run_publish_phase(
            ctx,
            client=None,
            metadata=artifacts.resolved_metadata,
        )
    )

    assert output.slowpics_url is None
    assert artifacts.slowpics_url == "https://slow.pics/c/example"


def test_run_report_phase_clears_report_path_when_no_screenshots(tmp_path: Path) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    ctx = execution_context(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[],
    )
    artifacts = RunArtifacts(report_path=tmp_path / "stale.html")

    output = phase_post_render.run_report_phase(
        ctx,
        frames=[1, 2],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    assert output.report_path is None
    assert artifacts.report_path == tmp_path / "stale.html"


def test_run_report_phase_builds_report_from_current_clip_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path)
    config = load_config(tmp_path / "config" / "config.toml")
    reference = clip_state(tmp_path / "comparison_videos" / "source.mkv", label="Reference")
    comparison = clip_state(
        tmp_path / "comparison_videos" / "encode.mkv",
        label="Encode 1",
        num_frames=80,
    )
    ctx = execution_context(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[comparison],
    )
    metadata = TmdbMetadata(
        tmdb_id=321,
        title="Collateral",
        original_title="Collateral",
        year=2004,
        media_type="movie",
    )
    render = _render_artifacts(
        screenshots_by_label={
            "Reference": [
                tmp_path / "screenshots" / "Reference_000007.png",
                tmp_path / "screenshots" / "Reference_000011.png",
            ],
            "Encode 1": [
                tmp_path / "screenshots" / "Encode_1_000007.png",
                tmp_path / "screenshots" / "Encode_1_000011.png",
            ],
        },
        screenshot_dir=tmp_path / "screenshots",
        source_frames_by_label={"Reference": [7, 11], "Encode 1": [7, 11]},
    )
    artifacts = RunArtifacts(
        render=render,
        resolved_metadata=metadata,
        slowpics_url="https://slow.pics/c/collateral",
    )
    captured: dict[str, Any] = {}
    expected_report_path = tmp_path / "run" / "report.html"

    def _fake_generate_report(report_data, report_config, *, output_path: Path):
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        assert output_path == expected_report_path
        return output_path

    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)

    output = phase_post_render.run_report_phase(
        ctx,
        frames=[7, 11],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_report_path
    assert report_data.frames == [7, 11]
    assert [image.path for image in report_data.clips[0].images] == paths_by_label(render.clips)[
        "Reference"
    ]
    assert [image.path for image in report_data.clips[1].images] == paths_by_label(render.clips)[
        "Encode 1"
    ]
    assert report_data.metadata == metadata
    assert report_data.slowpics_url == "https://slow.pics/c/collateral"
    assert [(clip.name, clip.frame_count) for clip in report_data.clips] == [
        ("Reference", 100),
        ("Encode 1", 80),
    ]
    assert captured["report_config"] == config.report


@pytest.mark.usefixtures("real_cli_runner")
@pytest.mark.parametrize("alignment_enabled", [False, True])
def test_cli_dropped_frames_notice_uses_shared_run_spacing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, alignment_enabled: bool
) -> None:
    if alignment_enabled:
        configure_computed_alignment(monkeypatch)
    root = tmp_path / "workspace"
    config_path = _write_minimal_config(root)
    with config_path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n[audio_alignment]\nenable = {str(alignment_enabled).lower()}\n"
            "[report]\nenable = false\n"
        )
    create_video_files(root / "comparison_videos", "reference.mkv", "encode.mkv")
    monkeypatch.setattr("frame_compare.cli.entry._sys_stream_isatty", lambda *_: True)
    monkeypatch.setattr("frame_compare.orchestration.progress.stream_is_tty", lambda *_: True)
    result = runner.invoke(
        app,
        [
            "run",
            "--root",
            str(root),
            "--skip-analysis",
            "--skip-metadata",
            "--no-upload",
            "--frames",
            "0,120",
            "--random-frame-count",
            "1",
            "--no-color",
        ],
        env={"TERM": "xterm-256color", "COLUMNS": "120"},
    )
    output = _normalize_cli_output(result.output)
    assert result.exit_code == 0, output
    message = (
        "2 requested frames fall outside the shared range and were skipped: 0, 120"
        if alignment_enabled
        else "1 requested frame falls outside the shared range and was skipped: 120"
    )
    assert output.count(message) == 2
    warnings = output[output.index("Warnings") :]
    assert warnings.count(message) == 1
    notice = output[: output.index("Warnings")]
    if alignment_enabled:
        assert notice.index(message) > notice.index("Align")
    else:
        assert f"╰─\n\n! {message}" in notice
        assert f"╰─\n\n\n! {message}" not in notice

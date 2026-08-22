"""Unit tests for progress reporting utilities."""

import re
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pytest
from rich.console import Console
from rich.progress import ProgressSample, Task

import frame_compare.utils.progress as progress_module
from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    PlainProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


def _captured_rich_reporter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[RichProgressReporter, StringIO]:
    monkeypatch.setenv("TERM", "xterm-256color")
    output = StringIO()
    console = Console(file=output, force_terminal=True, no_color=True, width=100)

    def _console(**_kwargs: object) -> Console:
        return console

    monkeypatch.setattr(progress_module, "Console", _console)
    return RichProgressReporter(no_color=True), output


def test_null_progress_reporter_noops():
    """Test that NullProgressReporter methods do not raise exceptions."""
    reporter = NullProgressReporter()
    reporter.start_phase("test", 10)
    reporter.advance(1)
    reporter.set_description("desc")
    reporter.complete_phase()
    reporter.suspend()
    reporter.resume()


def test_rich_progress_reporter_accepts_no_color() -> None:
    reporter = RichProgressReporter(no_color=True)

    assert reporter.no_color is True
    assert reporter.writes_to_stderr is True


def test_rich_progress_reporter_marks_active_work_without_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)

    reporter.start_phase("PLAN", 1)
    try:
        assert "[RUN] PLAN" in output.getvalue()

        reporter.set_description("Selecting frames")
        assert "[RUN] Selecting frames" in output.getvalue()
    finally:
        reporter.complete_phase()


def test_rich_progress_active_marker_style_does_not_leak_to_description() -> None:
    task = Task(
        0,
        "ALIGN | Interactive verification",
        total=1,
        completed=0,
        _get_time=lambda: 0.0,
    )
    rendered = progress_module._ActiveDescriptionColumn().render(task)  # noqa: SLF001

    assert isinstance(rendered, progress_module.Text)
    assert rendered.plain == "  [RUN] ALIGN | Interactive verification"
    assert str(rendered.get_style_at_offset(Console(), 2)) == "bright_cyan"
    assert str(rendered.get_style_at_offset(Console(), 8)) == "none"


@pytest.mark.parametrize(
    ("marker", "style"),
    [
        ("[OK]", "green"),
        ("[WARN]", "yellow"),
        ("[FAIL]", "red"),
        ("[SKIP]", "dim yellow"),
    ],
)
def test_rich_durable_status_styles_only_the_marker(marker: str, style: str) -> None:
    rendered = progress_module._status_line(marker, "ALIGN")  # noqa: SLF001

    assert rendered.plain == f"  {marker} ALIGN"
    assert str(rendered.get_style_at_offset(Console(), 2)) == style
    assert str(rendered.get_style_at_offset(Console(), 2 + len(marker) + 1)) == "none"


def test_rich_progress_reporter_indents_live_work(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)

    reporter.start_phase("PLAN", 1)
    try:
        assert re.search(r" {2,}\[RUN\] PLAN", output.getvalue()) is not None
    finally:
        reporter.complete_phase()


def test_log_progress_reporter_supports_nested_phases(capsys) -> None:
    """Nested phases should restore parent context on completion."""
    reporter = LogProgressReporter()
    reporter.start_phase("outer", 100)
    reporter.advance(10)

    reporter.start_phase("inner", 1)
    reporter.advance(1)
    reporter.complete_phase()
    reporter.advance(15)

    captured = capsys.readouterr()

    assert "phase=outer" in captured.out
    assert "percentage=10" in captured.out
    assert "phase=inner" in captured.out
    assert "percentage=100" in captured.out
    assert "percentage=25" in captured.out


def test_plain_progress_reporter_emits_one_ascii_line_per_top_level_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    clock = iter((0.0, 84.9, 85.0, 86.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))
    reporter = PlainProgressReporter(output)

    reporter.start_phase("ANALYZE", 100)
    reporter.start_indeterminate("D\N{LATIN SMALL LETTER E WITH ACUTE}CODE")
    reporter.complete_phase()
    reporter.complete_phase()
    reporter.start_phase("METADATA  Disabled", 1)
    reporter.complete_phase(ProgressPhaseStatus.SKIPPED)

    assert output.getvalue().splitlines() == [
        "[OK] ANALYZE  Completed in 1m 25s",
        "[SKIP] METADATA  Disabled",
    ]
    assert output.getvalue().isascii()
    assert "\x1b[" not in output.getvalue()
    assert "\r" not in output.getvalue()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ProgressPhaseStatus.WARNED, "[WARN] nested"),
        (ProgressPhaseStatus.FAILED, "[FAIL] nested"),
    ],
)
def test_plain_progress_reporter_preserves_material_nested_outcomes(
    status: ProgressPhaseStatus,
    expected: str,
) -> None:
    output = StringIO()
    reporter = PlainProgressReporter(output)

    reporter.start_phase("TOP", 1)
    reporter.start_indeterminate("nested")
    reporter.complete_phase(status)
    reporter.complete_phase()

    assert output.getvalue().splitlines()[0] == expected
    assert output.getvalue().count("TOP") == 1


def test_rich_progress_reporter_suspend_and_resume_preserves_active_task() -> None:
    reporter = RichProgressReporter()

    reporter.start_phase("test", 10)

    assert reporter._progress.live.is_started is True  # noqa: SLF001

    reporter.suspend()

    assert reporter._progress.live.is_started is False  # noqa: SLF001

    reporter.resume()

    assert reporter._progress.live.is_started is True  # noqa: SLF001

    reporter.complete_phase()


def test_rich_progress_reporter_hides_parent_while_nested_phase_is_active(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[tuple[object, dict[str, object]]] = []
    original_update = reporter._progress.update  # noqa: SLF001

    def _recording_update(task_id, **kwargs):
        update_calls.append((task_id, kwargs))
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)  # noqa: SLF001

    reporter.start_phase("outer", 10)
    outer_task_id = reporter._task_id  # noqa: SLF001
    reporter.start_phase("inner", 3)

    assert (outer_task_id, {"visible": False, "refresh": True}) in update_calls

    reporter.complete_phase()

    assert reporter._task_id == outer_task_id  # noqa: SLF001
    assert (outer_task_id, {"visible": True, "refresh": True}) in update_calls

    reporter.complete_phase()


def test_rich_progress_reporter_indeterminate_phase_is_spinner_only() -> None:
    reporter = RichProgressReporter()

    reporter.start_indeterminate("Loading cached data")

    task = reporter._progress.tasks[0]  # noqa: SLF001
    assert task.total is None
    assert task.fields["presentation"] == "indeterminate"

    reporter.complete_phase()


def test_rich_progress_reporter_uses_distinct_task_presentations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)

    reporter.start_phase("Rendering", 30)
    reporter.advance(10)
    measurable_output = output.getvalue()
    task = reporter._progress.tasks[0]  # noqa: SLF001

    assert task.fields["presentation"] == "measurable"
    assert "  [RUN] Rendering" in measurable_output
    assert "10/30" in measurable_output
    assert "ETA" not in measurable_output
    assert "%" not in measurable_output
    assert not re.search(r"[-\\|/]\s+\[RUN\]", measurable_output)
    reporter.complete_phase()
    output.seek(0)
    output.truncate()
    reporter.start_indeterminate("Loading alignment offsets")
    indeterminate_output = output.getvalue()

    assert re.search(r"\[RUN\] Loading alignment offsets\s+-", indeterminate_output)
    assert "ETA" not in indeterminate_output
    assert not re.search(r"\d+/\d+", indeterminate_output)
    assert "━" not in indeterminate_output
    reporter.complete_phase()

    output.seek(0)
    output.truncate()
    reporter.start_phase("PLAN", 1)
    simple_output = output.getvalue()

    assert "[RUN] PLAN" in simple_output
    assert "ETA" not in simple_output
    assert "0/1" not in simple_output
    assert "━" not in simple_output
    reporter.complete_phase()


def test_eta_column_appears_only_after_rich_has_an_estimate() -> None:
    column = progress_module._EstimatedTimeRemainingColumn()  # noqa: SLF001
    task = Task(0, "work", total=2, completed=0, _get_time=lambda: 1.0)

    assert column.render(task).plain == ""

    task.start_time = 0.0
    task.completed = 1
    task._progress.extend((ProgressSample(0.0, 0), ProgressSample(1.0, 1)))  # noqa: SLF001
    assert column.render(task).plain.startswith("ETA ")


def test_rich_progress_reporter_adds_one_blank_line_when_measurable_work_begins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)

    reporter.start_phase("Rendering", 30)
    reporter.advance(1)
    reporter.set_description("Rendering frame 1")
    reporter.advance(1)

    assert output.getvalue().startswith("\n")
    assert output.getvalue().count("\n") == 1
    reporter.complete_phase()


def test_rich_progress_reporter_ellipsizes_only_the_rendered_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)
    description = "Reference | " + "very-long-release-identity-" * 8

    reporter.start_phase(description, 30)
    reporter.advance(10)
    task = reporter._progress.tasks[0]  # noqa: SLF001

    assert task.description == description
    assert "…" in output.getvalue()
    assert re.search(r"[━-]", output.getvalue())
    assert "10/30" in output.getvalue()
    reporter.complete_phase()


def test_rich_progress_reporter_keeps_a_useful_bar_at_narrow_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    output = StringIO()
    console = Console(file=output, force_terminal=True, no_color=True, width=60)
    monkeypatch.setattr(progress_module, "Console", lambda **_kwargs: console)
    reporter = RichProgressReporter(no_color=True)

    reporter.start_phase("Reference | PMTP WEB-DL | DV HDR10+ | Kitsune", 30)
    reporter.advance(10)

    rendered_bar = max(re.findall(r"([━╸╺-][━╸╺ -]+)10/30", output.getvalue()), key=len)
    assert len(rendered_bar.rstrip()) >= 7
    assert len(rendered_bar) >= 20
    assert "10/30" in output.getvalue()
    reporter.complete_phase()


def test_rich_progress_reporter_restores_parent_when_nested_phase_fails(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[tuple[object, dict[str, object]]] = []
    original_update = reporter._progress.update  # noqa: SLF001

    def _recording_update(task_id, **kwargs):
        update_calls.append((task_id, kwargs))
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)  # noqa: SLF001

    reporter.start_phase("outer", 10)
    outer_task_id = reporter._task_id  # noqa: SLF001
    reporter.start_phase("inner", 3)

    reporter.complete_phase(ProgressPhaseStatus.FAILED)

    assert reporter._task_id == outer_task_id  # noqa: SLF001
    assert (outer_task_id, {"visible": True, "refresh": True}) in update_calls

    reporter.complete_phase()


def test_rich_progress_reporter_warned_phase_does_not_force_total(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[dict[str, object]] = []
    original_update = reporter._progress.update  # noqa: SLF001

    def _recording_update(task_id, **kwargs):
        update_calls.append(kwargs)
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)  # noqa: SLF001

    reporter.start_phase("test", 10)
    reporter.advance(3)
    reporter.complete_phase(ProgressPhaseStatus.WARNED)

    assert {"description": "Warning", "refresh": True} in update_calls
    assert {"completed": 10, "refresh": True} not in update_calls


def test_rich_progress_reporter_does_not_retain_success_below_ten_seconds(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 9.9))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("PLAN", 1)
    reporter.complete_phase()

    assert "[OK] PLAN" not in capsys.readouterr().err


def test_rich_progress_reporter_retain_success_at_ten_seconds(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 10.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("PLAN", 1)
    reporter.complete_phase()

    assert "  [OK] PLAN  Completed in 10s" in capsys.readouterr().err


def test_rich_progress_reporter_explicitly_retains_short_success(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 0.1))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("PUBLISH", 1)
    reporter.complete_phase(retain=True)

    assert "[OK] PUBLISH  Completed in 0s" in capsys.readouterr().err


def test_rich_progress_reporter_suppresses_long_nested_success(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 1.0, 12.0, 13.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("RENDER", 1)
    reporter.start_phase("ENCODE", 1)
    reporter.complete_phase()
    reporter.complete_phase()

    output = capsys.readouterr().err
    assert "[OK] ENCODE" not in output
    assert "[OK] RENDER  Completed in 13s" in output


def test_rich_progress_reporter_suppresses_generic_confirm_completion(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 10.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("CONFIRM", 1)
    reporter.complete_phase(retain=False)

    assert "[OK] CONFIRM" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ProgressPhaseStatus.SKIPPED, "[SKIP] ANALYZE"),
        (ProgressPhaseStatus.WARNED, "[WARN] ALIGN"),
        (ProgressPhaseStatus.FAILED, "[FAIL] RENDER"),
    ],
)
def test_rich_progress_reporter_retains_non_success_statuses(
    status: ProgressPhaseStatus,
    expected: str,
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()

    reporter.start_phase(expected.split(maxsplit=1)[1], 1)
    reporter.complete_phase(status)

    assert expected in capsys.readouterr().err


def test_rich_progress_reporter_refreshes_state_changes(monkeypatch) -> None:
    reporter = RichProgressReporter()
    refresh_count = 0
    original_refresh = reporter._progress.refresh  # noqa: SLF001

    def _recording_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1
        original_refresh()

    monkeypatch.setattr(reporter._progress, "refresh", _recording_refresh)  # noqa: SLF001

    reporter.start_phase("test", 3)
    started_refresh_count = refresh_count

    reporter.set_description("Rendering")
    reporter.advance(1)

    assert refresh_count >= started_refresh_count + 2

    reporter.complete_phase()


def test_rich_progress_reporter_serializes_concurrent_updates() -> None:
    reporter = RichProgressReporter()
    reporter.start_phase("test", 40)

    def _update(index: int) -> None:
        reporter.set_description(f"Rendering {index}")
        reporter.advance(1)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(_update, range(40)))

    reporter.complete_phase()


def test_progress_reporter_protocol_is_single_source() -> None:
    import frame_compare.analysis.metrics as metrics_module
    import frame_compare.utils.progress as progress_module
    import frame_compare.utils.progress_protocol as progress_protocol

    assert progress_module.ProgressReporter is progress_protocol.ProgressReporter
    assert metrics_module.ProgressReporter is progress_protocol.ProgressReporter

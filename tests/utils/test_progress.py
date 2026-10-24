import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Event, current_thread

import pytest
import structlog
from rich.console import Console
from rich.live import Live
from rich.text import Text

import frame_compare.utils.progress as progress_module
from frame_compare.utils.logging import configure_logging
from frame_compare.utils.progress import (
    PlainProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


def _captured_rich_reporter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    no_color: bool = True,
) -> tuple[RichProgressReporter, StringIO]:
    monkeypatch.setenv("TERM", "xterm-256color")
    if not no_color:
        monkeypatch.delenv("NO_COLOR", raising=False)
    output = StringIO()
    console = Console(
        file=output,
        force_terminal=True,
        no_color=no_color,
        color_system="standard",
        width=100,
    )

    def _console(**_kwargs: object) -> Console:
        return console

    monkeypatch.setattr(progress_module, "human_console", _console)
    return RichProgressReporter(no_color=no_color), output


def test_plain_progress_reporter_emits_one_ascii_line_per_top_level_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    clock = iter((0.0, 84.9, 85.0, 86.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))
    monkeypatch.setattr(sys, "stderr", output)
    reporter = PlainProgressReporter()

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


def test_rich_progress_reporter_suspend_and_resume_preserves_active_task() -> None:
    reporter = RichProgressReporter()

    reporter.start_phase("test", 10)

    assert reporter._progress.live.is_started is True

    reporter.suspend()

    assert reporter._progress.live.is_started is False

    reporter.resume()

    assert reporter._progress.live.is_started is True

    reporter.complete_phase()


def test_warning_uses_active_reporter_console_and_releases_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    configure_logging(rich_output=True, no_color=True)
    structlog.get_logger().warning("before_progress")
    assert "! before progress" in stderr.getvalue()
    stderr.truncate(0)
    stderr.seek(0)
    reporter, output = _captured_rich_reporter(monkeypatch)
    reporter.start_phase("outer", 10)
    try:
        reporter.start_phase("inner", 2)
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(
                structlog.get_logger().warning, "tmdb_lookup_failed", status=503
            ).result()
        assert "! tmdb lookup failed · status=503" in Text.from_ansi(output.getvalue()).plain
        assert stderr.getvalue() == ""
        reporter.complete_phase()
        structlog.get_logger().warning("parent_active")
        assert "! parent active" in Text.from_ansi(output.getvalue()).plain
        assert stderr.getvalue() == ""
        reporter.suspend()
        structlog.get_logger().warning("while_suspended")
        assert "! while suspended" in stderr.getvalue()
        reporter.resume()
        stderr.truncate(0)
        stderr.seek(0)
        structlog.get_logger().warning("after_resume")
        assert "! after resume" in Text.from_ansi(output.getvalue()).plain
        assert stderr.getvalue() == ""
    finally:
        reporter.complete_phase()
    structlog.get_logger().warning("after_completion")
    assert "! after completion" in stderr.getvalue()


def test_rich_progress_reporter_hides_parent_while_nested_phase_is_active(
    monkeypatch,
) -> None:
    reporter, _output = _captured_rich_reporter(monkeypatch, no_color=False)
    update_calls: list[tuple[object, dict[str, object]]] = []
    original_update = reporter._progress.update

    def _recording_update(task_id, **kwargs):
        update_calls.append((task_id, kwargs))
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)

    reporter.start_phase("outer", 10)
    outer_task_id = reporter._task_id
    reporter.start_phase("inner", 3)

    assert (outer_task_id, {"visible": False, "refresh": True}) in update_calls

    reporter.complete_phase()

    assert reporter._task_id == outer_task_id
    assert (outer_task_id, {"visible": True, "refresh": True}) in update_calls

    reporter.complete_phase()


def test_rich_progress_reporter_indeterminate_phase_shows_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter = RichProgressReporter()

    now = [0.0]
    monkeypatch.setattr(reporter._progress, "get_time", lambda: now[0])
    reporter.start_indeterminate("Loading cached data")
    now[0] = 42.0

    task = reporter._progress.tasks[0]
    assert task.total is None
    assert task.fields["presentation"] == "indeterminate"
    with reporter._progress.console.capture() as capture:
        reporter._progress.console.print(reporter._progress.get_renderable())
    assert "0:42" in capture.get()

    reporter.complete_phase()


def test_rich_progress_reporter_restores_parent_when_nested_phase_fails(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[tuple[object, dict[str, object]]] = []
    original_update = reporter._progress.update

    def _recording_update(task_id, **kwargs):
        update_calls.append((task_id, kwargs))
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)

    reporter.start_phase("outer", 10)
    outer_task_id = reporter._task_id
    reporter.start_phase("inner", 3)

    reporter.complete_phase(ProgressPhaseStatus.FAILED)

    assert reporter._task_id == outer_task_id
    assert (outer_task_id, {"visible": True, "refresh": True}) in update_calls

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


@pytest.mark.parametrize(
    ("status", "summary", "duration_text", "expected"),
    [
        (
            ProgressPhaseStatus.COMPLETED,
            "50 frames selected",
            None,
            "✓ Analyze         50 frames selected · 12s",
        ),
        (ProgressPhaseStatus.COMPLETED, None, None, "✓ Analyze         12s"),
        (
            ProgressPhaseStatus.COMPLETED,
            "offsets",
            "2s + 42s review",
            "✓ Analyze         offsets · 2s + 42s review",
        ),
        (ProgressPhaseStatus.FAILED, None, None, "✗ Analyze"),
        (ProgressPhaseStatus.WARNED, None, None, "! Analyze"),
        (ProgressPhaseStatus.SKIPPED, None, None, "– Analyze"),
    ],
)
def test_durable_phase_duration_is_inline(
    monkeypatch: pytest.MonkeyPatch,
    status: ProgressPhaseStatus,
    summary: str | None,
    duration_text: str | None,
    expected: str,
) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)
    reporter._progress.console.width = 120
    reporter._print_durable_line(
        status,
        "Analyze",
        summary=summary,
        duration=12,
        duration_text=duration_text,
    )
    rendered = Text.from_ansi(output.getvalue()).plain
    assert rendered == expected + "\n"
    assert all(line == line.rstrip() for line in rendered.splitlines())


def test_step_map_tracks_run_phases_and_nested_work(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter, _ = _captured_rich_reporter(monkeypatch)
    reporter.set_phase_steps(["Analyze", "Align", "Render", "Report", "Publish"])

    def footer() -> str:
        reporter.suspend()
        try:
            with reporter._progress.console.capture() as capture:
                reporter._progress.console.print(reporter._progress.get_renderable())
            return Text.from_ansi(capture.get()).plain.splitlines()[-1]
        finally:
            reporter.resume()

    try:
        reporter.start_phase("Analyze", 1)
        reporter.complete_phase()
        reporter.start_phase("Align", 1)
        reporter.start_indeterminate("Align · source · preparing audio")
        assert footer() == "  ✓ Analyze  ● Align  ○ Render  ○ Report  ○ Publish"
        reporter.complete_phase()
        reporter.complete_phase(ProgressPhaseStatus.WARNED)
        reporter.start_phase("Render", 1)
        reporter.complete_phase(ProgressPhaseStatus.FAILED)
        reporter.start_phase("Report", 1)
        reporter.complete_phase()
        reporter.start_phase("Publish", 1)
        reporter.complete_phase(ProgressPhaseStatus.SKIPPED, summary="declined")
        assert footer() == "  ✓ Analyze  ! Align  ✗ Render  ✓ Report  – Publish"
    finally:
        reporter._progress.stop()


def test_live_refresh_runs_without_events_and_stops_while_suspended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter, output = _captured_rich_reporter(monkeypatch)
    refreshed = Event()
    refresh = Live.refresh

    def observe_refresh(live: Live) -> None:
        refresh(live)
        if current_thread().name != "MainThread":
            refreshed.set()

    monkeypatch.setattr(Live, "refresh", observe_refresh)
    reporter.start_indeterminate("Align · source · preparing audio")
    try:
        assert refreshed.wait(2), "no automatic redraw while the task was active"
        reporter.suspend()
        refreshed.clear()
        reporter.start_indeterminate("nested while suspended")
        assert not reporter._progress.live.is_started
        assert not refreshed.wait(0.6), "redraw continued during suspension"
        reporter.complete_phase()
        reporter.resume()
        assert refreshed.wait(2), "redraw did not resume"
        reporter.complete_phase(retain=True, summary="finished")
        assert "finished · " in Text.from_ansi(output.getvalue()).plain
        assert reporter._progress.live._refresh_thread is None
    finally:
        reporter._progress.stop()


@pytest.mark.parametrize("width", [80, 100])
@pytest.mark.parametrize("mixed", [False, True])
def test_alignment_rows_follow_header_duration_and_precede_footage_note(
    monkeypatch: pytest.MonkeyPatch, mixed: bool, width: int
) -> None:
    from frame_compare.utils.progress_protocol import AlignmentSummary, AlignmentSummaryEntry

    reporter, output = _captured_rich_reporter(monkeypatch)
    reporter._progress.console.width = width
    summary = AlignmentSummary(
        entries=(
            AlignmentSummaryEntry(
                "Alpha [red] with a long source name", 2, "confirmed in VSView", 0
            ),
            AlignmentSummaryEntry(
                "Beta with a long source name", 0, "kept" if mixed else "confirmed in VSView"
            ),
        ),
        extra_footage="Reference has 2.0 s more at the end; frames come from the range all sources share.",
    )
    reporter.start_phase("Align", 1)
    reporter.complete_phase(
        retain=True, duration_text="2m 09s + 4m 41s review", alignment_summary=summary
    )
    lines = Text.from_ansi(output.getvalue()).plain.splitlines()
    header = next(index for index, line in enumerate(lines) if "sources aligned" in line)
    phase_value = " ".join(line[18:].strip() for line in lines[header:] if line.strip())
    assert "2m 09s + 4m 41s review" in phase_value
    assert all(len(line) <= width for line in lines)
    following = "\n".join(lines[header + 1 :])
    assert "Alpha [red] with a long source name  +2f (audio +0f)" in following
    assert "Beta with a long source name" in following
    assert following.index("Alpha") < following.index("Reference has")
    assert all(line.startswith(" " * 18) for line in lines[header + 1 :] if line.strip())
    assert (" kept" in following) is mixed
    assert ("confirmed in VSView" in phase_value.partition("Alpha")[2]) is mixed


def test_live_progress_caps_width_and_follows_resize(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter, _ = _captured_rich_reporter(monkeypatch)
    reporter.set_phase_steps(["Analyze", "Align", "Render", "Report", "Publish"])
    reporter.start_indeterminate("reading audio " + "source " * 30)
    reporter.suspend()
    try:
        for width in (187, 80, 150):
            reporter._progress.console.width = width
            with reporter._progress.console.capture() as capture:
                reporter._progress.console.print(reporter._progress.get_renderable())
            lines = Text.from_ansi(capture.get()).plain.splitlines()
            assert all(len(line) <= min(width, 120) for line in lines)
            assert "reading audio" in lines[0]
            assert "0:00" in lines[0]
            assert "Analyze" in lines[-1]
            assert reporter._progress.console.width == width
    finally:
        reporter.complete_phase()


@pytest.mark.parametrize("level", [logging.WARNING, logging.ERROR])
@pytest.mark.parametrize("log_format", ["console", "json"])
def test_stdlib_warning_uses_active_rich_console(
    monkeypatch: pytest.MonkeyPatch, level: int, log_format: str
) -> None:
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    reporter, output = _captured_rich_reporter(monkeypatch)
    monkeypatch.setattr(logging.getLogger(), "handlers", [])
    configure_logging(rich_output=True, no_color=True)
    reporter.start_indeterminate("Align")
    try:
        path = "/workspace/comparison_videos/source_name.mkv"
        message = f"Loading {path} without an L-SMASH index cache"
        logging.getLogger("frame_compare.vs.source").log(
            level, "Loading %s without an L-SMASH index cache", path
        )
        plain = Text.from_ansi(output.getvalue()).plain
        assert ("! " if level == logging.WARNING else "✗ ") + message in plain
        assert stderr.getvalue() == ""
    finally:
        reporter.complete_phase()
        configure_logging(log_format=log_format)
    logging.getLogger("frame_compare.vs.source").warning("plain_warning")
    assert stderr.getvalue() == "plain_warning\n"


def test_resumed_footer_preserves_section_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    from frame_compare.utils.terminal_sections import Section

    reporter, output = _captured_rich_reporter(monkeypatch)
    reporter.set_phase_steps(["Analyze", "Align", "Render"])
    reporter.start_indeterminate("Align")
    try:
        reporter.suspend()
        Section("Audio alignment").print(reporter._progress.console)
        assert Text.from_ansi(output.getvalue()).plain.endswith("╰─\n\n")
        start = output.tell()
        reporter.resume()
        # The first resumed draw must start at the current cursor. A stale
        # two-line footer issues cursor-up here, erasing the section's blank line.
        first_draw = output.getvalue()[start:].split("Align", 1)[0]
        assert "\x1b[1A" not in first_draw
        reporter.complete_phase(retain=True, summary="finished")
        reporter.start_indeterminate("Render")
        reporter.complete_phase(retain=True, summary="finished")
    finally:
        reporter._progress.stop()


@pytest.mark.parametrize("rows", [False, True])
def test_alignment_phase_and_completion_have_no_padding_or_overwide_lines(
    monkeypatch: pytest.MonkeyPatch,
    rows: bool,
) -> None:
    from frame_compare.cli.output import print_result_summary
    from frame_compare.orchestration import RunResult
    from frame_compare.utils.progress_protocol import AlignmentSummary, AlignmentSummaryEntry

    reporter, output = _captured_rich_reporter(monkeypatch)
    console = reporter._progress.console
    console.width = 120
    entries = [AlignmentSummaryEntry("日本語 Encode [red]", 2, "confirmed in VSView", 0)]
    if rows:
        entries.extend(
            AlignmentSummaryEntry(
                f"Another source with a long name {index}", 0, "confirmed in VSView"
            )
            for index in range(3)
        )
    summary = AlignmentSummary(
        entries=tuple(entries),
        extra_footage=(
            "Reference has 6.1 s more at the start and 5.4 s more at the end; "
            "frames come from the range all sources share."
        ),
    )
    reporter.suspend()
    reporter.start_phase("Align", 1)
    reporter.complete_phase(retain=True, alignment_summary=summary)
    print_result_summary(
        console, result=RunResult(success=True, alignment_summary=summary), quiet=False
    )
    lines = Text.from_ansi(output.getvalue()).plain.splitlines()
    assert any("alignment" in line for line in lines)
    assert any("frames come" in line for line in lines)
    assert all(line == line.rstrip() for line in lines)
    assert all(Text(line).cell_len <= 120 for line in lines)

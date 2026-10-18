"""LF2 progress follows real planning, streaming chunks, and video boundaries."""

from __future__ import annotations

import asyncio
import threading
from fractions import Fraction
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest
from rich.console import Console
from rich.progress import ProgressColumn

from frame_compare.services import alignment, alignment_video
from frame_compare.services.alignment_resolution import alignment_key
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    AlignmentWriteProvenance,
    ComparisonResolution,
)
from frame_compare.utils.progress import NullProgressReporter, RichProgressReporter
from frame_compare.vs.loader import VSLoader
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_synthetic_audio import make_program
from tests.services.test_alignment_workflow import _DURATION_SECONDS, _media, _stub_transport


class RecordingProgress(NullProgressReporter):
    def __init__(self) -> None:
        self.events: list[tuple[str, str, int | None]] = []
        self.threads: list[int] = []

    def _record(self, event: str, description: str = "", amount: int | None = None) -> None:
        self.events.append((event, description, amount))
        self.threads.append(threading.get_ident())

    def start_indeterminate(self, name: str) -> None:
        self._record("stage", name)

    def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
        assert presentation == "measurable"
        self._record("stage", name, total)

    def advance(self, amount: int = 1) -> None:
        self._record("advance", amount=amount)

    def set_description(self, desc: str) -> None:
        self._record("description", desc)

    def complete_phase(self, *args: object, **kwargs: object) -> None:
        assert kwargs == {"retain": False}
        self._record("end")


@pytest.mark.parametrize(
    "silent,video,origin",
    [
        (False, False, "shared_computed_offsets"),
        (True, True, "shared_computed_offsets"),
        (False, True, "shared_computed_offsets"),
        (False, False, "shared_previous_offsets"),
    ],
)
@pytest.mark.parametrize("fresh_count", [1, 2])
def test_staged_progress_excludes_cache_and_counts_streamed_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    silent: bool,
    video: bool,
    fresh_count: int,
    origin: AlignmentWriteProvenance,
) -> None:
    reference, comparison = _media(tmp_path)
    comparison = comparison.rename(tmp_path / "Encode [red].mkv")
    fresh = [comparison]
    if fresh_count == 2:
        extra = tmp_path / "another.mkv"
        extra.touch()
        fresh.append(extra)
    cached = tmp_path / "cached.mkv"
    cached.touch()
    program = make_program(11, _DURATION_SECONDS)
    if silent:
        program = np.zeros_like(program)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    request = alignment_request(
        reference=reference,
        comparisons=[cached, *fresh],
        generated_dir=tmp_path / "generated",
    )
    cached_resolution = ComparisonResolution(
        AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=cached.name,
            frame_offset=0,
            time_offset_seconds=0.0,
            correlation_score=1.0,
            algorithm="cross_correlation",
            source="cached",
        ),
        "cache-key",
        origin,
    )
    monkeypatch.setattr(
        alignment,
        "apply_shared_reuse",
        lambda **_kwargs: ({alignment_key(reference, cached): cached_resolution}, False),
    )
    worker_threads: list[int] = []
    original_plan = alignment._plan_audio_pair

    def plan(*args: object, **kwargs: object) -> object:
        worker_threads.append(threading.get_ident())
        return original_plan(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(alignment, "_plan_audio_pair", plan)
    video_loads: list[Path] = []

    def load(path: Path) -> object:
        video_loads.append(path)
        return SimpleNamespace(clip=object())

    def prepare(*_args: object) -> None:
        # Stop at the scoring boundary; no native media runtime is required.
        raise RuntimeError("scoring unavailable")

    monkeypatch.setattr(alignment_video, "_prepare_luma", prepare)
    reporter = RecordingProgress()
    main_thread = threading.get_ident()
    asyncio.run(
        alignment.align_clips_from_request(
            request,
            AlignmentConfig(cache_results=False),
            reference_fps=Fraction(24),
            progress=reporter,
            vs_loader=cast(VSLoader, SimpleNamespace(load=load)) if video else None,
        )
    )
    assert worker_threads and all(thread != main_thread for thread in worker_threads)
    assert set(reporter.threads) == {main_thread}
    stages = [event for event in reporter.events if event[0] == "stage"]
    expected = []
    for i, comp in enumerate(fresh, 1):
        prefix = f"Align · {comp.stem} ({i} of {fresh_count}) · "
        expected.extend(
            [("stage", prefix + "preparing audio", None), ("stage", prefix + "reading audio", 3)]
        )
        if video and not silent:
            expected.extend(
                [
                    ("stage", prefix + "indexing video", None),
                    ("stage", prefix + "checking video", None),
                ]
            )
    assert stages == expected
    # Exercise the actual Rich description column, whose input is literal text.
    # Markup escaping here would visibly introduce a backslash before the bracket.
    rich_reporter = RichProgressReporter(no_color=True)
    rich_progress = rich_reporter._progress
    task_id = rich_progress.add_task(stages[0][1], total=None, presentation="indeterminate")
    task = next(task for task in rich_progress.tasks if task.id == task_id)
    description_column = rich_progress.columns[0]
    assert isinstance(description_column, ProgressColumn)
    rendered = description_column.render(task)
    output = StringIO()
    Console(file=output, width=200, color_system=None).print(rendered)
    assert output.getvalue().strip() == (
        f"… Align · Encode [red] (1 of {fresh_count}) · preparing audio"
    )
    assert ("description", "Align · using cached audio evidence · cached", None) in reporter.events
    assert len(video_loads) == (2 * fresh_count if video and not silent else 0)
    # Each reading stage starts at zero; all planned chunks, including silence,
    # advance it exactly once, even when several fast chunks share one UI tick.
    for index, event in enumerate(reporter.events):
        if event[0] == "stage" and event[1].endswith("reading audio"):
            end = next(
                i for i in range(index + 1, len(reporter.events)) if reporter.events[i][0] == "end"
            )
            assert (
                sum(
                    amount or 0
                    for kind, _, amount in reporter.events[index + 1 : end]
                    if kind == "advance"
                )
                == 3
            )
    assert reporter.events[-1] == ("end", "", None)

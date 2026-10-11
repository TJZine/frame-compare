"""Late source changes must invalidate video evidence before it gains authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import numpy.typing as npt
import pytest

from frame_compare.services import alignment_video
from frame_compare.services.alignment_video import VideoClipRequest
from frame_compare.utils.alignment_evidence import AudioAlignmentAttempt
from frame_compare.utils.types import AlignmentClipIdentity
from frame_compare.vs.loader import VSLoader
from tests.services.test_alignment_evidence import attempt_with_chunks


class _ArrayClip:
    """Replace only native decoding; retain real motion, rank, and vote calculations."""

    num_frames = 4000

    def get_frame(self, frame: int) -> tuple[npt.NDArray[np.float32]]:
        return (np.random.default_rng(frame).random((18, 32), dtype=np.float32),)


def _attempt(*, with_target: bool) -> AudioAlignmentAttempt:
    attempt = attempt_with_chunks(5, lag=0)
    candidate = attempt.decision.candidate
    assert candidate is not None
    lags = (0, 0, 0, 0, 4000) if with_target else (0,) * 5
    return replace(
        attempt,
        fps_num=24,
        fps_den=1,
        chunks=replace(attempt.chunks, lags=lags, agrees=tuple(lag == 0 for lag in lags)),
        runs=(),
        audio=replace(
            attempt.audio,
            agreeing_chunks=4 if with_target else 5,
            subframe_estimate=0.0,
            rounded_frame=0,
        ),
        decision=replace(
            attempt.decision,
            candidate=replace(
                candidate, frame_offset=0, time_offset_seconds=0.0, subframe_estimate=0.0
            ),
        ),
    )


@pytest.fixture
def media(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def source(name: str) -> VideoClipRequest:
        path = tmp_path / name
        path.write_bytes(b"original")
        stat = path.stat()
        return VideoClipRequest(path, AlignmentClipIdentity(path, stat.st_size, stat.st_mtime_ns))

    reference = source("reference.mkv")
    comparison = source("comparison.mkv")
    loader = MagicMock(spec=VSLoader)
    loader.load.return_value = SimpleNamespace(clip=_ArrayClip(), num_frames=4000)
    monkeypatch.setattr(alignment_video, "_prepare_luma", lambda clip, _rect: clip)
    return reference, comparison, loader


def _after_scoring[**P, T](
    score: Callable[P, T], action: Callable[[], None], *, after_calls: int
) -> Callable[P, T]:
    calls = 0

    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        nonlocal calls
        result = score(*args, **kwargs)
        calls += 1
        if calls == after_calls:
            action()
        return result

    return wrapped


@pytest.mark.parametrize("with_target", [False, True])
def test_unchanged_sources_keep_video_confirmation(media, with_target: bool) -> None:
    reference, comparison, loader = media
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(with_target=with_target),
        fps_reference=Fraction(24),
        loader=loader,
    )
    assert result.observation == "observed"
    assert result.confirmed_offset == 0
    if with_target:
        assert len(result.targets) == 1
        assert result.targets[0].resolution == "resolved"
        assert len(result.targets[0].positions) == 4
    else:
        assert result.targets == ()


@pytest.mark.parametrize("phase", ["base", "last_target"])
@pytest.mark.parametrize("side", ["reference", "comparison"])
@pytest.mark.parametrize("mutation", ["replace", "delete"])
def test_source_changed_after_scoring_cannot_confirm(
    media, monkeypatch: pytest.MonkeyPatch, phase: str, side: str, mutation: str
) -> None:
    reference, comparison, loader = media
    path = reference.path if side == "reference" else comparison.path
    changed = False

    def change_source() -> None:
        nonlocal changed
        changed = True
        if mutation == "delete":
            path.unlink()
        else:
            path.write_bytes(b"replacement with a different size")

    name = "_score_base_positions" if phase == "base" else "_score_hypotheses"
    monkeypatch.setattr(
        alignment_video,
        name,
        _after_scoring(
            getattr(alignment_video, name), change_source, after_calls=1 if phase == "base" else 4
        ),
    )
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(with_target=phase == "last_target"),
        fps_reference=Fraction(24),
        loader=loader,
    )
    assert changed, "the test must reach the intended late source-change boundary"
    assert result.observation == "not_observed"
    assert result.confirmed_offset is None
    assert result.positions == ()
    assert result.targets == ()


@pytest.mark.parametrize("phase", ["base", "last_target"])
def test_cancellation_during_last_score_cannot_confirm(
    media, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    reference, comparison, loader = media
    cancellation = Event()
    name = "_score_base_positions" if phase == "base" else "_score_hypotheses"
    monkeypatch.setattr(
        alignment_video,
        name,
        _after_scoring(
            getattr(alignment_video, name),
            cancellation.set,
            after_calls=1 if phase == "base" else 4,
        ),
    )
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(with_target=phase == "last_target"),
        fps_reference=Fraction(24),
        loader=loader,
        cancellation=cancellation,
    )
    assert cancellation.is_set()
    assert result.observation == "not_observed"
    assert result.confirmed_offset is None

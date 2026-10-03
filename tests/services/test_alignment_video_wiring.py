"""Focused proof that computed alignment is gated by the video stage."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.services import alignment as alignment_service
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vs.loader import VSLoader
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_synthetic_audio import make_program
from tests.services.test_alignment_workflow import (
    _DURATION_SECONDS,
    _media,
    _stub_transport,
)


def _run(
    request: AlignmentRequest,
    config: AlignmentConfig,
    *,
    loader: VSLoader | None = None,
) -> list[AlignmentResult]:
    return asyncio.run(
        align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24, 1),
            vs_loader=loader,
        )
    )


def test_missing_loader_is_a_video_unavailable_provisional_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(11, _DURATION_SECONDS)
    _stub_transport(
        monkeypatch,
        tmp_path,
        reference_samples=program,
        comparison_samples=program,
    )
    config = AlignmentConfig(cache_results=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
    )

    saved: list[object] = []
    monkeypatch.setattr(
        alignment_service,
        "save_reusable_offsets",
        lambda request, provenances: saved.append((request, provenances)),
    )

    (result,) = _run(request, config)

    assert result.applied is False
    assert result.frame_offset is None
    assert result.diagnostic == "video_check_unavailable"
    assert result.audio_attempt is not None
    assert result.audio_attempt.video_check.observation == "not_observed"
    assert saved == []

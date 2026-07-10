"""Tests for optional analysis benchmark timing collection."""

from __future__ import annotations

from frame_compare.analysis.timing import AnalysisTimingRecorder


def test_analysis_timing_recorder_accumulates_and_sorts_spans() -> None:
    recorder = AnalysisTimingRecorder()

    recorder.add_seconds("source_load", 0.25)
    recorder.add_seconds("cache_lookup", 0.1)
    recorder.add_seconds("source_load", 0.5)
    recorder.cache_state = "hit"

    assert recorder.cache_state == "hit"
    assert recorder.as_dict() == {
        "cache_lookup": 0.1,
        "source_load": 0.75,
    }

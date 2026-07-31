"""Tests for optional analysis benchmark timing collection."""

from __future__ import annotations

import pytest

from frame_compare.analysis.timing import AnalysisTimingRecorder, record_span


def test_analysis_timing_recorder_accumulates_and_sorts_spans() -> None:
    recorder = AnalysisTimingRecorder()

    recorder.add_seconds("source_load", 0.25)
    recorder.add_seconds("cache_lookup", 0.1)
    recorder.add_seconds("source_load", 0.5)
    recorder.cache_state = "hit"

    assert recorder.cache_state == "hit"
    assert recorder.cache_write_state == "not_attempted"
    assert recorder.as_dict() == {
        "cache_lookup": 0.1,
        "source_load": 0.75,
    }


def test_record_span_is_a_noop_without_a_recorder() -> None:
    with record_span(None, "source_load"):
        pass


def test_record_span_records_elapsed_time_when_operation_fails() -> None:
    recorder = AnalysisTimingRecorder()

    with (
        pytest.raises(RuntimeError, match="failed operation"),
        record_span(recorder, "source_load"),
    ):
        raise RuntimeError("failed operation")

    assert recorder.as_dict()["source_load"] >= 0.0
